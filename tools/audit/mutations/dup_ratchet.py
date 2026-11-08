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
        "    extraction = find_extractions(added, removed, test_lines)",
        "    extraction = []",
    ),
    (
        "reference requirement dropped, any test file exempts",
        "The destination-reference check always returns True, so an "
        "extraction with no test file at all, or with an unrelated test "
        "file, passes. This is the exact hole the first review round "
        "proved with an unrelated test_other.py.",
        "    stem = Path(dest).stem\n"
        "    return any(stem in line for line in test_lines)",
        "    stem = Path(dest).stem\n"
        "    return True",
    ),
    (
        "old-baseline rule dropped, a raise silences its own diff",
        "evaluate() judges against the working-tree baseline instead of "
        "the baseline at the base ref, so a PR can raise the baseline and "
        "add the duplication in one diff and pass.",
        "            effective = load_baseline_at_ref(project, base)",
        "            effective = new_baseline",
    ),
    (
        "reference check dropped, extraction always fails",
        "The exemption call becomes `if False`, so an extraction WITH a "
        "test referencing the module still fails. This is the fail-closed "
        "direction, and it must still be caught: a gate that cries wolf on "
        "every tested extraction gets disabled, which is the same loss as "
        "the gate that never fires.",
        "            if _references_dest(test_lines, apath):\n"
        "                continue",
        "            if False:  # reference check dropped\n"
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
]
