#!/usr/bin/env python3
"""Persona review panel: domain reviewers over the added lines of a change.

WHY THIS EXISTS

The gate's `review` domain wants an artifact saying somebody other than the
author looked at this commit. Left to a human that step gets skipped, and left to
the author's own model it is worthless, because a model reviewing its own diff
agrees with itself. There is already an external-review harness in this setup
(dot-claude/bin/external-review-judge.py). CORRECTED 2026-07-30: this docstring
claimed both of its backends were shut, "the codex binary is not installed". That
is false and had been for long enough that two subagents read it as fact this
session. `python ~/.claude/bin/external-review-judge.py status` returns codex
installed true, chatgpt_auth true, codex-cli 0.146.0. Only the Gemini leg is shut,
barred for this repository's content by the project contract. The default reviewer
is still the local one, because it always works and never sends anything anywhere,
but that is now a choice rather than the only option.

WHAT A PERSONA IS HERE

Not a prompt saying "act as a security expert". A persona is a named set of
checks over the lines this change ADDED, each with a pattern, a reason a reader
would accept, and a severity. That is narrower than a human reviewer and it is
honest about being narrower: the artifact records its own coverage boundary, so
"the panel passed" can never be read as "a human would have no objection".

Every finding cites file and line. Every citation is verified against the parsed
diff before it is written out, so a reviewer that invents a location gets its
finding dropped and the drop is recorded. That check exists mostly for the
optional model backend, where invented line numbers are the normal failure.

BACKENDS

  local        (default) deterministic checks, no network, nothing leaves the box
  openrouter   adds a free-model second opinion for what a pattern cannot see.
               Opt-in with --allow-external, and it refuses outright if the diff
               contains anything resembling credential material.

USAGE
  python tools/review/panel.py run --project . [--base origin/main]
  python tools/review/panel.py run --project . --allow-external
  python tools/review/panel.py run --project . --allow-semantic-cache
  python tools/review/panel.py selftest

Decisions are memoized in tiers (tools/review/review_cache.py, issue #372):
exact, then normalized (formatting-insensitive), then semantic (opt-in via
--allow-semantic-cache). Every key carries the full conditioning tuple, so a
stale or differently-conditioned entry is a miss, never a replay.

The artifact lands at <project>/state/reviews/<sha>.json, which is where
tools/gate/gate.py looks for it.

EXIT CODES
  0  panel reached a pass verdict
  1  panel found blocking issues, or could not reach a verdict
  2  could not run (not a git repo, no change to review)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

import e_rows
import review_cache

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = os.path.abspath(os.path.join(HERE, ".."))

HIGH = "high"
MED = "medium"
LOW = "low"


# ------------------------------------------------------------------ diff model

def sh(cmd: str, cwd: str, timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "")
    except Exception as exc:
        return 127, str(exc)


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def default_base(project: str) -> str:
    """A base with something between it and HEAD.

    The obvious loop (take the first of origin/main, main, ...) picks a ref that on
    the main branch IS HEAD, leaving an empty diff and a review domain that can
    never pass on a clean tree. So a candidate that resolves to HEAD is no base at
    all and gets skipped. The last resort is the empty tree, which makes the first
    commit in a repository reviewable instead of unreviewable.
    """
    head = sh("git rev-parse HEAD", project)[1].strip()
    for cand in ("origin/main", "origin/master", "main", "master", "HEAD~1"):
        rc, sha = sh("git rev-parse --verify --quiet " + cand, project)
        if rc != 0 or not sha.strip():
            continue
        if sha.strip() == head:
            continue
        return cand
    return EMPTY_TREE


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


# Four checks read comments ON PURPOSE and must keep seeing them. Every other check
# is about code that runs, so a commented line is not its subject.
#
#   todo-added      a TODO/FIXME/XXX/HACK marker, which lives in a comment
#   commented-code  matches a line that BEGINS with # or //, by definition
#   py-type-ignore  `# type: ignore` IS a comment pragma
#   ts-escape       `// @ts-ignore` likewise
#
# This set was NOT hand-guessed. The first draft listed two and the panel's own
# selftest immediately reported `MISS correctness py-type-ignore`, which is the
# selftest doing precisely its job: a change that makes a noisy checker quiet is
# the shape of a suppression, and the fixture caught the over-reach on the first
# run. The remaining two were then found by probing every registered check in
# every language it declares against comment-only strings, rather than by reading
# the list again and trusting a second guess. tests/test_panel_comment_strip.py
# pins the membership so a future check that reads comments fails loudly here.
COMMENT_AWARE = {"todo-added", "commented-code", "py-type-ignore", "ts-escape"}

# Comment openers by language. Only the dialects the check list actually registers.
_LINE_COMMENT = {
    "py": ("#",), "sh": ("#",), "rb": ("#",), "yaml": ("#",), "yml": ("#",),
    "js": ("//",), "ts": ("//",), "go": ("//",), "rs": ("//",), "java": ("//",),
    "kt": ("//",), "swift": ("//",), "cs": ("//",), "php": ("//", "#"),
    "sql": ("--",),
}


def code_only(text: str, lang: str) -> str:
    """The part of a line that is code, with any trailing comment removed.

    WHY. On 2026-08-03 the review domain carried a HIGH from py-shell-true against
    tools/map/codemap.py:66, whose matched line is a COMMENT quoting

        subprocess.run("git " + args, shell=True)

    while explaining why that form is deliberately not used. The pattern is correct
    about the string and wrong about the world: a quotation of a dangerous call is
    not a dangerous call. That is L-2026-07-31-b, the gate checking the ruled form
    of a rule instead of the property the rule protects, and it is the third logged
    instance after sql-concat on this same file and hooks_exist on 2026-08-03.

    Deliberately conservative. The opener only counts when it is outside a string
    literal, so `subprocess.run(f"echo #{x}", shell=True)` is untouched and still
    fires, and a real call with a trailing `# noqa` still fires because the code
    precedes the comment.

    KNOWN RESIDUAL, stated rather than hidden: this is line-oriented, because the
    panel scans added diff lines and never holds the whole file. A line inside a
    triple-quoted docstring that quotes shell=True has no `#` on it and will still
    match. Closing that needs file-level parsing, which is a different change from
    this one; tests/test_panel_comment_strip.py pins the residual so it cannot be
    mistaken for solved.
    """
    openers = _LINE_COMMENT.get(lang)
    if not openers:
        return text
    quote = ""
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in "\"'`":
            quote = c
            i += 1
            continue
        for op in openers:
            if text.startswith(op, i):
                return text[:i]
        i += 1
    return text


def added_lines(project: str, base: str) -> list[dict]:
    """Every line this change adds, as {file, line, text}.

    Reviewing added lines rather than whole files is the difference between a
    review of the change and a review of the repository. A pre-existing problem
    is a separate conversation and blocking on it would make the gate impossible
    to ever turn on.
    """
    out: list[dict] = []
    # Three-dot against a branch base is what a reviewer wants: changes on this side
    # of the merge base, not changes that landed on main since. The empty tree has no
    # merge base with anything, so it needs the two-dot form.
    span = "{} HEAD".format(base) if base == EMPTY_TREE else "{}...HEAD".format(base)
    cmds = ["git diff -U0 " + span, "git diff -U0 HEAD", "git diff -U0 --cached"]
    seen: set[tuple[str, int]] = set()
    for cmd in cmds:
        rc, diff = sh(cmd, project, timeout=180)
        if rc != 0:
            continue
        path = None
        lineno = 0
        for raw in diff.splitlines():
            if raw.startswith("+++ "):
                p = raw[4:].strip()
                path = None if p == "/dev/null" else re.sub(r"^b/", "", p)
                continue
            m = HUNK.match(raw)
            if m:
                lineno = int(m.group(1))
                continue
            if raw.startswith("+") and not raw.startswith("+++") and path:
                key = (path, lineno)
                if key not in seen:
                    seen.add(key)
                    out.append({"file": path, "line": lineno, "text": raw[1:]})
                lineno += 1

    # Untracked files are part of the change too, and skipping them is how a whole
    # new module gets shipped unreviewed.
    rc, status = sh("git status --porcelain", project)
    if rc == 0:
        for row in status.splitlines():
            if not row.startswith("??"):
                continue
            rel = row[3:].strip().strip('"')
            full = os.path.join(project, rel)
            if os.path.isdir(full):
                for root, _dirs, files in os.walk(full):
                    if re.search(r"[\\/](\.git|node_modules|__pycache__|dist|build)([\\/]|$)", root):
                        continue
                    for f in files:
                        _collect_file(project, os.path.join(root, f), out, seen)
            else:
                _collect_file(project, full, out, seen)
    return drop_stale_lines(project, out)


def drop_stale_lines(project: str, rows: list[dict]) -> list[dict]:
    """Keep only lines the tree still contains at the position they claim.

    added_lines unions three diffs and dedupes by (path, lineno). The branch diff
    holds every line this branch ever ADDED, including ones a later commit on the
    same branch removed, and the first diff wins the dedupe. So a line that no
    longer exists is reported against a line number now occupied by other text.

    Measured 2026-07-30: both remaining HIGH findings were this. Line 66 of
    tools/map/codemap.py carried the snippet `subprocess.run("git " + args, ...
    shell=True` while the file's line 66 is a comment recording that the helper was
    deleted on 2026-07-27, and an AST walk for a shell=True keyword returns [].
    The reviewer was blocking on a vulnerability the change under review removes.

    This is the mirror of a rule the panel already enforces: cmd_selftest requires
    that findings citing a line the change did not add are discarded, because an
    invented file:line is unactionable. A line the change added and then removed is
    unactionable for the same reason.

    Fail-open by design. If the file cannot be read, the line is kept: a reviewer
    that goes silent on what it cannot check is worse than one that over-reports.
    Comparison ignores leading and trailing whitespace so a reindent or a CRLF does
    not read as a deleted line.
    """
    # A file that is GONE and a file that is unreadable are different facts and get
    # opposite answers. Gone means the change deleted it, so its lines are not in the
    # tree and must not be reported. Unreadable means we do not know, so we report.
    # Both raise OSError, which is why existence is checked separately rather than
    # inferred from the exception.
    MISSING: list[str] = []
    cache: dict[str, list[str] | None] = {}
    kept: list[dict] = []
    for row in rows:
        rel = row["file"]
        if rel not in cache:
            full = os.path.join(project, rel)
            if not os.path.isfile(full):
                cache[rel] = MISSING
            else:
                try:
                    with open(full, encoding="utf-8", errors="replace") as fh:
                        cache[rel] = fh.read().splitlines()
                except Exception:          # noqa: BLE001 - unreadable: fail open
                    cache[rel] = None
        body = cache[rel]
        if body is None:
            kept.append(row)
            continue
        i = row["line"] - 1
        if 0 <= i < len(body) and body[i].strip() == row["text"].strip():
            kept.append(row)
    return kept


def _collect_file(project: str, full: str, out: list, seen: set) -> None:
    rel = os.path.relpath(full, project).replace("\\", "/")
    if not re.search(r"\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|kt|swift|rb|php|cs|sql|sh|"
                     r"ps1|yml|yaml|json|css|scss|html|md|toml|env\.example)$", rel):
        return
    try:
        if os.path.getsize(full) > 500_000:
            return
        with open(full, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                key = (rel, i)
                if key not in seen:
                    seen.add(key)
                    out.append({"file": rel, "line": i, "text": line.rstrip("\n")})
    except OSError:
        return


def lang_of(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "ts": "ts", "tsx": "ts", "js": "js", "jsx": "js", "mjs": "js", "cjs": "js",
        "py": "py", "go": "go", "rs": "rs", "java": "java", "kt": "kt", "cs": "cs",
        "rb": "rb", "php": "php", "sql": "sql", "sh": "sh", "ps1": "ps1",
        "css": "css", "scss": "css", "html": "html", "yml": "yaml", "yaml": "yaml",
        "json": "json", "md": "md",
    }.get(ext, ext)


# ------------------------------------------------------------------ the panel
#
# Each entry is (id, severity, langs, pattern, why). `langs` empty means any file
# that is not prose; see run_local for why markdown is the one exclusion.
# `why` is written for the person who has to decide whether to fix it, so it says
# what goes wrong, not which rule was violated.

CODE_LANGS = ["ts", "js", "py", "go", "rs", "java", "kt", "cs", "rb", "php",
              "sql", "sh", "ps1", "css", "html"]

PERSONAS: dict[str, dict] = {
    "security": {
        "owns": "credential exposure, injection surface, transport and access control",
        "checks": [
            ("shell-interpolation", HIGH, ["js", "ts"],
             r"(?:exec|execSync|spawnSync)\s*\(\s*[`\"'][^`\"']*\$\{",
             "a shell command built by string interpolation runs whatever the "
             "interpolated value contains"),
            ("py-shell-true", HIGH, ["py"],
             r"subprocess\.(?:run|call|Popen|check_output)\([^)]*shell\s*=\s*True",
             "shell=True with any non-literal argument is command injection"),
            # Two lookaheads, deliberately, and neither is optional: the line must
            # carry SQL STRUCTURE and DYNAMIC ASSEMBLY. The earlier single pattern
            # asked only for a verb followed later by a concatenation, so any English
            # sentence that deletes one thing and adds another matched. Measured on
            # the 2026-07-30 tree, all three of its sql-concat HIGHs were prose:
            #   "Delete ~380 lines (... checks + their selftest); add ~150-200 lines"
            #   print("  delete .env: " + ("done" if rc == 0 else "FAILED " + out))
            # Both survive the verb test and neither contains FROM, INTO or SET.
            # Third waiver for this class; tests/test_panel_sql_concat.py now pins it.
            #
            # The rewrite also closes a hole the old pattern had: it required the
            # assembly marker to come AFTER the verb, so f"SELECT * FROM t WHERE a =
            # {x}" did not match, because the f-prefix sits before SELECT. That is the
            # commonest Python injection shape and it was going unreported.
            ("sql-concat", HIGH, [],
             r"(?i)(?=.*(?:SELECT\s+.*\s+FROM|INSERT\s+INTO|UPDATE\s+.*\s+SET|"
             r"DELETE\s+FROM))"
             r"(?=.*(?:\+\s*\w+|\$\{|%\s*\(|%s['\"]\s*%|f['\"]|\{\w+\}))",
             "SQL assembled from variables instead of bound parameters"),
            ("dangerous-html", HIGH, ["js", "ts"],
             r"dangerouslySetInnerHTML|\.innerHTML\s*=\s*[^'\"`]",
             "unsanitized markup insertion is stored XSS if the value ever comes "
             "from a user"),
            # No whitespace allowed between `eval` and `(`, deliberately. The
            # tolerant `eval\s*\(` also matches the English noun followed by a
            # parenthetical -- "built BrainTrust eval (300 scenarios)" in an HTML
            # text node was reported as a HIGH and cost a waiver on 2026-07-26.
            # Excluding html wholesale was rejected: `<script>eval(src)</script>`
            # is a real finding, so the separation belongs in the pattern.
            # Coverage boundary, stated rather than discovered later: `eval (x)`
            # written with a space is not matched. Every JS formatter emits
            # `eval(`, and ESLint's func-call-spacing defaults to "never", so the
            # unmatched form is one nothing in a normal toolchain produces.
            # `new Function` keeps `\s*` -- prose does not say "new Function (".
            ("eval-added", HIGH, [],
             r"(?<![\w.])eval\(|new\s+Function\s*\(",
             "eval executes whatever it is handed"),
            ("tls-off", HIGH, [],
             r"NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0|verify\s*=\s*False|"
             r"rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true",
             "certificate verification disabled, so the connection is not "
             "authenticated"),
            ("cors-wildcard", MED, [],
             r"Access-Control-Allow-Origin['\"]?\s*[:,]\s*['\"]\*|origin\s*:\s*['\"]\*",
             "a wildcard origin lets any site call this with the user's session"),
            ("http-url", LOW, [],
             r"['\"]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)",
             "plaintext HTTP to a remote host"),
            ("jwt-unverified", HIGH, ["js", "ts", "py"],
             r"jwt\.decode\((?![^)]*verify)|decode\([^)]*verify_signature['\"]?\s*:\s*False",
             "a token decoded without verifying its signature is attacker-controlled "
             "data, not identity"),
        ],
    },
    "correctness": {
        "owns": "error handling, type escapes, and silently swallowed failure",
        "checks": [
            ("empty-catch", MED, ["js", "ts"],
             r"catch\s*(?:\([^)]*\))?\s*\{\s*\}",
             "an empty catch turns a failure into a wrong result with no trace"),
            ("bare-except-pass", MED, ["py"],
             r"except\s*(?:Exception\s*)?:\s*(?:#.*)?$",
             "a bare except hides the failure it caught, including the ones you did "
             "not anticipate"),
            ("ts-escape", MED, ["ts"],
             r"@ts-(?:ignore|expect-error|nocheck)|\bas\s+any\b|:\s*any\b",
             "a type escape moves the failure from compile time to a user's screen"),
            ("py-type-ignore", LOW, ["py"],
             r"#\s*type:\s*ignore",
             "the typechecker was told to stop looking here"),
            ("float-money", MED, [],
             r"(?i)(?:(?:price|amount|total|balance|cost|salary)\w*\s*:\s*(?:float|number)\b"
             r"|(?:FLOAT|DOUBLE)\s*(?:\(|,|$).*(?:price|amount|total|balance))",
             "binary floating point cannot represent decimal currency exactly"),
            # The first version required `foo.bar.then(`, which cannot cross the
            # parentheses in `save(row).then(...)` — the shape the defect actually
            # takes. It matched nothing for its whole life and the selftest is what
            # said so.
            ("unawaited", MED, ["js", "ts"],
             r"^\s*(?!(?:return|await|void|const|let|var|export|import|yield)\b|[}/*)\]])"
             r"[\w.]+(?:\s*\([^;]*\))?\s*\.(?:then|catch)\s*\(",
             "a promise chain with nothing awaiting it fails after the response is "
             "already sent"),
            ("loose-equality-null", LOW, ["js", "ts"],
             r"==\s*(?:undefined)\b|!=\s*(?:undefined)\b",
             "comparing against undefined with loose equality"),
        ],
    },
    "ux_frontend": {
        "owns": "what a person on a phone actually experiences",
        "checks": [
            ("img-no-alt", MED, ["ts", "js", "html"],
             r"<img(?![^>]*\balt\s*=)[^>]*>",
             "an image with no alt is invisible to a screen reader and to anyone on "
             "a failed load"),
            ("click-on-div", MED, ["ts", "js"],
             r"<(?:div|span)(?![^>]*\brole\s*=)(?![^>]*\btabIndex)[^>]*onClick",
             "a clickable div cannot be reached by keyboard or announced as a control"),
            ("outline-none", MED, ["css"],
             r"outline\s*:\s*(?:none|0)\b",
             "removing the focus ring without replacing it leaves keyboard users with "
             "no idea where they are"),
            ("fixed-px-font", LOW, ["css"],
             r"font-size\s*:\s*(?:[0-9]|1[01])px",
             "text under 12px is not readable on a phone"),
            ("input-no-label", MED, ["ts", "js", "html"],
             r"<input(?![^>]*\b(?:aria-label|aria-labelledby|id)\s*=)[^>]*>",
             "an input with no label and no id to attach one to is unlabelled"),
            # A missing viewport meta is a real mobile defect and it is deliberately
            # not checked here: it is a property of a whole document, and this
            # scanner sees one line at a time, so any per-line pattern for it would
            # fire on every <head> in the repository. tools/e2e/flow.py checks the
            # rendered viewport in a real browser, which is the right instrument.
            ("px-width-large", LOW, ["css"],
             r"(?:min-)?width\s*:\s*(?:[4-9]\d{2}|\d{4,})px",
             "a hard pixel width wider than a phone viewport causes horizontal scroll"),
        ],
    },
    "ops_release": {
        "owns": "what happens after merge: config, noise, and half-landed changes",
        "checks": [
            ("debug-left", LOW, ["js", "ts"],
             r"console\.(?:log|debug|dir)\s*\(",
             "debug output left in shipped code"),
            ("py-print-debug", LOW, ["py"],
             r"^\s*print\s*\(\s*(?:f?['\"](?:DEBUG|TODO|XXX|here|test)|\w+\s*\))",
             "debug print left in shipped code"),
            ("test-only", HIGH, ["js", "ts"],
             r"\b(?:describe|it|test)\.only\s*\(",
             "a .only silently skips every other test in the file, so a green suite "
             "means almost nothing"),
            # `xit\(` without the boundary matched the tail of `SystemExit(` and
            # `sys.exit(`, which reported 50 ordinary Python entry points as
            # disabled tests. The boundary is the whole difference between a signal
            # and noise nobody reads.
            ("test-skipped", MED, ["js", "ts", "py"],
             r"\b(?:describe|it|test)\.skip\s*\(|@(?:pytest\.mark\.)?skip|\bxit\s*\(",
             "a test disabled in the same change that touches its subject"),
            # Scoped to code on purpose. Run unscoped against this repository it
            # returned 296 findings, 294 of them TODO lines inside markdown plans and
            # json state, where a TODO is the content rather than a defect. A
            # reviewer that reports 296 non-problems has taught its reader to skip it.
            ("todo-added", LOW, CODE_LANGS,
             r"(?:^|\s)(?:TODO|FIXME|XXX|HACK)\b",
             "unfinished work marked in the code"),
            ("commented-code", LOW, ["js", "ts", "py"],
             r"^\s*(?://|#)\s*(?:if|for|while|return|const|let|def |class |import )",
             "commented-out code, which future readers cannot tell from live code"),
        ],
    },
    # SIXTH PERSONA, added 2026-08-05. It exists because dot-claude/rules/
    # boundary-contracts.md was restored the day before after a "sync" had cut it
    # from 5557 bytes to 488, and the restored rule carries three language-level
    # bans that were readable again and enforced by nothing. A rule nobody can fail
    # is a preference. This makes three of its eight points checkable.
    #
    # It also closes part of a measured gap: panel.py's persona names and
    # actors.json's `_aspect_enum` shared two words out of eleven, and `boundary`
    # was one of the six the registry declared that no local rule set covered. Four
    # external actors already declare may_enact boundary; now something local does
    # too, so tools/review/allocate.py can plan both halves of the same dimension.
    #
    # PRIOR ART, searched 2026-08-05 after the gate stopped a claim that these were
    # unenforced. They are unenforced HERE and thoroughly solved elsewhere, and the
    # difference matters for whoever reads this next:
    #   errcheck with `check-blank: true` is go-discarded-marshal and
    #     go-discarded-read, done with type information rather than a regex. Its own
    #     documentation uses `num, _ := strconv.Atoi(numStr)` as the example.
    #     golangci-lint bundles it; `dogsled` covers the multi-blank form.
    #   @typescript-eslint/no-unsafe-assignment already flags the JSON.parse case,
    #     because JSON.parse returns `any`. zod is the community answer to the
    #     underlying problem: decode at the boundary against a schema.
    #   The Semgrep Registry (2000+ rules) would express all three natively.
    # WHAT THESE THREE ADD is one property none of those has: the panel reads ADDED
    # DIFF LINES with no toolchain, no compilable package and no node_modules,
    # against repositories it does not build. That is the whole of the case for
    # them. For any repository that actually builds, run golangci-lint and
    # typescript-eslint and delete these. See TODO PERSONA-12.
    #
    # NOT in COMMENT_AWARE, deliberately. A commented-out `payload, _ := json.Marshal`
    # is dead code and not a live discarded error, and the comment-strip pass added
    # 2026-08-04 already removes it before these patterns see the line. Registering
    # them would be belt-and-braces on a mechanism that is already tested.
    "boundary": {
        "owns": "typed contracts at IO edges, and errors that are discarded rather than handled",
        "checks": [
            # `x, _ := json.Marshal(...)`. The rule names this one by example and
            # the qc-telephony-api proxy it came from failed on exactly this line.
            # Anchored on the blank identifier in the SECOND slot of a short
            # declaration, so `a, b := json.Marshal(...)` and a genuine
            # `_ = something` both stay clean.
            ("go-discarded-marshal", HIGH, ["go"],
             r"\b\w+\s*,\s*_\s*:?=\s*(?:json|xml|yaml)\.(?:Marshal|Unmarshal)\s*\(",
             "a discarded (de)serialization error is a silent data-corruption path; "
             "boundary-contracts.md rule 3"),
            # `out, _ := io.ReadAll(...)`. Same shape, the other half of the same
            # incident: the proxy read the upstream body with a discarded error and
            # sent the bytes straight back.
            ("go-discarded-read", HIGH, ["go"],
             r"\b\w+\s*,\s*_\s*:?=\s*(?:io|ioutil)\.(?:ReadAll|ReadFile)\s*\(",
             "a discarded read error means the body may be truncated or empty and "
             "nothing downstream can tell; boundary-contracts.md rule 3"),
            # An unchecked JSON.parse. Requires the call to be the whole of an
            # assignment or an argument, and NOT already inside a try. The panel
            # sees added lines rather than whole files, so `try {` on an earlier
            # line is invisible; that is why this is MEDIUM and not HIGH, and why
            # the message says which check the reader has to do by eye.
            ("ts-unchecked-json-parse", MED, ["ts", "js"],
             r"(?<!\.)\bJSON\.parse\s*\(",
             "JSON.parse throws on malformed input; boundary-contracts.md rule 3 "
             "wants the decode error handled. Confirm a surrounding try or a "
             "schema decode, which this line-scoped panel cannot see"),
        ],
    },
    "data": {
        "owns": "schema change safety and query cost",
        "checks": [
            ("select-star", LOW, ["sql", "py", "ts", "js"],
             r"(?i)SELECT\s+\*\s+FROM",
             "SELECT * breaks silently when a column is added and moves more data "
             "than the caller needs"),
            ("drop-in-migration", HIGH, ["sql"],
             r"(?i)\b(?:DROP\s+(?:TABLE|COLUMN)|TRUNCATE)\b",
             "a destructive schema change with no stated recovery path"),
            # `SET[^;]*` used to swallow the WHERE clause it was meant to require,
            # so every correctly-scoped UPDATE was reported as touching every row.
            # The negative lookahead has to reach the end of the statement.
            ("no-where", HIGH, ["sql"],
             r"(?i)^\s*(?:UPDATE|DELETE\s+FROM)\s+[\w.\"`\[\]]+(?![^;]*\bWHERE\b)",
             "an UPDATE or DELETE with no WHERE clause touches every row"),
            # NOT NULL can sit on either side of REFERENCES, so the lookahead has to
            # temper the scan in both directions rather than only looking rightward.
            # This sees the single-line column form only; a multi-line CREATE TABLE
            # is past what a line-level check can decide.
            ("nullable-fk", LOW, ["sql"],
             r"(?i)^(?:(?!NOT\s+NULL).)*REFERENCES\s+\w+\s*\([^)]*\)(?:(?!NOT\s+NULL).)*$",
             "a nullable foreign key permits orphan rows, on the single-line column "
             "form this check can actually see"),
        ],
    },
}

# Findings inside these paths are noise: a test may legitimately use eval, and a
# lockfile or vendored bundle is not hand-written code.
EXEMPT = re.compile(
    r"(?i)(^|/)(?:tests?|__tests__|spec|fixtures?|mocks?|vendor|node_modules|dist|build|"
    r"\.next|migrations?/archive)/|"
    r"(?:\.min\.(?:js|css)|\.lock|lock\.json|-lock\.yaml|\.map|\.snap)$")

# A pattern's own definition contains the thing it looks for, so a file that IS a
# scanner trips every check in it. That is not a finding, it is the tool reading
# itself.
#
# state/ is the same property one step removed. This reviewer WRITES
# state/reviews/<sha>.json on every run, quoting each flagged line into a `snippet`
# field, and the next run reads those quotes back as source. Measured 2026-07-25:
# the high count went 4 -> 7 across two consecutive runs purely because one review
# file landed in between, and nothing bounded it. The append-only ledgers beside it
# are machine-written records of what tools saw, not code anyone can fix.
#
# Anchored with ^ and not (^|/) like the alternatives above, deliberately: an
# unanchored state/ would also exempt src/state/, which is ordinary application
# code in a very common layout. cmd_selftest plants exactly that file and requires
# it to still be found.
#
# NARROWED 2026-07-31, and the way this was found is the point. A codex review, the
# first external review this repository has ever completed, reported that `^state/`
# excludes REAL SOURCE under the root state/ directory and not only generated
# artifacts (CWE-693, protection mechanism failure). It was right: `git ls-files
# state/**/*.py` returns tracked Python, so every line of it was silently unreviewed
# while the panel reported a clean verdict. The anchoring comment above reasoned
# carefully about src/state/ and never asked what was in state/ itself.
#
# The first narrowing attempt exempted only state/reviews/ and state/gate-runs.jsonl,
# and the selftest rejected it: it plants state/bus.jsonl and requires ledgers to stay
# exempt. That requirement is right and the comment above already says why. A ledger is
# a machine-written record of what a tool saw, so a finding against it names nothing a
# human can fix, and sql-concat duly fired on a bus row the moment ledgers became
# reviewable.
#
# So the split is not by directory and not by tool ownership. It is by whether the file
# is CODE. Everything under state/ stays exempt except source, which is reviewed like
# source anywhere else. The negative lookahead carries the whole correction.
SOURCE_EXT = r"py|pyi|ts|tsx|js|jsx|mjs|cjs|sh|bash|ps1|rs|go|rb|java|kt|swift|php|cs|sql"
SELF_REFERENTIAL = re.compile(
    r"(?i)(^|/)(?:tools/(?:review|gate|e2e|refute)/|dot-claude/hooks/)"
    r"|^state/(?!.*\.(?:" + SOURCE_EXT + r")$)")


def run_local(lines: list[dict]) -> list[dict]:
    findings: list[dict] = []
    for persona, spec in PERSONAS.items():
        for cid, sev, langs, pat, why in spec["checks"]:
            comment_aware = cid in COMMENT_AWARE
            rx = re.compile(pat)
            for ln in lines:
                if EXEMPT.search(ln["file"]) or SELF_REFERENTIAL.search(ln["file"]):
                    continue
                lang = lang_of(ln["file"])
                if langs:
                    if lang not in langs:
                        continue
                elif lang == "md":
                    # An empty `langs` means any file, and that used to include prose.
                    # A document that SHOWS a vulnerable example is the document doing
                    # its job: red-team-review/EXAMPLE_SESSION.md was reported for the
                    # injection it exists to demonstrate. Narrowed to md alone rather
                    # than to CODE_LANGS, because rejectUnauthorized: false in a yaml
                    # CI config is a real tls-off finding and a json config can carry a
                    # wildcard CORS origin. No registered check names "md", so nothing
                    # that exists loses coverage here.
                    continue
                hay = ln["text"] if comment_aware else code_only(ln["text"], lang)
                if not rx.search(hay):
                    continue
                findings.append({
                    "persona": persona, "check": cid, "severity": sev,
                    "file": ln["file"], "line": ln["line"], "why": why,
                    "snippet": ln["text"].strip()[:160], "source": "local",
                })
    # Diff-level E-row checks (anatomy/e-rows/): composite shapes that do not
    # fit the per-line pattern tuples above. Same exemption rules apply.
    reviewable = [ln for ln in lines
                  if not EXEMPT.search(ln["file"])
                  and not SELF_REFERENTIAL.search(ln["file"])]
    findings += e_rows.composite_findings(reviewable, lines)
    return findings


# ------------------------------------------------------------------ external

# A judge that can read the SKILL.md it is grading grades the INTENT rather than
# the artifact: the definition states what the skill is supposed to do, so a model
# holding both tends to confirm the description instead of testing the output.
# CoEvoSkills runs its surrogate verifier blind to the generator's reasoning and to
# the skill content for this reason. run_local is unaffected, being pattern matching
# over code, and prose is already skipped by the md branch in it.
SKILL_DEFINITION = re.compile(
    r"(?i)(^|/)SKILL\.md$|(^|/)(?:dot-claude|dot-codex|dot-agents|\.claude)/"
    r"(?:skills|agents|commands)/")


def judge_blind(lines: list[dict]) -> tuple[list[dict], int]:
    """Remove skill and agent DEFINITIONS from what an external judge is shown.

    Returns (kept, stripped). The count is returned rather than swallowed so the
    note can say it out loud: a silent filter is indistinguishable from a filter
    that stopped working, which is the failure this whole tool exists to prevent.
    """
    kept = [ln for ln in lines if not SKILL_DEFINITION.search(ln["file"])]
    return kept, len(lines) - len(kept)


def screen_for_send(lines: list[dict]) -> tuple[list[dict], int, list[str]]:
    """Decide what may be transmitted. Pure, so it can be tested without a call.

    Returns (sendable, blinded, leaks). A non-empty `leaks` means send NOTHING.

    Order is the guarantee: the credential scan runs over every line BEFORE any
    blinding, so filtering can never remove a key from its own leak check. Both
    halves lived inline in run_external, fused to a network call, which is why
    mutation testing on 2026-07-27 found them completely unguarded.
    """
    leaks = redactable(lines)
    if leaks:
        return [], 0, leaks
    sendable, blinded = judge_blind(lines)
    return sendable, blinded, []


def validate_findings(raw: object, valid: set, model: str) -> tuple[list[dict], int]:
    """Keep only findings citing a line this change actually added.

    Returns (kept, dropped). An invented file:line is the normal failure mode of a
    model reviewer, and an unverifiable finding cannot be acted on, so it is
    discarded and counted. The count is returned rather than logged because a
    reviewer that quietly discards half its own output while reporting the rest as
    clean is worse than one that reports nothing.
    """
    out: list[dict] = []
    dropped = 0
    for f in raw if isinstance(raw, list) else []:
        if not isinstance(f, dict):
            dropped += 1
            continue
        try:
            fl, li = str(f.get("file")), int(f.get("line"))
        except (TypeError, ValueError):
            dropped += 1
            continue
        if (fl, li) not in valid:
            dropped += 1
            continue
        sev = str(f.get("severity", MED)).lower()
        out.append({"persona": "external", "check": "model-review",
                    "severity": sev if sev in (HIGH, MED, LOW) else MED,
                    "file": fl, "line": li, "why": str(f.get("why", ""))[:400],
                    "snippet": "", "source": "openrouter:{}".format(model)})
    return out, dropped


def build_note(model: str, kept: int, dropped: int, model_note: str,
               truncated: bool, blinded: int) -> str:
    """The note that ships with the artifact. Pure, so the counts can be asserted.

    Every number here is a thing a reader would otherwise have to take on trust:
    how many findings survived, how many were discarded for citing a line that
    does not exist, whether the input was cut short, and how much was withheld
    from the judge on purpose. Dropping any of them turns a partial review into
    one that reads as complete.
    """
    return (
        "model {} returned {} finding(s), {} dropped for citing a line this change "
        "did not add. {}{}{}".format(
            model, kept, dropped, str(model_note)[:300],
            "  Input was truncated at 60k chars." if truncated else "",
            "  {} skill/agent definition line(s) withheld from the judge.".format(blinded)
            if blinded else ""))


def redactable(lines: list[dict]) -> list[str]:
    """Credential-shaped content in the change. Fail closed if any is present."""
    pats = [
        r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"gh[pousr]_[A-Za-z0-9]{30,}", r"sk-[A-Za-z0-9]{20,}", r"AIza[0-9A-Za-z_\-]{35}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][A-Za-z0-9/+_\-\.]{16,}['\"]",
    ]
    hits = []
    for ln in lines:
        for p in pats:
            if re.search(p, ln["text"]):
                hits.append("{}:{}".format(ln["file"], ln["line"]))
                break
    return hits


def run_external(lines: list[dict], project: str, verbose: bool,
                 model: str | None = None) -> tuple[list[dict], str]:
    """A free model reads the change for what a pattern cannot see.

    `model` names the model to try FIRST; the client falls back to zero-priced
    alternates behind it. Left as None the client picks a free model itself, which
    is the historical behaviour. Exposed 2026-07-31 so a specific decorrelated
    family can be requested (tools/review/actors.json), because the client always
    accepted a model argument and this function was the reason nobody could pass
    one. Passing a PRICED model id here leaves the free tier: the client's daily
    quota counts requests, not dollars, so it will not stop a paid model from
    billing. Check the price before naming one.

    Returns (findings, note). Any finding whose citation is not a line this change
    actually added is dropped, because an invented file:line is the normal failure
    mode here and an unverifiable finding cannot be acted on.
    """
    lines, blinded, leaks = screen_for_send(lines)
    if leaks:
        return [], ("refused to send: the change contains credential-shaped content at {}. "
                    "Nothing was transmitted.".format(", ".join(leaks[:5])))
    if not lines:
        return [], ("nothing sent: every added line was a skill or agent definition, "
                    "which the judge is deliberately blind to. {} line(s) withheld."
                    .format(blinded))
    sys.path.insert(0, os.path.join(SETUP, "openrouter"))
    try:
        import client as orc  # type: ignore
    except Exception as exc:
        return [], "openrouter client unavailable: {}".format(exc)

    valid = {(l["file"], l["line"]) for l in lines}
    budget = 60_000
    body, used = [], 0
    for l in lines:
        row = "{}:{}: {}".format(l["file"], l["line"], l["text"][:300])
        if used + len(row) > budget:
            break
        body.append(row)
        used += len(row)
    truncated = len(body) < len(lines)

    prompt = (
        "Review these added lines from one change. Report only defects a reader could "
        "act on: a wrong result, a broken flow, a security hole, or a mobile UI that "
        "will not work on a 390px screen. Do not report style. Do not report anything "
        "you cannot point at a specific line for.\n\n"
        "Return JSON only: {\"findings\":[{\"file\":..,\"line\":..,\"severity\":"
        "\"high|medium|low\",\"why\":..}],\"note\":\"what you could not assess\"}\n\n"
        "If the change looks correct, return an empty findings array and say in note "
        "what you checked.\n\n" + "\n".join(body))
    try:
        # orc.chat returns a DICT ({model, text, usage, elapsed_s, id, tried}), not a
        # pair. This line read `text, model = orc.chat(...)` from the day the external
        # backend was written, so every --allow-external run died inside the try with
        # "too many values to unpack (expected 2)" and was reported as the polite
        # "external review call failed", one line of note text under a PASS verdict.
        # The leg has therefore never once returned a finding. Measured 2026-07-31.
        # 4000, not the client's 1200 default. A reasoning model bills its thinking
        # against the same completion budget, and z-ai/glm-4.7-flash was measured on
        # 2026-07-31 spending 564 to 904 tokens reasoning before writing a character
        # of the answer, so 1200 left too little to finish the JSON. The ceiling is
        # not the cost driver here: the answer itself is a few hundred tokens, and an
        # unfinished answer costs the same as a finished one while being worthless.
        reply = orc.chat(prompt, model=model, max_tokens=4000, system=(
            "You are a reviewer who did not write this code. Cite a real line number for "
            "every finding. An empty findings array is a valid and common answer."))
        text, model = reply["text"], reply["model"]
    except Exception as exc:
        return [], "external review call failed: {}".format(exc)

    # A reasoning model can spend the whole completion budget thinking and return no
    # parseable object. Measured 2026-07-31 with z-ai/glm-4.7-flash: at the budget
    # this function asks for, 904 of the completion tokens were reasoning tokens, the
    # content came back null, and the old code turned that into `findings: []`. The
    # panel then printed "0 finding(s), 0 dropped", which is character-for-character
    # what a genuinely clean change prints. A reviewer that failed to answer must not
    # be indistinguishable from a reviewer that found nothing, so an unparseable
    # non-empty reply is now reported as a failure instead of as silence.
    data = orc.extract_json(text)
    if data is None:
        if (text or "").strip():
            return [], ("external review UNUSABLE: {} returned {} character(s) that "
                        "contained no JSON object. This is not a clean result. A "
                        "reasoning model starved of completion budget looks exactly "
                        "like this.".format(model, len(text)))
        return [], "external review UNUSABLE: {} returned an empty reply.".format(model)
    out, dropped = validate_findings(data.get("findings") or [], valid, model)
    note = build_note(model, len(out), dropped, data.get("note", ""), truncated, blinded)
    if verbose:
        print("    " + note, file=sys.stderr)
    return out, note


# ------------------------------------------------------------------ verdict

def cmd_run(args: argparse.Namespace) -> int:
    project = os.path.abspath(args.project)
    rc, _ = sh("git rev-parse --git-dir", project)
    if rc != 0:
        print("not a git repository: {}".format(project))
        return 2
    base = args.base or default_base(project)
    sha = sh("git rev-parse HEAD", project)[1].strip() or "no-commit"

    lines = added_lines(project, base)
    if not lines:
        print("no added lines relative to {}, so there is nothing to review".format(base))
        return 2

    files = sorted({l["file"] for l in lines})
    print("persona panel: {} added line(s) across {} file(s), base {}".format(
        len(lines), len(files), base))

    findings = None
    ext_note = "external backend not requested"
    fp = e_rows.registry_fingerprint(PERSONAS)
    # The memoized decision is a function of the REVIEWABLE lines. Machine-
    # written state (the panel's own artifacts under state/, exempt from
    # findings by SELF_REFERENTIAL) must not enter the key: an untracked
    # artifact from run N would otherwise land in run N+1's diff and no
    # lookup could ever hit twice in a row. EXEMPT paths (tests, vendor,
    # lockfiles) contribute no findings by construction, so excluding them
    # cannot change the verdict being replayed.
    key_lines = [ln for ln in lines
                 if not EXEMPT.search(ln["file"])
                 and not SELF_REFERENTIAL.search(ln["file"])]
    # Tiered memoized decisions (#372, tools/review/review_cache.py):
    # exact -> normalized -> semantic (opt-in), every key under the full
    # conditioning tuple (registry fingerprint, file-type context,
    # external-backend mode, prior findings on the PR). A stale or
    # differently-conditioned entry is a miss, never a replay.
    cache = review_cache.TieredDecisionCache(
        os.path.join(project, "state", "reviews", "decision-cache.json"))
    cache_active = not args.allow_external and bool(key_lines)
    langs = sorted({lang_of(ln["file"]) for ln in key_lines})
    prior = review_cache.prior_findings_checksum(project, base,
                                                 exclude_sha=sha)
    ext_mode = ("external:" + str(getattr(args, "external_model", None) or "auto")
                if args.allow_external else "local-only")
    tier = None
    forced_live = False
    res = None
    if cache_active:
        res = cache.lookup(
            key_lines, registry_fp=fp, langs=langs, external_mode=ext_mode,
            prior_checksum=prior,
            semantic_enabled=bool(getattr(args, "allow_semantic_cache", False)))
        if res["forced_live"]:
            forced_live = True
            print("decision cache: anti-loop guard forced a live run "
                  "(replay cap reached)")
        elif res["tier"] is not None:
            tier = res["tier"]
            findings = res["entry"]["findings"]
            print("decision cache: {} hit (registry {})".format(tier, fp[:12]))
    live = findings is None
    if live:
        findings = run_local(lines)
    # Signals are computed ONCE and shared by the external-leg gate and the
    # cost table: the table must account for the decision it reports, never
    # a differently-based twin. Signal lines exclude machine-written state
    # (SELF_REFERENTIAL) but keep test files: a test file is exempt from
    # local checks yet is real change the external leg can review, and the
    # tests-aspect trigger needs to see it.
    signal_lines = [ln for ln in lines
                    if not SELF_REFERENTIAL.search(ln["file"])]
    signals = review_cache.review_signals(
        signal_lines, findings,
        {ln["file"]: lang_of(ln["file"]) for ln in signal_lines})
    trigger_eval = review_cache.evaluate_triggers(signals)
    ext_ran = False
    if args.allow_external and live:
        # Trigger-conditioned aspect execution (#372): the expensive external
        # leg runs only when at least one aspect's trigger fires; the skip is
        # recorded, never silent. This narrows the previous always-run
        # behavior for --allow-external (stated residual, see review_cache).
        if review_cache.external_should_run(trigger_eval):
            ext, ext_note = run_external(
                lines, project, args.verbose,
                getattr(args, "external_model", None))
            findings += ext
            ext_ran = True
        else:
            ext_note = ("external skipped: no aspect triggered "
                        "(trigger-conditioned execution, #372)")

    blocking = [f for f in findings if f["severity"] == HIGH]
    med = [f for f in findings if f["severity"] == MED]
    low = [f for f in findings if f["severity"] == LOW]

    by_persona: dict[str, list] = {}
    for f in findings:
        by_persona.setdefault(f["persona"], []).append(f)
    for persona in list(PERSONAS) + (["external"] if args.allow_external else []):
        got = by_persona.get(persona, [])
        owns = PERSONAS.get(persona, {}).get("owns", "what patterns cannot see")
        print("\n  {:<12} {:<24} {}".format(
            persona, owns[:24], "{} finding(s)".format(len(got)) if got else "no finding"))
        for f in sorted(got, key=lambda x: {HIGH: 0, MED: 1, LOW: 2}[x["severity"]])[:12]:
            print("      {:<7} {}:{}  {}".format(f["severity"], f["file"], f["line"], f["check"]))
            print("              {}".format(f["why"]))
            if f["snippet"]:
                print("              > {}".format(f["snippet"]))
        if len(got) > 12:
            print("      ... {} more not printed, all of them are in the artifact".format(
                len(got) - 12))

    fail_at = {"high": [HIGH], "medium": [HIGH, MED], "low": [HIGH, MED, LOW]}[args.fail_on]
    blockers = [f for f in findings if f["severity"] in fail_at]
    verdict = "pass" if not blockers else "changes-requested"
    if cache_active:
        # forced_key renews the capped entry's replay budget (anti-loop
        # guard contract); without it the guard would ratchet shut forever.
        cache.store(key_lines, registry_fp=fp, langs=langs,
                    external_mode=ext_mode, prior_checksum=prior,
                    verdict=verdict, findings=findings,
                    reset_replays_for_key=(res or {}).get("forced_key")
                    if forced_live else None)

    # Expected-calls-per-review accounting (#372, ch.11 Table 11-3):
    #   expected = P(triggered) x calls_when_triggered x (1 - memoized).
    # Rows are execution legs (measured actuals), not aspects: the cheap
    # deterministic panel is one leg, the external model pass is one leg.
    # Per-aspect trigger detail lives in aspect_triggers. trigger_eval is
    # the SAME evaluation that gated the external leg above, so the table
    # accounts for the decision it reports.
    cost_table = review_cache.expected_calls_table(
        trigger_eval, external_possible=args.allow_external,
        external_ran=ext_ran, local_ran=live,
        memoized_fraction=1.0 if tier is not None else 0.0)

    coverage = (
        "Reviewed {} added line(s) across {} file(s) against {} pattern checks in {} "
        "personas{}. This panel sees added lines only, not pre-existing code, and it sees "
        "syntax, not intent: a wrong algorithm that reads cleanly will pass it. It is not "
        "a substitute for a human reading the diff, and the artifact should not be cited "
        "as one.".format(
            len(lines), len(files),
            sum(len(p["checks"]) for p in PERSONAS.values()), len(PERSONAS),
            " plus one external model pass" if args.allow_external else ""))

    artifact = {
        "commit": sha,
        "base": base,
        "reviewer": "persona-panel/local" + ("+openrouter" if args.allow_external else ""),
        "reviewed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "summary": ("{} high, {} medium, {} low across {} personas".format(
            len(blocking), len(med), len(low), len(by_persona))
            + ("" if verdict == "pass" else "; blocking at --fail-on={}".format(args.fail_on))),
        "coverage_boundary": coverage,
        "external_note": ext_note,
        "counts": {"high": len(blocking), "medium": len(med), "low": len(low)},
        "findings": findings,
        "files": files,
        "decision_cache": {
            "tier": tier,
            "registry_fp": fp,
            "langs": langs,
            "external_mode": ext_mode,
            "prior_checksum": prior[:16],
            "forced_live": forced_live,
            "telemetry": cache.telemetry_snapshot(),
        },
        "aspect_triggers": trigger_eval,
        "cost_table": cost_table,
    }
    dest = args.out or os.path.join(project, "state", "reviews", "{}.json".format(sha))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=1)

    emit_github_annotations(findings)

    print("\nVERDICT: {}  ({} high, {} medium, {} low)".format(
        verdict.upper(), len(blocking), len(med), len(low)))
    print("  " + coverage)
    if args.allow_external:
        print("  external: " + ext_note)
    print("  expected calls per review (P(triggered) x calls x (1-memoized); "
          "actuals measured):")
    for row in cost_table:
        print("    {:<22} p={:.1f} calls={} memoized={:.1f} expected={} actual={} {}".format(
            row["leg"], row["p_triggered"],
            row["calls_when_triggered"], row["memoized"],
            row["expected_calls"], row["actual_calls"],
            "({})".format(row["trigger"]) if row["trigger"] else ""))
    print("  artifact: {}".format(os.path.relpath(dest, project)))
    if sh("git status --porcelain", project)[1].strip():
        print("  note: the tree is dirty, so this artifact describes uncommitted work while "
              "naming commit {}. The gate's review domain wants an artifact for a committed "
              "tree; commit first and rerun.".format(sha[:12]))
    return 0 if verdict == "pass" else 1


ANNOTATION_CAP = 10


def _wc_escape(s: str, prop: bool) -> str:
    """Escape a GitHub workflow-command field.

    GitHub parses `::error k=v,k=v::message`, so a raw newline ends the command and a
    raw comma or colon inside a property silently splits it. The documented escapes are
    %25 for percent, %0D and %0A for the line endings, and additionally %3A and %2C
    inside property values. Percent goes first or it double-escapes the others.
    """
    s = s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if prop:
        s = s.replace(":", "%3A").replace(",", "%2C")
    return s


def emit_github_annotations(findings: list, stream=None) -> int:
    """Print findings as GitHub workflow commands so they land on the PR diff.

    Written 2026-07-30 INSTEAD OF adopting reviewdog. That evaluation proposed
    panel.py -> to_rdjson.py -> reviewdog.exe to get findings onto a pull request, and
    reviewdog's own README documents its `github-annotations` reporter emitting exactly
    `::error line=,col=,file=::message`, the same string this function prints. The
    binary, the translator and the supply-chain surface were all carrying a payload we
    can emit directly from the artifact we already build.

    No-op outside Actions, so it is invisible locally and in the gate's own selftest.
    Capped because GitHub renders at most 10 annotations per level per step and
    silently drops the rest, and a silent drop reads as "nothing else was found".
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return 0
    out = stream or sys.stdout
    levels = (("high", "error"), ("medium", "warning"))
    written = 0
    for sev, level in levels:
        rows = [f for f in findings if str(f.get("severity", "")).lower() == sev]
        for f in rows[:ANNOTATION_CAP]:
            print("::{} file={},line={},title={}::{}".format(
                level,
                _wc_escape(str(f.get("file", "")), True),
                str(f.get("line", 0)),
                _wc_escape("panel/" + str(f.get("check", "review")), True),
                _wc_escape(str(f.get("why", "")), False)), file=out)
            written += 1
        if len(rows) > ANNOTATION_CAP:
            print("::notice::{} {} finding(s) not annotated; GitHub renders {} per "
                  "level per step. Full set in the review artifact.".format(
                      len(rows) - ANNOTATION_CAP, sev, ANNOTATION_CAP), file=out)
    return written


