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
future expiry date, and an owner. The expiry bounds the raise in time, and
an expired raise LAPSES rather than locking the repo: once the expiry
passes, the effective baseline is 0, a clean PR passes, and a PR with
duplication fails on the count against 0 with a note that the raise
lapsed. The raise is a dated exception, not a permanent allowance, and
expiry must never turn into a repo-wide block on clean work: the issue's
first mechanism is that legacy debt never blocks, and a clean PR adds no
new duplication. The file is in the diff, so every raise is visible to
panel review instead of silent. Deleting the baseline file is not an
escape: a diff that deletes it fails closed with a message naming the
lowering path. Lowering is the documented happy path: when a PR's count
drops below the baseline, the author may lower the baseline to the new
count in the same PR. Owner is attribution, not verification: the tool
checks only that the field is non-empty, and review is the backstop for a
lazy expiry or owner.

WHAT COUNTS AS A DUPLICATE

An exact repeat, not a similarity score. After normalization (blank lines
dropped, full-line comments dropped, import lines and bare docstring fences
dropped, whitespace collapsed), a run of 6 consecutive added lines that
appears at 2 or more places is a duplicate block. A place is a maximal run
of identical lines, not a window start: twelve identical lines in one file
are one place, not seven overlapping windows, so a single file holding
twelve identical lines counts 0 duplicated lines. Consecutive means
consecutive in the file: the 6 lines must have consecutive line numbers,
so lines added in two separate hunks never form a block that never
existed. The ratchet is net-new: a repeat whose added occurrences are
fully covered by removed occurrences does not count (a pure move counts
0), because the issue's first mechanism is that legacy debt never
blocks, and moving debt is not creating it. Same-looking code that
is not textually identical does NOT fire: same-looking code may encode
different concepts, and abstracting it is a judgement call this tool
refuses to make for the author. Similar-but-not-identical matches are out
of scope by design. For byte-identical blocks the tool does not decide
whether the copies share meaning either: before extracting, the author
records why the copies share meaning (same concept, same future changes)
in the PR description, where a human reviewer sees it. No tool in this
repo reads a PR description, so the printed reminder is the whole
mechanism. The gate enforces the choice, not the
judgement: extract with an asserting regression test, or keep the
duplication and raise the baseline with a recorded reason. The threshold (6) was
calibrated against real merged diffs (see
docs/specs/2026-11-08-dup-ratchet.md): N=6 fires on the repo's copy-pasted
corpus-profile blocks and stays silent on clean code diffs.

THE EXTRACTION GATE

Cross-module extraction requires regression tests first. When the diff
removes a repeated 6-line block AND the same block appears as added lines
in a different file, or survives in the base tree in a file the diff
rewires its call sites to (the code moved to a shared home), the extraction is
exempt only when an added test line inside an asserting `test_*` function
CALLS one of the destination's defined symbols (a top-level function,
class, or constant of the destination file), directly or module-qualified
(`dedup(...)`, `helpers.dedup(...)`). A call is necessary, not sufficient,
for characterization: the gate is a floor, not a proof that the test is
good. An import alone does NOT exempt: a test that imports and never calls
still characterizes nothing. A bare call with no assertion does not
exempt, a call that can never execute does not exempt (inside `if False:`,
inside a helper no test calls), and a call outside a test function does
not exempt. The symbol must appear as a whole identifier token:
`shared_cache`, `ratio` against a stem of `io`, and a bare assignment
such as `shared = 1` do not exempt. String literals and comments never
count: `assert "shared" in "shared_name"` is a mention, not a test. When
the destination defines no parseable symbols, the gate falls back to the
stem rule (a call to the module stem). Non-Python test files keep the
call-only floor: the test-function rule is implemented on the Python AST.

"Repeated" has two shapes, and both are gated. The clean-room shape is a
block removed from two or more places at once, where a place is a maximal
run of identical lines, not a window start: twelve identical lines moved
as a unit are one place, not two sources. The partial-migration
shape is a block removed from one place while the block was already
duplicated before the diff: the surviving copy is invisible to a
diff-only detector, so the gate counts the block's occurrences in the
base tree (via `git archive`) and fires when the block occurred twice or
more there. That count covers production code files only: a copy
surviving only in a test file does not count, because the test itself
characterizes it, the same reason test files are excluded from the
ratchet FAIL. A unique block that merely moves (one base-tree occurrence)
is not an extraction and is not gated. The third shape is the shared
home that already exists on main. A two-PR split defeats the two shapes
above: the first PR adds the helper with no removal, the second rewires
the call sites to it with no added copy of the block, so the added-lines
leg sees no destination. The gate closes that split: a removed window
that survives in the base tree is a destination when the diff's added
lines in the removal sources call that file's symbols (the rewiring).
The destination's line numbers are base-tree lines, because the
location is read from the base tree. A pure
deletion adds no call, so it does not fire, and a surviving copy in a
file the diff never calls is not a home. The same exemption applies:
an added test in an asserting test function calling the destination's
symbols exempts. The destination may itself be one
of the files the block was removed from (consolidation into an existing
holder file); a base location in such a file counts only under
occurrence accounting, when the file holds more base occurrences of
the window than were removed from it, and only the surviving
occurrence is reported. It is skipped only when it is the SOLE file the block was
removed from, which is an in-place edit, not a move. The clean-room
shape fires only when the destination holds strictly fewer occurrences
of the block than were removed: a destination that still holds as many
copies as were removed consolidated nothing, so the move is not an
extraction (a function moved whole, repeat inside it included, passes
both gates). Test files are excluded from the extraction gate entirely:
moving a fixture block between test files is fixture deduplication, not
an extraction. Deleting duplicated code without adding a shared home is
not an extraction and is not gated.

MEASUREMENT

A check that cannot obtain a diff fails closed instead of passing
vacuously: outside a git repository, with an unresolvable base ref, or
when `git diff` itself errors, `check` exits 1 with "cannot measure".
One case stays a vacuous PASS by repo convention: when the base ref
resolves to HEAD (running `check` on main, which ship-gate does on main
pushes), the diff is empty and there is nothing to ratchet. Diff-scoped
checks in this repo share that convention; the fail-closed rule covers
only a diff that cannot be obtained at all.

WHAT THIS DOES NOT DO

It never suggests an extraction and never rewrites code. Test files are
excluded from the ratchet FAIL (fixture repetition is characterized by the
test itself) but are listed in the report, so the exclusion is visible, not
silent. A block appearing once in production code and once in a test file
is reported as a cross-copy, also informationally.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterator, TypedDict

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
    baseline_lapsed: str
    baseline_errors: list[str]
    blocks: list[Block]
    test_blocks: list[Block]
    test_duplicated_lines: int
    cross_blocks: list[Block]
    extraction: list[ExtractionHit]
    changed_files: list[str]


class BaselineError(ValueError):
    """The baseline file is unreadable or malformed."""


class CheckError(Exception):
    """The check cannot measure (not a repo, unresolvable base, git failed)."""


