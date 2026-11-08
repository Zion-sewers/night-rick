# -*- coding: utf-8 -*-
"""Structure and reachability oracle for design documents.

Three rules, all mechanical, all cheap:

  R1 STRUCTURE   every doc under docs/specs/, docs/prd/ and docs/standards/
                 declares a status
                 from a fixed vocabulary in its first 20 lines, as YAML
                 frontmatter or a `Status:` line.

  R2 REACHABILITY every doc under docs/analysis/, docs/specs/, docs/prd/ and
                 docs/standards/ is
                 referenced by at least one file that is NOT docs/INDEX.md.

  R3 ROOT LAYOUT  every .md / .mdx / .txt file, and every extensionless
                 file that reads as UTF-8 text without NUL bytes, at the
                 repo root is on the allowlist (README, CLAUDE, CLAUDE-OS,
                 AGENTS, CONTRIBUTING, TODO, REVIEW, LICENSE, CODEOWNERS).
                 Anything else in that set at the root is a stray: it
                 belongs in the subtree matching its kind, and the check
                 fails until it moves. Tracked files only (git ls-files),
                 like R1/R2: an unstaged stray is invisible until `git add`.
                 Other suffixes (.rst, .markdown, .md.bak), dotfiles, empty
                 files and binaries are out of scope for this rule. Known
                 non-document build files (Makefile, Dockerfile,
                 requirements.txt and the like) are exempt by name: they
                 are not documents, and moving one would break the build.

Why R2 excludes the index. `docs/INDEX.md` links every document by construction,
so counting it as a reference makes the rule vacuous. A catalogue entry is not a
consumer. What R2 asks is whether anything that gets READ during work (a rule, a
spec, TODO.md, the spine, a hook, a tool) points at the document.

WHAT THIS DOES NOT MEASURE, stated up front because the gap matters. On
2026-08-03 a hand pass over docs/analysis/ found 7 of 37 documents whose
FINDINGS never reached a mechanism, while most of them were referenced
somewhere. Reachability is a proxy for absorption and it is a weak one: it
catches a document nobody links, and it cannot catch a document that is linked
and ignored. It is worth having because it is the half that a machine can check
on every commit, and the report says so in its own output.

Existing debt is carried in docs/strand-exempt.txt, one path per line with a
reason after `|`. That file is the visible, countable backlog. A new document
that strands fails the check immediately; an old one shows up in the exempt
count, which is meant to be uncomfortable rather than invisible.

Usage:
  python tools/docmap/strand.py check      # exit 1 on any violation
  python tools/docmap/strand.py report     # the table, always exit 0
  python tools/docmap/strand.py selftest   # prove both rules can fire
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GOVERNED = ("docs/analysis/", "docs/specs/", "docs/prd/", "docs/standards/")
STRUCTURED = ("docs/specs/", "docs/prd/", "docs/standards/")
INDEX_PATH = "docs/INDEX.md"
EXEMPT_PATH = "docs/strand-exempt.txt"
# R3 ROOT LAYOUT. A document at the repo root is an entry point, not a pile.
# The root holds the canonical entry points only (ROOT_ALLOWED); anything else
# in the enforced set is a stray that belongs in the subtree matching its
# kind. Measured 2026-11-07: nine doc files and one extensionless note landed
# at the root between 2026-08-31 and 2026-10-15, months after #92 filed the
# same complaint, because no check failed when they landed. They now live in
# docs/archive/root-pile-2026-11-07/, whose README.md is the "where things
# live" note; docs/INDEX.md links it, and the violation strings below point
# there (a stable pointer, not the dated archive path). An extensionless file
# counts as a document here when it reads as UTF-8 text without NUL bytes:
# the one that proved the rule (gem07-10, a Gemini research note with no
# suffix) would otherwise slip past a suffix-only check. The allowlist IS the
# exemption mechanism, by design: a future legitimate root document lands by
# editing this checker, which is itself gated, so the exemption cannot be
# gamed from the tree. The same list appears in prose in the archive manifest
# and on the INDEX.md line; this frozenset is the enforcing copy.
ROOT_ALLOWED = frozenset({
    "README.md", "CLAUDE.md", "CLAUDE-OS.md", "AGENTS.md", "CONTRIBUTING.md",
    "TODO.md", "REVIEW.md", "LICENSE", "CODEOWNERS",
})
ROOT_DOC_SUFFIXES = (".md", ".mdx", ".txt")
# Known non-document files that conventionally live at a repo root. A Makefile
# or Dockerfile reads as UTF-8 text, so without this set the extensionless and
# .txt branches below would flag them and the violation message would tell the
# operator to move a build file into a docs subtree. Measured 2026-11-07:
# Makefile, Dockerfile and requirements.txt all fired before this exemption.
# The set is closed and named here, not inferred: a new build file lands by
# editing this checker, which is itself gated. Documents stay on ROOT_ALLOWED.
ROOT_NON_DOCUMENT = frozenset({
    "Makefile", "Dockerfile", "Containerfile", "Jenkinsfile", "Vagrantfile",
    "Brewfile", "Procfile", "Earthfile", "Justfile", "Gemfile", "Rakefile",
    "requirements.txt", "CMakeLists.txt",
})
# A bookkeeping surface is never a consumer. Three instances of one rule, all found by
# the rule failing to fire:
#   INDEX_PATH        links every document by construction
#   EXEMPT_PATH       lists precisely the documents it excuses, so an exemption would
#                     clear the violation it was written for
#   DOCMAP / CODEBASE-MAP  are GENERATED inventories. DOCMAP.md carries 990 rows naming
#                     nearly every document in the repo, which made R2 largely vacuous
#                     from the day it shipped. The "0 stranded across 59 governed
#                     documents" reported 2026-08-04 was that, not a clean result.
NOT_A_CONSUMER = frozenset({
    INDEX_PATH,
    EXEMPT_PATH,
    "docs/DOCMAP.md",
    "docs/CODEBASE-MAP.md",
})

# The fourth instance of the same rule, and the first one whose paths cannot be listed
# by name: `state/reviews/<sha>.json` is written by panel.py per commit, and it names
# every file the diff added. So the act of committing a document makes a review
# artifact "reference" it, one new artifact per commit, forever.
#
# Found 2026-08-05 by `strand.py check` reporting 10 violations of the form "is exempt
# and is now referenced. Remove the exemption." on a clean tree. The 10 documents are
# imported research references with no consumer at all; the only thing naming them
# outside the bookkeeping surfaces above was
# state/reviews/bca1d6942e6075ce4d89bf6b9a07b397c14f616c.json. Removing the exemptions
# as the message instructs would have recorded 10 genuinely stranded documents as
# reached, which is the opposite of what this oracle is for.
NOT_A_CONSUMER_PREFIXES = ("state/reviews/",)


def _is_consumer(ref: str) -> bool:
    """A bookkeeping surface is never a consumer, whether it is named or prefixed."""
    return ref not in NOT_A_CONSUMER and not ref.startswith(NOT_A_CONSUMER_PREFIXES)

# The declared vocabulary. A status outside this set is a violation, because a
# scheme that grows silently is how the unified PRD ended up declaring five
# verdicts and using eight.
STATUS_VOCAB = {
    "active", "proposed", "design", "draft", "living", "measurement",
    "superseded", "parked", "done", "approved", "point-in-time", "reference",
    # Nygard's ADR vocabulary. Every file in docs/adr/ uses `accepted`, and rejecting it
    # was this oracle checking its own ruled form rather than the property the rule
    # protects. Third instance of that on 2026-08-05, after `superseded by <target>` and
    # `<status> for <purpose>`; all three are pinned by tests.
    "accepted", "rejected", "deprecated",
}

FRONTMATTER_STATUS = re.compile(r"^status\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
BODY_STATUS = re.compile(r"^[-*\s]*\**status\**\s*[:=]\s*(.+)$", re.IGNORECASE | re.MULTILINE)

SEARCHABLE_SUFFIXES = {".md", ".py", ".sh", ".ps1", ".yml", ".yaml", ".json", ".txt", ".toml"}


def tracked(project: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(project), "ls-files"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return []
    return [line for line in out.stdout.splitlines() if line]


def governed_docs(paths: list[str]) -> list[str]:
    return sorted(p for p in paths
                  if p.endswith(".md") and p.startswith(GOVERNED))


def read_exempt(project: Path) -> dict[str, str]:
    f = project / EXEMPT_PATH
    if not f.exists():
        return {}
    out = {}
    for line in f.read_text(encoding="utf8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path, _, reason = line.partition("|")
        out[path.strip()] = reason.strip()
    return out


def declared_status(text: str) -> str | None:
    """Frontmatter first, then the first 20 lines of body."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            m = FRONTMATTER_STATUS.search(text[3:end])
            if m:
                return _normalise(m.group(1).strip().strip("`*"))
    head = "\n".join(text.splitlines()[:20])
    m = BODY_STATUS.search(head)
    if m:
        # take the first word-ish token; "DESIGN, 2026-08-03. Nothing here..."
        raw = m.group(1).strip().strip("`*")
        return _normalise(raw)
    return None


