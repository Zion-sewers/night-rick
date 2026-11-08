#!/usr/bin/env python3
"""Report duplication on changed lines, with a ratchet on new code.

WHY THIS EXISTS

night-rick#376 (Perplexity corpus, DRY/AHA/WET balance): duplication used to
be reported, when it was reported at all, as a repo-wide legacy debt dump.
That shape punishes the author for debt they did not create and teaches
everyone to ignore the report. This checker inverts the default: it looks
only at lines the diff ADDS, and the number that matters is the count of
added lines that repeat an added block elsewhere. Legacy debt is measured
separately (`report`) and never blocks.

THE RATCHET

`state/dup-ratchet.json` holds one number, the baseline (0 at ship), plus a
reason, an expiry date, and an owner. `check` fails when duplicated added
lines exceed the baseline. Two properties make the ratchet real rather than
a self-serve knob. First, the baseline is judged as it stood at the base
ref: a raise inside the very diff it would silence does not take effect
until that raise merges, so a PR must land the raise first and the
duplication second. Second, a raise above 0 needs a non-empty reason, a
future expiry date, and an owner, and `check` fails once the expiry passes
until the baseline is lowered or re-justified. The file is in the diff, so
every raise is visible to panel review instead of silent. Lowering is the
documented happy path: when a PR's count drops below the baseline, the
author may lower the baseline to the new count in the same PR.

WHAT COUNTS AS A DUPLICATE

An exact repeat, not a similarity score. After normalization (blank lines
dropped, full-line comments dropped, import lines and bare docstring fences
dropped, whitespace collapsed), a run of 6 consecutive added lines that
appears at 2 or more locations is a duplicate block. Same-looking code that
is not textually identical does NOT fire: same-looking code may encode
different concepts, and abstracting it is a judgement call this tool
refuses to make for the author. Similar-but-not-identical matches are out
of scope by design: no shared-meaning justification is collected or
checked, and the "abstraction needs a shared-meaning justification" line
on each reported group is a reminder, not a gate. The threshold (6) was
calibrated against real merged diffs (see
docs/specs/2026-11-08-dup-ratchet.md): N=6 fires on the repo's copy-pasted
corpus-profile blocks and stays silent on clean code diffs.

THE EXTRACTION GATE

Cross-module extraction requires regression tests first. When the diff
removes a repeated 6-line block AND the same block appears as added lines
in a different file (the code moved to a shared home), the extraction is
exempt only when a test file in the diff has added lines referencing the
destination module (its stem, e.g. `shared` for `tools/a/shared.py`).
A test file that never names the extracted module does not exempt; neither
does a test that asserts nothing about it. A reference is necessary, not
sufficient, for characterization: the gate is a floor, not a proof that the
test is good.

WHAT THIS DOES NOT DO

It never suggests an extraction and never rewrites code. Test files are
excluded from the ratchet FAIL (fixture repetition is characterized by the
test itself) but are listed in the report, so the exclusion is visible, not
silent. A block appearing once in production code and once in a test file
is reported as a cross-copy, also informationally.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict

WINDOW = 6
BASELINE_PATH = "state/dup-ratchet.json"

CODE_EXTS = frozenset(
    [".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
     ".swift", ".rb", ".php", ".cs", ".sql", ".sh", ".ps1"]
)

OUT_OF_SCOPE_PREFIXES = (
    "dot-codex/skills/.system/",
    "research-papers/",
    "work-docs/audits/",
)

LINE_COMMENT = (
    (".py", "#"),
    (".ts", "//"), (".tsx", "//"), (".js", "//"), (".jsx", "//"),
    (".go", "//"), (".rs", "//"), (".java", "//"), (".kt", "//"),
    (".swift", "//"), (".rb", "#"), (".php", "//"), (".cs", "//"),
    (".sql", "--"), (".sh", "#"), (".ps1", "#"),
)


class Baseline(TypedDict):
    baseline: int
    reason: str
    expires: str
    owner: str


class Location(TypedDict):
    path: str
    start_line: int
    end_line: int


class Block(TypedDict):
    path: str
    start_line: int
    end_line: int
    lines: int
    sample: str
    locations: list[Location]


class ExtractionHit(TypedDict):
    sources: list[Location]
    dest: Location
    sample: str


class CheckResult(TypedDict):
    added_lines: int
    duplicated_lines: int
    baseline: int
    baseline_errors: list[str]
    blocks: list[Block]
    test_blocks: list[Block]
    test_duplicated_lines: int
    cross_blocks: list[Block]
    extraction: list[ExtractionHit]
    changed_files: list[str]


class BaselineError(ValueError):
    """The baseline file is unreadable or malformed."""


def is_code(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in CODE_EXTS and not path.startswith(OUT_OF_SCOPE_PREFIXES)


def is_test_file(path: str) -> bool:
    name = Path(path).name
    return (
        path.startswith("tests/")
        or name == "test.py"
        or name.startswith("test_")
        or "_test." in name
        or ".test." in name
    )


def normalize(line: str, path: str) -> str | None:
    s = line.strip()
    if not s:
        return None
    ext = Path(path).suffix.lower()
    for suffix, marker in LINE_COMMENT:
        if ext == suffix and s.startswith(marker):
            return None
    if s in ('"""', "'''"):
        return None
    if re.match(r"^(import\s|from\s+\S+\s+import\s)", s):
        return None
    return re.sub(r"\s+", " ", s)


