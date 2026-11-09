#!/usr/bin/env python3
"""a2a_agreement_oracle.py, the audit.jsonl oracle for the two-model agreement gate.

Why this exists
---------------
night-rick#13: ~/.claude/cache/a2a/audit.jsonl is the dispatch skill's
canonical record of every agent-to-agent call, and it did not exist, the
bridge was fully deployed and had never fired. The absence was only
discoverable by thinking to look.

This oracle makes the absence checkable: given a commit SHA, it fails unless
audit.jsonl holds at least one COMPLETED dispatch recorded for that commit.
A missing log fails closed (LOG_MISSING), because no record is exactly the
failure the EPIC names. A record for another commit, or a failed/timed-out
record for this commit, does not satisfy the gate.

The commit a record carries comes from dot-claude/bin/a2a-audit.py, which
resolves it as: explicit argument, else $A2A_COMMIT, else `git rev-parse HEAD`
in the caller's working directory, else the literal "unknown". A record whose
commit is "unknown" never matches a real SHA.

Usage:
    python tools/audit/a2a_agreement_oracle.py check [--commit SHA] [--audit-log PATH]
    python tools/audit/a2a_agreement_oracle.py selftest

Exit codes for `check`: 0 = a completed call is recorded for the commit,
1 = the gate is not satisfied (reason printed), 2 = usage error (no commit
could be determined and none was given).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_AUDIT_LOG = Path.home() / ".claude" / "cache" / "a2a" / "audit.jsonl"

UNKNOWN_COMMIT = "unknown"
MIN_PREFIX_LEN = 7

REASON_LOG_MISSING = "LOG_MISSING"
REASON_NO_RECORD_FOR_COMMIT = "NO_RECORD_FOR_COMMIT"
REASON_NO_COMPLETED_CALL = "NO_COMPLETED_CALL"
REASON_PASS = "PASS"


def commit_matches(record_commit: str, want: str) -> bool:
    """True when a record's commit identifies the wanted commit.

    Exact match, or a prefix match in either direction when the shorter side
    is at least 7 hex characters (a short SHA the caller or the writer
    produced). "unknown" never matches a real SHA, and a real SHA never
    matches "unknown".
    """
    if record_commit == UNKNOWN_COMMIT or want == UNKNOWN_COMMIT:
        return record_commit == want == UNKNOWN_COMMIT and False
    if record_commit == want:
        return True
    shorter = record_commit if len(record_commit) <= len(want) else want
    longer = want if len(record_commit) <= len(want) else record_commit
    return len(shorter) >= MIN_PREFIX_LEN and longer.startswith(shorter)


def resolve_head_commit(cwd: str | None = None) -> str | None:
    """Current HEAD SHA, or None when the working directory is not a repo."""
    try:
        proc = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = proc.stdout.strip()
    if proc.returncode != 0 or len(sha) < MIN_PREFIX_LEN:
        return None
    return sha


def check_commit(commit: str, audit_log: Path) -> tuple[str, str, int]:
    """Check the agreement gate for one commit.

    Returns (verdict, reason, malformed_lines): verdict is "PASS" or "FAIL".
    Malformed log lines are skipped and counted, never a crash.
    """
    if not audit_log.exists():
        return (
            "FAIL",
            f"{REASON_LOG_MISSING}: no audit log at {audit_log}, "
            "zero dispatches have ever been recorded",
            0,
        )
    saw_commit = False
    saw_completed = False
    malformed = 0
    for line in audit_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(record, dict):
            malformed += 1
            continue
        if not commit_matches(str(record.get("commit", UNKNOWN_COMMIT)), commit):
            continue
        saw_commit = True
        if record.get("state") == "completed":
            saw_completed = True
    if not saw_commit:
        return (
            "FAIL",
            f"{REASON_NO_RECORD_FOR_COMMIT}: no audit record for commit {commit}",
            malformed,
        )
    if not saw_completed:
        return (
            "FAIL",
            f"{REASON_NO_COMPLETED_CALL}: audit has records for commit {commit} "
            "but none completed",
            malformed,
        )
    return ("PASS", f"{REASON_PASS}: completed dispatch recorded for commit {commit}", malformed)


def selftest() -> int:
    """Adversarial cases, in-process. Every planted violation must be caught."""
    checks = 0

    def expect(name: str, got: tuple[str, str, int], want_verdict: str, want_reason: str) -> None:
        nonlocal checks
        checks += 1
        verdict, reason, _ = got
        assert verdict == want_verdict, f"{name}: verdict {verdict} != {want_verdict} ({reason})"
        assert reason.startswith(want_reason), f"{name}: reason {reason!r} lacks {want_reason!r}"

    commit = "a" * 40
    other = "b" * 40

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 1. Missing log fails closed.
        expect(
            "missing-log",
            check_commit(commit, root / "audit.jsonl"),
            "FAIL",
            REASON_LOG_MISSING,
        )
        log = root / "audit.jsonl"
        # 2. Only other-commit records fail.
        log.write_text(json.dumps({"commit": other, "state": "completed"}) + "\n")
        expect("other-commit", check_commit(commit, log), "FAIL", REASON_NO_RECORD_FOR_COMMIT)
        # 3. Failed record for this commit fails.
        log.write_text(json.dumps({"commit": commit, "state": "failed"}) + "\n")
        expect("failed-only", check_commit(commit, log), "FAIL", REASON_NO_COMPLETED_CALL)
        # 4. Timeout record for this commit fails.
        log.write_text(json.dumps({"commit": commit, "state": "timeout"}) + "\n")
        expect("timeout-only", check_commit(commit, log), "FAIL", REASON_NO_COMPLETED_CALL)
        # 5. Completed record for this commit passes.
        log.write_text(json.dumps({"commit": commit, "state": "completed"}) + "\n")
        expect("completed", check_commit(commit, log), "PASS", REASON_PASS)
        # 6. Short-SHA prefix matches (writer wrote a short SHA).
        log.write_text(json.dumps({"commit": commit[:12], "state": "completed"}) + "\n")
        expect("short-prefix", check_commit(commit, log), "PASS", REASON_PASS)
        # 7. Short SHA given on the command line matches a full recorded SHA.
        expect(
            "short-want",
            check_commit(commit[:12], log),
            "PASS",
            REASON_PASS,
        )
        # 8. Malformed line is skipped; the verdict still follows the records.
        log.write_text(
            "{not json\n" + json.dumps({"commit": commit, "state": "completed"}) + "\n"
        )
        verdict, _, malformed = check_commit(commit, log)
        checks += 1
        assert verdict == "PASS" and malformed == 1, f"malformed: {verdict} {malformed}"
        # 9. A record with no commit field (pre-seam log) never satisfies the gate.
        log.write_text(json.dumps({"state": "completed"}) + "\n")
        expect("no-commit-field", check_commit(commit, log), "FAIL", REASON_NO_RECORD_FOR_COMMIT)
        # 10. commit="unknown" never matches a real SHA.
        log.write_text(json.dumps({"commit": UNKNOWN_COMMIT, "state": "completed"}) + "\n")
        expect("unknown-commit", check_commit(commit, log), "FAIL", REASON_NO_RECORD_FOR_COMMIT)

    # commit_matches unit pins.
    pins: list[tuple[str, str, bool]] = [
        ("a" * 40, "a" * 40, True),
        ("a" * 12, "a" * 40, True),
        ("a" * 40, "a" * 12, True),
        ("a" * 6, "a" * 40, False),
        ("b" * 40, "a" * 40, False),
        (UNKNOWN_COMMIT, "a" * 40, False),
        ("a" * 40, UNKNOWN_COMMIT, False),
    ]
    for record_commit, want, expected in pins:
        checks += 1
        assert commit_matches(record_commit, want) is expected, (
            f"commit_matches({record_commit!r}, {want!r}) != {expected}"
        )

    print(f"PASS a2a_agreement_oracle selftest ({checks} checks)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="fail unless a completed call is recorded for a commit")
    p_check.add_argument("--commit", default=None, help="commit SHA (default: git HEAD)")
    p_check.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG)
    sub.add_parser("selftest", help="run the adversarial cases")
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return selftest()

    commit = args.commit or resolve_head_commit()
    if commit is None:
        print(
            "usage error: no --commit given and HEAD is not resolvable here "
            "(not a git checkout?)",
            file=sys.stderr,
        )
        return 2
    verdict, reason, malformed = check_commit(commit, args.audit_log)
    if malformed:
        print(f"note: skipped {malformed} malformed log line(s)", file=sys.stderr)
    print(reason)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
