"""Oracle for tools/audit/a2a_dispatch_oracle.py (night-rick#13).

A claimed second-model review is only checkable if it can be traced to a
recorded dispatch for the commit under review. These checks pin the
oracle's verdicts, including the adversarial cases:

  - a missing audit log fails closed (that absence is the #13 finding);
  - an unreadable audit log fails closed with LOG_UNREADABLE, no traceback;
  - records for another commit do not satisfy the check;
  - failed / timed-out records for the commit do not satisfy the check;
  - a completed record for the commit passes; a short SHA never matches,
    in either direction (exact full-SHA matching only);
  - reviewer and prompt-hash filters bind the check to the named review;
  - malformed lines are skipped, counted, and named in the reason;
  - a record with commit "unknown" never matches a real SHA;
  - the writer seam: HEAD is authoritative over explicit/env hints (a
    disagreeing hint is recorded as commit_hint_mismatch), invalid hints
    are ignored, and resolve_commit falls back to "unknown" outside a repo
    without raising;
  - the Gemini bridge: a stubbed successful call returns state "completed"
    and writes a completed record the oracle accepts.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ORACLE_PATH = ROOT / "tools" / "audit" / "a2a_dispatch_oracle.py"
AUDIT_PATH = ROOT / "dot-claude" / "bin" / "a2a-audit.py"
GEMINI_PATH = ROOT / "dot-claude" / "bin" / "a2a-gemini-call.py"

COMMIT = "a" * 40
OTHER = "b" * 40


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


oracle = _load(ORACLE_PATH, "a2a_dispatch_oracle_under_test")
a2a_audit = _load(AUDIT_PATH, "a2a_audit_under_test")


def _load_gemini():
    """Load the Gemini bridge with a controlled argv (it reads sys.argv at import)."""
    saved_argv = sys.argv
    sys.argv = ["a2a-gemini-call.py", "test prompt"]
    try:
        return _load(GEMINI_PATH, "a2a_gemini_call_under_test")
    finally:
        sys.argv = saved_argv


def _write_log(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


class TestOracleVerdicts(unittest.TestCase):
    def test_missing_log_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            verdict, reason, _ = oracle.check_commit(COMMIT, Path(tmp) / "audit.jsonl")
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("LOG_MISSING"), reason)

    def test_unreadable_log_fails_closed_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            verdict, reason, _ = oracle.check_commit(COMMIT, Path(tmp))
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("LOG_UNREADABLE"), reason)

    def test_other_commit_records_do_not_satisfy(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": OTHER, "state": "completed"}])
            verdict, reason, _ = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("NO_RECORD_FOR_COMMIT"), reason)

    def test_failed_and_timeout_records_do_not_satisfy(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [
                {"commit": COMMIT, "state": "failed"},
                {"commit": COMMIT, "state": "timeout"},
                {"commit": COMMIT, "state": "auth_failed"},
            ])
            verdict, reason, _ = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("NO_COMPLETED_CALL"), reason)

    def test_completed_record_for_commit_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [
                {"commit": OTHER, "state": "completed"},
                {"commit": COMMIT, "state": "failed"},
                {"commit": COMMIT, "state": "completed"},
            ])
            verdict, reason, _ = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "PASS")
            self.assertTrue(reason.startswith("PASS"), reason)

    def test_short_sha_never_matches_either_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": COMMIT[:12], "state": "completed"}])
            verdict, _, _ = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "FAIL")
            _write_log(log, [{"commit": COMMIT, "state": "completed"}])
            verdict, _, _ = oracle.check_commit(COMMIT[:12], log)
            self.assertEqual(verdict, "FAIL")

    def test_reviewer_filter_binds_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": COMMIT, "state": "completed", "to": "codex:home"}])
            verdict, reason, _ = oracle.check_commit(
                COMMIT, log, to="gemini:gemini-2.5-flash"
            )
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("NO_MATCHING_CALL"), reason)
            verdict, _, _ = oracle.check_commit(COMMIT, log, to="codex:home")
            self.assertEqual(verdict, "PASS")

    def test_prompt_hash_filter_binds_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{
                "commit": COMMIT,
                "state": "completed",
                "to": "codex:home",
                "prompt_hash": "abc123",
            }])
            verdict, reason, _ = oracle.check_commit(
                COMMIT, log, to="codex:home", prompt_hash="def456"
            )
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("NO_MATCHING_CALL"), reason)
            verdict, _, _ = oracle.check_commit(
                COMMIT, log, to="codex:home", prompt_hash="abc123"
            )
            self.assertEqual(verdict, "PASS")

    def test_malformed_lines_skipped_counted_and_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            log.write_text(
                "{not json\n"
                + json.dumps({"commit": COMMIT, "state": "completed"})
                + "\n"
                + "[1, 2, 3]\n"
            )
            verdict, reason, malformed = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "PASS")
            self.assertEqual(malformed, 2)
            self.assertIn("2 malformed line(s) skipped", reason)

    def test_unknown_commit_never_matches_real_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": "unknown", "state": "completed"}])
            verdict, reason, _ = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("NO_RECORD_FOR_COMMIT"), reason)

    def test_pre_seam_records_without_commit_field_do_not_satisfy(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"state": "completed"}])
            verdict, _, _ = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "FAIL")


class TestOracleCli(unittest.TestCase):
    def _run_cli(self, *args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            (sys.executable, str(ORACLE_PATH), *args),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_cli_check_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            proc = self._run_cli("check", "--commit", COMMIT, "--audit-log", str(log))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("LOG_MISSING", proc.stdout)
            _write_log(log, [{"commit": COMMIT, "state": "completed"}])
            proc = self._run_cli("check", "--commit", COMMIT, "--audit-log", str(log))
            self.assertEqual(proc.returncode, 0)
            self.assertIn("PASS", proc.stdout)

    def test_cli_check_with_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{
                "commit": COMMIT,
                "state": "completed",
                "to": "gemini:gemini-2.5-flash",
                "prompt_hash": "abc123",
            }])
            proc = self._run_cli(
                "check", "--commit", COMMIT, "--to", "codex:home",
                "--audit-log", str(log),
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("NO_MATCHING_CALL", proc.stdout)
            proc = self._run_cli(
                "check", "--commit", COMMIT, "--to", "gemini:gemini-2.5-flash",
                "--prompt-hash", "abc123", "--audit-log", str(log),
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("PASS", proc.stdout)

    def test_cli_rejects_short_and_empty_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": COMMIT, "state": "completed"}])
            proc = self._run_cli("check", "--commit", COMMIT[:12], "--audit-log", str(log))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("full 40-hex SHA", proc.stderr)
            proc = self._run_cli("check", "--commit", "", "--audit-log", str(log))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("empty value", proc.stderr)

    def test_cli_selftest_passes(self):
        proc = self._run_cli("selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS a2a_dispatch_oracle selftest", proc.stdout)

    def test_cli_check_defaults_to_head_in_a_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": COMMIT, "state": "completed"}])
            proc = self._run_cli("check", "--audit-log", str(log), cwd=str(ROOT))
            # ROOT is a git checkout, so HEAD resolves; COMMIT is not HEAD.
            self.assertEqual(proc.returncode, 1)
            self.assertIn("NO_RECORD_FOR_COMMIT", proc.stdout)


class TestWriterSeam(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self._old_cwd)

    def _run_audit_cli(self, *args: str, home: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["HOME"] = str(home)
        env.pop("A2A_COMMIT", None)
        return subprocess.run(
            (sys.executable, str(AUDIT_PATH), *args),
            env=env,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _read_records(self, home: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in (home / ".claude" / "cache" / "a2a" / "audit.jsonl").read_text().splitlines()
        ]

    def test_log_call_records_explicit_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            proc = self._run_audit_cli(
                "log", "claude:home", "codex:home", "abc123", "100", "completed",
                "--commit", COMMIT, home=home,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            records = self._read_records(home)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["state"], "completed")
            # HEAD of the test checkout wins over the explicit hint; the hint
            # is recorded as a mismatch instead of silently winning.
            head = subprocess.run(
                ("git", "rev-parse", "HEAD"), cwd=str(ROOT),
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            self.assertEqual(records[0]["commit"], head)
            self.assertEqual(records[0].get("commit_hint_mismatch"), COMMIT)
            self.assertIn("repo", records[0])

    def test_log_call_hint_matching_head_is_not_a_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            head = subprocess.run(
                ("git", "rev-parse", "HEAD"), cwd=str(ROOT),
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            proc = self._run_audit_cli(
                "log", "claude:home", "codex:home", "abc123", "100", "completed",
                "--commit", head, home=home,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            records = self._read_records(home)
            self.assertEqual(records[0]["commit"], head)
            self.assertNotIn("commit_hint_mismatch", records[0])

    def test_log_call_invalid_hint_is_ignored(self):
        # A whitespace-only or non-hex hint falls through to HEAD, not a crash.
        self.assertEqual(a2a_audit.resolve_commit("   "), a2a_audit.resolve_commit())
        self.assertEqual(a2a_audit.resolve_commit("not-a-sha!!"), a2a_audit.resolve_commit())

    def test_log_call_env_commit_and_unknown_fallback(self):
        self.assertEqual(a2a_audit.resolve_commit(COMMIT), a2a_audit.resolve_commit())
        saved = os.environ.pop("A2A_COMMIT", None)
        try:
            os.environ["A2A_COMMIT"] = OTHER
            # OTHER disagrees with HEAD, so HEAD still wins.
            self.assertEqual(a2a_audit.resolve_commit(), a2a_audit._head_commit())
            self.assertEqual(a2a_audit.resolve_commit_note(), OTHER)
        finally:
            if saved is None:
                del os.environ["A2A_COMMIT"]
            else:
                os.environ["A2A_COMMIT"] = saved
        # No explicit arg, no env, cwd outside any repo: "unknown", not a raise.
        saved = os.environ.pop("A2A_COMMIT", None)
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                self.assertEqual(a2a_audit.resolve_commit(), "unknown")
                self.assertEqual(a2a_audit.resolve_repo(), "unknown")
        finally:
            os.chdir(old_cwd)
            if saved is not None:
                os.environ["A2A_COMMIT"] = saved


class TestGeminiBridge(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self._old_cwd)

    def test_successful_call_returns_completed_and_logs_it(self):
        gemini = _load_gemini()
        body = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "review: looks good"}]}}]
        }).encode()

        class FakeResponse:
            def read(self):
                return body

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude" / "bin").mkdir(parents=True)
            shutil.copy(AUDIT_PATH, home / ".claude" / "bin" / "a2a-audit.py")
            saved_home = os.environ.get("HOME")
            saved_key = os.environ.get("GEMINI_API_KEY")
            os.environ["HOME"] = str(home)
            os.environ["GEMINI_API_KEY"] = "test-key"
            try:
                with mock.patch(
                    "urllib.request.urlopen", return_value=FakeResponse()
                ):
                    result = gemini.call("review this", "gemini-2.5-flash")
                self.assertEqual(result["state"], "completed")
                self.assertIn("duration_ms", result)
                gemini._log_call(result, "review this")
            finally:
                if saved_home is None:
                    del os.environ["HOME"]
                else:
                    os.environ["HOME"] = saved_home
                if saved_key is None:
                    del os.environ["GEMINI_API_KEY"]
                else:
                    os.environ["GEMINI_API_KEY"] = saved_key
            records = [
                json.loads(line)
                for line in (home / ".claude" / "cache" / "a2a" / "audit.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["state"], "completed")
            self.assertEqual(records[0]["to"], "gemini:gemini-2.5-flash")
            head = subprocess.run(
                ("git", "rev-parse", "HEAD"), cwd=str(ROOT),
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            self.assertEqual(records[0]["commit"], head)
            # And the oracle accepts that record for HEAD.
            verdict, _, _ = oracle.check_commit(
                head,
                home / ".claude" / "cache" / "a2a" / "audit.jsonl",
                to="gemini:gemini-2.5-flash",
            )
            self.assertEqual(verdict, "PASS")


if __name__ == "__main__":
    unittest.main()