def git(project: Path, args: str) -> str:
    r = subprocess.run(
        ["git"] + args.split(), cwd=project, capture_output=True, text=True
    )
    return r.stdout


def default_base(project: Path) -> str:
    # Mirrors gate.py default_base (same candidate order, same HEAD~1
    # fallback). A shared home for the three copies (gate.py, panel.py,
    # here) is a follow-up; see docs/specs/2026-11-08-dup-ratchet.md.
    for cand in ("origin/main", "origin/master", "main", "master"):
        if git(project, f"rev-parse --verify --quiet {cand}").strip():
            return cand
    return "HEAD~1"


def parse_added(diff: str) -> dict[str, list[tuple[str, int]]]:
    """Added normalized lines per file: {path: [(text, new_lineno)]}."""
    added: dict[str, list[tuple[str, int]]] = defaultdict(list)
    path: str | None = None
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
            lineno = 0
        elif raw.startswith("+++ "):
            path = None
        elif raw.startswith("@@ ") and path is not None:
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
        elif path is not None and raw.startswith(" "):
            lineno += 1
        elif path is not None and raw.startswith("+") and not raw.startswith("+++"):
            if is_code(path):
                norm = normalize(raw[1:], path)
                if norm is not None:
                    added[path].append((norm, lineno))
            lineno += 1
    return added