def is_code(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in CODE_EXTS and not path.startswith(OUT_OF_SCOPE_PREFIXES)


def is_test_file(path: str) -> bool:
    name = Path(path).name
    return (
        path.startswith(("tests/", "__tests__/"))
        or "/__tests__/" in path
        or name == "test.py"
        or name.startswith(("test_", "spec_"))
        or "_test." in name
        or ".test." in name
        or ".spec." in name
        or "_spec." in name
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


def git(project: Path, args: str, check: bool = False) -> str:
    r = subprocess.run(
        ["git"] + args.split(), cwd=project, capture_output=True, text=True
    )
    if check and r.returncode != 0:
        raise CheckError(
            f"git {' '.join(args.split())} failed "
            f"(exit {r.returncode}): {r.stderr.strip()[:200]}")
    return r.stdout


def default_base(project: Path) -> str:
    # Mirrors gate.py default_base (same candidate order, same HEAD~1
    # fallback). A shared home for the three copies (gate.py, panel.py,
    # here) is a follow-up; see docs/specs/2026-11-08-dup-ratchet.md.
    for cand in ("origin/main", "origin/master", "main", "master"):
        if git(project, f"rev-parse --verify --quiet {cand}").strip():
            return cand
    return "HEAD~1"


def _scan_diff(diff: str) -> Iterator[tuple[str, int, int, str, str]]:
    """One walk over a unified diff.

    Yields (path, old_lineno, new_lineno, kind, text) for every
    context, added, and removed line, with both line numbers tracked
    from the hunk header. `kind` is "context", "added", or "removed";
    `text` is the line without its leading marker. The three consumers
    (parse_added, parse_removed, _raw_added_test_lines_by_file) used to
    each walk the diff with their own copy of this loop, and the copies
    drifted into a 13-line repeat the ratchet flags on its own diff;
    there is one walk now.

    No reset on `/dev/null` headers: a deleted file's removed lines
    still belong to it (its `+++ /dev/null` header must not orphan
    them), and a new file's `+++ b/` header sets the path before any
    content line, so dropping the reset changes nothing observable
    on a well-formed git diff.

    Header guards match only the actual header forms (`+++ ` and
    `--- ` with a trailing space): a content line starting with `++`
    or `--` at column 0 (`++count;`, `--count;`) produces a diff line
    starting with `+++` / `---`, and a bare-prefix guard would drop
    it and shift every later line number in the hunk by one.
    """
    path: str | None = None
    old_lineno = 0
    new_lineno = 0
    for raw in diff.splitlines():
        if raw.startswith(("+++ b/", "--- a/")):
            path = raw[6:]
            old_lineno = 0
            new_lineno = 0
        elif raw.startswith("@@ ") and path is not None:
            m_old = re.search(r"-(\d+)", raw)
            m_new = re.search(r"\+(\d+)", raw)
            old_lineno = int(m_old.group(1)) if m_old else 0
            new_lineno = int(m_new.group(1)) if m_new else 0
        elif path is not None and raw.startswith(" "):
            yield path, old_lineno, new_lineno, "context", raw[1:]
            old_lineno += 1
            new_lineno += 1
        elif path is not None and raw.startswith("+") \
                and not raw.startswith("+++ "):
            yield path, old_lineno, new_lineno, "added", raw[1:]
            new_lineno += 1
        elif path is not None and raw.startswith("-") \
                and not raw.startswith("--- "):
            yield path, old_lineno, new_lineno, "removed", raw[1:]
            old_lineno += 1


def parse_added(diff: str) -> dict[str, list[tuple[str, int]]]:
    """Added normalized lines per file: {path: [(text, new_lineno)]}."""
    added: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path, _old, new_lineno, kind, text in _scan_diff(diff):
        if kind != "added" or not is_code(path):
            continue
        norm = normalize(text, path)
        if norm is not None:
            added[path].append((norm, new_lineno))
    return added


def parse_removed(diff: str) -> dict[str, list[tuple[str, int]]]:
    """Removed normalized lines per file: {path: [(text, old_lineno)]}."""
    removed: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path, old_lineno, _new, kind, text in _scan_diff(diff):
        if kind != "removed" or not is_code(path):
            continue
        norm = normalize(text, path)
        if norm is not None:
            removed[path].append((norm, old_lineno))
    return removed


def changed_files(diff: str) -> list[str]:
    files: set[str] = set()
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            files.add(raw[6:])
        elif raw.startswith("--- a/"):
            # A deleted file has no `+++ b/` header, so without this
            # its path never appears in the changed list.
            files.add(raw[6:])
    return sorted(files)


def _window_at(
    lines: list[tuple[str, int]], i: int,
) -> tuple[str, ...] | None:
    """The 6-line window starting at stream index i, or None.

    None when the window would run past the end of the stream, and
    None when the 6 lines are not consecutive in the file: a window
    spanning a hunk boundary, or a dropped blank/comment line, is a
    block that never existed as a block, so it must not count. The
    line numbers are the file's own, so consecutive in the stream is
    not enough; the check is lineno[i+5] - lineno[i] == 5.
    """
    if i < 0 or i + WINDOW > len(lines):
        return None
    if lines[i + WINDOW - 1][1] - lines[i][1] != WINDOW - 1:
        return None
    return tuple(t for t, _ in lines[i:i + WINDOW])


def _contiguous_windows(
    lines: list[tuple[str, int]],
) -> Iterator[tuple[int, tuple[str, ...]]]:
    """(index, window) for every contiguous 6-line window in a stream."""
    for i in range(len(lines) - WINDOW + 1):
        window = _window_at(lines, i)
        if window is not None:
            yield i, window


def _window_places(
    streams: dict[str, list[tuple[str, int]]],
) -> dict[tuple[str, ...], list[tuple[str, int]]]:
    """Distinct places of each contiguous window, per file collapsed.

    A place is a maximal run of identical lines, not a window start:
    twelve identical lines moved as a unit are one place, not two
    non-overlapping windows. `_distinct_starts` does the collapsing
    per file; the places of a window are the collapsed starts across
    all files that hold it.
    """
    places: dict[tuple[str, ...], list[tuple[str, int]]] = defaultdict(list)
    for path, lines in streams.items():
        starts: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for i, window in _contiguous_windows(lines):
            starts[window].append(i)
        for window, idxs in starts.items():
            for s in _distinct_starts(idxs, [t for t, _ in lines]):
                places[window].append((path, s))
    return places


def find_blocks(
    streams: dict[str, list[tuple[str, int]]],
    removed_places: dict[tuple[str, ...], list[tuple[str, int]]] | None = None,
) -> tuple[list[Block], int]:
    """Group duplicate windows into maximal blocks; count net-new dup lines.

    A place is a maximal run of identical lines (see `_window_places`),
    and a window is a duplicate only when it appears at 2 or more
    places. The count is the set of distinct added lines inside any
    duplicate block beyond the first occurrence, so a 12-line repeat
    counts 12 lines in one block, not 7 overlapping windows, and a
    single file holding 12 identical lines counts 0: there is no
    second copy anywhere.

    The ratchet is net-new: `removed_places` maps each window to the
    distinct places it was removed from, and a repeat whose added
    occurrences are fully covered by removed occurrences does not
    count. Counted places are the added places beyond
    max(1, removed places) per window: one place is always free (the
    first occurrence), and each removed place covers one more, so a
    pure move counts 0 and a block added twice while removed once
    counts one copy. With no removed map (report, calibration) the
    free count is 1, the old rule. Reporting groups windows into
    maximal families: a family is a maximal run of consecutive windows
    whose location set shifts with the window, where the shift is
    checked by tuple equality at the shifted position in every file
    holding a place, so a uniform run extends to its full length in
    every copy and the family's span is the shortest run across its
    places. Every location of every family is reported, first
    occurrence included.
    """
    places = _window_places(streams)

    def free_count(window: tuple[str, ...]) -> int:
        if removed_places is None:
            return 1
        return max(1, len(removed_places.get(window, [])))

    def is_duplicate(window: tuple[str, ...]) -> bool:
        return len(places.get(window, [])) > free_count(window)

    def tuple_at(path: str, idx: int) -> tuple[str, ...] | None:
        lines = streams.get(path)
        if lines is None:
            return None
        return _window_at(lines, idx)

    def extends(
        base_places: list[tuple[str, int]], ref_path: str,
        from_idx: int, to_idx: int,
    ) -> bool:
        """Does the family starting at from_idx extend to to_idx?

        Every base place's shifted position must hold the same window
        tuple as the reference position to_idx. For a block of
        distinct lines that is the shifted place itself; for a uniform
        run it is any position inside the run, which is what lets the
        family span the whole run instead of one window.
        """
        target = tuple_at(ref_path, to_idx)
        if target is None:
            return False
        delta = to_idx - from_idx
        for p, s in base_places:
            if tuple_at(p, s + delta) != target:
                return False
        return True

    blocks: list[Block] = []
    marked: set[tuple[str, int]] = set()
    seen: set[tuple[tuple[tuple[str, int], ...], int]] = set()
    for path, lines in streams.items():
        i = 0
        while i <= len(lines) - WINDOW:
            key = tuple_at(path, i)
            if key is None or not is_duplicate(key):
                i += 1
                continue
            locs = places[key]
            if i > 0:
                prev = tuple_at(path, i - 1)
                if prev is not None and is_duplicate(prev) \
                        and extends(places[prev], path, i - 1, i):
                    i += 1
                    continue
            j = i
            while extends(locs, path, i, j + 1):
                j += 1
            span = j - i + WINDOW
            family_key = (tuple(sorted(locs)), span)
            if family_key in seen:
                i = j + 1
                continue
            seen.add(family_key)
            free = free_count(key)
            for p, idx in locs[free:]:
                for k in range(idx, idx + span):
                    marked.add((p, k))
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


def _strip_code_text(line: str) -> str:
    """A test line with string literals and comments removed.

    Only code counts toward a reference: a stem inside a string literal
    ("shared" in "shared_name") or a comment (# call shared()) is a
    mention, not a use.
    """
    s = re.sub(r"'[^']*'|\"[^\"]*\"", "''", line)
    s = s.split("#", 1)[0]
    s = s.split("//", 1)[0]
    return s


def _const_truth(node: ast.AST) -> bool | None:
    """Static truth of a branch condition, or None when unknowable.

    Only literal constants (and `not` of them) are decided: `if False:`,
    `if 0:`, `if not True:` are dead; anything with a name in it is
    unknown and treated as live. A wrong guess here would silently
    exempt a never-executed call, so unknown means live.
    """
    if isinstance(node, ast.Constant):
        value = node.value
        if value is True:
            return True
        if value is False or value is None:
            return False
        if isinstance(value, (int, float, complex)):
            return value != 0
        if isinstance(value, (str, bytes)):
            return len(value) > 0
        return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _const_truth(node.operand)
        return None if inner is None else not inner
    return None


def _iter_test_functions(
    tree: ast.Module,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """`test_*` functions pytest would collect: module-level or methods.

    A test function nested inside another function is not yielded: it
    never runs unless the outer function calls it, and the gate does
    not trace that call.
    """
    def rec(
        node: ast.AST, in_func: bool,
    ) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not in_func and child.name.startswith("test_"):
                    yield child
                yield from rec(child, True)
            elif isinstance(child, ast.ClassDef):
                yield from rec(child, in_func)
            else:
                yield from rec(child, in_func)
    yield from rec(tree, False)


def _scan_test_body(stmts: list[ast.stmt]) -> tuple[set[int], bool]:
    """Calls and assert-presence for one test-function body.

    Returns (call linenos, asserted). A call counts only when it sits
    directly in the test body: nested def/class/lambda bodies are not
    descended into (their code runs only if called, which the gate does
    not trace), and bodies under a constant-false branch are skipped
    (their code never runs; the `else` branch of such a test is live
    and still scanned). A test function asserts when it holds an
    `assert` statement, an `assert*` method call (`self.assertEqual`),
    or a `pytest.raises` guard.
    """
    calls: set[int] = set()
    asserted = False

    def scan(node: ast.AST) -> None:
        nonlocal asserted
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Lambda)):
            return
        if isinstance(node, ast.Assert):
            asserted = True
        if isinstance(node, ast.Call):
            calls.add(node.lineno)
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr.startswith("assert"):
                    asserted = True
                elif func.attr == "raises" and isinstance(
                        func.value, ast.Name) \
                        and func.value.id == "pytest":
                    asserted = True
            elif isinstance(func, ast.Name) \
                    and func.id.startswith("assert"):
                asserted = True
        if isinstance(node, ast.If):
            truth = _const_truth(node.test)
            scan(node.test)
            if truth is False:
                for stmt in node.orelse:
                    scan(stmt)
            elif truth is True:
                for stmt in node.body:
                    scan(stmt)
            else:
                for stmt in node.body + node.orelse:
                    scan(stmt)
            return
        if isinstance(node, ast.While):
            truth = _const_truth(node.test)
            scan(node.test)
            if truth is False:
                for stmt in node.orelse:
                    scan(stmt)
            else:
                for stmt in node.body + node.orelse:
                    scan(stmt)
            return
        for child in ast.iter_child_nodes(node):
            scan(child)

    for stmt in stmts:
        scan(stmt)
    return calls, asserted


def _qualifying_call_lines(source: str) -> set[int]:
    """Line numbers of calls that count as regression-test references.

    A call counts only when it sits directly in a `test_*` function body
    (not inside a nested def/class, not under a constant-false branch)
    and that test function asserts something. A bare call with no
    assertion, a call under `if False:`, and a call inside a helper no
    test calls all characterize nothing, so none of them qualifies.
    Unparseable source qualifies nothing: fail closed, the author fixes
    the syntax error anyway.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    qualifying: set[int] = set()
    for test_fn in _iter_test_functions(tree):
        calls, asserted = _scan_test_body(test_fn.body)
        if asserted:
            qualifying.update(calls)
    return qualifying


def _symbols_in_source(source: str) -> set[str] | None:
    """Top-level defined names of a Python source text, or None.

    None means the source is not parseable, or it defines no top-level
    functions, classes, or UPPER constants: the caller falls back to
    the stem rule. Shared by the on-disk and at-ref readers so the two
    agree on what a defined name is.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) \
                and isinstance(node.target, ast.Name) \
                and node.target.id.isupper():
            names.add(node.target.id)
    return names or None