def _normalise(raw: str) -> str | None:
    """First token, with two forms the corpus actually uses folded in.

    `superseded by <target>` is a declared status carrying its target, and
    `<status> for <purpose>` is a declared status carrying its scope. Splitting
    on the first delimiter alone would report both as unknown statuses, which
    would be the oracle checking its own ruled form rather than the property
    the rule protects (L-2026-07-31-b).
    """
    token = re.split(r"[,.;(]| - ", raw, 1)[0].strip().lower()
    if token.startswith("superseded by"):
        return "superseded"
    head = token.split(" for ", 1)[0].strip()
    if head in STATUS_VOCAB:
        return head
    return token or None


def build_reference_index(project: Path, paths: list[str]) -> dict[str, set[str]]:
    """basename -> set of files that mention it, excluding the file itself."""
    hits: dict[str, set[str]] = {}
    corpus = []
    for p in paths:
        if Path(p).suffix.lower() not in SEARCHABLE_SUFFIXES:
            continue
        fp = project / p
        try:
            corpus.append((p, fp.read_text(encoding="utf8", errors="ignore")))
        except OSError:
            continue
    for doc in governed_docs(paths):
        base = Path(doc).name
        stem = Path(doc).stem
        found = set()
        for p, text in corpus:
            if p == doc:
                continue
            if base in text or doc in text or ("[[" + stem + "]]") in text:
                found.add(p)
        hits[doc] = found
    return hits