def cmd_selftest(args: argparse.Namespace) -> int:
    """Plant one defect per persona and prove each is found, then prove a clean
    change is not decorated with invented findings."""
    import tempfile
    rc = 0
    # One planted line per check in the registry. A check with no positive case is
    # indistinguishable from a check that can never fire, so the assertion below
    # requires every registered check id to appear here.
    planted = {
        "app.ts": [
            "export function q(id: string) {",
            "  return db.query('SELECT * FROM users WHERE id = ' + id);",   # sql-concat
            "}",
            "  execSync(`rm -rf ${dir}`);",                                 # shell-interpolation
            "  el.innerHTML = untrusted;",                                  # dangerous-html
            "  eval(src);",                                                 # eval-added
            "  const a = { rejectUnauthorized: false };",                   # tls-off
            "  const c = { origin: '*' };",                                 # cors-wildcard
            "  fetch(\"http://api.example.com/v1\");",                      # http-url
            "  const who = jwt.decode(token);",                             # jwt-unverified
            "  try { risky(); } catch {}",                                  # empty-catch
            "  const x = y as any;",                                        # ts-escape
            "  const cfg = JSON.parse(raw);",                               # ts-unchecked-json-parse
            "  let price: number = 0;",                                     # float-money
            "  save(row).then(done);",                                      # unawaited
            "  if (x == undefined) { return; }",                            # loose-equality-null
            "  console.log('debug');",                                      # debug-left
            "  // return 1;",                                               # commented-code
            "  // TODO: handle the empty case",                             # todo-added
            "const bad = <div onClick={go}>press</div>;",                    # click-on-div
            "const pic = <img src=\"/a.png\" />;",                           # img-no-alt
            "const f = <input type=\"text\" />;",                            # input-no-label
            "it.only('one test', () => {});",                               # test-only
            "it.skip('another', () => {});",                                # test-skipped
        ],
        "run.py": [
            "import subprocess  # type: ignore",                            # py-type-ignore
            "def go(cmd):",
            "    subprocess.run(cmd, shell=True)",                          # py-shell-true
            "    requests.get(u, verify=False)",                            # tls-off (py form)
            "    print(\"DEBUG\")",                                         # py-print-debug
            "    try:",
            "        work()",
            "    except:",                                                  # bare-except-pass
            "        pass",
        ],
        # Go has no fixture file until now, because no check declared it. The
        # boundary persona added 2026-08-05 is the first, so the language arrives
        # with its own positive cases rather than being asserted to work.
        "proxy.go": [
            "func handler(c *fiber.Ctx) error {",
            "\tpayload, _ := json.Marshal(req)",                            # go-discarded-marshal
            "\tout, _ := io.ReadAll(resp.Body)",                            # go-discarded-read
            "\treturn c.Send(out)",
            "}",
        ],
        "schema.sql": [
            "DROP TABLE users;",                                            # drop-in-migration
            "DELETE FROM sessions;",                                        # no-where
            "CREATE TABLE t (uid int REFERENCES users(id));",               # nullable-fk
            "SELECT * FROM audit;",                                         # select-star
        ],
        "ui.css": [
            "button { outline: none; }",                                    # outline-none
            ".panel { min-width: 1200px; }",                                # px-width-large
            ".tiny { font-size: 10px; }",                                   # fixed-px-font
        ],
    }
    want = [(p, c) for p, spec in PERSONAS.items() for c, *_ in spec["checks"]]
    with tempfile.TemporaryDirectory() as td:
        sh("git init -q .", td)
        sh('git -c user.email=t@t -c user.name=t commit -q --allow-empty -m base', td)
        for name, body in planted.items():
            open(os.path.join(td, name), "w", encoding="utf-8").write("\n".join(body) + "\n")
        lines = added_lines(td, "HEAD")
        found = {(f["persona"], f["check"]) for f in run_local(lines)}
        print("planted change produced {} finding(s) over {} line(s)".format(
            len(run_local(lines)), len(lines)))
        for persona, check in want:
            ok = (persona, check) in found
            print("  {}  {:<12} {}".format("ok  " if ok else "MISS", persona, check))
            rc |= 0 if ok else 1

        # A clean change must produce nothing. A reviewer that always finds
        # something is a reviewer nobody reads, and every false positive here is a
        # line somebody has to defend in review for no reason.
        #
        # The lines below are not hypothetical. Every one of them was flagged by an
        # earlier version of this file when it was pointed at real code: `xit\(`
        # matched the tail of `SystemExit(`, so 50 ordinary Python entry points were
        # reported as disabled tests. A pattern is only as good as the innocent text
        # it has been shown to leave alone.
        for name in planted:
            os.remove(os.path.join(td, name))
        innocent = {
            "clean.ts": [
                "export function add(a: number, b: number): number {",
                "  return a + b;",
                "}",
                "export const Img = () => <img src=\"/x.png\" alt=\"a diagram\" />;",
                "await save(row);",
                "  return save(row).then(done);",
                "    .then(next)",
            ],
            "entry.py": [
                "import sys",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
                "    sys.exit(main())",
            ],
            "ok.sql": [
                "UPDATE users SET seen = 1 WHERE id = 4;",
                "CREATE TABLE t (uid int NOT NULL REFERENCES users(id));",
            ],
            "ok.css": [
                ".btn:focus-visible { outline: 2px solid var(--ring); }",
                ".card { max-width: 100%; font-size: 1rem; }",
            ],
            # Prose that happens to contain the English noun "eval". The first line
            # is verbatim from new-recruit's 00001061-AUDIT_DASHBOARD.html:333, which
            # eval-added reported as a HIGH on 2026-07-26 and cost a waiver: there is
            # no JavaScript on it at all. HTML is not excluded the way markdown is,
            # because `<script>eval(src)</script>` in a page is a real finding, so the
            # separation has to come from the pattern rather than the file type.
            "page.html": [
                "<div class=\"kcard-desc\">Oded built BrainTrust eval (300 scenarios)."
                " Needs dev environment before connecting to live.</div>",
                "<p>We ran the eval (twice) and the medical eval (again).</p>",
                "<li>Retrieval eval (nDCG@10) beat the baseline.</li>",
            ],
        }
        for name, body in innocent.items():
            open(os.path.join(td, name), "w", encoding="utf-8").write("\n".join(body) + "\n")
        clean = run_local(added_lines(td, "HEAD"))
        ok = not clean
        print("\n  {}  ordinary code produces no findings".format("ok  " if ok else "MISS"))
        for f in clean:
            print("        false positive: {} {} {}:{}  {}".format(
                f["persona"], f["check"], f["file"], f["line"], f["snippet"]))
        rc |= 0 if ok else 1

        # A reviewer must not review its own output, and a ledger is not source.
        #
        # Every run writes state/reviews/<sha>.json, and that file QUOTES each line
        # it flagged in a `snippet` field. The next run reads those quotes back as
        # source and reports them again. That is not one stale finding, it is a
        # feedback loop with nothing bounding it: measured on this repo on
        # 2026-07-25, the high count went 4 -> 7 across two consecutive runs purely
        # because one review file landed in between. The append-only ledgers under
        # state/ have the same shape, recording what a tool saw rather than anything
        # a person wrote, and a prose file has it for a different reason: an example
        # of an injection in documentation is the documentation working.
        #
        # Exempting them costs no credential coverage. gate.py's secret_scan walks
        # every tracked file and its SECRET_SKIP does not exclude state/, so a key
        # committed there is still caught by the check meant to catch it. What is
        # given up is injection review of machine-written logs, which was never
        # signal.
        #
        # Committed first and appended to second, on purpose. Untracked files reach
        # the reviewer through _collect_file, which filters by extension and would
        # never have collected a .jsonl at all. The real bus.jsonl finding came
        # through the diff path, which applies no extension filter whatsoever, so a
        # fixture that only planted untracked files would pass without the fix.
        echoed = {
            "state/reviews/abc123.json":
                '  "snippet": "db.query(\'SELECT * FROM users WHERE id = \' + id)"',
            "state/bus.jsonl":
                '{"level":"warn","text":"SELECT * FROM t WHERE id = \' + uid"}',
            "docs/EXAMPLE_SESSION.md":
                "    db.query('SELECT * FROM users WHERE id = ' + id)",
            # The counter-case, and the reason the exemption is anchored at the repo
            # root: an unanchored `state/` also swallows src/state/, which is
            # ordinary application code in a very common layout.
            "src/state/api.ts":
                "  return db.query('SELECT * FROM users WHERE id = ' + id);",
        }
        for rel in echoed:
            full = os.path.join(td, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            open(full, "w", encoding="utf-8").write("placeholder\n")
        sh("git add -A && git -c user.email=t@t -c user.name=t commit -q -m echoed", td)
        for rel, body in echoed.items():
            with open(os.path.join(td, rel.replace("/", os.sep)), "a", encoding="utf-8") as fh:
                fh.write(body + "\n")

        echo_found = run_local(added_lines(td, "HEAD"))
        noise = [f for f in echo_found if f["file"] != "src/state/api.ts"]
        ok = not noise
        print("\n  {}  neither its own output nor a ledger is reviewed as source".format(
            "ok  " if ok else "MISS"))
        for f in noise:
            print("        false positive: {} {} {}:{}".format(
                f["persona"], f["check"], f["file"], f["line"]))
        rc |= 0 if ok else 1

        ok = any(f["file"] == "src/state/api.ts" and f["check"] == "sql-concat"
                 for f in echo_found)
        print("  {}  an ordinary src/state/ file is still reviewed".format(
            "ok  " if ok else "MISS"))
        rc |= 0 if ok else 1

        # A base that resolves to HEAD yields an empty diff, which reads as "nothing
        # to review" and quietly makes the review domain unpassable on a clean tree.
        # On the branch being gated that is the common case, not an edge case.
        sh("git add -A && git -c user.email=t@t -c user.name=t commit -q -m clean", td)
        head = sh("git rev-parse HEAD", td)[1].strip()
        base = default_base(td)
        base_sha = sh("git rev-parse " + base, td)[1].strip()
        ok = base_sha != head
        print("  {}  default base on a committed branch is not HEAD itself ({})".format(
            "ok  " if ok else "MISS", base))
        rc |= 0 if ok else 1

        n = len(added_lines(td, base))
        ok = n > 0
        print("  {}  a clean committed tree still has {} line(s) to review".format(
            "ok  " if ok else "MISS", n))
        rc |= 0 if ok else 1

    def assert_(ok: bool, msg: str) -> int:
        """Print one assertion. On failure also emit a `[FAIL] ` line.

        tools/audit/mutate.py decides whether a mutation was caught by a NAMED
        check by scanning stdout for lines starting with `[FAIL]` (mutate.py:174).
        This selftest printed only `MISS`, so every mutation against this file was
        recorded as a weak signal no matter how well covered the behaviour was.
        """
        print("  {}  {}".format("ok  " if ok else "MISS", msg))
        if not ok:
            print("[FAIL] {}".format(msg))
        return 0 if ok else 1

    # A judge that reads the SKILL.md it is grading grades the intent, not the
    # artifact. These assertions exist because that filter is invisible from
    # outside: a filter that silently stopped working looks exactly like one that
    # had nothing to remove.
    probe = [
        {"file": "dot-claude/skills/explain-simply/SKILL.md", "line": 1, "text": "x"},
        {"file": ".claude/agents/reviewer.md", "line": 1, "text": "x"},
        {"file": "hiring_engine/today.py", "line": 1, "text": "x"},
        {"file": "docs/SKILL-notes.md", "line": 1, "text": "x"},
    ]
    kept, blinded = judge_blind(probe)
    kept_files = {ln["file"] for ln in kept}

    ok = "dot-claude/skills/explain-simply/SKILL.md" not in kept_files \
        and ".claude/agents/reviewer.md" not in kept_files
    print("  {}  a skill or agent definition is withheld from the external judge".format(
        "ok  " if ok else "MISS"))

    ok = "hiring_engine/today.py" in kept_files and "docs/SKILL-notes.md" in kept_files
    rc |= assert_(ok, "ordinary code and prose are still sent (a doc merely NAMING a skill "
          "is not a definition)")

    ok = blinded == 2
    rc |= assert_(ok, "the withheld count is returned, not swallowed ({} of 4)".format(blinded))

    # A SKILL.md is a skill definition wherever it lives. Covering only the
    # skills-directory form would leave a plugin or a vendored pack unfiltered.
    loose, _ = judge_blind([{"file": "plugins/mypack/SKILL.md", "line": 1, "text": "x"}])
    ok = not loose
    rc |= assert_(ok, "a bare SKILL.md outside a skills directory is still withheld")

    # These two guard the fail-closed credential path, which had no coverage at all
    # before 2026-07-27 despite being the only thing standing between a private key
    # and a third-party model.
    planted = [{"file": "src/cfg.ts", "line": 3,
                "text": 'const k = "AKIA' + "A" * 16 + '";'}]
    ok = bool(redactable(planted))
    rc |= assert_(ok, "a credential-shaped literal is detected before anything is sent")

    # Ordering matters: the scan must run over EVERYTHING, before blinding. If it
    # ran after, a key inside a SKILL.md would be filtered out of its own leak check.
    in_skill = [{"file": "dot-claude/skills/x/SKILL.md", "line": 1,
                 "text": 'token = "' + "b" * 40 + '"  # sk-' + "c" * 24}]
    ok = bool(redactable(in_skill))
    rc |= assert_(ok, "a credential inside a skill definition is still scanned "
          "(scan precedes blinding)")

    # screen_for_send and validate_findings were extracted from run_external on
    # 2026-07-27 for one reason: fused to a network call they could not be tested,
    # and mutation testing showed both were completely unguarded.
    key_in_skill = [{"file": "dot-claude/skills/x/SKILL.md", "line": 1,
                     "text": 'AKIA' + "A" * 16}]
    sendable, _, leaks = screen_for_send(key_in_skill)
    rc |= assert_(bool(leaks) and not sendable,
                  "a credential inside a blinded file still stops the send "
                  "(scan precedes blinding, inside the real send path)")

    mixed = [{"file": "src/a.ts", "line": 1, "text": "const x = 1;"},
             {"file": "dot-claude/skills/y/SKILL.md", "line": 1, "text": "# y"}]
    sendable, blinded, leaks = screen_for_send(mixed)
    rc |= assert_(not leaks and blinded == 1
                  and [ln["file"] for ln in sendable] == ["src/a.ts"],
                  "a clean mixed change sends only the code and reports 1 withheld")

    valid = {("src/a.ts", 1)}
    kept, dropped = validate_findings(
        [{"file": "src/a.ts", "line": 1, "severity": "high", "why": "real"},
         {"file": "src/a.ts", "line": 999, "severity": "high", "why": "invented line"},
         {"file": "nope.ts", "line": 1, "severity": "high", "why": "invented file"},
         {"file": "src/a.ts", "line": "NaN", "severity": "high", "why": "unparseable"},
         "not even a dict"],
        valid, "test-model")
    rc |= assert_(len(kept) == 1 and kept[0]["line"] == 1,
                  "only findings citing a line the change added survive")
    rc |= assert_(dropped == 4,
                  "every discarded finding is counted, not silently dropped "
                  "({} of 4)".format(dropped))
    rc |= assert_(kept and kept[0]["severity"] == "high"
                  and validate_findings([{"file": "src/a.ts", "line": 1,
                                          "severity": "bogus"}], valid, "m")[0][0]
                  ["severity"] == MED,
                  "an unknown severity falls back to medium rather than passing through")

    n = build_note("m", 2, 5, "could not assess the css", True, 3)
    rc |= assert_("5 dropped" in n,
                  "the note states how many findings were discarded")
    rc |= assert_("3 skill/agent definition line(s) withheld" in n,
                  "the note states how much was withheld from the judge")
    rc |= assert_("truncated" in n,
                  "the note states when the input was cut short")
    rc |= assert_("  0 skill" not in build_note("m", 1, 0, "", False, 0),
                  "a review that withheld nothing does not claim it withheld zero")

    print("\nVERDICT: {}".format(
        "every planted defect is caught and a clean change passes clean" if rc == 0
        else "panel selftest has failures above"))
    return rc


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="panel.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--project", default=".")
    r.add_argument("--base")
    r.add_argument("--out")
    r.add_argument("--fail-on", choices=("high", "medium", "low"), default="high")
    r.add_argument("--allow-external", action="store_true",
                   help="also send the change to a free OpenRouter model; refuses if the "
                        "change contains credential-shaped content. Trigger-conditioned "
                        "(#372): the leg runs only when an aspect trigger fires; a run "
                        "with no fired trigger skips it and records the skip")
    r.add_argument("--external-model",
                   help="OpenRouter model id to try first, e.g. z-ai/glm-4.7-flash. "
                        "Omitted, the client picks a zero-priced model. A priced id "
                        "here bills; the daily quota counts requests, not dollars")
    r.add_argument("--allow-semantic-cache", action="store_true",
                   help="opt in to the semantic cache tier (token-shape similarity, "
                        "tau 0.95, same persona scope and full conditioning). Off by "
                        "default: a mis-memoized verdict is a hallucinated approval")
    r.add_argument("-v", "--verbose", action="store_true")
    r.set_defaults(fn=cmd_run)
    t = sub.add_parser("selftest")
    t.set_defaults(fn=cmd_selftest)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
