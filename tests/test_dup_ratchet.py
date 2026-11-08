"""Oracle for tools/audit/dup_ratchet.py: changed-line duplication reporting.

The instruction was "duplication on the diff, with a ratchet on new code"
(night-rick#376). The rule these checks pin is not "a report exists" but
"the count is the added lines that repeat, the ratchet holds, extraction
needs tests, and nothing that is not textually identical ever fires".

Two failure modes get their own checks because both are the live risk here:

  - A similarity score would fire on same-looking code that encodes
    different concepts. normalize() keeps identifiers and literals, so a
    block that differs in a name or a value is not a duplicate, and
    test_same_shape_different_identifiers_passes pins that.
  - Overlapping windows would double-count one long repeat into several
    short ones. find_blocks() marks distinct lines, so a 12-line repeat
    counts 12 duplicated lines in one block, and
    test_long_repeat_counts_distinct_lines pins that.
  - A pure move counts nothing: find_blocks() takes the removed places,
    so a repeat fully covered by removed occurrences is net-new
    duplication of zero, and a window spanning a hunk boundary or a
    dropped line is not a block at all.
  - A test that calls the wrong name, or never really runs, would exempt
    an extraction it never characterizes. _qualifying_call_lines() admits
    only calls inside an asserting test function, and _references_dest()
    matches the destination's defined symbols, so a direct-import test of
    a symbol whose name differs from the file stem exempts while a bare
    call, a call under `if False:`, and a call in an uncalled helper do
    not.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "audit" / "dup_ratchet.py"


def _load():
    spec = importlib.util.spec_from_file_location("dup_ratchet_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


D = _load()

BLOCK = [f"    value_{i} = compute_{i}(row)" for i in range(6)]


def _diff_for(files: dict[str, list[str]]) -> str:
    """A -U0 style diff adding the given normalized lines per file."""
    out = []
    for path, lines in files.items():
        out.append(f"diff --git a/{path} b/{path}")
        out.append(f"+++ b/{path}")
        out.append(f"@@ -0,0 +1,{len(lines) + 1} @@")
        out.append("+def f():")
        out.extend("+" + line for line in lines)
    return "\n".join(out) + "\n"


class TestNormalize(unittest.TestCase):
    def test_blank_and_full_line_comments_dropped(self):
        self.assertIsNone(D.normalize("", "a.py"))
        self.assertIsNone(D.normalize("   ", "a.py"))
        self.assertIsNone(D.normalize("# a note", "a.py"))
        self.assertIsNone(D.normalize("// a note", "a.ts"))

    def test_imports_and_docstring_fences_dropped(self):
        self.assertIsNone(D.normalize("import json", "a.py"))
        self.assertIsNone(D.normalize("from pathlib import Path", "a.py"))
        self.assertIsNone(D.normalize('"""', "a.py"))

    def test_trailing_comment_kept_so_it_still_differs(self):
        # Conservative by design: a trailing comment is part of the text.
        # Two lines differing only there do NOT match.
        self.assertEqual(
            D.normalize("x = 1  # one", "a.py"), "x = 1 # one")
        self.assertNotEqual(
            D.normalize("x = 1  # one", "a.py"),
            D.normalize("x = 1  # two", "a.py"))

    def test_whitespace_collapsed(self):
        self.assertEqual(
            D.normalize("    x   =   1", "a.py"),
            D.normalize("x = 1", "a.py"))


class TestFindBlocks(unittest.TestCase):
    def test_repeat_across_files_counts_six(self):
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + BLOCK)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + BLOCK)],
        }
        blocks, dup = D.find_blocks(streams)
        self.assertEqual(dup, 6)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["path"], "a.py")
        self.assertEqual({loc["path"] for loc in blocks[0]["locations"]},
                         {"a.py", "b.py"})

    def test_five_line_repeat_is_not_a_duplicate(self):
        short = BLOCK[:5]
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + short)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + short)],
        }
        _, dup = D.find_blocks(streams)
        self.assertEqual(dup, 0)

    def test_same_shape_different_identifiers_passes(self):
        other = [line.replace("compute_", "fetch_") for line in BLOCK]
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + BLOCK)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + other)],
        }
        _, dup = D.find_blocks(streams)
        self.assertEqual(dup, 0)

    def test_long_repeat_counts_distinct_lines(self):
        long_block = [f"    step_{i} = run_{i}(x)" for i in range(12)]
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + long_block)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + long_block)],
        }
        blocks, dup = D.find_blocks(streams)
        self.assertEqual(dup, 12)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["lines"], 12)

    def test_repeat_within_one_file_counts(self):
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(
                ["def f():"] + BLOCK + ["def g():"] + BLOCK)],
        }
        _, dup = D.find_blocks(streams)
        self.assertEqual(dup, 6)

    def test_twelve_identical_lines_in_one_file_is_not_a_duplicate(self):
        twelve = ["    pass"] * 12
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + twelve)],
        }
        _, dup = D.find_blocks(streams)
        self.assertEqual(dup, 0)

    def test_twelve_identical_lines_across_two_files_counts_twelve(self):
        twelve = ["    pass"] * 12
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + twelve)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + twelve)],
        }
        blocks, dup = D.find_blocks(streams)
        self.assertEqual(dup, 12)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["lines"], 12)

    def test_seven_identical_lines_across_two_files_counts_seven(self):
        seven = ["    pass"] * 7
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + seven)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + seven)],
        }
        _, dup = D.find_blocks(streams)
        self.assertEqual(dup, 7)

    def test_noncontiguous_window_is_not_a_duplicate(self):
        # The same 3 lines added in two places in each of two files are
        # never consecutive in either file, so no 6-line window exists.
        three = ["x = 1", "y = 2", "z = 3"]
        streams = {
            "a.py": [(t, n) for t, n in zip(
                three + three, [2, 3, 4, 9, 10, 11])],
            "b.py": [(t, n) for t, n in zip(
                three + three, [2, 3, 4, 9, 10, 11])],
        }
        _, dup = D.find_blocks(streams)
        self.assertEqual(dup, 0)

    def test_net_rule_pure_move_counts_zero(self):
        # Two added places fully covered by two removed places: a pure
        # move is net-new duplication of zero.
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + BLOCK)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + BLOCK)],
        }
        removed = {tuple(BLOCK): [("a.py", 1), ("b.py", 1)]}
        _, dup = D.find_blocks(streams, removed)
        self.assertEqual(dup, 0)

    def test_net_rule_partial_move_counts_net(self):
        # Three added places, two removed: one net-new copy counts 6.
        streams = {
            "a.py": [(t, i + 1) for i, t in enumerate(["def f():"] + BLOCK)],
            "b.py": [(t, i + 1) for i, t in enumerate(["def g():"] + BLOCK)],
            "c.py": [(t, i + 1) for i, t in enumerate(["def h():"] + BLOCK)],
        }
        removed = {tuple(BLOCK): [("a.py", 1), ("b.py", 1)]}
        _, dup = D.find_blocks(streams, removed)
        self.assertEqual(dup, 6)