def _is_text_file(project: Path, path: str) -> bool:
    """True when an extensionless root file reads as UTF-8 text without NULs."""
    try:
        raw = (project / path).read_bytes()
    except OSError:
        return False
    if not raw or b"\x00" in raw:
        return False
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def root_layout_violations(project: Path, paths: list[str]) -> list[str]:
    """R3: every document-like file at the repo root is on the allowlist."""
    out = []
    for p in sorted(paths):
        if "/" in p:
            continue
        name = Path(p).name
        if name in ROOT_ALLOWED:
            continue
        # Dotfiles are machine config (.gitignore, .gitattributes), not piled
        # documents. R3 governs what an operator drops at the root, not what
        # the tooling needs there.
        if name.startswith("."):
            continue
        # Known non-document build files are not documents; flagging one
        # would misdirect the operator into moving a build file.
        if name in ROOT_NON_DOCUMENT:
            continue
        suffix = Path(p).suffix.lower()
        if suffix in ROOT_DOC_SUFFIXES:
            out.append("{}: document at the repo root and not on the R3 allowlist. "
                       "Move it to the subtree matching its kind; see docs/INDEX.md "
                       "for where things live.".format(p))
        elif not suffix and _is_text_file(project, p):
            out.append("{}: extensionless text file at the repo root and not on the "
                       "R3 allowlist. Move it to the subtree matching its kind; see "
                       "docs/INDEX.md for where things live.".format(p))
    return out


