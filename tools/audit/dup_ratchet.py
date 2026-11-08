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

`state/dup-ratchet.json` holds one number, the baseline (0 at ship). `check`
fails when duplicated-added-lines exceed it. The baseline may only be raised
by a reviewed commit to that file carrying a non-empty reason; a raised
baseline without a reason fails the check. The file is in the diff, so the
exception is visible to panel review instead of silent.

WHAT COUNTS AS A DUPLICATE

An exact repeat, not a similarity score. After normalization (blank lines
dropped, full-line comments dropped, import lines and bare docstring fences
dropped, whitespace collapsed), a run of 6 consecutive added lines that
appears at 2+ locations is a duplicate block. Same-looking code that is not
textually identical does NOT fire: same-looking code may encode different
concepts, and abstracting it is a judgement call this tool refuses to make
for the author. The threshold (6) was calibrated against real merged diffs
(see docs/specs/2026-11-08-dup-ratchet.md): N=6 fires on the repo's
copy-pasted corpus-profile blocks and stays silent on clean code diffs.

THE EXTRACTION GATE

Cross-module extraction requires regression tests first. When the diff
removes a repeated 6-line block AND the same block appears as added lines in
a different file (the code moved to a shared home) with no test file in the
diff, `check` fails. A test file in the diff satisfies it.

WHAT THIS DOES NOT DO

It never suggests an extraction and never rewrites code. Every reported
group carries the line "abstraction requires a shared-meaning justification".
Test files are excluded from the ratchet FAIL (fixture repetition is
characterized by the test itself) but are listed in the report, so the
exclusion is visible, not silent.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
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


class Block(TypedDict):
    path: str
    start_line: int
    end_line: int
    lines: int
    sample: str


class CheckResult(TypedDict):
    added_lines: int
    duplicated_lines: int
    baseline: int
    blocks: list[Block]
    test_blocks: list[Block]
    test_duplicated_lines: int
    extraction: list[str]
    changed_files: list[str]