def parse_removed(diff: str) -> dict[str, list[tuple[str, int]]]:
    """Removed normalized lines per file: {path: [(text, old_lineno)]}."""
    removed: dict[str, list[tuple[str, int]]] = defaultdict(list)
    path: str | None = None
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("--- a/"):
            path = raw[6:]
            lineno = 0
        elif raw.startswith("--- "):
            path = None
        elif raw.startswith("@@ ") and path is not None:
            m = re.search(r"-(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
        elif path is not None and raw.startswith(" "):
            lineno += 1
        elif path is not None and raw.startswith("-") and not raw.startswith("---"):
            if is_code(path):
                norm = normalize(raw[1:], path)
                if norm is not None:
                    removed[path].append((norm, lineno))
            lineno += 1
    return removed


def changed_files(diff: str) -> list[str]:
    files: set[str] = set()
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            files.add(raw[6:])
    return sorted(files)


def find_blocks(
    streams: dict[str, list[tuple[str, int]]],
) -> tuple[list[Block], int]:
    """Group duplicate windows into maximal blocks; count distinct dup lines.

    The count is the set of distinct added lines inside any duplicate
    window beyond the first occurrence, so a 12-line repeat counts 12
    lines in one block, not 7 overlapping windows. Reporting groups
    windows into maximal families: a family is a maximal run of consecutive
    windows whose location set shifts with the window. Every location of
    every family is reported, first occurrence included.
    """
    windows: dict[tuple[str, ...], list[tuple[str, int]]] = defaultdict(list)
    for path, lines in streams.items():
        for i in range(len(lines) - WINDOW + 1):
            windows[tuple(t for t, _ in lines[i:i + WINDOW])].append((path, i))
    marked: set[tuple[str, int]] = set()
    for locs in windows.values():
        if len(locs) < 2:
            continue
        for path, i in locs[1:]:
            for j in range(i, i + WINDOW):
                marked.add((path, j))
    blocks: list[Block] = []
    seen: set[tuple[tuple[tuple[str, int], ...], int]] = set()
    for path, lines in streams.items():
        i = 0
        while i <= len(lines) - WINDOW:
            key = tuple(t for t, _ in lines[i:i + WINDOW])
            locs = windows.get(key, [])
            if len(locs) < 2:
                i += 1
                continue
            if i > 0:
                prev = tuple(t for t, _ in lines[i - 1:i - 1 + WINDOW])
                prev_locs = windows.get(prev, [])
                shifted = sorted((p, idx + 1) for p, idx in prev_locs)
                if len(prev_locs) >= 2 and sorted(locs) == shifted:
                    i += 1
                    continue
            j = i
            run_locs = locs
            while j + 1 <= len(lines) - WINDOW:
                nxt = tuple(t for t, _ in lines[j + 1:j + 1 + WINDOW])
                nxt_locs = windows.get(nxt, [])
                shifted = sorted((p, idx + 1) for p, idx in run_locs)
                if len(nxt_locs) >= 2 and sorted(nxt_locs) == shifted:
                    j += 1
                    run_locs = nxt_locs
                else:
                    break
            span = j - i + WINDOW
            family_key = (tuple(sorted(locs)), span)
            if family_key in seen:
                i = j + 1
                continue
            seen.add(family_key)
            locations: list[Location] = []
            for p, idx in locs:
                plines = streams[p]
                locations.append({
                    "path": p,
                    "start_line": plines[idx][1],
                    "end_line": plines[idx + span - 1][1],
                })
            blocks.append({
                "path": path,
                "start_line": lines[i][1],
                "end_line": lines[j + WINDOW - 1][1],
                "lines": span,
                "sample": lines[i][0][:100],
                "locations": sorted(
                    locations, key=lambda loc: (loc["path"], loc["start_line"])),
            })
            i = j + 1
    return blocks, len(marked)


def _references_dest(test_lines: list[str], dest: str) -> bool:
    """Does any added test line name the destination module?"""
    stem = Path(dest).stem
    return any(stem in line for line in test_lines)


def find_extractions(
    added: dict[str, list[tuple[str, int]]],
    removed: dict[str, list[tuple[str, int]]],
    test_lines: list[str],
) -> list[ExtractionHit]:
    """Removed repeated block reappearing as added lines in another file.

    A hit is exempt only when an added test line references the
    destination module. A test file that never names the extracted module
    does not exempt, however it is named.
    """
    removed_windows: dict[tuple[str, ...], set[str]] = defaultdict(set)
    removed_counts: Counter[tuple[str, ...]] = Counter()
    for path, lines in removed.items():
        for i in range(len(lines) - WINDOW + 1):
            window = tuple(t for t, _ in lines[i:i + WINDOW])
            removed_windows[window].add(path)
            removed_counts[window] += 1
    added_windows: dict[tuple[str, ...], list[tuple[str, int]]] = defaultdict(list)
    for path, lines in added.items():
        for i in range(len(lines) - WINDOW + 1):
            added_windows[tuple(t for t, _ in lines[i:i + WINDOW])].append((path, i))
    merged: dict[tuple[tuple[str, ...], str], ExtractionHit] = {}
    for window, rpaths in removed_windows.items():
        # A removed block counts as repeated when it occurs 2+ times among
        # removed lines: same window seen from 2 files, or twice in one file.
        if removed_counts[window] < 2:
            continue
        for apath, aidx in added_windows.get(window, []):
            if apath in rpaths:
                continue
            if _references_dest(test_lines, apath):
                continue
            sources: list[Location] = [
                {
                    "path": rpath,
                    "start_line": removed[rpath][i][1],
                    "end_line": removed[rpath][i + WINDOW - 1][1],
                }
                for rpath in sorted(rpaths)
                for i in range(len(removed[rpath]) - WINDOW + 1)
                if tuple(t for t, _ in removed[rpath][i:i + WINDOW]) == window
            ]
            alines = added[apath]
            dest: Location = {
                "path": apath,
                "start_line": alines[aidx][1],
                "end_line": alines[aidx + WINDOW - 1][1],
            }
            key = (tuple(sorted(rpaths)), apath)
            hit = merged.get(key)
            if hit is None:
                merged[key] = {
                    "sources": sources,
                    "dest": dest,
                    "sample": window[0][:100],
                }
            else:
                hit["dest"]["end_line"] = max(
                    hit["dest"]["end_line"], dest["end_line"])
    return sorted(merged.values(),
                  key=lambda h: (h["dest"]["path"], h["dest"]["start_line"]))


def _parse_baseline(data: object) -> Baseline:
    if not isinstance(data, dict):
        raise BaselineError("baseline is not a JSON object")
    baseline = data.get("baseline", 0)
    if not isinstance(baseline, int) or isinstance(baseline, bool) or baseline < 0:
        raise BaselineError("baseline is not a non-negative integer")
    return {
        "baseline": baseline,
        "reason": str(data.get("reason", "")),
        "expires": str(data.get("expires", "")),
        "owner": str(data.get("owner", "")),
    }


def load_baseline(project: Path) -> Baseline:
    p = project / BASELINE_PATH
    if not p.exists():
        return {"baseline": 0, "reason": "", "expires": "", "owner": ""}
    try:
        return _parse_baseline(json.loads(p.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        raise BaselineError(f"baseline unreadable: {exc}")


def load_baseline_at_ref(project: Path, ref: str) -> Baseline:
    out = git(project, f"show {ref}:{BASELINE_PATH}")
    if not out.strip():
        return {"baseline": 0, "reason": "", "expires": "", "owner": ""}
    try:
        return _parse_baseline(json.loads(out))
    except ValueError as exc:
        raise BaselineError(f"baseline at {ref} unreadable: {exc}")


def validate_baseline(rec: Baseline, today: date) -> list[str]:
    errors: list[str] = []
    if rec["baseline"] <= 0:
        return errors
    if not rec["reason"].strip():
        errors.append("baseline raised without a recorded reason in "
                      f"{BASELINE_PATH}")
    try:
        expires = date.fromisoformat(rec["expires"])
    except ValueError:
        errors.append(f"baseline expires {rec['expires']!r} is not an ISO date")
        return errors
    if expires < today:
        errors.append(f"baseline expired on {expires.isoformat()}: lower it "
                      "or re-justify with a new expiry")
    if not rec["owner"].strip():
        errors.append("baseline raised without a recorded owner in "
                      f"{BASELINE_PATH}")
    return errors


def evaluate(project: Path) -> CheckResult:
    base = default_base(project)
    diffs = [git(project, f"diff -U0 {base}...HEAD"), git(project, "diff -U0 HEAD")]
    added: dict[str, list[tuple[str, int]]] = defaultdict(list)
    removed: dict[str, list[tuple[str, int]]] = defaultdict(list)
    files: set[str] = set()
    for diff in diffs:
        for path, lines in parse_added(diff).items():
            seen = {(t, n) for t, n in added[path]}
            added[path].extend([(t, n) for t, n in lines if (t, n) not in seen])
        for path, rlines in parse_removed(diff).items():
            seen_r = {(t, n) for t, n in removed[path]}
            removed[path].extend([(t, n) for t, n in rlines if (t, n) not in seen_r])
        files.update(changed_files(diff))
    blocks, dup = find_blocks(
        {p: lines for p, lines in added.items() if not is_test_file(p)})
    test_blocks, test_dup = find_blocks(
        {p: lines for p, lines in added.items() if is_test_file(p)})
    combined, _ = find_blocks(added)
    cross = [b for b in combined
             if any(is_test_file(loc["path"]) for loc in b["locations"])
             and any(not is_test_file(loc["path"]) for loc in b["locations"])]
    test_lines = [t for p, lines in added.items() if is_test_file(p)
                  for t, _ in lines]
    extraction = find_extractions(added, removed, test_lines)
    today = date.today()
    errors: list[str] = []
    try:
        new_baseline = load_baseline(project)
    except BaselineError as exc:
        errors.append(str(exc))
        new_baseline = {"baseline": 0, "reason": "", "expires": "", "owner": ""}
    if BASELINE_PATH in files:
        # The ratchet judges against the baseline as it stood at the base
        # ref. A raise inside this diff takes effect only after it merges.
        try:
            effective = load_baseline_at_ref(project, base)
        except BaselineError as exc:
            errors.append(str(exc))
            effective = new_baseline
        errors.extend(validate_baseline(new_baseline, today))
    else:
        effective = new_baseline
    errors.extend(validate_baseline(effective, today))
    return {
        "added_lines": sum(len(v) for v in added.values()),
        "duplicated_lines": dup,
        "baseline": effective["baseline"],
        "baseline_errors": errors,
        "blocks": blocks,
        "test_blocks": test_blocks,
        "test_duplicated_lines": test_dup,
        "cross_blocks": cross,
        "extraction": extraction,
        "changed_files": sorted(files),
    }


def _fmt_locations(locations: list[Location]) -> str:
    return ", ".join(
        f"{loc['path']}:{loc['start_line']}-{loc['end_line']}"
        for loc in locations)


def _print_blocks(heading: str, blocks: list[Block]) -> None:
    if not blocks:
        return
    print(f"\n{heading}")
    for b in blocks[:10]:
        print(f"  {b['path']}:{b['start_line']}-{b['end_line']} "
              f"({b['lines']} lines): {b['sample']}")
        print(f"    copies: {_fmt_locations(b['locations'])}")


def cmd_check(a: argparse.Namespace) -> int:
    project = Path(a.project).resolve()
    result = evaluate(project)
    print(f"added code lines: {result['added_lines']}")
    print(f"duplicated added lines: {result['duplicated_lines']} "
          f"(baseline: {result['baseline']})")
    _print_blocks("DUPLICATE BLOCKS (abstraction needs a shared-meaning "
                  "justification):", result["blocks"])
    _print_blocks("TEST-FILE DUPLICATION (informational, not ratcheted):",
                  result["test_blocks"])
    _print_blocks("CROSS-COPIES, production code and test file "
                  "(informational, not ratcheted):", result["cross_blocks"])
    if result["extraction"]:
        print("\nEXTRACTION WITHOUT REGRESSION TESTS:")
        for hit in result["extraction"]:
            print(f"  {_fmt_locations(hit['sources'])} -> "
                  f"{hit['dest']['path']}:{hit['dest']['start_line']}-"
                  f"{hit['dest']['end_line']}: {hit['sample']}")
    failures: list[str] = list(result["baseline_errors"])
    if result["duplicated_lines"] > result["baseline"]:
        failures.append(
            f"duplicated added lines {result['duplicated_lines']} exceed "
            f"baseline {result['baseline']}")
    if result["extraction"]:
        failures.append("extraction without regression tests in the diff")
    if result["added_lines"] == 0 and not failures:
        print("\nVERDICT: PASS (no added code lines to ratchet)")
        return 0
    if failures:
        print("\nVERDICT: FAIL")
        for f in failures:
            print(f"  [FAIL] {f}")
        if result["duplicated_lines"] > result["baseline"]:
            print("  fix: deduplicate the listed blocks, or raise the "
                  f"baseline in {BASELINE_PATH} with a recorded reason, "
                  "expiry and owner (a raise takes effect for later diffs, "
                  "not this one). See "
                  "docs/specs/2026-11-08-dup-ratchet.md")
        if result["extraction"]:
            print("  fix: add a regression test in the diff that references "
                  "the extracted module (import it and assert on its "
                  "behavior). See docs/specs/2026-11-08-dup-ratchet.md")
        return 1
    if result["duplicated_lines"] < result["baseline"]:
        print(f"\n  note: duplicated lines are below baseline; the baseline "
              f"can be lowered to {result['duplicated_lines']} in a "
              "follow-up with reason 'lowered after dedup'")
    print("\nVERDICT: PASS")
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    """Repo-wide legacy duplication count. Informational only, never fails."""
    project = Path(a.project).resolve()
    streams: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for raw in git(project, "ls-files").splitlines():
        path = raw.strip()
        if not path or not is_code(path):
            continue
        p = project / path
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            norm = normalize(line, path)
            if norm is not None:
                streams[path].append((norm, i))
    blocks, dup = find_blocks(streams)
    total = sum(len(v) for v in streams.values())
    print(f"tracked code lines: {total}")
    print(f"legacy duplicated lines: {dup} in {len(blocks)} block(s)")
    _print_blocks("LEGACY BLOCKS (locations, informational only):", blocks)
    print("VERDICT: REPORT ONLY (legacy debt never blocks)")
    return 0


def cmd_selftest(_a: argparse.Namespace) -> int:
    rc = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal rc
        print("  {}  {}".format("ok  " if ok else "MISS", label))
        if detail and not ok:
            print("        " + detail[:400])
        if not ok:
            rc = 1

    def write_files(project: Path, files: dict[str, str]) -> None:
        for path, text in files.items():
            p = project / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    def make_repo(files: dict[str, str]) -> Path:
        td = tempfile.mkdtemp()
        project = Path(td)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"],
                       cwd=project, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=project, check=True)
        write_files(project, files)
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=project, check=True)
        subprocess.run(["git", "checkout", "-q", "-b", "pr"], cwd=project, check=True)
        return project

    def commit(project: Path, files: dict[str, str]) -> None:
        write_files(project, files)
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "pr"], cwd=project, check=True)

    def run_check(project: Path) -> tuple[int, CheckResult]:
        return cmd_check(argparse.Namespace(project=str(project))), evaluate(project)

    def future(days: int = 90) -> str:
        return (date.today() + timedelta(days=days)).isoformat()

    block = "\n".join(f"    value_{i} = compute_{i}(row)" for i in range(6)) + "\n"
    base_files = {"tools/a/one.py": "def f():\n    return 1\n"}

    # 1. a 6-line block repeated across two new files fails the ratchet
    repo = make_repo(base_files)
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("6-line block repeated across two files fails (count >= 6)",
          code == 1 and res["duplicated_lines"] >= 6, json.dumps(res))

    # 2. a 5-line repeat passes: under the threshold is not a duplicate
    repo = make_repo(base_files)
    short = "\n".join(f"    value_{i} = compute_{i}(row)" for i in range(5)) + "\n"
    commit(repo, {
        "tools/a/two.py": "def g():\n" + short,
        "tools/a/three.py": "def h():\n" + short,
    })
    code, res = run_check(repo)
    check("5-line repeat passes (under threshold)", code == 0, json.dumps(res))

    # 3. full-line comments do not hide a repeat; trailing comments do differ
    repo = make_repo(base_files)
    commented = "# note one\n" + block
    commit(repo, {
        "tools/a/two.py": "def g():\n" + commented,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("full-line comment difference still caught", code == 1, json.dumps(res))

    # 4. same shape, different meaning (different identifiers) passes
    repo = make_repo(base_files)
    other = block.replace("compute_", "fetch_")
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + other,
    })
    code, res = run_check(repo)
    check("same shape with different identifiers passes", code == 0, json.dumps(res))

    # 5. extraction without tests fails; with a referencing test passes;
    #    with an unrelated test still fails
    extract_body = (
        "    total = 0\n"
        "    total += 1\n"
        "    total += 2\n"
        "    total += 3\n"
        "    total += 4\n"
        "    total += 5\n"
        "    return total\n"
    )
    extract_base = {
        "tools/a/one.py": "def f():\n" + extract_body,
        "tools/a/two.py": "def g():\n" + extract_body,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    extract_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/two.py": "def g():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n" + extract_body,
    }
    repo = make_repo(extract_base)
    commit(repo, extract_pr)
    code, res = run_check(repo)
    check("extraction without regression tests fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_shared.py":
                      "from tools.a.shared import shared\n\n\n"
                      "def test_shared():\n    assert shared() == 15\n"})
    code, res = run_check(repo)
    check("extraction with a test referencing the module passes",
          code == 0 and res["extraction"] == [], json.dumps(res))
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_other.py":
                      "def test_other():\n    assert 1 == 1\n"})
    code, res = run_check(repo)
    check("extraction with an unrelated test still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))

    # 6. empty diff passes
    repo = make_repo(base_files)
    code, res = run_check(repo)
    check("empty diff passes (no added code lines)",
          code == 0 and res["added_lines"] == 0, json.dumps(res))

    # 7. baseline respected; raised baseline without a reason fails.
    #    The raise must already be on main: a raise inside the diff under
    #    review does not take effect until it merges (case 11).
    repo = make_repo({**base_files, BASELINE_PATH: json.dumps(
        {"baseline": 6, "reason": "sibling profile scripts, recorded",
         "expires": future(), "owner": "claude-376-test"})})
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("count at baseline passes", code == 0, json.dumps(res))
    repo = make_repo({**base_files, BASELINE_PATH: json.dumps(
        {"baseline": 6, "reason": "", "expires": future(),
         "owner": "claude-376-test"})})
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("raised baseline without a reason fails", code == 1, json.dumps(res))

    # 8. the same repeat inside test files is informational, not a FAIL
    repo = make_repo(base_files)
    commit(repo, {
        "tests/test_two.py": "def test_g():\n" + block,
        "tests/test_three.py": "def test_h():\n" + block,
    })
    code, res = run_check(repo)
    check("repeat inside test files passes the ratchet",
          code == 0 and res["duplicated_lines"] == 0
          and res["test_duplicated_lines"] >= 6, json.dumps(res))

    # 9. report never fails, even with duplication present
    repo = make_repo(base_files)
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    check("report exits 0 with duplication present",
          cmd_report(argparse.Namespace(project=str(repo))) == 0)

    # 10. a malformed baseline file fails cleanly, not with a traceback
    repo = make_repo(base_files)
    (repo / BASELINE_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / BASELINE_PATH).write_text("{not json", encoding="utf-8")
    code, res = run_check(repo)
    check("malformed baseline fails cleanly",
          code == 1 and len(res["baseline_errors"]) > 0, json.dumps(res))

    # 11. a raise inside the diff under review does not silence the gate
    repo = make_repo({**base_files, BASELINE_PATH: json.dumps(
        {"baseline": 0, "reason": "", "expires": "", "owner": ""})})
    commit(repo, {
        BASELINE_PATH: json.dumps(
            {"baseline": 6, "reason": "raise in this diff",
             "expires": future(), "owner": "claude-376-test"}),
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("baseline raised in the same diff does not silence the gate",
          code == 1 and res["baseline"] == 0
          and res["duplicated_lines"] >= 6, json.dumps(res))

    print("\nVERDICT: {}".format(
        "duplication on changed lines is reported, the ratchet holds, and "
        "extraction needs tests" if rc == 0 else "selftest has failures above"))
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="fail when new-code duplication "
                             "exceeds the baseline, or on extraction "
                             "without tests")
    p_check.add_argument("--project", default=".")
    p_check.set_defaults(func=cmd_check)

    p_report = sub.add_parser("report", help="repo-wide legacy duplication "
                              "count (never fails)")
    p_report.add_argument("--project", default=".")
    p_report.set_defaults(func=cmd_report)

    p_self = sub.add_parser("selftest", help="plant duplication, extraction "
                            "and baseline cases, verify detection")
    p_self.set_defaults(func=cmd_selftest)

    a = ap.parse_args()
    return int(a.func(a))


if __name__ == "__main__":
    raise SystemExit(main())
