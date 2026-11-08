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


if __name__ == "__main__":
    unittest.main()
