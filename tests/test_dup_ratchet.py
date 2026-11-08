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
        self.assertEqual(blocks[0]["path"], "b.py")

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


class TestExtraction(unittest.TestCase):
    def _setup(self):
        added = D.parse_added(_diff_for({"tools/a/shared.py": BLOCK}))
        # Removed lines arrive normalized, exactly as parse_removed returns.
        norm = [D.normalize(line, "tools/a/one.py") for line in BLOCK]
        removed = {"tools/a/one.py": norm, "tools/a/two.py": norm}
        return added, removed

    def test_extraction_without_tests_is_a_hit(self):
        added, removed = self._setup()
        hits = D.find_extractions(
            added, removed, ["tools/a/one.py", "tools/a/two.py",
                             "tools/a/shared.py"])
        self.assertEqual(len(hits), 1)

    def test_extraction_with_tests_is_not_a_hit(self):
        added, removed = self._setup()
        hits = D.find_extractions(
            added, removed, ["tools/a/one.py", "tools/a/two.py",
                             "tools/a/shared.py", "tests/test_shared.py"])
        self.assertEqual(hits, [])

    def test_single_removal_is_not_an_extraction(self):
        added, _ = self._setup()
        hits = D.find_extractions(
            added, {"tools/a/one.py": BLOCK},
            ["tools/a/one.py", "tools/a/shared.py"])
        self.assertEqual(hits, [])


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
        block = "\n".join(BLOCK) + "\n"
        project = self._repo({"tools/a/one.py": "def f():\n    return 1\n"}, {})
        (project / "state").mkdir(exist_ok=True)
        (project / "state" / "dup-ratchet.json").write_text(json.dumps(
            {"baseline": 6, "reason": "sibling scripts, recorded"}),
            encoding="utf-8")
        for path, text in {
            "tools/a/two.py": "def g():\n" + block,
            "tools/a/three.py": "def h():\n" + block,
        }.items():
            p = project / path
            p.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "pr"], cwd=project, check=True)
        self.assertEqual(D.cmd_check(argparse.Namespace(
            project=str(project))), 0)


if __name__ == "__main__":
    unittest.main()
