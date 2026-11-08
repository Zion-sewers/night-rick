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
        '    if result["duplicated_lines"] > result["baseline"]:',
        "    if False:  # baseline ignored",
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
        "    extraction = find_extractions(added, removed, sorted(files))",
        "    extraction = []",
    ),
    (
        "test-file exemption swallowed, extraction always fails",
        "The return drops the `else []`, so an extraction WITH tests in the "
        "diff still fails. This is the fail-closed direction, and it must "
        "still be caught: a gate that cries wolf on every tested extraction "
        "gets disabled, which is the same loss as the gate that never fires.",
        "    return sorted(set(hits)) if not any(is_test_file(f) for f in files) else []",
        "    return sorted(set(hits))",
    ),
    (
        "test-file exclusion dropped, fixtures trip the ratchet",
        "evaluate() stops splitting test streams out, so the repeated "
        "fixture setup every test file carries counts toward the ratchet "
        "and a test-only diff fails.",
        "    blocks, dup = find_blocks(\n"
        "        {p: lines for p, lines in added.items() if not is_test_file(p)})\n"
        "    test_blocks, test_dup = find_blocks(\n"
        "        {p: lines for p, lines in added.items() if is_test_file(p)})",
        "    blocks, dup = find_blocks(added)\n"
        "    test_blocks, test_dup = [], 0",
    ),
    (
        "missing baseline defaults to 999",
        "A project with no baseline file reads as baseline 999 instead of "
        "0, so the first duplicated diff in a fresh checkout passes.",
        '        return {"baseline": 0, "reason": ""}',
        '        return {"baseline": 999, "reason": "x"}',
    ),
]
