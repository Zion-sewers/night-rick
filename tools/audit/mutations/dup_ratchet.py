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
        "    extraction = find_extractions(added, removed, test_lines, "
        "base_windows)",
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
        "            if _references_dest(test_lines, apath):\n"
        "                continue",
        "            if False:  # reference check dropped\n"
        "                continue",
    ),
    (
        "import alone exempts again",
        "The call-only rule gains an import branch, so a test file "
        "that merely imports the destination module exempts an "
        "extraction it never calls. The flipped selftest case (an "
        "import-only test still fails) must catch this.",
        "        if call.search(line) or attr.search(line):\n"
        "            return True",
        "        if call.search(line) or attr.search(line) \\\n"
        "                or line.strip().startswith((\"import \", \"from \")):\n"
        "            return True",
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
]