class TestParseAdded(unittest.TestCase):
    def test_hunk_line_numbers_are_real(self):
        diff = _diff_for({"tools/a/x.py": BLOCK})
        added = D.parse_added(diff)
        self.assertEqual(added["tools/a/x.py"][0], ("def f():", 1))
        self.assertEqual(added["tools/a/x.py"][1], (BLOCK[0].strip(), 2))

    def test_non_code_files_ignored(self):
        diff = _diff_for({"docs/notes.md": BLOCK})
        self.assertEqual(D.parse_added(diff), {})

    def test_deleted_files_ignored(self):
        diff = ("diff --git a/old.py b/old.py\n"
                "--- a/old.py\n"
                "+++ /dev/null\n"
                "@@ -1,7 +0,0 @@\n"
                + "\n".join("-" + line for line in ["def f():"] + BLOCK) + "\n")
        self.assertEqual(D.parse_added(diff), {})

    def test_deleted_file_removed_lines_are_collected(self):
        # A deleted file's `+++ /dev/null` header must not orphan its
        # removed lines: parse_removed still sees them.
        diff = (
            "diff --git a/old.py b/old.py\n"
            "--- a/old.py\n"
            "+++ /dev/null\n"
            "@@ -1,7 +0,0 @@\n" + "\n".join("-" + line for line in ["def f():"] + BLOCK) + "\n"
        )
        removed = D.parse_removed(diff)
        self.assertEqual(len(removed["old.py"]), 7)
        self.assertEqual(removed["old.py"][0], ("def f():", 1))

    def test_column_zero_plus_plus_lines_are_content(self):
        # A content line starting with `++` at column 0 produces a
        # diff line starting with `+++`, which is not a header.
        diff = ("diff --git a/a.js b/a.js\n"
                "--- a/a.js\n"
                "+++ b/a.js\n"
                "@@ -1,1 +1,7 @@\n"
                " function f() {\n"
                "+++count;\n"
                "+    step_a(x);\n"
                "+    step_b(x);\n"
                "+    step_c(x);\n"
                "+    step_d(x);\n"
                "+    step_e(x);\n"
                " }\n")
        added = D.parse_added(diff)
        self.assertEqual(len(added["a.js"]), 6)
        self.assertEqual(added["a.js"][0], ("++count;", 2))

    def test_column_zero_minus_minus_lines_are_content(self):
        diff = ("diff --git a/a.js b/a.js\n"
                "--- a/a.js\n"
                "+++ b/a.js\n"
                "@@ -1,7 +1,1 @@\n"
                " function f() {\n"
                "---count;\n"
                "-    step_a(x);\n"
                "-    step_b(x);\n"
                "-    step_c(x);\n"
                "-    step_d(x);\n"
                "-    step_e(x);\n"
                " }\n")
        removed = D.parse_removed(diff)
        self.assertEqual(len(removed["a.js"]), 6)
        self.assertEqual(removed["a.js"][0], ("--count;", 2))
        self.assertEqual(removed["a.js"][1], ("step_a(x);", 3))

    def test_changed_files_includes_deleted_files(self):
        diff = ("diff --git a/old.py b/old.py\n"
                "--- a/old.py\n"
                "+++ /dev/null\n"
                "@@ -1,1 +0,0 @@\n"
                "-x = 1\n"
                "diff --git a/new.py b/new.py\n"
                "--- /dev/null\n"
                "+++ b/new.py\n"
                "@@ -0,0 +1,1 @@\n"
                "+y = 2\n")
        self.assertEqual(D.changed_files(diff), ["new.py", "old.py"])


