"""Oracle for tools/audit/a2a_agreement_oracle.py (night-rick#13).

The agreement gate (ADR-0004) is only real if a claimed second-model review
can be traced to a recorded dispatch for the commit under review. These
checks pin the oracle's verdicts, including the adversarial cases:

  - a missing audit log fails closed (that absence is the #13 finding);
  - records for another commit do not satisfy the gate;
  - failed / timed-out records for the commit do not satisfy the gate;
  - a completed record for the commit passes, including short-SHA prefixes;
  - malformed lines are skipped, never a crash;
  - a record with commit "unknown" never matches a real SHA;
  - the writer seam: log_call records the commit it was given, resolves
    $A2A_COMMIT, and falls back to "unknown" outside a repo without raising.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORACLE_PATH = ROOT / "tools" / "audit" / "a2a_agreement_oracle.py"
AUDIT_PATH = ROOT / "dot-claude" / "bin" / "a2a-audit.py"

COMMIT = "a" * 40
OTHER = "b" * 40


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


oracle = _load(ORACLE_PATH, "a2a_agreement_oracle_under_test")
a2a_audit = _load(AUDIT_PATH, "a2a_audit_under_test")


def _write_log(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


class TestOracleVerdicts(unittest.TestCase):
    def test_missing_log_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            verdict, reason, _ = oracle.check_commit(COMMIT, Path(tmp) / "audit.jsonl")
            self.assertEqual(verdict, "FAIL")
            self.assertTrue(reason.startswith("LOG_MISSING"), reason)

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

    def test_short_sha_prefix_matches_both_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": COMMIT[:12], "state": "completed"}])
            self.assertEqual(oracle.check_commit(COMMIT, log)[0], "PASS")
            _write_log(log, [{"commit": COMMIT, "state": "completed"}])
            self.assertEqual(oracle.check_commit(COMMIT[:12], log)[0], "PASS")

    def test_malformed_lines_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            log.write_text(
                "{not json\n"
                + json.dumps({"commit": COMMIT, "state": "completed"})
                + "\n"
                + "[1, 2, 3]\n"
            )
            verdict, _, malformed = oracle.check_commit(COMMIT, log)
            self.assertEqual(verdict, "PASS")
            self.assertEqual(malformed, 2)

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

    def test_cli_selftest_passes(self):
        proc = self._run_cli("selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS a2a_agreement_oracle selftest", proc.stdout)

    def test_cli_check_defaults_to_head_in_a_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            _write_log(log, [{"commit": COMMIT, "state": "completed"}])
            proc = self._run_cli("check", "--audit-log", str(log), cwd=str(ROOT))
            # ROOT is a git checkout, so HEAD resolves; COMMIT is not HEAD.
            self.assertEqual(proc.returncode, 1)
            self.assertIn("NO_RECORD_FOR_COMMIT", proc.stdout)


class TestWriterSeam(unittest.TestCase):
    def test_log_call_records_explicit_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = dict(os.environ)
            env["HOME"] = str(home)
            # The module binds AUDIT_LOG at import time from the real HOME,
            # so drive it through the CLI with a redirected HOME instead.
            proc = subprocess.run(
                (
                    sys.executable,
                    str(AUDIT_PATH),
                    "log",
                    "claude:home",
                    "codex:home",
                    "abc123",
                    "100",
                    "completed",
                    "--commit",
                    COMMIT,
                ),
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            records = [
                json.loads(line)
                for line in (home / ".claude" / "cache" / "a2a" / "audit.jsonl").read_text().splitlines()
            ]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["commit"], COMMIT)
            self.assertEqual(records[0]["state"], "completed")

    def test_log_call_env_commit_and_unknown_fallback(self):
        self.assertEqual(a2a_audit.resolve_commit(COMMIT), COMMIT)
        saved = os.environ.pop("A2A_COMMIT", None)
        try:
            os.environ["A2A_COMMIT"] = OTHER
            self.assertEqual(a2a_audit.resolve_commit(), OTHER)
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
        finally:
            os.chdir(old_cwd)
            if saved is not None:
                os.environ["A2A_COMMIT"] = saved


if __name__ == "__main__":
    unittest.main()