def evaluate(project: Path) -> dict:
    paths = tracked(project)
    docs = governed_docs(paths)
    exempt = read_exempt(project)
    refs = build_reference_index(project, paths)
    root = root_layout_violations(project, paths)

    rows = []
    for doc in docs:
        try:
            text = (project / doc).read_text(encoding="utf8", errors="ignore")
        except OSError:
            text = ""
        status = declared_status(text)
        needs_status = doc.startswith(STRUCTURED)
        bad_status = None
        if needs_status:
            if status is None:
                bad_status = "no status declared"
            elif status not in STATUS_VOCAB:
                bad_status = "status '{}' is outside the declared vocabulary".format(status)

        # NOT_A_CONSUMER: surfaces that mention a document as bookkeeping rather than as
        # readers of it. INDEX_PATH links everything by construction; EXEMPT_PATH lists
        # precisely the documents it excuses. Counting either makes the rule vacuous, and
        # counting EXEMPT_PATH makes it self-satisfying: adding an exemption would mark the
        # document as referenced and clear the very violation the exemption was written for.
        consumers = sorted(r for r in refs.get(doc, ()) if _is_consumer(r))
        indexed = INDEX_PATH in refs.get(doc, ())
        stranded = not consumers

        rows.append({
            "path": doc,
            "status": status or "",
            "bad_status": bad_status,
            "consumers": len(consumers),
            "indexed": indexed,
            "stranded": stranded,
            "exempt": doc in exempt,
            "exempt_reason": exempt.get(doc, ""),
        })
    return {"rows": rows, "exempt": exempt, "root": root}


def problems(state: dict) -> list[str]:
    out = []
    out.extend(state.get("root", []))
    for r in state["rows"]:
        if r["bad_status"]:
            out.append("{}: {}. Declare one of: {}".format(
                r["path"], r["bad_status"], ", ".join(sorted(STATUS_VOCAB))))
        if r["stranded"] and not r["exempt"]:
            out.append("{}: nothing outside {} references it. Either link it from a "
                       "surface that gets read, or add it to {} with a reason.".format(
                           r["path"], INDEX_PATH, EXEMPT_PATH))
    # an exempt entry for a document that is now wired is stale bookkeeping
    wired = {r["path"] for r in state["rows"] if not r["stranded"]}
    for path in state["exempt"]:
        if path in wired:
            out.append("{} is exempt in {} and is now referenced. Remove the "
                       "exemption.".format(path, EXEMPT_PATH))
        elif path not in {r["path"] for r in state["rows"]}:
            out.append("{} is exempt in {} and is not a governed document.".format(
                path, EXEMPT_PATH))
    return out


def report(state: dict) -> str:
    rows = state["rows"]
    lines = []
    lines.append("{:<62} {:<14} {:>5}  {}".format("document", "status", "refs", "verdict"))
    for r in sorted(rows, key=lambda x: (not x["stranded"], x["path"])):
        if r["bad_status"]:
            verdict = "STRUCTURE: " + r["bad_status"]
        elif r["stranded"] and r["exempt"]:
            verdict = "stranded, EXEMPT: " + (r["exempt_reason"] or "no reason given")
        elif r["stranded"]:
            verdict = "STRANDED"
        else:
            verdict = "wired"
        lines.append("{:<62} {:<14} {:>5}  {}".format(
            r["path"][:62], r["status"][:14], r["consumers"], verdict))
    n = len(rows)
    stranded = sum(1 for r in rows if r["stranded"])
    ex = sum(1 for r in rows if r["stranded"] and r["exempt"])
    lines.append("")
    lines.append("{} governed documents, {} stranded ({} exempt, {} blocking)".format(
        n, stranded, ex, stranded - ex))
    root = state.get("root", [])
    lines.append("Root layout (R3): {} violation(s)".format(len(root)))
    for v in root:
        lines.append("  " + v)
    lines.append("Reachability is a PROXY for absorption. It catches a document nobody "
                 "links. It cannot catch a document that is linked and ignored.")
    return "\n".join(lines)


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf8")