class TestReferencesDest(unittest.TestCase):
    def test_call_counts(self):
        self.assertTrue(D._references_dest(
            ["assert shared() == 15"], "tools/a/shared.py"))

    def test_attribute_call_counts(self):
        self.assertTrue(D._references_dest(
            ["result = shared.compute(row)"], "tools/a/shared.py"))

    def test_attribute_use_counts(self):
        self.assertTrue(D._references_dest(
            ["assert shared.VALUE == 15"], "tools/a/shared.py"))

    def test_import_from_does_not_count(self):
        self.assertFalse(D._references_dest(
            ["from tools.a.shared import shared"], "tools/a/shared.py"))

    def test_import_dotted_does_not_count(self):
        self.assertFalse(D._references_dest(
            ["import tools.a.shared"], "tools/a/shared.py"))

    def test_bare_assignment_does_not_count(self):
        self.assertFalse(D._references_dest(
            ["shared = 1", "assert shared == 1"], "tools/a/shared.py"))

    def test_string_mention_does_not_count(self):
        self.assertFalse(D._references_dest(
            ['assert "shared" in "shared_name"'], "tools/a/shared.py"))

    def test_variable_containing_stem_does_not_count(self):
        self.assertFalse(D._references_dest(
            ["shared_cache = {}"], "tools/a/shared.py"))

    def test_stem_inside_ordinary_word_does_not_count(self):
        self.assertFalse(D._references_dest(
            ["ratio = 2"], "tools/a/io.py"))

    def test_comment_mention_does_not_count(self):
        self.assertFalse(D._references_dest(
            ["# call shared() to verify"], "tools/a/shared.py"))

    def test_unrelated_import_does_not_count(self):
        self.assertFalse(D._references_dest(
            ["from fixtures import other"], "tools/a/shared.py"))

    def test_import_name_collision_does_not_count(self):
        # An import alone never exempts, so importing a name that
        # collides with the module stem does not exempt either. The
        # gate cannot resolve imports, but it no longer needs to: only
        # a call is the signal.
        self.assertFalse(D._references_dest(
            ["from fixtures import shared"], "tools/a/shared.py"))

    def test_import_plus_call_counts(self):
        self.assertTrue(D._references_dest(
            ["from tools.a.shared import shared", "assert shared() == 15"],
            "tools/a/shared.py"))

    def test_direct_import_of_symbol_counts(self):
        # The destination file is helpers.py, the extracted symbol is
        # dedup: the gate matches the symbol, not the file stem.
        self.assertTrue(D._references_dest(
            ["from tools.a.helpers import dedup",
             "assert dedup(row) == 15"],
            "tools/a/helpers.py", {"dedup"}))

    def test_module_qualified_symbol_call_counts(self):
        self.assertTrue(D._references_dest(
            ["assert helpers.dedup(row) == 15"],
            "tools/a/helpers.py", {"dedup"}))

    def test_stem_call_does_not_count_when_symbol_known(self):
        # Calling the module itself is not calling the extracted symbol.
        self.assertFalse(D._references_dest(
            ["assert helpers() == 15"],
            "tools/a/helpers.py", {"dedup"}))

    def test_attribute_use_of_defined_constant_counts(self):
        self.assertTrue(D._references_dest(
            ["assert shared.VALUE == 15"],
            "tools/a/shared.py", {"VALUE", "compute"}))


class TestQualifyingCallLines(unittest.TestCase):
    def test_asserting_call_qualifies(self):
        lines = D._qualifying_call_lines(
            "def test_dedup():\n    assert dedup() == 15\n")
        self.assertEqual(lines, {2})

    def test_bare_call_without_assert_does_not_qualify(self):
        lines = D._qualifying_call_lines(
            "def test_dedup():\n    dedup()\n")
        self.assertEqual(lines, set())

    def test_call_under_if_false_does_not_qualify(self):
        lines = D._qualifying_call_lines(
            "def test_dedup():\n"
            "    if False:\n        assert dedup() == 15\n")
        self.assertEqual(lines, set())

    def test_call_in_uncalled_helper_does_not_qualify(self):
        lines = D._qualifying_call_lines(
            "def helper():\n    return dedup()\n\n\n"
            "def test_dedup():\n    assert 1 == 1\n")
        self.assertEqual(lines, set())

    def test_unittest_style_assert_qualifies(self):
        lines = D._qualifying_call_lines(
            "import unittest\n\n\n"
            "class TestDedup(unittest.TestCase):\n"
            "    def test_dedup(self):\n"
            "        self.assertEqual(dedup(), 15)\n")
        self.assertEqual(lines, {6})

    def test_module_level_call_does_not_qualify(self):
        lines = D._qualifying_call_lines("assert dedup() == 15\n")
        self.assertEqual(lines, set())

    def test_unparseable_source_qualifies_nothing(self):
        lines = D._qualifying_call_lines("def test_x(:\n")
        self.assertEqual(lines, set())