def is_code(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in CODE_EXTS and not path.startswith(OUT_OF_SCOPE_PREFIXES)


def is_test_file(path: str) -> bool:
    name = Path(path).name
    return (
        path.startswith("tests/")
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
        elif path is not None and raw.startswith("+") and not raw.startswith("+++"):
            if is_code(path):
                norm = normalize(raw[1:], path)
                if norm is not None:
                    added[path].append((norm, lineno))
            lineno += 1
    return added


def parse_removed(diff: str) -> dict[str, list[str]]:
    removed: dict[str, list[str]] = defaultdict(list)
    path: str | None = None
    for raw in diff.splitlines():
        if raw.startswith("--- a/"):
            path = raw[6:]
        elif raw.startswith("--- "):
            path = None
        elif path is not None and raw.startswith("-") and not raw.startswith("---"):
            if is_code(path):
                norm = normalize(raw[1:], path)
                if norm is not None:
                    removed[path].append(norm)
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
    """Merge overlapping duplicate windows into blocks; count dup lines."""
    windows: dict[tuple[str, ...], list[tuple[str, int]]] = defaultdict(list)
    for path, lines in streams.items():
        for i in range(len(lines) - WINDOW + 1):
            windows[tuple(t for t, _ in lines[i:i + WINDOW])].append((path, i))
    marked: set[tuple[str, int]] = set()
    intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for locs in windows.values():
        if len(locs) < 2:
            continue
        for path, i in locs[1:]:
            for j in range(i, i + WINDOW):
                marked.add((path, j))
            intervals[path].append((i, i + WINDOW))
    blocks: list[Block] = []
    for path, ivs in intervals.items():
        lines = streams[path]
        merged: list[tuple[int, int]] = []
        for start, end in sorted(ivs):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        for start, end in merged:
            blocks.append({
                "path": path,
                "start_line": lines[start][1],
                "end_line": lines[end - 1][1],
                "lines": end - start,
                "sample": lines[start][0][:100],
            })
    return blocks, len(marked)


def find_extractions(
    added: dict[str, list[tuple[str, int]]],
    removed: dict[str, list[str]],
    files: list[str],
) -> list[str]:
    """Removed repeated block reappearing as added lines in another file."""
    removed_windows: dict[tuple[str, ...], set[str]] = defaultdict(set)
    removed_counts: Counter[tuple[str, ...]] = Counter()
    for path, lines in removed.items():
        for i in range(len(lines) - WINDOW + 1):
            window = tuple(lines[i:i + WINDOW])
            removed_windows[window].add(path)
            removed_counts[window] += 1
    added_windows: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for path, alines in added.items():
        for i in range(len(alines) - WINDOW + 1):
            added_windows[tuple(t for t, _ in alines[i:i + WINDOW])].add(path)
    hits: list[str] = []
    for window, rpaths in removed_windows.items():
        # A removed block counts as repeated when it occurs 2+ times among
        # removed lines: same window seen from 2 files, or twice in one file.
        if removed_counts[window] < 2:
            continue
        hits.extend(
            f"{sorted(rpaths)[0]} (+{len(rpaths) - 1} more) -> {apath}"
            for apath in added_windows.get(window, set())
            if apath not in rpaths
        )
    return sorted(set(hits)) if not any(is_test_file(f) for f in files) else []


def load_baseline(project: Path) -> Baseline:
    p = project / BASELINE_PATH
    if not p.exists():
        return {"baseline": 0, "reason": ""}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"baseline": int(data.get("baseline", 0)),
            "reason": str(data.get("reason", ""))}


def evaluate(project: Path) -> CheckResult:
    base = default_base(project)
    diffs = [git(project, f"diff -U0 {base}...HEAD"), git(project, "diff -U0 HEAD")]
    added: dict[str, list[tuple[str, int]]] = defaultdict(list)
    removed: dict[str, list[str]] = defaultdict(list)
    files: set[str] = set()
    for diff in diffs:
        for path, lines in parse_added(diff).items():
            seen = {(t, n) for t, n in added[path]}
            added[path].extend([(t, n) for t, n in lines if (t, n) not in seen])
        for path, rlines in parse_removed(diff).items():
            removed[path].extend(rlines)
        files.update(changed_files(diff))
    blocks, dup = find_blocks(
        {p: lines for p, lines in added.items() if not is_test_file(p)})
    test_blocks, test_dup = find_blocks(
        {p: lines for p, lines in added.items() if is_test_file(p)})
    extraction = find_extractions(added, removed, sorted(files))
    base_rec = load_baseline(project)
    return {
        "added_lines": sum(len(v) for v in added.values()),
        "duplicated_lines": dup,
        "baseline": base_rec["baseline"],
        "blocks": blocks,
        "test_blocks": test_blocks,
        "test_duplicated_lines": test_dup,
        "extraction": extraction,
        "changed_files": sorted(files),
    }


def cmd_check(a: argparse.Namespace) -> int:
    project = Path(a.project).resolve()
    result = evaluate(project)
    base_rec = load_baseline(project)
    print(f"added code lines: {result['added_lines']}")
    print(f"duplicated added lines: {result['duplicated_lines']} "
          f"(baseline: {result['baseline']})")
    if result["blocks"]:
        print("\nDUPLICATE BLOCKS (abstraction needs a shared-meaning "
              "justification):")
        for b in result["blocks"][:10]:
            print(f"  {b['path']}:{b['start_line']}-{b['end_line']} "
                  f"({b['lines']} lines): {b['sample']}")
    if result["test_blocks"]:
        print("\nTEST-FILE DUPLICATION (informational, not ratcheted):")
        for b in result["test_blocks"][:10]:
            print(f"  {b['path']}:{b['start_line']}-{b['end_line']} "
                  f"({b['lines']} lines): {b['sample']}")
    if result["extraction"]:
        print("\nEXTRACTION WITHOUT REGRESSION TESTS:")
        for hit in result["extraction"]:
            print(f"  {hit}")
    failures: list[str] = []
    if result["baseline"] > 0 and not base_rec["reason"].strip():
        failures.append("baseline raised without a recorded reason in "
                        f"{BASELINE_PATH}")
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
        return 1
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

    # 5. extraction without tests fails; with a test file passes
    extract_base = {
        "tools/a/one.py": "def f():\n" + block,
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    extract_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/two.py": "def g():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n" + block,
    }
    repo = make_repo(extract_base)
    commit(repo, extract_pr)
    code, res = run_check(repo)
    check("extraction without regression tests fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_shared.py": "def test_shared():\n    assert True\n"})
    code, res = run_check(repo)
    check("extraction with a test file in the diff passes",
          code == 0 and res["extraction"] == [], json.dumps(res))

    # 6. empty diff passes
    repo = make_repo(base_files)
    code, res = run_check(repo)
    check("empty diff passes (no added code lines)",
          code == 0 and res["added_lines"] == 0, json.dumps(res))

    # 7. baseline respected; raised baseline without a reason fails
    repo = make_repo(base_files)
    (repo / BASELINE_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / BASELINE_PATH).write_text(json.dumps(
        {"baseline": 6, "reason": "sibling profile scripts, recorded"}),
        encoding="utf-8")
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("count at baseline passes", code == 0, json.dumps(res))
    repo = make_repo(base_files)
    (repo / BASELINE_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / BASELINE_PATH).write_text(json.dumps(
        {"baseline": 6, "reason": ""}), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo, check=True)
    code, res = run_check(repo)
    check("raised baseline without a reason fails", code == 1, json.dumps(res))

    # 9. the same repeat inside test files is informational, not a FAIL
    repo = make_repo(base_files)
    commit(repo, {
        "tests/test_two.py": "def test_g():\n" + block,
        "tests/test_three.py": "def test_h():\n" + block,
    })
    code, res = run_check(repo)
    check("repeat inside test files passes the ratchet",
          code == 0 and res["duplicated_lines"] == 0
          and res["test_duplicated_lines"] >= 6, json.dumps(res))

    # 8. report never fails, even with duplication present
    repo = make_repo(base_files)
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    check("report exits 0 with duplication present",
          cmd_report(argparse.Namespace(project=str(repo))) == 0)

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
