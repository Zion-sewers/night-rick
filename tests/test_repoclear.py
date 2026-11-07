"""Tests for tools/repoclear/scan.py (night-rick#35, Repo Clear gate domain).

The detectors are exercised against planted synthetic git repos, the same
shape the tool's own selftest uses, plus two pins on the real tree: the
contract declares the repoclear domain, and the committed baseline matches
the counts the tool measures on this tree right now.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_PATH = ROOT / "tools" / "repoclear" / "scan.py"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("repoclear_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


scan = _load(SCAN_PATH)


def _plant_repo(proj: Path) -> None:
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.name", "t"], check=True)


def _commit(proj: Path) -> None:
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-qm", "x"], check=True)


class TestEmptyDirs(unittest.TestCase):
    def test_topmost_empty_dir_reported_once(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "planted").mkdir()
            (proj / "planted" / "empty").mkdir()
            (proj / "kept").mkdir()
            (proj / "kept" / "f.txt").write_text("x\n")
            _commit(proj)
            self.assertEqual(scan.find_empty_dirs(proj), ["planted"])

    def test_worktrees_never_reported_empty(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / ".claude" / "worktrees" / "other").mkdir(parents=True)
            (proj / "f.txt").write_text("x\n")
            _commit(proj)
            self.assertEqual(scan.find_empty_dirs(proj), [])


class TestArtifacts(unittest.TestCase):
    def test_tracked_pycache_is_an_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "__pycache__").mkdir()
            (proj / "__pycache__" / "x.pyc").write_bytes(b"\x00")
            (proj / "ok.py").write_text("x = 1\n")
            _commit(proj)
            self.assertEqual(scan.find_artifacts(proj), ["__pycache__/x.pyc"])

    def test_plain_py_is_not_an_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "ok.py").write_text("x = 1\n")
            _commit(proj)
            self.assertEqual(scan.find_artifacts(proj), [])


class TestStaleDestinations(unittest.TestCase):
    def test_missing_destination_dir_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text("Output lands in ~/docs/no-such-dir/.\n")
            (prompts / "p2.md").write_text("Output lands in work-docs/research/.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["file"], "work-docs/research/prompts/p1.md")
            self.assertEqual(stale[0]["line"], 1)

    def test_land_as_line_checks_parent_dir(self):
        # "Land as <file>" validates the directory the file would land in,
        # not the not-yet-created file itself.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text(
                "Land as work-docs/research/2026-07-future.md.\n")
            _commit(proj)
            self.assertEqual(scan.find_stale_destinations(proj), [])


class TestDuplicateReuse(unittest.TestCase):
    def test_identical_docs_counted_via_pile(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "old").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            (proj / "old" / "a.md").write_text("same body\n")
            (proj / "docs" / "b.md").write_text("unique\n")
            _commit(proj)
            counts = scan.duplicate_counts(proj)
            self.assertEqual(counts["duplicate_doc_groups"], 1)
            self.assertEqual(counts["duplicate_doc_copies"], 1)


class TestRatchet(unittest.TestCase):
    def _check(self, proj: Path, baseline: Path, update: bool = False) -> int:
        import argparse
        return scan.cmd_check(argparse.Namespace(
            project=str(proj), baseline=str(baseline), update_baseline=update))

    def test_check_passes_at_baseline_fails_on_growth_missing_is_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            baseline = proj / "state" / "repoclear-baseline.json"
            self.assertEqual(self._check(proj, baseline), 2)
            self.assertEqual(self._check(proj, baseline, update=True), 0)
            self.assertEqual(self._check(proj, baseline), 0)
            grown = json.loads(baseline.read_text(encoding="utf-8"))
            grown["counts"]["duplicate_doc_groups"] -= 1
            baseline.write_text(json.dumps(grown, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(self._check(proj, baseline), 1)


class TestWiring(unittest.TestCase):
    def test_contract_declares_repoclear_domain(self):
        contract = json.loads((ROOT / "quality-contract.json").read_text(encoding="utf-8"))
        domain = contract["domains"].get("repoclear")
        self.assertIsNotNone(domain, "quality-contract.json has no repoclear domain")
        self.assertTrue(domain.get("required"))
        self.assertIn("tools/repoclear/scan.py check", domain.get("cmd", ""))

    def test_committed_baseline_matches_live_tree(self):
        baseline = scan.load_baseline(ROOT / "state" / "repoclear-baseline.json")
        measured = scan.collect(ROOT)["counts"]
        self.assertEqual(measured, baseline,
                         "committed baseline drifted from the live tree; "
                         "collapse the growth or regenerate it deliberately")


if __name__ == "__main__":
    unittest.main()
