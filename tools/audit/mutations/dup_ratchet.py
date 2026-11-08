"""Mutation spec for tools/audit/dup_ratchet.py.

This tool's output is a gate verdict. Every failure mode here ends with a
duplicated block, an untested extraction, or a baseless baseline raise
passing the gate, which is the one direction that cannot be undone by
re-running the check: the PR merges and the duplication is in main.
"""

TARGET = "tools/audit/dup_ratchet.py"
ARGV = ["selftest"]

MUTATIONS = [
    (
        "threshold ignored, every repeat passes",
        "WINDOW jumps from 6 to 100, so the 6-line repeat the selftest "
        "plants no longer forms a window and the ratchet passes a diff it "
        "was built to fail.",
        "WINDOW = 6",
        "WINDOW = 100",
    ),
    (
        "baseline ignored, the ratchet never fires",
        "The duplicated-lines-vs-baseline comparison becomes `if False`, "
        "so a diff over baseline passes and the ratchet is decoration.",
        '    if result["duplicated_lines"] > result["baseline"]:\n'
        '        failures.append(',
        "    if False:  # baseline ignored\n"
        "        failures.append(",
    ),
    (
        "duplicate lines undercounted to one per window",
        "Only the window start is marked instead of all six lines, so a "
        "6-line repeat counts as 1 duplicated line and stays under any "
        "baseline that matters.",
        "        for path, i in locs[1:]:\n"
        "            for j in range(i, i + WINDOW):\n"
        "                marked.add((path, j))",
        "        for path, i in locs[1:]:\n"
        "            marked.add((path, i))",
    ),
    (
        "extraction gate dropped",
        "find_extractions is replaced with an empty list, so a cross-module "
        "extraction with no regression tests in the diff passes.",
        "    extraction = find_extractions(\n"
        "        added, removed, test_lines, base_windows, dest_symbols)",
        "    extraction = []",
    ),
    (
        "reference requirement dropped, any test file exempts",
        "The destination-reference check returns True on the first test "
        "line, so an extraction with any test file in the diff passes, "
        "however unrelated. This is the exact hole the first review round "
        "proved with an unrelated test_other.py.",
        "    for raw in test_lines:\n"
        "        line = _strip_code_text(raw)",
        "    for raw in test_lines:\n"
        "        return True",
    ),
    (
        "reference loosened to a substring",
        "The call/attribute match becomes a bare substring test, so a "
        "test that only assigns `shared = 1`, mentions the stem in a "
        "string, or uses a variable like `shared_cache` exempts an "
        "extraction it never tests.",
        "        if call.search(line) or attr.search(line):",
        "        if stem in line:",
    ),
    (
        "old-baseline rule dropped, a raise silences its own diff",
        "evaluate() judges against the working-tree baseline instead of "
        "the baseline at the base ref, so a PR can raise the baseline and "
        "add the duplication in one diff and pass.",
        "            old = load_baseline_at_ref(project, base)",
        "            old = new_baseline",
    ),
    (
        "expiry never lapses, an expired raise stays in force",
        "The expiry comparison always returns False, so an expired "
        "baseline keeps its old value forever: a PR with duplication and "
        "no baseline change passes against the dead raise, and the lapse "
        "never happens.",
        "        return rec[\"baseline\"] > 0 \\\n"
        "            and date.fromisoformat(rec[\"expires\"]) < today",
        "        return False",
    ),
    (
        "reference check dropped, extraction always fails",
        "The exemption call becomes `if False`, so an extraction WITH a "
        "test referencing the module still fails. This is the fail-closed "
        "direction, and it must still be caught: a gate that cries wolf on "
        "every tested extraction gets disabled, which is the same loss as "
        "the gate that never fires.",
        "            if _references_dest(test_lines, apath, syms):\n"
        "                continue",
        "            if False:  # reference check dropped\n"
        "                continue",
    ),
    (
        "test-function filter dropped, any test line exempts",
        "The AST filter is bypassed, so every added test line reaches "
        "the reference check: a bare call, a call under `if False:`, or "
        "a call in an uncalled helper exempts an extraction it never "
        "characterizes. The flipped selftest cases (a bare call, a call "
        "under if False, a call in an uncalled helper still fail) must "
        "catch this. This replaces the old import-branch mutation: an "
        "import line can no longer reach the matcher at all, so the "
        "import-only rejection is enforced by this filter, not by the "
        "regex.",
        "        lines.extend(raw for raw, n in entries if n in ok)",
        "        lines.extend(raw for raw, _ in entries)  # filter dropped",
    ),
    (
        "partial migration ignored, base tree unread",
        "The base-tree occurrence clause is dropped, so a block "
        "removed from one of two files and re-added as a shared home "
        "passes with no test: the surviving copy is invisible to a "
        "diff-only detector, which is exactly the hole the base-tree "
        "read closes.",
        "        if len(removed_positions[window]) < 2 \\\n"
        "                and base_counts.get(window, 0) < 2:\n"
        "            continue",
        "        if len(removed_positions[window]) < 2:\n"
        "            continue",
    ),
    (
        "test files counted in the base tree again",
        "The base-tree count includes test files, so a production move "
        "whose only surviving copy is a test-file fixture fails the "
        "extraction gate for lack of a test the surviving copy already "
        "supplies. The flipped selftest case (a move with only a "
        "test-file copy surviving passes) must catch this.",
        "            if not member.isfile() or not is_code(member.name) \\\n"
        "                    or is_test_file(member.name):\n"
        "                continue",
        "            if not member.isfile() or not is_code(member.name):\n"
        "                continue  # test files counted",
    ),
    (
        "one identical run counted as two sources",
        "The run collapse is dropped, so twelve identical lines moved "
        "as a unit count as two non-overlapping windows and a "
        "single-site move is reported as a two-source extraction. The "
        "flipped selftest case (a single removal of 12 identical "
        "lines is not an extraction) must catch this.",
        "        if taken and all(\n"
        "                line == lines[taken[-1]]\n"
        "                for line in lines[taken[-1]:s + WINDOW]):\n"
        "            continue",
        "        if False:  # run collapse dropped\n            continue",
    ),
    (
        "holder consolidation skipped again",
        "The destination skip goes back to exempting any destination "
        "that is also a removal source, so consolidating duplicated "
        "code into an existing holder file passes with no test.",
        "            if rpaths == {apath}:\n"
        "                continue",
        "            if apath in rpaths:\n"
        "                continue",
    ),
    (
        "missing baseline defaults to 999",
        "A project with no baseline file reads as baseline 999 instead of "
        "0, so the first duplicated diff in a fresh checkout passes.",
        '    if not p.exists():\n'
        '        return {"baseline": 0, "reason": "", "expires": "", "owner": ""}',
        '    if not p.exists():\n'
        '        return {"baseline": 999, "reason": "x", "expires": "", "owner": ""}',
    ),
    (
        "assert requirement dropped, a bare call exempts",
        "The assert requirement is dropped, so a bare call with no "
        "assertion qualifies as a regression test and an extraction with "
        "a vacuous test passes. The flipped selftest case (a bare call "
        "still fails) must catch this.",
        "        if asserted:\n            qualifying.update(calls)",
        "        if True:  # assert requirement dropped\n"
        "            qualifying.update(calls)",
    ),
    (
        "symbol matching dropped to stem-only",
        "The destination-symbol map is emptied, so every destination "
        "falls back to the stem rule and a direct-import test of a symbol "
        "whose name differs from the file stem no longer exempts. The "
        "flipped selftest case (a direct-import test of the symbol "
        "passes) must catch this.",
        "    dest_symbols = {\n        path: syms\n"
        "        for path in added\n"
        "        if (syms := _dest_symbols_on_disk(project, path)) is not None\n"
        "    }",
        "    dest_symbols = {}  # symbol matching dropped",
    ),
    (
        "dead branches count as live",
        "The constant-truth check never runs, so every branch reads as "
        "live and a call under `if False:` qualifies as a regression "
        "test. The flipped selftest case (a call under if False still "
        "fails) must catch this.",
        "    if isinstance(node, ast.Constant):\n        value = node.value",
        "    if False:  # dead-branch check dropped\n        value = node.value",
    ),
]