class TestExtraction(unittest.TestCase):
    def _setup(self):
        added = D.parse_added(_diff_for({"tools/a/shared.py": BLOCK}))
        # Removed lines arrive normalized with line numbers, exactly as
        # parse_removed returns.
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {
            path: [(t, i + 1) for i, t in enumerate(norm)]
            for path in ("tools/a/one.py", "tools/a/two.py")
        }
        return added, removed

    def test_extraction_without_tests_is_a_hit(self):
        added, removed = self._setup()
        hits = D.find_extractions(added, removed, [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["dest"]["path"], "tools/a/shared.py")
        self.assertEqual(len(hits[0]["sources"]), 2)

    def test_extraction_with_referencing_test_is_not_a_hit(self):
        added, removed = self._setup()
        hits = D.find_extractions(
            added, removed,
            ["from tools.a.shared import shared", "assert shared() == 15"])
        self.assertEqual(hits, [])

    def test_extraction_with_import_only_test_is_a_hit(self):
        added, removed = self._setup()
        hits = D.find_extractions(
            added, removed, ["from tools.a.shared import shared"])
        self.assertEqual(len(hits), 1)

    def test_partial_migration_is_an_extraction(self):
        # Removed from one of two files, re-added as a shared home,
        # no test: the base tree shows the block was duplicated
        # before the diff (2 occurrences), so the gate fires.
        added, _ = self._setup()
        window = tuple(
            D.normalize(line, "tools/a/one.py") for line in BLOCK)
        removed = {
            "tools/a/one.py": [(t, i + 1) for i, t in enumerate(
                [D.normalize(line, "tools/a/one.py") for line in BLOCK])],
        }
        hits = D.find_extractions(
            added, removed, [], {window: 2})
        self.assertEqual(len(hits), 1)

    def test_partial_migration_of_unique_block_is_not(self):
        # Same shape, but the block occurred once in the base tree:
        # a unique block that merely moves is not an extraction.
        added, _ = self._setup()
        window = tuple(
            D.normalize(line, "tools/a/one.py") for line in BLOCK)
        removed = {
            "tools/a/one.py": [(t, i + 1) for i, t in enumerate(
                [D.normalize(line, "tools/a/one.py") for line in BLOCK])],
        }
        hits = D.find_extractions(
            added, removed, [], {window: 1})
        self.assertEqual(hits, [])

    def test_consolidation_into_holder_is_an_extraction(self):
        # Removed from two files, re-added in one of them (the holder):
        # the destination is a removal source, but not the sole one.
        added = D.parse_added(_diff_for({"tools/a/two.py": BLOCK}))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {
            path: [(t, i + 1) for i, t in enumerate(norm)]
            for path in ("tools/a/one.py", "tools/a/two.py")
        }
        hits = D.find_extractions(added, removed, [])
        self.assertEqual(len(hits), 1)

    def test_in_place_rewrite_is_not_an_extraction(self):
        # Removed from and re-added in the same single file: an
        # in-place edit, not a move to a shared home.
        added = D.parse_added(_diff_for({"tools/a/one.py": BLOCK}))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {
            "tools/a/one.py": [(t, i + 1) for i, t in enumerate(norm)],
        }
        hits = D.find_extractions(added, removed, [])
        self.assertEqual(hits, [])

    def test_seven_identical_lines_single_removal_is_not(self):
        # Seven identical lines are one occurrence (overlapping windows
        # collapse), so a single removal is not a repeated block.
        seven = ["    pass"] * 7
        added = D.parse_added(_diff_for({"tools/a/shared.py": seven}))
        norm = [D.normalize(line, "tools/a/one.py") for line in seven]
        removed = {
            "tools/a/one.py": [(t, i + 1) for i, t in enumerate(norm)],
        }
        hits = D.find_extractions(added, removed, [])
        self.assertEqual(hits, [])

    def test_twelve_identical_lines_single_removal_is_not(self):
        # Twelve identical lines are one occurrence (one maximal run,
        # not two non-overlapping windows), so a single removal is not
        # a repeated block.
        twelve = ["    pass"] * 12
        added = D.parse_added(_diff_for({"tools/a/shared.py": twelve}))
        norm = [D.normalize(line, "tools/a/one.py") for line in twelve]
        removed = {
            "tools/a/one.py": [(t, i + 1) for i, t in enumerate(norm)],
        }
        hits = D.find_extractions(added, removed, [])
        self.assertEqual(hits, [])

    def test_twelve_identical_lines_report_one_source(self):
        # When the same 12-line run does fire (the block was already
        # duplicated in the base tree), the report names one source,
        # not one file twice.
        twelve = ["    pass"] * 12
        added = D.parse_added(_diff_for({"tools/a/shared.py": twelve}))
        norm = [D.normalize(line, "tools/a/one.py") for line in twelve]
        removed = {
            "tools/a/one.py": [(t, i + 1) for i, t in enumerate(norm)],
        }
        window = tuple(norm[:6])
        hits = D.find_extractions(added, removed, [], {window: 2})
        self.assertEqual(len(hits), 1)
        self.assertEqual(len(hits[0]["sources"]), 1)
        self.assertEqual(hits[0]["sources"][0]["path"], "tools/a/one.py")

    def test_extraction_with_unrelated_test_is_a_hit(self):
        added, removed = self._setup()
        hits = D.find_extractions(
            added, removed, ["def test_other():", "assert 1 == 1"])
        self.assertEqual(len(hits), 1)

    def test_single_removal_is_not_an_extraction(self):
        added, _ = self._setup()
        hits = D.find_extractions(
            added, {"tools/a/one.py": [(t, i + 1) for i, t in enumerate(
                [D.normalize(line, "tools/a/one.py") for line in BLOCK])]},
            [])
        self.assertEqual(hits, [])

    def _rewire_setup(self):
        # The two-PR split (night-rick#376, arch-6 finding 1): the shared
        # home already exists on main, so the rewiring PR adds no copy of
        # the block, only calls to the home. `added` holds the rewiring
        # lines, `removed` the block from both call sites, and the base
        # tree holds the block in both call sites plus the home.
        added = D.parse_added(_diff_for({
            "tools/a/one.py": ["    return shared()"],
            "tools/a/two.py": ["    return shared()"],
        }))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {
            path: [(t, i + 1) for i, t in enumerate(norm)]
            for path in ("tools/a/one.py", "tools/a/two.py")
        }
        window = tuple(norm)
        base_locations = {window: [
            {"path": "tools/a/one.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/two.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/shared.py", "start_line": 2, "end_line": 7},
        ]}
        return added, removed, window, base_locations

    def test_rewiring_to_existing_home_is_a_hit(self):
        added, removed, window, base_locations = self._rewire_setup()
        hits = D.find_extractions(
            added, removed, [], {window: 3},
            {"tools/a/shared.py": {"shared"}}, base_locations)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["dest"]["path"], "tools/a/shared.py")
        self.assertEqual(len(hits[0]["sources"]), 2)

    def test_rewiring_with_referencing_test_is_not_a_hit(self):
        added, removed, window, base_locations = self._rewire_setup()
        hits = D.find_extractions(
            added, removed,
            ["from tools.a.shared import shared", "assert shared() == 15"],
            {window: 3}, {"tools/a/shared.py": {"shared"}}, base_locations)
        self.assertEqual(hits, [])

    def test_pure_deletion_without_rewiring_is_not_a_hit(self):
        # The block is deleted from one call site and replaced with a
        # plain return: no added line calls the home, so nothing was
        # consolidated into it and the gate stays silent.
        added = D.parse_added(_diff_for({
            "tools/a/one.py": ["    return 0"],
        }))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {"tools/a/one.py": [(t, i + 1) for i, t in enumerate(norm)]}
        window = tuple(norm)
        base_locations = {window: [
            {"path": "tools/a/one.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/two.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/shared.py", "start_line": 2, "end_line": 7},
        ]}
        hits = D.find_extractions(
            added, removed, [], {window: 3},
            {"tools/a/shared.py": {"shared"}}, base_locations)
        self.assertEqual(hits, [])

    def test_surviving_copy_is_not_a_destination(self):
        # One call site rewired, the other copy still on main: the
        # surviving copy is not a shared home, only the file the diff
        # actually calls is.
        added = D.parse_added(_diff_for({
            "tools/a/one.py": ["    return shared()"],
        }))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {"tools/a/one.py": [(t, i + 1) for i, t in enumerate(norm)]}
        window = tuple(norm)
        base_locations = {window: [
            {"path": "tools/a/one.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/two.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/shared.py", "start_line": 2, "end_line": 7},
        ]}
        hits = D.find_extractions(
            added, removed, [], {window: 3},
            {"tools/a/shared.py": {"shared"}, "tools/a/two.py": {"g"}},
            base_locations)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["dest"]["path"], "tools/a/shared.py")

    def test_rewiring_of_unique_block_is_not_a_hit(self):
        # The block occurred once in the base tree, in the file it was
        # removed from: a unique block that merely moves is not an
        # extraction, even though the diff rewires to a call.
        added = D.parse_added(_diff_for({
            "tools/a/one.py": ["    return shared()"],
        }))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {"tools/a/one.py": [(t, i + 1) for i, t in enumerate(norm)]}
        window = tuple(norm)
        base_locations = {window: [
            {"path": "tools/a/one.py", "start_line": 2, "end_line": 7},
        ]}
        hits = D.find_extractions(
            added, removed, [], {window: 1},
            {"tools/a/shared.py": {"shared"}}, base_locations)
        self.assertEqual(hits, [])

    def test_rewiring_to_holder_that_is_a_removal_source_is_a_hit(self):
        # Arch-7 finding 1: the shared home lives in a file that is
        # itself a removal source. one.py holds the block twice (the
        # helper at lines 2-7 and the removed copy at 11-16); two.py
        # holds it once. Both call sites rewire to helper() with no
        # test. Occurrence accounting must report the surviving copy
        # in one.py as the destination, never the removed copy.
        added = D.parse_added(_diff_for({
            "tools/a/one.py": ["    return helper()"],
            "tools/a/two.py": ["    return helper()"],
        }))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {
            "tools/a/one.py": [(t, i + 11) for i, t in enumerate(norm)],
            "tools/a/two.py": [(t, i + 2) for i, t in enumerate(norm)],
        }
        window = tuple(norm)
        base_locations = {window: [
            {"path": "tools/a/one.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/one.py", "start_line": 11, "end_line": 16},
            {"path": "tools/a/two.py", "start_line": 2, "end_line": 7},
        ]}
        hits = D.find_extractions(
            added, removed, [], {window: 3},
            {"tools/a/one.py": {"helper", "f"},
             "tools/a/two.py": {"g"}},
            base_locations)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["dest"]["path"], "tools/a/one.py")
        self.assertEqual(hits[0]["dest"]["start_line"], 2)
        self.assertEqual(hits[0]["dest"]["end_line"], 7)
        self.assertEqual(len(hits[0]["sources"]), 2)

    def test_removed_copy_in_holder_is_not_a_destination(self):
        # The holder file holds exactly as many base occurrences as
        # were removed from it, so no copy survives there: the removed
        # copy must not be reported as a destination.
        added = D.parse_added(_diff_for({
            "tools/a/one.py": ["    return helper()"],
            "tools/a/two.py": ["    return helper()"],
        }))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {
            "tools/a/one.py": [(t, i + 11) for i, t in enumerate(norm)],
            "tools/a/two.py": [(t, i + 2) for i, t in enumerate(norm)],
        }
        window = tuple(norm)
        base_locations = {window: [
            {"path": "tools/a/one.py", "start_line": 11, "end_line": 16},
            {"path": "tools/a/two.py", "start_line": 2, "end_line": 7},
        ]}
        hits = D.find_extractions(
            added, removed, [], {window: 2},
            {"tools/a/one.py": {"helper", "f"},
             "tools/a/two.py": {"g"}},
            base_locations)
        self.assertEqual(hits, [])

    def test_sole_removal_source_holder_is_not_a_destination(self):
        # The holder file is the SOLE file the block was removed from:
        # an in-place edit, skipped outright like the added leg.
        added = D.parse_added(_diff_for({
            "tools/a/one.py": ["    return helper()"],
        }))
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {
            "tools/a/one.py": [(t, i + 11) for i, t in enumerate(norm)],
        }
        window = tuple(norm)
        base_locations = {window: [
            {"path": "tools/a/one.py", "start_line": 2, "end_line": 7},
            {"path": "tools/a/one.py", "start_line": 11, "end_line": 16},
        ]}
        hits = D.find_extractions(
            added, removed, [], {window: 2},
            {"tools/a/one.py": {"helper", "f"}}, base_locations)
        self.assertEqual(hits, [])

    def test_consolidation_without_reduction_is_not_an_extraction(self):
        # Removed from two files, re-added twice in the destination:
        # the destination holds as many copies as were removed, so
        # nothing was consolidated and the move is not an extraction.
        stanza = ["    v0 = 0", "    v1 = 1", "    v2 = 2",
                  "    v3 = 3", "    v4 = 4", "    v5 = 5"]
        added = D.parse_added(_diff_for({"tools/a/shared.py":
            ["def shared():"] + stanza + ["    out = []"] + stanza}))
        norm = [D.normalize(line, "tools/a/one.py") for line in stanza]
        removed = {
            path: [(t, i + 1) for i, t in enumerate(norm)]
            for path in ("tools/a/one.py", "tools/a/two.py")
        }
        hits = D.find_extractions(added, removed, [])
        self.assertEqual(hits, [])

    def test_dest_range_does_not_span_gap(self):
        # Removed from three files, re-added twice in the destination
        # (two separate occurrences): two hits, each 6 lines, neither
        # spanning the gap line between the occurrences.
        stanza = ["    v0 = 0", "    v1 = 1", "    v2 = 2",
                  "    v3 = 3", "    v4 = 4", "    v5 = 5"]
        added = D.parse_added(_diff_for({"tools/a/shared.py":
            ["def shared():"] + stanza + ["    out = []"] + stanza}))
        norm = [D.normalize(line, "tools/a/one.py") for line in stanza]
        removed = {
            path: [(t, i + 1) for i, t in enumerate(norm)]
            for path in ("tools/a/one.py", "tools/a/two.py",
                         "tools/a/three.py")
        }
        hits = D.find_extractions(added, removed, [])
        self.assertEqual(len(hits), 2)
        for hit in hits:
            self.assertEqual(
                hit["dest"]["end_line"] - hit["dest"]["start_line"], 5)