def selftest(_project: Path) -> int:
    """All three rules must be able to fire, and all must be able to stay silent."""
    failures = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)

        # a spec with a good status, referenced from a rule -> clean
        _write(root / "docs/specs/good.md", "---\nstatus: active\n---\n\n# Good\n")
        _write(root / "docs/rules.md", "See docs/specs/good.md for the design.\n")
        # a spec with no status, referenced -> STRUCTURE violation only
        _write(root / "docs/specs/nostatus.md", "# No status here\n")
        _write(root / "docs/notes.md", "nostatus.md is mentioned here\n")
        # an analysis nobody links except the index -> STRANDED
        _write(root / "docs/analysis/lonely.md", "# Lonely\n")
        _write(root / INDEX_PATH, "- [analysis/lonely.md](analysis/lonely.md)\n"
                                  "- [specs/good.md](specs/good.md)\n")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                       capture_output=True)

        state = evaluate(root)
        probs = problems(state)
        joined = "\n".join(probs)

        if "nostatus.md" not in joined:
            failures.append("R1 did not fire on a spec with no status")
        if "lonely.md" not in joined:
            failures.append("R2 did not fire on a document only the index links")
        if "good.md" in joined:
            failures.append("a clean document was reported as a violation")

        # a stranded doc that is exempt must NOT be a problem
        _write(root / EXEMPT_PATH, "docs/analysis/lonely.md | grandfathered by selftest\n")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                       capture_output=True)
        probs2 = problems(evaluate(root))
        if any("lonely.md: nothing outside" in p for p in probs2):
            failures.append("an exempt stranded document still blocked")

        # an exemption for a wired document must be reported as stale
        _write(root / EXEMPT_PATH, "docs/specs/good.md | stale exemption\n")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                       capture_output=True)
        probs3 = problems(evaluate(root))
        if not any("Remove the exemption" in p for p in probs3):
            failures.append("a stale exemption for a wired document was not reported")

        # A generated review artifact is not a consumer. panel.py writes
        # state/reviews/<sha>.json naming every file a diff added, so without the
        # prefix exclusion the act of committing a document marks it reached, one new
        # artifact per commit, forever. Measured 2026-08-05: this fired as 10 false
        # "Remove the exemption" violations on a clean tree, and obeying them would
        # have recorded 10 genuinely stranded documents as reached.
        _write(root / EXEMPT_PATH, "docs/analysis/lonely.md | grandfathered by selftest\n")
        _write(root / "state/reviews/deadbeef.json",
               '{"added": ["docs/analysis/lonely.md"]}\n')
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                       capture_output=True)
        probs4 = problems(evaluate(root))
        if any("lonely.md" in p and "Remove the exemption" in p for p in probs4):
            failures.append("a generated review artifact counted as a consumer, so "
                            "committing a document marks it reached")

        # R3 ROOT LAYOUT. A stray document at the root must fire; an allowlisted
        # entry point, LICENSE, and a binary file must stay silent. The rule that
        # caught the 2026-11-07 pile is suffix-based plus extensionless-text, so
        # both halves need a firing case and a silence case.
        _write(root / "stray-note.md", "# Stray\n")
        _write(root / "stray-note.mdx", "# Stray\n")
        _write(root / "TODO.md", "# Roadmap\n")
        _write(root / "LICENSE", "MIT License\n")
        _write(root / "gem-note", "a research note with no suffix\n")
        (root / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0not text")
        (root / "gem-blob").write_bytes(b"\xff\xd8\xff\xe0not text")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                       capture_output=True)
        probs5 = problems(evaluate(root))
        joined5 = "\n".join(probs5)
        if "stray-note.md" not in joined5:
            failures.append("R3 did not fire on a stray .md at the repo root")
        if "stray-note.mdx" not in joined5:
            failures.append("R3 did not fire on a stray .mdx at the repo root")
        if "gem-note" not in joined5:
            failures.append("R3 did not fire on an extensionless text file at the root")
        if "TODO.md" in joined5 or "LICENSE" in joined5:
            failures.append("R3 fired on an allowlisted root file")
        if "photo.jpg" in joined5 or "gem-blob" in joined5:
            failures.append("R3 fired on a binary file at the root")

    if failures:
        for f in failures:
            print("selftest FAIL: " + f)
        return 1
    print("strand selftest: 12 assertions, all held")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["check", "report", "selftest"])
    ap.add_argument("--project", default=".")
    args = ap.parse_args()
    project = Path(args.project).resolve()

    if args.command == "selftest":
        return selftest(project)

    state = evaluate(project)
    if args.command == "report":
        print(report(state))
        return 0

    probs = problems(state)
    if probs:
        for p in probs:
            print("strand: " + p)
        print("")
        print("{} violation(s).".format(len(probs)))
        return 1
    rows = state["rows"]
    ex = sum(1 for r in rows if r["stranded"] and r["exempt"])
    print("strand clean: {} governed documents, {} structured, {} carried as "
          "exempt debt in {}; root layout clean (R3)".format(
              len(rows), sum(1 for r in rows if r["path"].startswith(STRUCTURED)),
              ex, EXEMPT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
