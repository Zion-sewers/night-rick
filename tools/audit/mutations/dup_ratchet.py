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
        "            for p, idx in locs[free:]:\n"
        "                for k in range(idx, idx + span):\n"
        "                    marked.add((p, k))",
        "            for p, idx in locs[free:]:\n"
        "                marked.add((path, idx))  # one line per place",
    ),
    (
        "extraction gate dropped",
        "find_extractions is replaced with an empty list, so a cross-module "
        "extraction with no regression tests in the diff passes.",
        "    extraction = find_extractions(\n"
        "        prod_added, prod_removed, test_lines, base_windows, dest_symbols,\n"
        "        base_locations)",
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
    (
        "net rule dropped, a pure move fails the ratchet",
        "The free-place count ignores removed places, so a repeat whose "
        "added occurrences are fully covered by removed occurrences "
        "counts as new duplication and a pure move fails the gate. The "
        "flipped selftest case (a pure move of a function with an "
        "internal repeat passes) must catch this.",
        "        return max(1, len(removed_places.get(window, [])))",
        "        return 1  # net rule dropped",
    ),
    (
        "contiguity dropped, phantom windows fire",
        "The window check accepts any 6 stream entries, so lines added "
        "in two separate hunks concatenate into a block that never "
        "existed in any file and the gate fails clean diffs. The "
        "flipped selftest case (lines added in two separate hunks do "
        "not form a block) must catch this.",
        "    if lines[i + WINDOW - 1][1] - lines[i][1] != WINDOW - 1:\n"
        "        return None",
        "    if False:  # contiguity dropped\n"
        "        return None",
    ),
    (
        "consolidation rule dropped, a move that consolidates nothing fires",
        "The destination-occurrence check is dropped, so a function "
        "moved whole with its internal repeat still inside it fires "
        "the extraction gate even though nothing was consolidated. The "
        "flipped selftest case (a pure move of a function with an "
        "internal repeat passes) must catch this.",
        "                if dest_occ >= len(removed_positions[window]):\n"
        "                    continue",
        "                if False:  # consolidation dropped\n"
        "                    continue",
    ),
    (
        "test files reach the extraction gate again",
        "The production-only filter is dropped, so moving a fixture "
        "block between test files fires the extraction gate even though "
        "the ratchet excludes test files for the same reason. The "
        "flipped selftest case (moving a fixture block between test "
        "files is not an extraction) must catch this.",
        "    extraction = find_extractions(\n"
        "        prod_added, prod_removed, test_lines, base_windows, dest_symbols,\n"
        "        base_locations)",
        "    extraction = find_extractions(\n"
        "        added, removed, test_lines, base_windows, dest_symbols,\n"
        "        base_locations)",
    ),
    (
        "non-UTF8 base file silently skipped again",
        "The decode failure is swallowed, so a partial-migration "
        "verdict rests on a partially read base tree and a move that "
        "should fail closed passes. The flipped selftest case (a "
        "non-UTF8 base-tree file fails closed) must catch this.",
        "            except UnicodeDecodeError:\n"
        "                raise CheckError(\n"
        "                    f\"cannot read the base tree at {base}: \"\n"
        "                    f\"{member.name} is not UTF-8\")",
        "            except UnicodeDecodeError:\n"
        "                continue  # unread file skipped",
    ),
    (
        "per-diff source resolution dropped, committed lines read from disk",
        "The committed diff's test lines are resolved against the "
        "working tree instead of HEAD, so uncommitted padding above a "
        "calling test voids a valid exemption and the gate fails a "
        "tested extraction. The flipped selftest case (dirty-tree "
        "padding above a calling test still exempts) must catch this.",
        "        lambda path: _head_source(project, path),",
        "        lambda path: _disk_source(project, path),",
    ),
    (
        "prose test lines exempt an extraction",
        "The code-file filter is dropped from the raw test-line "
        "collector, so a document named like a test exempts an "
        "extraction with a line of prose. The flipped selftest case "
        "(a test-named Markdown note does not exempt an extraction) "
        "must catch this.",
        '            if kind == "added" and is_test_file(path) and is_code(path):',
        '            if kind == "added" and is_test_file(path):',
    ),
    (
        "diff header guards loosened to bare prefixes",
        "The header guard matches bare `+++` again, so a content line "
        "starting with `++` at column 0 is dropped as a header and the "
        "repeat it belonged to passes the gate. The flipped selftest "
        "case (column-0 ++ lines are content and the repeat fails) must "
        "catch this.",
        '                and not raw.startswith("+++ "):',
        '                and not raw.startswith("+++"):',
    ),
    (
        "PASS line claims no repeats when repeats exist",
        "The verdict line goes back to asserting there are no "
        "byte-identical repeats whenever the gate passes, which is "
        "false on every passing PR at a nonzero baseline. The flipped "
        "selftest case (PASS line states the ratchet outcome at the "
        "baseline) must catch this.",
        "        print(f\"\\nVERDICT: PASS (duplicated added lines \"\n"
        "              f\"{result['duplicated_lines']} within baseline \"\n"
        "              f\"{result['baseline']})\")",
        "        print(\"\\nVERDICT: PASS (no byte-identical 6-line repeats \"\n"
        "              \"in added lines)\")",
    ),
    (
        "run collapse dropped in the ratchet leg",
        "The ratchet leg stops collapsing overlapping window starts "
        "inside one maximal run, so twelve identical lines in one file "
        "count as duplication with no second copy anywhere. The "
        "flipped selftest case (twelve identical lines in one new "
        "file are not a duplicate) must catch this.",
        "            for s in _distinct_starts(idxs, [t for t, _ in lines]):\n"
        "                places[window].append((path, s))",
        "            for s in idxs:  # run collapse dropped\n"
        "                places[window].append((path, s))",
    ),
    (
        "base-home leg dropped, a two-PR split passes",
        "find_extractions never walks the base-tree locations, so a PR "
        "that rewires call sites to a helper already on main passes "
        "with no regression test: the gate only fires when the removed "
        "block also appears as added lines in the same diff. The "
        "flipped selftest case (rewiring to a shared home already on "
        "main fails without a test) must catch this.",
        "        for bloc in base_locs.get(window, []):",
        "        for bloc in []:  # base-home leg dropped",
    ),
]