class TestPrintBlocks(unittest.TestCase):
    def test_all_blocks_printed_not_just_the_first_ten(self):
        import io
        from contextlib import redirect_stdout
        blocks = [{
            "path": f"a{i}.py",
            "start_line": 1,
            "end_line": 6,
            "lines": 6,
            "sample": "x = 1",
            "locations": [{"path": f"a{i}.py", "start_line": 1,
                           "end_line": 6}],
        } for i in range(12)]
        buf = io.StringIO()
        with redirect_stdout(buf):
            D._print_blocks("BLOCKS:", blocks)
        out = buf.getvalue()
        for i in range(12):
            self.assertIn(f"a{i}.py:1-6", out)


class TestIsTestFile(unittest.TestCase):
    def test_tests_directory_variants(self):
        self.assertTrue(D.is_test_file("tools/a/__tests__/x.ts"))
        self.assertTrue(D.is_test_file("__tests__/x.js"))
        self.assertTrue(D.is_test_file("tools/a/x.spec.ts"))
        self.assertTrue(D.is_test_file("tools/a/x_spec.py"))
        self.assertFalse(D.is_test_file("tools/a/x.py"))


class TestEvaluateEndToEnd(unittest.TestCase):
    def _repo(self, base: dict[str, str], pr: dict[str, str]):
        td = tempfile.mkdtemp()
        project = Path(td)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"],
                       cwd=project, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=project, check=True)
        for path, text in base.items():
            p = project / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=project, check=True)
        subprocess.run(["git", "checkout", "-q", "-b", "pr"], cwd=project, check=True)
        for path, text in pr.items():
            p = project / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "pr"],
                       cwd=project, check=True)
        return project

    def test_check_passes_on_main_with_no_diff(self):
        project = self._repo({"tools/a/one.py": "def f():\n    return 1\n"}, {})
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)

    def test_baseline_with_reason_is_honoured(self):
        # The raise must already be on main: a raise inside the diff under
        # review does not take effect until it merges.
        block = "\n".join(BLOCK) + "\n"
        future = (date.today() + timedelta(days=90)).isoformat()
        base = {
            "tools/a/one.py": "def f():\n    return 1\n",
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 6, "reason": "sibling scripts, recorded",
                 "expires": future, "owner": "test"}),
        }
        project = self._repo(base, {
            "tools/a/two.py": "def g():\n" + block,
            "tools/a/three.py": "def h():\n" + block,
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)

    def test_raise_inside_the_diff_does_not_silence_the_gate(self):
        block = "\n".join(BLOCK) + "\n"
        future = (date.today() + timedelta(days=90)).isoformat()
        base = {
            "tools/a/one.py": "def f():\n    return 1\n",
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 0, "reason": "", "expires": "", "owner": ""}),
        }
        project = self._repo(base, {
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 6, "reason": "raise in this diff",
                 "expires": future, "owner": "test"}),
            "tools/a/two.py": "def g():\n" + block,
            "tools/a/three.py": "def h():\n" + block,
        })
        code = D.cmd_check(argparse.Namespace(project=str(project)))
        res = D.evaluate(project)
        self.assertEqual(code, 1)
        self.assertEqual(res["baseline"], 0)

    def test_malformed_baseline_fails_cleanly(self):
        project = self._repo({"tools/a/one.py": "def f():\n    return 1\n"}, {})
        (project / "state").mkdir(exist_ok=True)
        (project / "state" / "dup-ratchet.json").write_text(
            "{not json", encoding="utf-8")
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)

    def _expired_base(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        return {
            "tools/a/one.py": "def f():\n    return 1\n",
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 6, "reason": "sibling scripts, recorded",
                 "expires": past, "owner": "test"}),
        }

    def test_clean_pr_passes_with_expired_baseline(self):
        project = self._repo(self._expired_base(), {
            "tools/a/clean.py": "def c():\n    return 2\n",
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)
        self.assertNotEqual(D.evaluate(project)["baseline_lapsed"], "")

    def test_rejustify_expired_baseline_passes(self):
        future = (date.today() + timedelta(days=90)).isoformat()
        block = "\n".join(BLOCK) + "\n"
        project = self._repo(self._expired_base(), {
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 6, "reason": "re-justified",
                 "expires": future, "owner": "test"}),
            "tools/a/two.py": "def g():\n" + block,
            "tools/a/three.py": "def h():\n" + block,
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)

    def test_lower_expired_baseline_passes(self):
        project = self._repo(self._expired_base(), {
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 0, "reason": "lowered after expiry",
                 "expires": "", "owner": ""}),
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)

    def test_dup_with_lapsed_baseline_fails_against_zero(self):
        block = "\n".join(BLOCK) + "\n"
        project = self._repo(self._expired_base(), {
            "tools/a/two.py": "def g():\n" + block,
            "tools/a/three.py": "def h():\n" + block,
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        self.assertEqual(D.evaluate(project)["baseline"], 0)

    def test_new_record_with_past_expiry_fails(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        project = self._repo({"tools/a/one.py": "def f():\n    return 1\n"}, {
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 6, "reason": "raise with a past expiry",
                 "expires": past, "owner": "test"}),
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)

    def test_baseline_deletion_fails(self):
        project = self._repo({
            "tools/a/one.py": "def f():\n    return 1\n",
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 0, "reason": "", "expires": "", "owner": ""}),
        }, {})
        (project / "state" / "dup-ratchet.json").unlink()
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "delete baseline"],
                       cwd=project, check=True)
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)

    def test_check_outside_a_git_repo_fails_closed(self):
        td = tempfile.mkdtemp()
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=td)), 1)

    def _extract_repo(self, test_text):
        extract_body = (
            "    total = 0\n    total += 1\n    total += 2\n    total += 3\n"
            "    total += 4\n    total += 5\n    return total\n"
        )
        base = {
            "tools/a/one.py": "def f():\n" + extract_body,
            "tools/a/two.py": "def g():\n" + extract_body,
            "tools/a/helpers.py": "def h():\n    return 0\n",
        }
        pr = {
            "tools/a/one.py": "def f():\n    return dedup()\n",
            "tools/a/two.py": "def g():\n    return dedup()\n",
            "tools/a/helpers.py": "def dedup():\n" + extract_body,
            "tests/test_helpers.py": test_text,
        }
        return self._repo(base, pr)

    def test_extraction_direct_import_of_symbol_passes(self):
        project = self._extract_repo(
            "from tools.a.helpers import dedup\n\n\n"
            "def test_dedup():\n    assert dedup() == 15\n")
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)
        self.assertEqual(D.evaluate(project)["extraction"], [])

    def test_rewiring_to_existing_home_fails(self):
        # The two-PR split end to end (arch-6 finding 1): the shared
        # home already exists on main, so the rewiring PR adds no copy
        # of the block, only calls to it. The gate must still fire.
        extract_body = (
            "    total = 0\n    total += 1\n    total += 2\n    total += 3\n"
            "    total += 4\n    total += 5\n    return total\n"
        )
        base = {
            "tools/a/one.py": "def f():\n" + extract_body,
            "tools/a/two.py": "def g():\n" + extract_body,
            "tools/a/shared.py": "def shared():\n" + extract_body,
        }
        pr = {
            "tools/a/one.py": "def f():\n    return shared()\n",
            "tools/a/two.py": "def g():\n    return shared()\n",
        }
        project = self._repo(base, pr)
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        res = D.evaluate(project)
        self.assertEqual(len(res["extraction"]), 1)
        self.assertEqual(
            res["extraction"][0]["dest"]["path"], "tools/a/shared.py")

    def test_rewiring_to_holder_that_is_a_removal_source_fails(self):
        # Arch-7 finding 1 end to end: the shared home lives in one.py,
        # which is itself a removal source (it holds the block twice,
        # as helper() and as f()). Both call sites rewire to helper()
        # with no test, so the gate must fire on the surviving copy.
        extract_body = (
            "    total = 0\n    total += 1\n    total += 2\n    total += 3\n"
            "    total += 4\n    total += 5\n    return total\n"
        )
        base = {
            "tools/a/one.py": ("def helper():\n" + extract_body
                               + "\ndef f():\n" + extract_body),
            "tools/a/two.py": "def g():\n" + extract_body,
        }
        pr = {
            "tools/a/one.py": ("def helper():\n" + extract_body
                               + "\ndef f():\n    return helper()\n"),
            "tools/a/two.py": ("from tools.a.one import helper\n\n\n"
                               "def g():\n    return helper()\n"),
        }
        project = self._repo(base, pr)
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        res = D.evaluate(project)
        self.assertEqual(len(res["extraction"]), 1)
        self.assertEqual(
            res["extraction"][0]["dest"]["path"], "tools/a/one.py")
        self.assertEqual(
            res["extraction"][0]["dest"]["start_line"], 2)
        self.assertEqual(
            res["extraction"][0]["dest"]["end_line"], 8)

    def test_extraction_bare_call_without_assert_fails(self):
        project = self._extract_repo(
            "from tools.a.helpers import dedup\n\n\n"
            "def test_dedup():\n    dedup()\n")
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        self.assertTrue(len(D.evaluate(project)["extraction"]) > 0)

    def test_extraction_call_under_if_false_fails(self):
        project = self._extract_repo(
            "from tools.a.helpers import dedup\n\n\n"
            "def test_dedup():\n"
            "    if False:\n        assert dedup() == 15\n")
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        self.assertTrue(len(D.evaluate(project)["extraction"]) > 0)

    def test_extraction_call_in_uncalled_helper_fails(self):
        project = self._extract_repo(
            "from tools.a.helpers import dedup\n\n\n"
            "def helper():\n    return dedup()\n\n\n"
            "def test_dedup():\n    assert 1 == 1\n")
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        self.assertTrue(len(D.evaluate(project)["extraction"]) > 0)

    def test_extraction_test_calling_unrelated_symbol_fails(self):
        project = self._extract_repo(
            "def test_other():\n    assert other() == 1\n")
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        self.assertTrue(len(D.evaluate(project)["extraction"]) > 0)

    def test_new_record_expiring_today_fails(self):
        today = date.today().isoformat()
        project = self._repo({"tools/a/one.py": "def f():\n    return 1\n"}, {
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 6, "reason": "raise expiring today",
                 "expires": today, "owner": "test"}),
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)

    def test_malformed_baseline_on_main_surfaces_when_touched(self):
        project = self._repo({
            "tools/a/one.py": "def f():\n    return 1\n",
            "state/dup-ratchet.json": "{not json",
        }, {
            "state/dup-ratchet.json": json.dumps(
                {"baseline": 0, "reason": "repair",
                 "expires": "", "owner": "test"}),
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 1)
        self.assertTrue(len(D.evaluate(project)["baseline_errors"]) > 0)

    def test_pure_move_with_internal_repeat_passes(self):
        # A function moved whole, its internal 6-line repeat included,
        # passes both gates: the repeat predates the diff and nothing
        # was consolidated into fewer occurrences.
        stanza = (
            "    if row is None:\n"
            "        continue\n"
            "    total += 1\n"
            "    total += 2\n"
            "    total += 3\n"
            "    total += 4\n"
        )
        project = self._repo({
            "tools/a/old.py": "def process():\n" + stanza + "    out = []\n" + stanza,
            "tools/a/shared.py": "def s():\n    return 0\n",
        }, {
            "tools/a/old.py": "def process():\n    return shared()\n",
            "tools/a/shared.py": "def shared():\n" + stanza + "    out = []\n" + stanza,
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)
        res = D.evaluate(project)
        self.assertEqual(res["duplicated_lines"], 0)
        self.assertEqual(res["extraction"], [])

    def test_test_file_extraction_does_not_fire(self):
        # A fixture block moved between test files is fixture
        # deduplication, not an extraction.
        block_text = "\n".join(BLOCK) + "\n"
        project = self._repo({
            "tests/test_one.py": "def test_one():\n" + block_text,
            "tests/test_two.py": "def test_two():\n" + block_text,
            "tests/helpers.py": "def h():\n    return 0\n",
        }, {
            "tests/test_one.py": "def test_one():\n    return helper()\n",
            "tests/test_two.py": "def test_two():\n    return helper()\n",
            "tests/helpers.py": "def helper():\n" + block_text,
        })
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)
        self.assertEqual(D.evaluate(project)["extraction"], [])

    def test_dirty_tree_padding_above_calling_test_still_exempts(self):
        # Uncommitted comment lines above a calling test shift the
        # on-disk call line, but the committed diff's lines are
        # resolved against HEAD, so the exemption survives.
        project = self._extract_repo(
            "from tools.a.helpers import dedup\n\n\n"
            "def test_dedup():\n    assert dedup() == 15\n")
        test_path = project / "tests/test_helpers.py"
        text = test_path.read_text(encoding="utf-8")
        test_path.write_text(
            text.replace("def test_dedup():",
                         "# pad\n# pad\n# pad\ndef test_dedup():"),
            encoding="utf-8")
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)
        self.assertEqual(D.evaluate(project)["extraction"], [])


if __name__ == "__main__":
    unittest.main()
