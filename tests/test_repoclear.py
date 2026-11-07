"""Tests for tools/repoclear/scan.py (night-rick#35, Repo Clear gate domain).

The detectors are exercised against planted synthetic git repos, the same
shape the tool's own selftest uses, plus two pins on the real tree: the
contract declares the repoclear domain, and the committed baseline matches
the counts the tool measures on this tree right now.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_PATH = ROOT / "tools" / "repoclear" / "scan.py"
GUARD_PATH = ROOT / "tools" / "repoclear" / "baseline_guard.py"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("repoclear_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


scan = _load(SCAN_PATH)


def _load_guard(path: Path):
    spec = importlib.util.spec_from_file_location("baseline_guard_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard(GUARD_PATH)


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

    def test_skipped_dir_with_content_is_not_empty(self):
        # B1: a directory whose only child is a skipped directory holding
        # real files (__pycache__/, node_modules/, build/) is not empty.
        # The old code pruned the skipped child and reported the parent.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "onlycache" / "__pycache__").mkdir(parents=True)
            (proj / "onlycache" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
            (proj / "onlynode" / "node_modules" / "pkg").mkdir(parents=True)
            (proj / "onlynode" / "node_modules" / "pkg" / "f").write_text("x\n")
            (proj / "onlybuild" / "build").mkdir(parents=True)
            (proj / "onlybuild" / "build" / "out.txt").write_text("x\n")
            _commit(proj)
            self.assertEqual(scan.find_empty_dirs(proj), [])

    def test_empty_skipped_child_is_empty(self):
        # M1: a directory whose only child is an EMPTY skipped directory
        # is empty: the skipped child counts as content only when its
        # subtree holds a file.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "a" / "__pycache__").mkdir(parents=True)
            (proj / "keep.txt").write_text("x\n")
            _commit(proj)
            self.assertEqual(scan.find_empty_dirs(proj), ["a"])

    def test_symlink_to_dir_with_files_is_not_empty(self):
        # m1: the walk never descends into a symlinked directory
        # (followlinks=False), so without this a directory whose only child
        # is a symlink to a directory with files would read as empty.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "real").mkdir()
            (proj / "real" / "f.txt").write_text("x\n")
            (proj / "holder").mkdir()
            os.symlink(proj / "real", proj / "holder" / "link")
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

    def test_non_ascii_artifact_found(self):
        # M4: git quotes non-ASCII paths under core.quotepath, so plain
        # ls-files delivered the quoted form and the matcher never saw it.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "__pycache__").mkdir()
            (proj / "__pycache__" / "café.pyc").write_bytes(b"\x00")
            _commit(proj)
            self.assertEqual(scan.find_artifacts(proj), ["__pycache__/café.pyc"])

    def test_uppercase_suffix_is_an_artifact(self):
        # M9: X.PYC is a build artifact the same as x.pyc.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "lib").mkdir()
            (proj / "lib" / "X.PYC").write_bytes(b"\x00")
            _commit(proj)
            self.assertEqual(scan.find_artifacts(proj), ["lib/X.PYC"])


class TestStaleDestinations(unittest.TestCase):
    def test_missing_destination_dir_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text("Output lands in work-docs/no-such-dir/.\n")
            (prompts / "p2.md").write_text("Output lands in work-docs/research/.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["file"], "work-docs/research/prompts/p1.md")
            self.assertEqual(stale[0]["line"], 1)
            self.assertEqual(stale[0]["reason"], "missing_dir")

    def test_home_path_destination_is_stale(self):
        # A destination under ~ names a location outside the repo, so it can
        # never be a valid in-repo destination, even if the dir happens to
        # exist on this machine.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text("Output lands in ~/docs/no-such-dir/.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["reason"], "home_path")

    def test_prompt_without_destination_is_stale(self):
        # A prompt the check cannot parse is a prompt the check cannot verify.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text("A prompt with no destination line.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["reason"], "no_destination")

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

    def test_missing_dir_without_trailing_slash_is_stale(self):
        # B2: the natural prose form has no trailing slash, and the parent
        # exists, so the old slash rule checked the parent and missed it.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (proj / "work-docs").mkdir(exist_ok=True)
            (prompts / "p1.md").write_text(
                "Output lands in work-docs/no-such-dir.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["reason"], "missing_dir")
            self.assertIn("no-such-dir", stale[0]["missing_dir"])

    def test_missing_dir_through_dotdot_is_stale(self):
        # M11: a missing directory named through ".." must be checked as
        # itself, not via its parent (which resolves to an existing dir).
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text(
                "Output lands in work-docs/research/../no-such.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["reason"], "missing_dir")

    def test_two_destinations_on_one_line_both_checked(self):
        # M8: search() per line dropped the second destination on a line.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text(
                "Output lands in work-docs/research/. "
                "Land as work-docs/no-such/file.md.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["reason"], "missing_dir")

    def test_lowercase_lead_in_is_checked(self):
        # M8: the lead-in is a convention, not a capitalisation.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text(
                "output lands in work-docs/no-such/.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["reason"], "missing_dir")

    def test_absolute_destination_outside_repo_is_stale(self):
        # B1: an absolute destination outside the repo is stale even when
        # it exists on this machine (/tmp does): existence alone would
        # bless it here and fail it in CI. A missing absolute path is
        # outside_repo too, not missing_dir: containment is checked first.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text("Output lands in /tmp/.\n")
            (prompts / "p2.md").write_text(
                "Output lands in /nonexistent-dir-xyz/.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 2)
            self.assertEqual({s["reason"] for s in stale}, {"outside_repo"})

    def test_dotdot_escape_outside_repo_is_stale(self):
        # B1: a .. path that escapes the project is stale even when the
        # parent directory exists: the destination must name a directory
        # inside the repo.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            prompts = proj / "work-docs" / "research" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "p1.md").write_text("Output lands in ../.\n")
            _commit(proj)
            stale = scan.find_stale_destinations(proj)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["reason"], "outside_repo")


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

    def test_identical_and_forked_skills_counted_via_pile(self):
        # Same fixture shape pile.py's own selftest uses: a skill name in two
        # payload trees, identical in one pair, forked in the other.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            for tree in ("dot-claude/skills", "dot-agents/skills"):
                (proj / tree / "twin").mkdir(parents=True)
                (proj / tree / "twin" / "SKILL.md").write_text("identical\n")
                (proj / tree / "split").mkdir(parents=True)
            (proj / "dot-claude/skills" / "split" / "SKILL.md").write_text("version one\n")
            (proj / "dot-agents/skills" / "split" / "SKILL.md").write_text("version two, longer\n")
            _commit(proj)
            counts = scan.duplicate_counts(proj)
            self.assertEqual(counts["identical_skills"], 1)
            self.assertEqual(counts["forked_skills"], 1)

    def test_manifest_validation_fails_closed(self):
        # A pile manifest row without the pile.v1 schema, with an unknown
        # kind, or with a duplicate-doc copies count below 2 must raise, not
        # count as zero: an oracle that goes silent must not read as clean.
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            good = scan.duplicate_counts(proj)
            self.assertEqual(good["duplicate_doc_groups"], 0)
            bad_rows = [
                {"schema": "pile.v2", "kind": "duplicate-doc", "copies": 2},
                {"schema": "pile.v1", "kind": "mystery-kind"},
                {"schema": "pile.v1", "kind": "duplicate-doc", "copies": 1},
            ]
            for bad in bad_rows:
                # Feed the bad manifest through the real reader by replacing
                # pile.py with a stub that writes the bad row.
                stub = Path(td) / "stub-pile.py"
                stub.write_text(
                    "import json, sys\n"
                    f"open(sys.argv[sys.argv.index('--out') + 1], 'w').write("
                    f"{json.dumps(bad)!r} + '\\n')\n")
                with mock.patch.object(scan, "PILE", stub):
                    with self.assertRaises(RuntimeError):
                        scan.duplicate_counts(proj)

    def test_malformed_manifest_line_fails_closed(self):
        # M10: one malformed JSONL line used to crash the whole scan with a
        # traceback; a gate tool must fail closed with a named error.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            stub = Path(td) / "stub-pile.py"
            stub.write_text(
                "import sys\n"
                "open(sys.argv[sys.argv.index('--out') + 1], 'w').write("
                "'{\"schema\": \"pile.v1\", \"kind\": \"duplicate-doc\", "
                "\"copies\": 2}\\nnot json{\\n')\n")
            with mock.patch.object(scan, "PILE", stub):
                with self.assertRaises(RuntimeError):
                    scan.duplicate_counts(proj)

    def test_pile_timeout_fails_closed(self):
        # M10: a hung pile.py must surface as a named error, not a silent
        # gate timeout with no domain evidence.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            with mock.patch.object(
                    scan.subprocess, "run",
                    side_effect=subprocess.TimeoutExpired("pile.py", 30)):
                with self.assertRaises(RuntimeError):
                    scan.duplicate_counts(proj)


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
            # Growth is a real duplicate added after baselining, not a
            # baseline edited below zero: a negative baseline count is now
            # malformed and fails closed with exit 2 instead.
            (proj / "old").mkdir()
            (proj / "old" / "a.md").write_text("same body\n")
            _commit(proj)
            self.assertEqual(self._check(proj, baseline), 1)

    def test_empty_dir_growth_fails(self):
        # M12: the ratchet fires on empty-dir growth too, not only on
        # duplicate growth (the new detectors need a growth proof each).
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "planted").mkdir()
            (proj / "planted" / "empty").mkdir()
            (proj / "keep.txt").write_text("x\n")
            _commit(proj)
            baseline = proj / "state" / "repoclear-baseline.json"
            self.assertEqual(self._check(proj, baseline, update=True), 0)
            self.assertEqual(self._check(proj, baseline), 0)
            # No commit: git never tracks an empty directory, so the second
            # empty dir exists on the filesystem only, which is exactly what
            # the empty-dir detector walks.
            (proj / "planted2").mkdir()
            (proj / "planted2" / "empty").mkdir()
            self.assertEqual(self._check(proj, baseline), 1)

    def test_update_baseline_refuses_under_ci(self):
        # A baseline increase is a reviewed decision: CI must never raise
        # the ceiling it enforces.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            baseline = proj / "state" / "repoclear-baseline.json"
            saved = os.environ.pop("CI", None)
            os.environ["CI"] = "true"
            try:
                self.assertEqual(self._check(proj, baseline, update=True), 2)
            finally:
                if saved is None:
                    os.environ.pop("CI", None)
                else:
                    os.environ["CI"] = saved
            self.assertFalse(baseline.is_file())

    def test_update_baseline_refuses_when_ci_set_but_empty(self):
        # m5: CI="" (set but empty) used to pass the truthiness check and
        # the update proceeded. Presence in the environment is the signal,
        # not the value: GitHub Actions sets CI=true, and an empty value is
        # still a CI-shaped environment, never a developer machine.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            baseline = proj / "state" / "repoclear-baseline.json"
            saved = os.environ.pop("CI", None)
            os.environ["CI"] = ""
            try:
                self.assertEqual(self._check(proj, baseline, update=True), 2)
            finally:
                if saved is None:
                    os.environ.pop("CI", None)
                else:
                    os.environ["CI"] = saved
            self.assertFalse(baseline.is_file())

    def test_update_baseline_refuses_on_dirty_tracked_tree(self):
        # The baseline measures a commit: with tracked modifications the
        # base_commit it records would name a commit that does not include
        # the measured tree.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            baseline = proj / "state" / "repoclear-baseline.json"
            saved = os.environ.pop("CI", None)
            try:
                (proj / "docs" / "a.md").write_text("changed\n")
                self.assertEqual(self._check(proj, baseline, update=True), 2)
                self.assertFalse(baseline.is_file())
            finally:
                if saved is not None:
                    os.environ["CI"] = saved

    def test_malformed_baseline_is_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            _commit(proj)
            baseline = proj / "state" / "repoclear-baseline.json"
            baseline.parent.mkdir(parents=True)
            good = {"schema": "repoclear-baseline.v1",
                    "counts": dict.fromkeys(scan.COUNT_KEYS, 0),
                    "measured_on": "2026-11-07", "base_commit": "a" * 40,
                    "recheck_after": "2027-02-05", "follow_up": "night-rick#35"}
            for broken in (
                {**good, "schema": "repoclear-baseline.v2"},
                {**good, "counts": {**good["counts"], "artifacts": -1}},
                {k: v for k, v in good.items() if k != "measured_on"},
                # m3: provenance is validated for shape, not just presence.
                {**good, "measured_on": "not-a-date"},
                {**good, "recheck_after": "yesterday"},
                {**good, "base_commit": "x" * 40},
                {**good, "base_commit": "abc"},
            ):
                baseline.write_text(json.dumps(broken, indent=2) + "\n", encoding="utf-8")
                self.assertEqual(self._check(proj, baseline), 2)

    def test_pass_line_names_the_outstanding_backlog(self):
        # PASS must never read as clean while the ratchet blesses a backlog.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "docs").mkdir()
            (proj / "old").mkdir()
            (proj / "docs" / "a.md").write_text("same body\n")
            (proj / "old" / "a.md").write_text("same body\n")
            _commit(proj)
            baseline = proj / "state" / "repoclear-baseline.json"
            self.assertEqual(self._check(proj, baseline, update=True), 0)
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(self._check(proj, baseline), 0)
            self.assertIn("known outstanding: 1 duplicate-doc group (1 redundant copy)",
                          buf.getvalue())


class TestBaselineGuard(unittest.TestCase):
    def _head(self, proj: Path) -> str:
        return subprocess.run(
            ["git", "-C", str(proj), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()

    def _setup(self, proj: Path) -> str:
        _plant_repo(proj)
        (proj / "state").mkdir()
        (proj / "state" / "repoclear-baseline.json").write_text("{}\n")
        (proj / "a.py").write_text("x = 1\n")
        _commit(proj)
        return self._head(proj)

    def test_baseline_modified_with_other_files_fails(self):
        # M1: a baseline raise riding along in a feature PR is the drive-by
        # the ratchet exists to stop.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            base = self._setup(proj)
            (proj / "state" / "repoclear-baseline.json").write_text("{}\n ")
            (proj / "a.py").write_text("x = 2\n")
            _commit(proj)
            self.assertEqual(guard.guard(proj, base, self._head(proj)), 1)

    def test_baseline_modified_alone_passes(self):
        # The reviewed decision: a baseline change landing as its own change.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            base = self._setup(proj)
            (proj / "state" / "repoclear-baseline.json").write_text("{}\n ")
            _commit(proj)
            self.assertEqual(guard.guard(proj, base, self._head(proj)), 0)

    def test_other_files_only_passes(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            base = self._setup(proj)
            (proj / "a.py").write_text("x = 2\n")
            _commit(proj)
            self.assertEqual(guard.guard(proj, base, self._head(proj)), 0)

    def test_baseline_added_with_other_files_passes(self):
        # The domain's first landing adds the baseline file alongside the
        # tool: an addition is not a raise of a committed ceiling.
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            _plant_repo(proj)
            (proj / "a.py").write_text("x = 1\n")
            _commit(proj)
            base = self._head(proj)
            (proj / "state").mkdir()
            (proj / "state" / "repoclear-baseline.json").write_text("{}\n")
            (proj / "a.py").write_text("x = 2\n")
            _commit(proj)
            self.assertEqual(guard.guard(proj, base, self._head(proj)), 0)


class TestWiring(unittest.TestCase):
    def test_contract_declares_repoclear_domain(self):
        contract = json.loads((ROOT / "quality-contract.json").read_text(encoding="utf-8"))
        domain = contract["domains"].get("repoclear")
        self.assertIsNotNone(domain, "quality-contract.json has no repoclear domain")
        self.assertTrue(domain.get("required"))
        self.assertIn("tools/repoclear/scan.py check", domain.get("cmd", ""))

    def test_skip_dirs_cover_pile_skip_dirs(self):
        # The scanner's SKIP_DIRS is a local copy, not shared with pile.py.
        # The drift that split invites is pinned here: the scanner's set
        # must cover pile.py's, so a directory pile.py skips is never one
        # the empty-dir walk descends into.
        pile = _load(ROOT / "tools" / "audit" / "pile.py")
        self.assertTrue(pile.SKIP_DIRS <= scan.SKIP_DIRS,
                        f"pile SKIP_DIRS {pile.SKIP_DIRS} not covered by "
                        f"repoclear SKIP_DIRS {scan.SKIP_DIRS}")

    def test_committed_baseline_matches_live_tree(self):
        baseline = scan.load_baseline(ROOT / "state" / "repoclear-baseline.json")
        measured = scan.collect(ROOT)["counts"]
        self.assertEqual(measured, baseline,
                         "committed baseline drifted from the live tree; "
                         "collapse the growth or regenerate it deliberately")


if __name__ == "__main__":
    unittest.main()