def _dest_symbols_on_disk(project: Path, path: str) -> set[str] | None:
    """Top-level defined names of the destination file, or None.

    None means the destination is not Python or cannot be parsed: the
    caller falls back to the stem rule. A Python file with no top-level
    defs, classes, or constants also yields None, so a destination
    that only holds data is still gated on its stem.
    """
    if Path(path).suffix.lower() != ".py":
        return None
    try:
        return _symbols_in_source((project / path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def _dest_symbols_at_ref(project: Path, base: str, path: str) -> set[str] | None:
    """Top-level defined names of the file at the base ref, or None.

    The base-home leg needs the destination's symbols as they stood
    before the diff: the file is unchanged by the diff (or changed
    only elsewhere), so the disk copy is not the base copy, and a
    symbol the diff renamed must not decide the exemption. None means
    the same as on disk: not Python, not at the ref, or unparseable,
    and the caller falls back to the stem rule.
    """
    if Path(path).suffix.lower() != ".py":
        return None
    out = git(project, f"show {base}:{path}")
    if not out:
        return None
    return _symbols_in_source(out)


def _head_source(project: Path, path: str) -> str | None:
    """The test file's content at HEAD, or None when it is not there.

    The committed diff's line numbers refer to HEAD, so its test lines
    are resolved against this source, never against the working tree.
    """
    out = git(project, f"show HEAD:{path}")
    return out if out else None


def _disk_source(project: Path, path: str) -> str | None:
    """The test file's content on disk, or None when unreadable.

    The working-tree diff's line numbers refer to the working tree,
    so its test lines are resolved against this source.
    """
    try:
        return (project / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _raw_added_test_lines_by_file(
    diffs: list[str],
) -> dict[str, list[tuple[str, int]]]:
    """Raw added lines of test files per file: {path: [(text, new_lineno)]}.

    Raw, not normalized: the reference check reads the original text so
    its string-literal and comment stripping sees what the author wrote.
    Line numbers are the new-file numbers, so they line up with the
    test file the AST filter reads. Only code files supply test lines:
    a document named like a test (`test_notes.md`) is prose, not a
    regression test, and its lines must not exempt an extraction.
    """
    added: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for diff in diffs:
        for path, _old, new_lineno, kind, text in _scan_diff(diff):
            if kind == "added" and is_test_file(path) and is_code(path):
                added[path].append((text, new_lineno))
    return added


def _qualifying_test_lines(
    raw_by_file: dict[str, list[tuple[str, int]]],
    source_for: "Callable[[str], str | None]",
) -> list[str]:
    """Added test lines that can exempt an extraction, flat.

    For Python test files, only lines the AST filter qualifies: a call
    inside an asserting `test_*` function. `source_for` resolves the
    file's content for the diff these lines came from: the committed
    diff's lines are checked against the file at HEAD, the
    working-tree diff's lines against the file on disk. The two diffs
    number lines on different bases (HEAD vs working tree), so one
    source for both would void a valid exemption whenever uncommitted
    edits above the test shift its lines. An unreadable or unparseable
    test file qualifies nothing (fail closed). Non-Python test files
    keep the call-only floor: the test-function rule is implemented on
    the Python AST, and the regex match in `_references_dest` is still
    the check that the line calls the destination.
    """
    lines: list[str] = []
    for path, entries in raw_by_file.items():
        if Path(path).suffix.lower() != ".py":
            lines.extend(raw for raw, _ in entries)
            continue
        source = source_for(path)
        if source is None:
            continue
        ok = _qualifying_call_lines(source)
        lines.extend(raw for raw, n in entries if n in ok)
    return lines


def _references_dest(
    test_lines: list[str], dest: str, symbols: set[str] | None = None,
) -> bool:
    """Does any added test line call one of the destination's symbols?

    With symbols given (the destination's defined names, from
    `_dest_symbols_on_disk`), a direct call (`dedup(...)`) or a
    module-qualified call (`helpers.dedup(...)`) counts, as does an
    attribute use (`shared.VALUE`). With symbols None, the old stem
    rule applies (a call to the module stem, or `stem.attr`): the
    fallback for a destination with no parseable symbols. A bare
    assignment (shared = 1), a variable that merely contains the name
    (shared_cache), a stem inside an ordinary word (ratio against io),
    and a string mention do not count. An import alone does NOT count:
    importing a module and never calling it characterizes nothing, so
    `from ... import shared` without a call does not exempt. Which
    lines reach this function is the AST filter's job: only calls
    inside an asserting test function are passed in.
    """
    stem = Path(dest).stem
    if symbols is None:
        call = re.compile(rf"\b{re.escape(stem)}\s*\(")
        attr = re.compile(rf"\b{re.escape(stem)}\.[A-Za-z_]\w*")
    else:
        alt = "|".join(re.escape(s) for s in sorted(symbols))
        call = re.compile(
            rf"\b(?:{alt})\s*\(|\b{re.escape(stem)}\.(?:{alt})\s*\(")
        attr = re.compile(rf"\b{re.escape(stem)}\.(?:{alt})\b")
    for raw in test_lines:
        line = _strip_code_text(raw)
        if call.search(line) or attr.search(line):
            return True
    return False


def _distinct_starts(starts: list[int], lines: list[str]) -> list[int]:
    """Start indices with overlapping windows collapsed (greedy, in order).

    Seven identical consecutive lines form two overlapping 6-line
    windows, but they are one occurrence, not two: a start that falls
    inside an already-taken window is not a second occurrence. The
    same holds for two non-overlapping starts inside one maximal run
    of identical lines: twelve identical lines form two 6-line
    windows, but the run is one place, not two sources, so a
    single-site move must not be reported as a two-source extraction.
    A start joins the previous taken start's run only when every line
    between them is the same value; a repeated 6-line pattern of
    distinct lines still counts each copy separately.
    """
    taken: list[int] = []
    last_end = -1
    for s in sorted(starts):
        if s < last_end:
            continue
        if taken and all(
                line == lines[taken[-1]]
                for line in lines[taken[-1]:s + WINDOW]):
            continue
        taken.append(s)
        last_end = s + WINDOW
    return taken


def _base_tree_window_counts(
    project: Path, base: str, candidates: set[tuple[str, ...]]
) -> tuple[dict[tuple[str, ...], int], dict[tuple[str, ...], list[Location]]]:
    """Distinct base-tree occurrences of each candidate window.

    Reads the base tree once via `git archive` and counts, per window,
    the distinct (file, start) occurrences with overlapping windows
    collapsed. Only candidate windows are counted, so the memory cost is
    bounded by the candidate set, not the tree. Test files are not
    counted: a copy that survives only in a test file is characterized
    by the test itself, the same reason test files are excluded from
    the ratchet FAIL, so it must not turn a production move into an
    extraction. Raises CheckError when the base tree cannot be read: a
    partial-migration verdict must not rest on an unread tree. That
    covers a git-level failure and a code file that cannot be decoded
    as UTF-8: either is a tree that cannot be read, so the check fails
    closed instead of silently skipping the file.

    Returns (counts, locations): the counts feed the partial-migration
    repeated test, and the locations feed the base-home leg of
    find_extractions, which needs the file and the real file line
    numbers of each surviving occurrence. The counts are derived from
    the same collapsed starts as the locations, so the two agree.
    """
    import io
    import tarfile

    try:
        r = subprocess.run(
            ["git", "archive", base], cwd=project, capture_output=True)
    except OSError as exc:
        raise CheckError(f"cannot read the base tree at {base}: {exc}")
    if r.returncode != 0:
        raise CheckError(
            f"cannot read the base tree at {base}: "
            f"{r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    counts: Counter[tuple[str, ...]] = Counter()
    locations: dict[tuple[str, ...], list[Location]] = defaultdict(list)
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        for member in tf.getmembers():
            if not member.isfile() or not is_code(member.name) \
                    or is_test_file(member.name):
                continue
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            try:
                text = extracted.read().decode("utf-8")
            except UnicodeDecodeError:
                raise CheckError(
                    f"cannot read the base tree at {base}: "
                    f"{member.name} is not UTF-8")
            lines = [
                (norm, lineno)
                for lineno, line in enumerate(text.splitlines(), start=1)
                if (norm := normalize(line, member.name)) is not None
            ]
            positions: dict[tuple[str, ...], list[int]] = defaultdict(list)
            for i, window in _contiguous_windows(lines):
                if window in candidates:
                    positions[window].append(i)
            for window, starts in positions.items():
                taken = _distinct_starts(starts, [t for t, _ in lines])
                counts[window] += len(taken)
                for s in taken:
                    locations[window].append({
                        "path": member.name,
                        "start_line": lines[s][1],
                        "end_line": lines[s + WINDOW - 1][1],
                    })
    return dict(counts), dict(locations)


def find_extractions(
    added: dict[str, list[tuple[str, int]]],
    removed: dict[str, list[tuple[str, int]]],
    test_lines: list[str],
    base_windows: dict[tuple[str, ...], int] | None = None,
    dest_symbols: dict[str, set[str]] | None = None,
    base_locations: dict[tuple[str, ...], list[Location]] | None = None,
) -> list[ExtractionHit]:
    """Removed repeated block reappearing as added lines in another file.

    A hit is exempt only when an added test line in an asserting test
    function CALLS one of the destination's defined symbols (directly
    or module-qualified). `dest_symbols` maps destination path to its
    defined names; a destination absent from it falls back to the stem
    rule. A test file that never calls the extracted symbol does not
    exempt, however it is named, and an import alone does not exempt.

    "Repeated" has two shapes. The clean-room shape: the block was
    removed from two or more distinct places in the diff. The
    partial-migration shape: the block was removed from one place, but
    `base_windows` (distinct occurrences in the base tree) shows it
    occurred twice or more before the diff, so a copy survives outside
    the diff. A unique block that merely moves (one base-tree
    occurrence) is not an extraction. The destination is skipped only
    when it is the SOLE file the block was removed from (an in-place
    edit); consolidation into an existing holder file still fires.
    The clean-room shape fires only when the destination holds strictly
    fewer occurrences of the block than were removed: a destination
    that still holds as many copies as were removed consolidated
    nothing, so the move is not an extraction. Windows are contiguous
    6-line runs in the file: a window spanning a hunk boundary or a
    dropped line never existed as a block, so it cannot be an
    extraction. A hit's destination range covers one run of
    consecutive windows only, never the gap between two separate
    occurrences of the same block in the destination.

    The third shape is the shared home that already exists on main.
    A two-PR split defeats the two shapes above: the first PR adds the
    helper with no removal, the second rewires the call sites to it
    with no added copy of the block, so the added-lines leg sees no
    destination. `base_locations` (base-tree occurrences of each
    removed window, from `_base_tree_window_counts`) closes that
    split: a removed window that survives in the base tree is a
    destination when the diff's added lines in the removal sources
    CALL that file's symbols (the rewiring). A pure deletion adds no
    call, so it does not fire, and a surviving copy in a file the diff
    never calls is not a home. A base location in a removal source
    counts only under occurrence accounting: the file must hold more
    base occurrences of the window than were removed from it, and only
    the surviving occurrence is reported, never a removed copy; the
    destination is skipped outright only when its file is the SOLE
    file the block was removed from. The destination's line numbers
    are base-tree lines, because the location is read from the base
    tree. The same exemption applies: an
    added test calling the destination's symbols exempts. A base-home
    hit is deduped against an added-leg hit for the same (removal
    set, destination) key.
    """
    removed_positions = _window_places(removed)
    removed_windows: dict[tuple[str, ...], set[str]] = {
        window: {p for p, _ in rplaces}
        for window, rplaces in removed_positions.items()
    }
    added_windows: dict[tuple[str, ...], list[tuple[str, int]]] = defaultdict(list)
    for path, lines in added.items():
        for i, window in _contiguous_windows(lines):
            added_windows[window].append((path, i))
    base_counts = base_windows or {}
    base_locs = base_locations or {}
    merged: list[ExtractionHit] = []
    active: dict[tuple[tuple[str, ...], str], int] = {}
    last_aidx: dict[tuple[tuple[str, ...], str], int] = {}
    base_active: dict[tuple[tuple[str, ...], str], int] = {}
    base_last_start: dict[tuple[tuple[str, ...], str], int] = {}

    def sources_for(window: tuple[str, ...]) -> list[Location]:
        return [
            {
                "path": rpath,
                "start_line": removed[rpath][i][1],
                "end_line": removed[rpath][i + WINDOW - 1][1],
            }
            for rpath, i in sorted(removed_positions[window])
        ]

    for window, rpaths in removed_windows.items():
        # A removed block counts as repeated when it occurs 2+ distinct
        # times among removed lines, or occurred 2+ times in the base
        # tree (partial migration: one copy removed, one surviving).
        if len(removed_positions[window]) < 2 \
                and base_counts.get(window, 0) < 2:
            continue
        for apath, aidx in added_windows.get(window, []):
            if rpaths == {apath}:
                continue
            if len(removed_positions[window]) >= 2:
                # Clean-room leg: the destination must hold strictly
                # fewer occurrences than were removed, or nothing was
                # consolidated and the move is not an extraction.
                dest_starts = [
                    i for p, i in added_windows[window] if p == apath
                ]
                dest_occ = len(_distinct_starts(
                    dest_starts, [t for t, _ in added[apath]]))
                if dest_occ >= len(removed_positions[window]):
                    continue
            syms = (dest_symbols or {}).get(apath)
            if _references_dest(test_lines, apath, syms):
                continue
            alines = added[apath]
            dest: Location = {
                "path": apath,
                "start_line": alines[aidx][1],
                "end_line": alines[aidx + WINDOW - 1][1],
            }
            key = (tuple(sorted(rpaths)), apath)
            if key in active and aidx == last_aidx[key] + 1:
                hit = merged[active[key]]
                hit["dest"]["end_line"] = max(
                    hit["dest"]["end_line"], dest["end_line"])
                last_aidx[key] = aidx
            else:
                active[key] = len(merged)
                last_aidx[key] = aidx
                merged.append({
                    "sources": sources_for(window),
                    "dest": dest,
                    "sample": window[0][:100],
                })
        # Base-home leg: the block survives in the base tree in a file
        # that may itself be one of the removal sources. That file is a
        # shared home only when the diff rewires to it: an added line in
        # a removal source must call the file's symbols. A pure deletion
        # adds no call, and a surviving copy the diff never calls is not
        # a home. Occurrence accounting (arch-7 finding 1): a base
        # location in a removal source counts only when that file holds
        # more base occurrences of the window than were removed from it,
        # and only the surviving occurrence may be reported, so the
        # removed copies are never reported as destinations. The sole
        # removal source is an in-place edit, skipped outright like the
        # added leg.
        rewire_lines = [
            t for p in rpaths for t, _ in added.get(p, [])
        ]
        removed_starts: dict[str, set[int]] = defaultdict(set)
        removed_counts: Counter[str] = Counter()
        for rpath, i in removed_positions[window]:
            removed_counts[rpath] += 1
            removed_starts[rpath].add(removed[rpath][i][1])
        base_counts_by_file: Counter[str] = Counter(
            loc["path"] for loc in base_locs.get(window, []))
        for bloc in base_locs.get(window, []):
            bpath = bloc["path"]
            if bpath in rpaths:
                if rpaths == {bpath}:
                    continue
                if base_counts_by_file[bpath] <= removed_counts[bpath]:
                    continue
                if bloc["start_line"] in removed_starts[bpath]:
                    continue
            key = (tuple(sorted(rpaths)), bpath)
            if key in active:
                continue
            bsyms = (dest_symbols or {}).get(bpath)
            if not _references_dest(rewire_lines, bpath, bsyms):
                continue
            if _references_dest(test_lines, bpath, bsyms):
                continue
            dest = {
                "path": bpath,
                "start_line": bloc["start_line"],
                "end_line": bloc["end_line"],
            }
            if key in base_active \
                    and bloc["start_line"] == base_last_start[key] + 1:
                # Consecutive window of the same run (a 7-line block is
                # two windows): extend the range, as the added leg does.
                hit = merged[base_active[key]]
                hit["dest"]["end_line"] = max(
                    hit["dest"]["end_line"], dest["end_line"])
            else:
                base_active[key] = len(merged)
                merged.append({
                    "sources": sources_for(window),
                    "dest": dest,
                    "sample": window[0][:100],
                })
            base_last_start[key] = bloc["start_line"]
    return sorted(merged,
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
    if not git(project, f"rev-parse --verify --quiet {ref}").strip():
        raise BaselineError(f"baseline ref {ref} is not resolvable")
    out = git(project, f"show {ref}:{BASELINE_PATH}")
    if not out.strip():
        return {"baseline": 0, "reason": "", "expires": "", "owner": ""}
    try:
        return _parse_baseline(json.loads(out))
    except ValueError as exc:
        raise BaselineError(f"baseline at {ref} unreadable: {exc}")


def _baseline_expired(rec: Baseline, today: date) -> bool:
    """True when a raise above 0 has passed its expiry date.

    This is the single comparison the expiry mechanism rests on: the
    mutation spec neuters it, and the lapsed-baseline cases catch that.
    """
    try:
        return rec["baseline"] > 0 \
            and date.fromisoformat(rec["expires"]) < today
    except ValueError:
        return False


def validate_baseline(rec: Baseline, today: date) -> list[str]:
    """Shape errors in one baseline record.

    This validates a record as written: a raise above 0 needs a reason, a
    future expiry, and an owner. The expiry must be strictly future: a
    raise expiring today fails validation (re-justify with a later date
    or lower the baseline). A record that already lapsed (expiry in the
    past) is not an error here: the lapse rule in evaluate() handles it,
    and a PR that does not touch the file is not failed by the record it
    did not write.
    """
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
    if expires <= today:
        errors.append(f"baseline expiry {rec['expires']} is not a future "
                      "date: set a future expiry or lower the baseline to 0")
    if not rec["owner"].strip():
        errors.append("baseline raised without a recorded owner in "
                      f"{BASELINE_PATH}")
    return errors


def _baseline_deleted(diff: str) -> bool:
    """True when the diff deletes the baseline file outright."""
    lines = diff.splitlines()
    for i, raw in enumerate(lines[:-1]):
        if raw == f"--- a/{BASELINE_PATH}" and lines[i + 1] == "+++ /dev/null":
            return True
    return False


def evaluate(project: Path) -> CheckResult:
    if not git(project, "rev-parse --git-dir").strip():
        raise CheckError(f"{project} is not a git repository")
    base = default_base(project)
    if not git(project, f"rev-parse --verify --quiet {base}").strip():
        raise CheckError(f"base ref {base} is not resolvable in {project}")
    diffs = [git(project, f"diff -U0 {base}...HEAD", check=True),
             git(project, "diff -U0 HEAD", check=True)]
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
    prod_added = {p: lines for p, lines in added.items()
                  if not is_test_file(p)}
    test_added = {p: lines for p, lines in added.items()
                  if is_test_file(p)}
    prod_removed = {p: lines for p, lines in removed.items()
                    if not is_test_file(p)}
    test_removed = {p: lines for p, lines in removed.items()
                    if is_test_file(p)}
    blocks, dup = find_blocks(prod_added, _window_places(prod_removed))
    test_blocks, test_dup = find_blocks(
        test_added, _window_places(test_removed))
    combined, _ = find_blocks(added, _window_places(removed))
    cross = [b for b in combined
             if any(is_test_file(loc["path"]) for loc in b["locations"])
             and any(not is_test_file(loc["path"]) for loc in b["locations"])]
    # The two diffs number lines on different bases (HEAD vs working
    # tree), so each diff's test lines are resolved against its own
    # source: HEAD for the committed diff, disk for the working one.
    test_lines = _qualifying_test_lines(
        _raw_added_test_lines_by_file([diffs[0]]),
        lambda path: _head_source(project, path),
    ) + _qualifying_test_lines(
        _raw_added_test_lines_by_file([diffs[1]]),
        lambda path: _disk_source(project, path),
    )
    # Partial migration needs the base tree: a removed window re-added
    # elsewhere with only one distinct removal is an extraction only
    # when the block was already duplicated before the diff. The
    # base-home leg needs it too: a removed window that survives in the
    # base tree is a shared home the diff may have rewired to, even when
    # the block never appears as added lines. A base location in a
    # removal source counts only when the file holds more base
    # occurrences than were removed from it (occurrence accounting).
    # Read the base tree whenever any window was removed, not only when
    # a removed window is also an added window.
    base_windows: dict[tuple[str, ...], int] = {}
    base_locations: dict[tuple[str, ...], list[Location]] = {}
    removed_set = {
        window for lines in removed.values()
        for _, window in _contiguous_windows(lines)
    }
    if removed_set:
        base_windows, base_locations = _base_tree_window_counts(
            project, base, removed_set)
    dest_symbols = {
        path: syms
        for path in added
        if (syms := _dest_symbols_on_disk(project, path)) is not None
    }
    # Base-home destinations are read at the base ref: a file the diff
    # never touches still holds its base symbols on disk, but a file
    # the diff edits may not, so the base tree is the source of truth.
    for path in {loc["path"] for locs in base_locations.values()
                 for loc in locs}:
        if path not in dest_symbols:
            if (syms := _dest_symbols_at_ref(project, base, path)) is not None:
                dest_symbols[path] = syms
    # The extraction gate sees production code only: a move inside
    # test files is fixture deduplication, not an extraction, the same
    # reason test files are excluded from the ratchet FAIL.
    extraction = find_extractions(
        prod_added, prod_removed, test_lines, base_windows, dest_symbols,
        base_locations)
    today = date.today()
    errors: list[str] = []
    lapsed = ""
    if any(_baseline_deleted(diff) for diff in diffs):
        errors.append(
            f"{BASELINE_PATH} deleted in this diff: lower the baseline to 0 "
            "instead of deleting the record")
    try:
        new_baseline = load_baseline(project)
    except BaselineError as exc:
        errors.append(str(exc))
        new_baseline = {"baseline": 0, "reason": "", "expires": "", "owner": ""}
    if BASELINE_PATH in files:
        # Two judgements, split. The count is judged against the OLD
        # baseline number, so a raise cannot silence its own diff. The
        # metadata (reason, expiry, owner) is judged on the NEW record
        # only, so a diff that lowers or re-justifies an expired baseline
        # is not failed by the record it replaces.
        try:
            old = load_baseline_at_ref(project, base)
        except BaselineError as exc:
            # A malformed record on main is surfaced, not silently
            # replaced with 0: the count is still judged against 0
            # (fail closed), and the error names the repair.
            errors.append(f"baseline at {base} is unreadable: {exc}")
            old = {"baseline": 0, "reason": "", "expires": "", "owner": ""}
        errors.extend(validate_baseline(new_baseline, today))
        effective = old["baseline"]
    elif _baseline_expired(new_baseline, today):
        # An expired raise lapses to 0 instead of blocking clean work: a
        # clean PR passes, and a PR with duplication fails on the count
        # against 0. The record on main stays as written; the next PR that
        # touches the file must lower it or re-justify it.
        lapsed = new_baseline["expires"]
        effective = 0
    else:
        errors.extend(validate_baseline(new_baseline, today))
        effective = new_baseline["baseline"]
    return {
        "added_lines": sum(len(v) for v in added.values()),
        "duplicated_lines": dup,
        "baseline": effective,
        "baseline_lapsed": lapsed,
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
    for b in blocks:
        print(f"  {b['path']}:{b['start_line']}-{b['end_line']} "
              f"({b['lines']} lines): {b['sample']}")
        print(f"    copies: {_fmt_locations(b['locations'])}")


def cmd_check(a: argparse.Namespace) -> int:
    project = Path(a.project).resolve()
    try:
        result = evaluate(project)
    except CheckError as exc:
        print(f"cannot measure duplication: {exc}")
        print("\nVERDICT: FAIL")
        print(f"  [FAIL] cannot measure: {exc}")
        return 1
    print(f"added code lines: {result['added_lines']}")
    print(f"duplicated added lines: {result['duplicated_lines']} "
          f"(baseline: {result['baseline']})")
    _print_blocks("DUPLICATE BLOCKS (abstraction needs a shared-meaning "
                  "justification):", result["blocks"])
    if result["blocks"]:
        print("  (duplicated lines count distinct added lines beyond the "
              "first occurrence of each block, net of lines moved as a "
              "unit: a repeat fully covered by removed occurrences does "
              "not count)")
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
    if result["baseline_lapsed"]:
        print(f"  note: the recorded baseline raise expired on "
              f"{result['baseline_lapsed']} and has lapsed; the count is "
              "judged against 0")
    if result["duplicated_lines"] > result["baseline"]:
        failures.append(
            f"duplicated added lines {result['duplicated_lines']} exceed "
            f"baseline {result['baseline']}"
            + (f" (the recorded raise expired on "
               f"{result['baseline_lapsed']} and has lapsed)"
               if result["baseline_lapsed"] else ""))
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
                  "not this one; a raise permits that many duplicated "
                  "lines in every PR until expiry). Before extracting a "
                  "shared idiom, record why the copies share meaning "
                  "(same concept, same future changes) in the PR "
                  "description; without that justification, keep the "
                  "duplication and raise the baseline instead. "
                  "Extracting a shared idiom will also require a test "
                  "that calls the extracted symbol and asserts on its "
                  "behavior. See "
                  "docs/specs/2026-11-08-dup-ratchet.md")
        if result["extraction"]:
            print("  fix: add a regression test in the diff that calls the "
                  "extracted symbol and asserts on its behavior (a bare "
                  "call, a call in dead code, or a call outside a test "
                  "function does not count). Tests already on main do not "
                  "count: the test must be in the diff. See "
                  "docs/specs/2026-11-08-dup-ratchet.md")
        return 1
    if result["duplicated_lines"] < result["baseline"]:
        print(f"\n  note: duplicated lines are below baseline; the baseline "
              f"can be lowered to {result['duplicated_lines']} in a "
              "follow-up with reason 'lowered after dedup'")
    if result["blocks"] or result["test_blocks"] or result["cross_blocks"] \
            or result["duplicated_lines"] > 0:
        # The verdict line states the ratchet outcome, not the absence
        # of repeats: repeats within the baseline, and repeats the
        # ratchet excludes (test files, cross-copies), are real repeats
        # the old wording denied.
        print(f"\nVERDICT: PASS (duplicated added lines "
              f"{result['duplicated_lines']} within baseline "
              f"{result['baseline']})")
    else:
        print("\nVERDICT: PASS (no byte-identical 6-line repeats in added lines)")
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

    def make_repo(files: dict[str, str],
                  raw: dict[str, bytes] | None = None) -> Path:
        td = tempfile.mkdtemp()
        project = Path(td)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"],
                       cwd=project, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=project, check=True)
        write_files(project, files)
        for path, data in (raw or {}).items():
            p = project / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
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

    def past(days: int = 1) -> str:
        return (date.today() - timedelta(days=days)).isoformat()

    block = "\n".join(f"    value_{i} = compute_{i}(row)" for i in range(6)) + "\n"
    base_files = {"tools/a/one.py": "def f():\n    return 1\n"}

    def repo_with_baseline() -> Path:
        return make_repo({**base_files, BASELINE_PATH: json.dumps(
            {"baseline": 6, "reason": "sibling profile scripts, recorded",
             "expires": future(), "owner": "claude-376-test"})})

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
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_shared.py":
                      "from tools.a.shared import shared\n"})
    code, res = run_check(repo)
    check("extraction with an import-only test still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_shared.py":
                      "shared = 1\n\n\n"
                      "def test_shared():\n    assert shared == 1\n"})
    code, res = run_check(repo)
    check("extraction with a bare-assignment test still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_shared.py":
                      "def test_shared():\n"
                      '    assert "shared" in "shared_name"\n'})
    code, res = run_check(repo)
    check("extraction with a string-mention test still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))

    # 5b. extraction with a direct-import test of a symbol whose name
    #     differs from the destination file stem passes: the gate
    #     matches the extracted symbol, not the file stem.
    dedup_base = {
        "tools/a/one.py": "def f():\n" + extract_body,
        "tools/a/two.py": "def g():\n" + extract_body,
        "tools/a/helpers.py": "def h():\n    return 0\n",
    }
    dedup_pr = {
        "tools/a/one.py": "def f():\n    return dedup()\n",
        "tools/a/two.py": "def g():\n    return dedup()\n",
        "tools/a/helpers.py": "def dedup():\n" + extract_body,
    }
    repo = make_repo(dedup_base)
    commit(repo, {**dedup_pr,
                  "tests/test_helpers.py":
                      "from tools.a.helpers import dedup\n\n\n"
                      "def test_dedup():\n    assert dedup() == 15\n"})
    code, res = run_check(repo)
    check("extraction with a direct-import test of the symbol passes",
          code == 0 and res["extraction"] == [], json.dumps(res))
    # 5c. a bare call with no assertion does not exempt
    repo = make_repo(dedup_base)
    commit(repo, {**dedup_pr,
                  "tests/test_helpers.py":
                      "from tools.a.helpers import dedup\n\n\n"
                      "def test_dedup():\n    dedup()\n"})
    code, res = run_check(repo)
    check("extraction with a bare call and no assertion still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    # 5d. a call under `if False:` never executes and does not exempt
    repo = make_repo(dedup_base)
    commit(repo, {**dedup_pr,
                  "tests/test_helpers.py":
                      "from tools.a.helpers import dedup\n\n\n"
                      "def test_dedup():\n"
                      "    if False:\n        assert dedup() == 15\n"})
    code, res = run_check(repo)
    check("extraction with a call under if False still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    # 5e. a call inside a helper no test calls does not exempt
    repo = make_repo(dedup_base)
    commit(repo, {**dedup_pr,
                  "tests/test_helpers.py":
                      "from tools.a.helpers import dedup\n\n\n"
                      "def helper():\n    return dedup()\n\n\n"
                      "def test_dedup():\n    assert 1 == 1\n"})
    code, res = run_check(repo)
    check("extraction with a call in an uncalled helper still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    # 5f. a unittest-style asserting call exempts
    repo = make_repo(dedup_base)
    commit(repo, {**dedup_pr,
                  "tests/test_helpers.py":
                      "import unittest\n"
                      "from tools.a.helpers import dedup\n\n\n"
                      "class TestDedup(unittest.TestCase):\n"
                      "    def test_dedup(self):\n"
                      "        self.assertEqual(dedup(), 15)\n"})
    code, res = run_check(repo)
    check("extraction with a unittest-style asserting test passes",
          code == 0 and res["extraction"] == [], json.dumps(res))
    # 5g. a test that calls an unrelated symbol does not exempt: the
    #     call qualifies (asserting test function) but matches no
    #     destination symbol.
    repo = make_repo(dedup_base)
    commit(repo, {**dedup_pr,
                  "tests/test_helpers.py":
                      "def test_other():\n    assert other() == 1\n"})
    code, res = run_check(repo)
    check("extraction with a test calling an unrelated symbol still fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))

    # 5h. the two-PR split: the shared home already exists on main, so
    #     the rewiring PR adds no copy of the block, only calls to it.
    #     Without a regression test the gate must still fire.
    split_base = {
        "tools/a/one.py": "def f():\n" + extract_body,
        "tools/a/two.py": "def g():\n" + extract_body,
        "tools/a/shared.py": "def shared():\n" + extract_body,
    }
    split_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/two.py": "def g():\n    return shared()\n",
    }
    repo = make_repo(split_base)
    commit(repo, split_pr)
    code, res = run_check(repo)
    check("rewiring to a shared home already on main fails without a test",
          code == 1 and len(res["extraction"]) == 1
          and res["extraction"][0]["dest"]["path"] == "tools/a/shared.py",
          json.dumps(res))
    repo = make_repo(split_base)
    commit(repo, {**split_pr,
                  "tests/test_shared.py":
                      "from tools.a.shared import shared\n\n\n"
                      "def test_shared():\n    assert shared() == 15\n"})
    code, res = run_check(repo)
    check("rewiring to a shared home with a referencing test passes",
          code == 0 and res["extraction"] == [], json.dumps(res))
    # 5i. one call site rewired: the block still survives in the other
    #     file on main, so the partial-migration shape fires.
    repo = make_repo(split_base)
    commit(repo, {"tools/a/one.py": "def f():\n    return shared()\n"})
    code, res = run_check(repo)
    check("rewiring one call site to an existing home still fails",
          code == 1 and len(res["extraction"]) == 1
          and res["extraction"][0]["dest"]["path"] == "tools/a/shared.py",
          json.dumps(res))
    # 5j. deleting the duplicated block without rewiring to the home is
    #     not an extraction: no call is added, so nothing was consolidated.
    repo = make_repo(split_base)
    commit(repo, {"tools/a/one.py": "def f():\n    return 0\n"})
    code, res = run_check(repo)
    check("deleting a duplicated block without rewiring passes",
          code == 0 and res["extraction"] == [], json.dumps(res))
    # 5k. adding the helper alone (the first PR of the split) passes:
    #     nothing is removed yet, so there is no extraction to gate; the
    #     rewiring PR is the gated step.
    repo = make_repo(extract_base)
    commit(repo, {"tools/a/shared.py": "def shared():\n" + extract_body})
    code, res = run_check(repo)
    check("adding an untested helper with no removal passes",
          code == 0 and res["extraction"] == [], json.dumps(res))
    # 5l. the shared home lives in a file that is itself a removal
    #     source (arch-7 finding 1): one.py holds the block twice
    #     (helper plus f), two.py once. The PR rewires both call sites
    #     to helper() with no test. Occurrence accounting must fire on
    #     the surviving copy in one.py, not skip the file outright.
    holder_base = {
        "tools/a/one.py": ("def helper():\n" + extract_body
                           + "\ndef f():\n" + extract_body),
        "tools/a/two.py": "def g():\n" + extract_body,
    }
    repo = make_repo(holder_base)
    commit(repo, {
        "tools/a/one.py": ("def helper():\n" + extract_body
                           + "\ndef f():\n    return helper()\n"),
        "tools/a/two.py": ("from tools.a.one import helper\n\n\n"
                           "def g():\n    return helper()\n"),
    })
    code, res = run_check(repo)
    check("rewiring to a home housed in a removal source fails",
          code == 1 and len(res["extraction"]) == 1
          and res["extraction"][0]["dest"]["path"] == "tools/a/one.py"
          and res["extraction"][0]["dest"]["start_line"] == 2
          and res["extraction"][0]["dest"]["end_line"] == 8,
          json.dumps(res))
    # 5m. the same consolidation inside a single file passes: the
    #     holder file is the SOLE file the block was removed from, an
    #     in-place edit, not a move.
    repo = make_repo({
        "tools/a/one.py": ("def helper():\n" + extract_body
                           + "\ndef f():\n" + extract_body),
    })
    commit(repo, {
        "tools/a/one.py": ("def helper():\n" + extract_body
                           + "\ndef f():\n    return helper()\n"),
    })
    code, res = run_check(repo)
    check("consolidation inside a single file passes",
          code == 0 and res["extraction"] == [], json.dumps(res))

    # 6. empty diff passes
    repo = make_repo(base_files)
    code, res = run_check(repo)
    check("empty diff passes (no added code lines)",
          code == 0 and res["added_lines"] == 0, json.dumps(res))

    # 7. baseline respected; raised baseline without a reason fails.
    #    The raise must already be on main: a raise inside the diff under
    #    review does not take effect until it merges (case 11).
    repo = repo_with_baseline()
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

    # 12. an expired raise lapses instead of locking the repo
    expired_base = {**base_files, BASELINE_PATH: json.dumps(
        {"baseline": 6, "reason": "sibling scripts, recorded",
         "expires": past(), "owner": "claude-376-test"})}
    # (a) re-justifying with a future expiry passes, judged vs old number 6
    repo = make_repo(expired_base)
    commit(repo, {
        BASELINE_PATH: json.dumps(
            {"baseline": 6, "reason": "re-justified",
             "expires": future(), "owner": "claude-376-test"}),
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("re-justifying an expired baseline passes",
          code == 0 and res["baseline"] == 6, json.dumps(res))
    # (b) lowering to 0 passes
    repo = make_repo(expired_base)
    commit(repo, {
        BASELINE_PATH: json.dumps(
            {"baseline": 0, "reason": "lowered after expiry",
             "expires": "", "owner": ""}),
    })
    code, res = run_check(repo)
    check("lowering an expired baseline to 0 passes",
          code == 0, json.dumps(res))
    # (c) an unrelated clean PR passes with an expired baseline on main
    repo = make_repo(expired_base)
    commit(repo, {"tools/a/clean.py": "def c():\n    return 2\n"})
    code, res = run_check(repo)
    check("clean PR passes with an expired baseline on main",
          code == 0 and res["baseline_lapsed"] != "", json.dumps(res))
    # (d) a PR with duplication and no baseline change fails vs lapsed 0
    repo = make_repo(expired_base)
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, res = run_check(repo)
    check("duplication with a lapsed baseline fails against 0",
          code == 1 and res["baseline"] == 0
          and res["baseline_lapsed"] != "", json.dumps(res))

    # 13. a new record with a past expiry fails
    repo = make_repo(base_files)
    commit(repo, {
        BASELINE_PATH: json.dumps(
            {"baseline": 6, "reason": "raise with a past expiry",
             "expires": past(), "owner": "claude-376-test"}),
    })
    code, res = run_check(repo)
    check("new baseline record with a past expiry fails",
          code == 1 and len(res["baseline_errors"]) > 0, json.dumps(res))

    # 13b. a new record expiring today fails: the expiry must be future.
    repo = make_repo(base_files)
    commit(repo, {
        BASELINE_PATH: json.dumps(
            {"baseline": 6, "reason": "raise expiring today",
             "expires": date.today().isoformat(),
             "owner": "claude-376-test"}),
    })
    code, res = run_check(repo)
    check("new baseline record expiring today fails",
          code == 1 and len(res["baseline_errors"]) > 0, json.dumps(res))

    # 14. deleting the baseline file fails closed
    repo = make_repo({**base_files, BASELINE_PATH: json.dumps(
        {"baseline": 0, "reason": "", "expires": "", "owner": ""})})
    (repo / BASELINE_PATH).unlink()
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "delete baseline"],
                   cwd=repo, check=True)
    code, res = run_check(repo)
    check("deleting the baseline file fails closed",
          code == 1 and len(res["baseline_errors"]) > 0, json.dumps(res))

    # 14b. a malformed record on main is surfaced, not silently
    #      replaced with 0, when the PR touches the file with a valid
    #      record.
    repo = make_repo({**base_files, BASELINE_PATH: "{not json"})
    commit(repo, {
        BASELINE_PATH: json.dumps(
            {"baseline": 0, "reason": "repair",
             "expires": "", "owner": "claude-376-test"}),
    })
    code, res = run_check(repo)
    check("malformed baseline on main is surfaced when the file is touched",
          code == 1 and len(res["baseline_errors"]) > 0, json.dumps(res))

    # 15. partial migration: the block is removed from ONE of two files
    #    and re-added as a shared home, with no test, while the second
    #    copy survives outside the diff. The base tree shows the block
    #    was duplicated before the diff, so the extraction gate fires;
    #    a calling test exempts it.
    partial_base = {
        "tools/a/one.py": "def f():\n" + extract_body,
        "tools/a/two.py": "def g():\n" + extract_body,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    partial_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n" + extract_body,
    }
    repo = make_repo(partial_base)
    commit(repo, partial_pr)
    code, res = run_check(repo)
    check("partial migration without a test fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))
    repo = make_repo(partial_base)
    commit(repo, {**partial_pr,
                  "tests/test_shared.py":
                      "from tools.a.shared import shared\n\n\n"
                      "def test_shared():\n    assert shared() == 15\n"})
    code, res = run_check(repo)
    check("partial migration with a calling test passes",
          code == 0 and res["extraction"] == [], json.dumps(res))

    # 15b. partial migration where the surviving copy lives only in a
    #      test file: the base-tree count covers production code only,
    #      so the move is not an extraction and passes with no test.
    partial_test_base = {
        "tools/a/one.py": "def f():\n" + extract_body,
        "tests/test_fixture.py": extract_body,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    repo = make_repo(partial_test_base)
    commit(repo, partial_pr)
    code, res = run_check(repo)
    check("partial migration with only a test-file copy surviving passes",
          code == 0 and res["extraction"] == [], json.dumps(res))

    # 16. consolidation into an existing holder file: the block is
    #    removed from two files and re-added in one of them (the holder),
    #    with no test. The holder's copy is reindented under the new
    #    `def shared():`, so the raw diff shows it removed and re-added
    #    (normalization collapses the indent, so it is the same window).
    #    The destination is a removal source, but not the sole one, so
    #    the gate fires.
    holder_base = {
        "tools/a/one.py": "def f():\n" + extract_body,
        "tools/a/two.py": "def g():\n    if True:\n"
        + "".join("        " + line.lstrip() + "\n"
                  for line in extract_body.splitlines()) + "",
    }
    holder_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/two.py": "def shared():\n" + extract_body,
    }
    repo = make_repo(holder_base)
    commit(repo, holder_pr)
    code, res = run_check(repo)
    check("consolidation into an existing holder without a test fails",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))

    # 17. a check that cannot obtain a diff fails closed, not vacuously
    td = tempfile.mkdtemp()
    code = cmd_check(argparse.Namespace(project=td))
    check("check outside a git repository fails closed",
          code == 1, "")

    # 18. seven identical consecutive lines removed once and re-added
    #    elsewhere are one occurrence, not two overlapping windows, so
    #    the extraction gate does not fire on a single removal.
    seven = "".join("    pass\n" for _ in range(7))
    seven_base = {
        "tools/a/one.py": "def f():\n" + seven,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    seven_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n" + seven,
    }
    repo = make_repo(seven_base)
    commit(repo, seven_pr)
    code, res = run_check(repo)
    check("single removal of 7 identical lines is not an extraction",
          res["extraction"] == [], json.dumps(res))

    # 18b. twelve identical consecutive lines removed once and re-added
    #     elsewhere are one occurrence, not two non-overlapping windows,
    #     so the extraction gate does not fire on a single removal.
    twelve = "".join("    pass\n" for _ in range(12))
    twelve_base = {
        "tools/a/one.py": "def f():\n" + twelve,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    twelve_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n" + twelve,
    }
    repo = make_repo(twelve_base)
    commit(repo, twelve_pr)
    code, res = run_check(repo)
    check("single removal of 12 identical lines is not an extraction",
          res["extraction"] == [], json.dumps(res))

    # 19. twelve identical lines in ONE new file are one place, not a
    #     duplicate: there is no second copy anywhere.
    repo = make_repo(base_files)
    commit(repo, {"tools/a/two.py": "def g():\n" + twelve})
    code, res = run_check(repo)
    check("twelve identical lines in one new file are not a duplicate",
          code == 0 and res["duplicated_lines"] == 0, json.dumps(res))

    # 19b. the same run in two files counts 12, not 23 overlapping
    #      windows.
    repo = make_repo(base_files)
    commit(repo, {
        "tools/a/two.py": "def g():\n" + twelve,
        "tools/a/three.py": "def h():\n" + twelve,
    })
    code, res = run_check(repo)
    check("twelve identical lines in two files count 12",
          code == 1 and res["duplicated_lines"] == 12, json.dumps(res))

    # 19c. seven identical lines in two files count 7.
    repo = make_repo(base_files)
    commit(repo, {
        "tools/a/two.py": "def g():\n" + seven,
        "tools/a/three.py": "def h():\n" + seven,
    })
    code, res = run_check(repo)
    check("seven identical lines in two files count 7",
          code == 1 and res["duplicated_lines"] == 7, json.dumps(res))

    # 20. the same 3 lines added in two places in each of two files do
    #     not form a 6-line block: the lines were never consecutive.
    phantom_base = {
        "tools/a/one.py": "def f1():\n    return 1\n\n\ndef f2():\n    return 2\n",
        "tools/a/two.py": "def g1():\n    return 1\n\n\ndef g2():\n    return 2\n",
    }
    three = "    x = 1\n    y = 2\n    z = 3\n"
    phantom_pr = {
        "tools/a/one.py": "def f1():\n" + three + "    return 1\n\n\ndef f2():\n" + three + "    return 2\n",
        "tools/a/two.py": "def g1():\n" + three + "    return 1\n\n\ndef g2():\n" + three + "    return 2\n",
    }
    repo = make_repo(phantom_base)
    commit(repo, phantom_pr)
    code, res = run_check(repo)
    check("lines added in two separate hunks do not form a block",
          code == 0 and res["duplicated_lines"] == 0, json.dumps(res))

    # 20b. the same 6 lines removed in two halves around a kept line
    #      and re-added contiguously are not an extraction: the block
    #      never existed contiguously in any file.
    split_base = {
        "tools/a/one.py": "def f():\n    v0 = 0\n    v1 = 1\n    v2 = 2\n    keep = 1\n    v3 = 3\n    v4 = 4\n    v5 = 5\n",
        "tools/a/two.py": "def g():\n    v0 = 0\n    v1 = 1\n    v2 = 2\n    keep = 2\n    v3 = 3\n    v4 = 4\n    v5 = 5\n",
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    split_pr = {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/two.py": "def g():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n    v0 = 0\n    v1 = 1\n    v2 = 2\n    v3 = 3\n    v4 = 4\n    v5 = 5\n",
    }
    repo = make_repo(split_base)
    commit(repo, split_pr)
    code, res = run_check(repo)
    check("lines removed in two halves are not an extraction",
          code == 0 and res["extraction"] == [], json.dumps(res))

    # 21. a pure move of a function containing a 6-line stanza twice
    #     passes both gates: the repeat predates the diff, nothing was
    #     extracted, and the ratchet is net-new.
    stanza = (
        "    if row is None:\n"
        "        continue\n"
        "    total += 1\n"
        "    total += 2\n"
        "    total += 3\n"
        "    total += 4\n"
    )
    move_base = {
        "tools/a/old.py": "def process():\n" + stanza + "    out = []\n" + stanza,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }
    move_pr = {
        "tools/a/old.py": "def process():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n" + stanza + "    out = []\n" + stanza,
    }
    repo = make_repo(move_base)
    commit(repo, move_pr)
    code, res = run_check(repo)
    check("pure move of a function with an internal repeat passes",
          code == 0 and res["duplicated_lines"] == 0
          and res["extraction"] == [], json.dumps(res))

    # 22. moving a fixture block between test files is not an
    #     extraction: test files are excluded from the gate, the same
    #     reason they are excluded from the ratchet FAIL.
    fixture_base = {
        "tests/test_one.py": "def test_one():\n" + block,
        "tests/test_two.py": "def test_two():\n" + block,
        "tests/helpers.py": "def h():\n    return 0\n",
    }
    fixture_pr = {
        "tests/test_one.py": "def test_one():\n    return helper()\n",
        "tests/test_two.py": "def test_two():\n    return helper()\n",
        "tests/helpers.py": "def helper():\n" + block,
    }
    repo = make_repo(fixture_base)
    commit(repo, fixture_pr)
    code, res = run_check(repo)
    check("moving a fixture block between test files is not an extraction",
          code == 0 and res["extraction"] == [], json.dumps(res))

    # 23. a base-tree code file that cannot be decoded as UTF-8 fails
    #     closed instead of silently skipping the file: the
    #     partial-migration verdict must not rest on a partial read.
    #     The latin-1 file is written as bytes into the BASE commit:
    #     amending the base commit would orphan main and the diff
    #     itself would fail with "no merge base" instead.
    import io
    from contextlib import redirect_stdout
    repo = make_repo({
        "tools/a/one.py": "def f():\n" + extract_body,
        "tools/a/shared.py": "def s():\n    return 0\n",
    }, raw={
        "tools/a/two.py":
            ("def g():  # caf\xe9\n" + extract_body).encode("latin-1"),
    })
    commit(repo, {
        "tools/a/one.py": "def f():\n    return shared()\n",
        "tools/a/shared.py": "def shared():\n" + extract_body,
    })
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cmd_check(argparse.Namespace(project=str(repo)))
    check("non-UTF8 base-tree file fails closed",
          code == 1 and "cannot measure" in buf.getvalue(),
          buf.getvalue()[:400])

    # 24. uncommitted padding above a calling test does not void the
    #     exemption: the committed diff's lines are resolved against
    #     HEAD, the working diff's against the file on disk.
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_shared.py":
                      "from tools.a.shared import shared\n\n\n"
                      "def test_shared():\n    assert shared() == 15\n"})
    test_path = repo / "tests/test_shared.py"
    text = test_path.read_text(encoding="utf-8")
    test_path.write_text(
        text.replace("def test_shared():",
                     "# pad\n# pad\n# pad\ndef test_shared():"),
        encoding="utf-8")
    code, res = run_check(repo)
    check("dirty-tree padding above a calling test still exempts",
          code == 0 and res["extraction"] == [], json.dumps(res))

    # 25. a document named like a test does not exempt an extraction:
    #     only code files supply test lines.
    repo = make_repo(extract_base)
    commit(repo, {**extract_pr,
                  "tests/test_notes.md":
                      "# notes\n\n```python\nassert shared() == 15\n```\n"})
    code, res = run_check(repo)
    check("a test-named Markdown note does not exempt an extraction",
          code == 1 and len(res["extraction"]) > 0, json.dumps(res))

    # 26. a column-0 `++` line is content, not a diff header: two .js
    #     files adding the same 6-line block starting with `++count;`
    #     fail the ratchet. The files hold ONLY the block: a trailing
    #     line would supply the sixth window line even if `++count;`
    #     were dropped, and the pin would not pin anything.
    plus_block = (
        "++count;\n"
        "    step_a(x);\n"
        "    step_b(x);\n"
        "    step_c(x);\n"
        "    step_d(x);\n"
        "    step_e(x);\n"
    )
    repo = make_repo(base_files)
    commit(repo, {
        "tools/a/one.js": plus_block,
        "tools/a/two.js": plus_block,
    })
    code, res = run_check(repo)
    check("column-0 ++ lines are content and the repeat fails",
          code == 1 and res["duplicated_lines"] >= 6, json.dumps(res))

    # 27. the PASS line states the ratchet outcome: repeats within the
    #     baseline, and repeats the ratchet excludes, are real repeats
    #     the old wording denied.
    def check_output(project: Path) -> tuple[int, str]:
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            out_code = cmd_check(argparse.Namespace(project=str(project)))
        return out_code, out_buf.getvalue()

    # 27a. repeats at the baseline pass, and the line says so.
    repo = repo_with_baseline()
    commit(repo, {
        "tools/a/two.py": "def g():\n" + block,
        "tools/a/three.py": "def h():\n" + block,
    })
    code, out = check_output(repo)
    check("PASS line states the ratchet outcome at the baseline",
          code == 0 and "within baseline" in out
          and "no byte-identical 6-line repeats" not in out, out[-400:])
    # 27b. a clean PR with no repeats keeps the no-repeats line.
    repo = make_repo(base_files)
    commit(repo, {"tools/a/clean.py": "def c():\n    return 2\n"})
    code, out = check_output(repo)
    check("PASS line keeps the no-repeats wording with no repeats",
          code == 0 and "no byte-identical 6-line repeats" in out,
          out[-400:])

    print("\nVERDICT: {}".format(
        "duplication on changed lines is reported, the ratchet holds, and "
        "extraction needs asserting tests" if rc == 0 else "selftest has failures above"))
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
