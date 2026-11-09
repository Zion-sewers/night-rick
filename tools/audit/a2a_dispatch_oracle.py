#!/usr/bin/env python3
"""a2a_dispatch_oracle.py, a log-presence check for the two-model agreement gate.

Why this exists
---------------
night-rick#13: ~/.claude/cache/a2a/audit.jsonl is the dispatch skill's
canonical record of every agent-to-agent call, and it did not exist, the
bridge was fully deployed and had never fired. The absence was only
discoverable by thinking to look.

This tool makes the absence cheap to detect by hand. Given a commit SHA, it
fails unless audit.jsonl holds at least one COMPLETED dispatch recorded for
that commit. A missing log fails closed (LOG_MISSING), because no record is
exactly the failure the EPIC names.

What PASS does and does not prove
---------------------------------
PASS proves one thing: a completed dispatch is recorded for the commit, and,
when the caller passes them, for the named reviewer and prompt hash. It does
NOT prove the second model agreed with anything, reviewed the right content,
or was even a different model. A completed call with the wrong prompt, a
truncated review, or an unrelated second model passes. The log is a plain
local file the claimant can write by hand, so this is a tripwire for
forgetfulness, not proof of agreement. Never present it as the agreement gate
itself. The gate needs a later unit: a bound claim (commit, reviewer,
prompt hash, agreement outcome) checked against evidence the claimant
cannot rewrite.

Matching is exact and strict. The commit must be a full 40-hex SHA; short
prefixes never match, because a prefix identifies a snapshot only when it is
proven unique, and this tool proves nothing about uniqueness. A record whose
commit is "unknown" never matches a real SHA. Optional --to and
--prompt-hash filters bind the check to the reviewer and the review the
_provenance claim refers to; pass them whenever the claim names them.

The commit a record carries comes from dot-claude/bin/a2a-audit.py, which
resolves it as: a valid explicit argument or $A2A_COMMIT hint, checked
against `git rev-parse HEAD` (HEAD wins on mismatch, the hint is recorded as
commit_hint_mismatch), else HEAD, else the hint when no repo is present,
else the literal "unknown". Commit resolution never raises: a logging
failure must not break a dispatch.

Usage:
    python tools/audit/a2a_dispatch_oracle.py check [--commit SHA] [--to ADDR] [--prompt-hash HASH] [--audit-log PATH]
    python tools/audit/a2a_dispatch_oracle.py selftest

Exit codes for `check`: 0 = a completed call is recorded for the commit
(and matches the given filters), 1 = the gate is not satisfied (reason
printed), 2 = usage error (no commit could be determined, an empty commit,
or a commit that is not a full 40-hex SHA).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_AUDIT_LOG = Path.home() / ".claude" / "cache" / "a2a" / "audit.jsonl"

UNKNOWN_COMMIT = "unknown"

FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")

REASON_LOG_MISSING = "LOG_MISSING"
REASON_LOG_UNREADABLE = "LOG_UNREADABLE"
REASON_NO_RECORD_FOR_COMMIT = "NO_RECORD_FOR_COMMIT"
REASON_NO_COMPLETED_CALL = "NO_COMPLETED_CALL"
REASON_NO_MATCHING_CALL = "NO_MATCHING_CALL"
REASON_PASS = "PASS"


def is_full_sha(value: str) -> bool:
    """True only for a full 40-hex SHA. Anything else is not a commit identity."""
    return FULL_SHA_RE.fullmatch(value) is not None


def commit_matches(record_commit: str, want: str) -> bool:
    """True only when a record's commit is exactly the wanted full SHA.

    Short prefixes never match, and "unknown" never matches a real SHA.
    """
    return record_commit == want and is_full_sha(record_commit) and is_full_sha(want)


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
    if proc.returncode != 0 or not is_full_sha(sha):
        return None
    return sha


def check_commit(
    commit: str,
    audit_log: Path,
    to: str | None = None,
    prompt_hash: str | None = None,
) -> tuple[str, str, int]:
    """Check the dispatch log for one commit.

    Returns (verdict, reason, malformed_lines): verdict is "PASS" or "FAIL".
    Malformed log lines are skipped and counted, never a crash, and the count
    is appended to the reason so a corrupt log cannot pass quietly.
    """
    try:
        text = audit_log.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return (
            "FAIL",
            f"{REASON_LOG_MISSING}: no audit log at {audit_log}, "
            "zero dispatches have ever been recorded",
            0,
        )
    except OSError as exc:
        return (
            "FAIL",
            f"{REASON_LOG_UNREADABLE}: audit log at {audit_log} cannot be read ({exc})",
            0,
        )
    saw_commit = False
    saw_completed = False
    saw_matching = False
    malformed = 0
    for line in text.splitlines():
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
        if record.get("state") != "completed":
            continue
        saw_completed = True
        if to is not None and str(record.get("to", "")) != to:
            continue
        if prompt_hash is not None and str(record.get("prompt_hash", "")) != prompt_hash:
            continue
        saw_matching = True
    suffix = f" [{malformed} malformed line(s) skipped]" if malformed else ""
    if not saw_commit:
        return (
            "FAIL",
            f"{REASON_NO_RECORD_FOR_COMMIT}: no audit record for commit {commit}{suffix}",
            malformed,
        )
    if not saw_completed:
        return (
            "FAIL",
            f"{REASON_NO_COMPLETED_CALL}: audit has records for commit {commit} "
            f"but none completed{suffix}",
            malformed,
        )
    if not saw_matching:
        return (
            "FAIL",
            f"{REASON_NO_MATCHING_CALL}: completed dispatch recorded for commit {commit} "
            "but none matches the given reviewer / prompt hash"
            f"{suffix}",
            malformed,
        )
    return (
        "PASS",
        f"{REASON_PASS}: completed dispatch recorded for commit {commit}{suffix}",
        malformed,
    )


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
        # 2. Unreadable log (a directory) fails closed, no traceback.
        expect(
            "unreadable-log",
            check_commit(commit, root),
            "FAIL",
            REASON_LOG_UNREADABLE,
        )
        log = root / "audit.jsonl"
        # 3. Only other-commit records fail.
        log.write_text(json.dumps({"commit": other, "state": "completed"}) + "\n")
        expect("other-commit", check_commit(commit, log), "FAIL", REASON_NO_RECORD_FOR_COMMIT)
        # 4. Failed record for this commit fails.
        log.write_text(json.dumps({"commit": commit, "state": "failed"}) + "\n")
        expect("failed-only", check_commit(commit, log), "FAIL", REASON_NO_COMPLETED_CALL)
        # 5. Timeout record for this commit fails.
        log.write_text(json.dumps({"commit": commit, "state": "timeout"}) + "\n")
        expect("timeout-only", check_commit(commit, log), "FAIL", REASON_NO_COMPLETED_CALL)
        # 6. Completed record for this commit passes.
        log.write_text(json.dumps({"commit": commit, "state": "completed"}) + "\n")
        expect("completed", check_commit(commit, log), "PASS", REASON_PASS)
        # 7. A short-SHA record never matches a full SHA (exact matching only).
        log.write_text(json.dumps({"commit": commit[:12], "state": "completed"}) + "\n")
        expect("short-record", check_commit(commit, log), "FAIL", REASON_NO_RECORD_FOR_COMMIT)
        # 8. A short SHA given on the command line never matches a full record.
        log.write_text(json.dumps({"commit": commit, "state": "completed"}) + "\n")
        expect(
            "short-want",
            check_commit(commit[:12], log),
            "FAIL",
            REASON_NO_RECORD_FOR_COMMIT,
        )
        # 9. Malformed lines are skipped and counted in the reason.
        log.write_text(
            "{not json\n" + json.dumps({"commit": commit, "state": "completed"}) + "\n"
        )
        verdict, reason, malformed = check_commit(commit, log)
        checks += 1
        assert verdict == "PASS" and malformed == 1, f"malformed: {verdict} {malformed}"
        assert "1 malformed line(s) skipped" in reason, f"malformed not in reason: {reason}"
        # 10. A record with no commit field (pre-seam log) never satisfies the gate.
        log.write_text(json.dumps({"state": "completed"}) + "\n")
        expect("no-commit-field", check_commit(commit, log), "FAIL", REASON_NO_RECORD_FOR_COMMIT)
        # 11. commit="unknown" never matches a real SHA.
        log.write_text(json.dumps({"commit": UNKNOWN_COMMIT, "state": "completed"}) + "\n")
        expect("unknown-commit", check_commit(commit, log), "FAIL", REASON_NO_RECORD_FOR_COMMIT)
        # 12. Reviewer filter: a completed record for another reviewer fails.
        log.write_text(
            json.dumps({"commit": commit, "state": "completed", "to": "codex:home"}) + "\n"
        )
        expect(
            "wrong-reviewer",
            check_commit(commit, log, to="gemini:gemini-2.5-flash"),
            "FAIL",
            REASON_NO_MATCHING_CALL,
        )
        # 13. Reviewer filter: the named reviewer passes.
        expect(
            "right-reviewer",
            check_commit(commit, log, to="codex:home"),
            "PASS",
            REASON_PASS,
        )
        # 14. Prompt-hash filter: a mismatched hash fails, a matching hash passes.
        log.write_text(
            json.dumps(
                {"commit": commit, "state": "completed", "to": "codex:home", "prompt_hash": "abc123"}
            )
            + "\n"
        )
        expect(
            "wrong-prompt-hash",
            check_commit(commit, log, to="codex:home", prompt_hash="def456"),
            "FAIL",
            REASON_NO_MATCHING_CALL,
        )
        expect(
            "right-prompt-hash",
            check_commit(commit, log, to="codex:home", prompt_hash="abc123"),
            "PASS",
            REASON_PASS,
        )

    # commit_matches unit pins.
    pins: list[tuple[str, str, bool]] = [
        ("a" * 40, "a" * 40, True),
        ("a" * 12, "a" * 40, False),
        ("a" * 40, "a" * 12, False),
        ("a" * 6, "a" * 40, False),
        ("b" * 40, "a" * 40, False),
        ("z" * 40, "z" * 40, False),
        (UNKNOWN_COMMIT, "a" * 40, False),
        ("a" * 40, UNKNOWN_COMMIT, False),
    ]
    for record_commit, want, expected in pins:
        checks += 1
        assert commit_matches(record_commit, want) is expected, (
            f"commit_matches({record_commit!r}, {want!r}) != {expected}"
        )

    print(f"PASS a2a_dispatch_oracle selftest ({checks} checks)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser(
        "check",
        help="fail unless a completed dispatch is recorded for a commit",
    )
    p_check.add_argument("--commit", default=None, help="full 40-hex commit SHA (default: git HEAD)")
    p_check.add_argument("--to", default=None, help="reviewer address the record must name")
    p_check.add_argument("--prompt-hash", default=None, help="prompt hash the record must carry")
    p_check.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG)
    sub.add_parser("selftest", help="run the adversarial cases")
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return selftest()

    if args.commit is not None and args.commit == "":
        print("usage error: --commit was given an empty value", file=sys.stderr)
        return 2
    commit = args.commit or resolve_head_commit()
    if commit is None:
        print(
            "usage error: no --commit given and HEAD is not resolvable here "
            "(not a git checkout?)",
            file=sys.stderr,
        )
        return 2
    if not is_full_sha(commit):
        print(
            f"usage error: --commit must be a full 40-hex SHA, got {commit!r}",
            file=sys.stderr,
        )
        return 2
    verdict, reason, malformed = check_commit(commit, args.audit_log, args.to, args.prompt_hash)
    if malformed:
        print(f"note: skipped {malformed} malformed log line(s)", file=sys.stderr)
    print(reason)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
