#!/usr/bin/env python3
"""a2a-audit.py — append-only JSONL audit log for A2A calls.

Single source of truth at ~/.claude/cache/a2a/audit.jsonl. No sqlite tables
in v1 (per refined plan). Add tables only if querying becomes painful.

Usage as a module:
    from a2a_audit import log_call
    log_call(from_addr, to_addr, prompt_hash, duration_ms, state, conversation_id, **extra)

Usage as CLI (for shell bridges):
    a2a-audit.py log <from> <to> <prompt_hash> <duration_ms> <state> [<conversation_id>] [--commit SHA]
    a2a-audit.py tail [N]
    a2a-audit.py stats

Every record carries a "commit" field (night-rick#13): the commit the dispatch
was made for. HEAD of the repo under review is authoritative: a valid explicit
argument or $A2A_COMMIT is only a hint, checked against `git rev-parse HEAD`
(HEAD wins on mismatch and the hint is recorded as commit_hint_mismatch), else
HEAD, else the hint when no repo is present, else "unknown".
tools/audit/a2a_dispatch_oracle.py fails unless a completed call is recorded
for a given commit, so a record without a commit can never satisfy the check.
Commit resolution never raises: a logging failure must not break a dispatch.
(AUDIT_WRITER_SEAM is the version marker bridges check before relying on the
commit seam: 1 means this file records commits. A deployed copy without it
predates the seam.)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AUDIT_DIR = Path.home() / ".claude" / "cache" / "a2a"
AUDIT_LOG = AUDIT_DIR / "audit.jsonl"

UNKNOWN_COMMIT = "unknown"
AUDIT_WRITER_SEAM = 1

_HEX_RE = re.compile(r"[0-9a-f]+")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def hash_prompt(prompt: str, length: int = 12) -> str:
    return hashlib.sha1(prompt.encode("utf-8", errors="replace")).hexdigest()[:length]


def _valid_hint(value: str | None) -> str | None:
    """A commit hint is usable only as stripped hex, 7 to 40 chars, else None."""
    if value is None:
        return None
    hint = value.strip()
    if not 7 <= len(hint) <= 40:
        return None
    if _HEX_RE.fullmatch(hint) is None:
        return None
    return hint


def _head_commit() -> str | None:
    """HEAD SHA of the repo in the caller's working directory, else None."""
    try:
        proc = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            timeout=10,
        )
        sha = proc.stdout.strip()
        if proc.returncode == 0 and len(sha) == 40 and _HEX_RE.fullmatch(sha):
            return sha
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _head_repo() -> str:
    """Basename of the repo in the caller's working directory, else "unknown"."""
    try:
        proc = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            capture_output=True,
            text=True,
            timeout=10,
        )
        top = proc.stdout.strip()
        if proc.returncode == 0 and top:
            return Path(top).name or UNKNOWN_COMMIT
    except (OSError, subprocess.SubprocessError):
        pass
    return UNKNOWN_COMMIT


def _prefix_compatible(shorter: str, longer: str) -> bool:
    return longer.startswith(shorter) or shorter.startswith(longer)


def resolve_commit(explicit: str | None = None) -> str:
    """Commit a dispatch record belongs to. Never raises, never empty.

    HEAD is authoritative: a valid hint that disagrees with HEAD loses to
    HEAD (see resolve_commit_note for the recorded mismatch).
    """
    hint = _valid_hint(explicit) or _valid_hint(os.environ.get("A2A_COMMIT"))
    head = _head_commit()
    if head is not None:
        return head
    if hint is not None:
        return hint
    return UNKNOWN_COMMIT


def resolve_commit_note(explicit: str | None = None) -> str | None:
    """The hint, when it was valid but HEAD overruled it, else None.

    A mismatch is diagnosable, not silent: the caller passed a commit that
    is not the checkout's HEAD, so the record carries HEAD and this note.
    """
    hint = _valid_hint(explicit) or _valid_hint(os.environ.get("A2A_COMMIT"))
    if hint is None:
        return None
    head = _head_commit()
    if head is None:
        return None
    if _prefix_compatible(hint, head):
        return None
    return hint


def resolve_repo() -> str:
    """Repo identity for a dispatch record. Never raises."""
    return _head_repo()


def log_call(
    from_addr: str,
    to_addr: str,
    prompt_hash: str,
    duration_ms: int,
    state: str,
    conversation_id: str | None = None,
    commit: str | None = None,
    **extra,
) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    mismatch = resolve_commit_note(commit)
    record = {
        "ts": now_iso(),
        "from": from_addr,
        "to": to_addr,
        "prompt_hash": prompt_hash,
        "duration_ms": int(duration_ms),
        "state": state,
        "conversation_id": conversation_id,
        "commit": resolve_commit(commit),
        "repo": resolve_repo(),
        **extra,
    }
    if mismatch is not None:
        record["commit_hint_mismatch"] = mismatch
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def tail(n: int = 20) -> None:
    if not AUDIT_LOG.exists():
        print("(no audit log yet)")
        return
    lines = AUDIT_LOG.read_text().splitlines()[-n:]
    for line in lines:
        try:
            r = json.loads(line)
            commit = str(r.get("commit", UNKNOWN_COMMIT))[:7]
            print(f"{r['ts']}  {r['from']:30s} -> {r['to']:30s}  {r['state']:10s}  {r['duration_ms']:>6}ms  {r.get('prompt_hash','-')}  {commit}")
        except Exception:
            print(line)


def stats() -> None:
    if not AUDIT_LOG.exists():
        print("(no audit log yet)")
        return
    by_pair: dict[tuple[str, str], dict] = {}
    by_state: dict[str, int] = {}
    for line in AUDIT_LOG.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        key = (r["from"], r["to"])
        agg = by_pair.setdefault(key, {"count": 0, "total_ms": 0, "ok": 0, "fail": 0})
        agg["count"] += 1
        agg["total_ms"] += r.get("duration_ms", 0)
        if r.get("state") == "completed":
            agg["ok"] += 1
        else:
            agg["fail"] += 1
        by_state[r.get("state", "?")] = by_state.get(r.get("state", "?"), 0) + 1

    print(f"Total calls: {sum(a['count'] for a in by_pair.values())}\n")
    print("By state:")
    for s, n in sorted(by_state.items(), key=lambda x: -x[1]):
        print(f"  {s:15s} {n}")
    print("\nBy pair (count, ok/fail, avg_ms):")
    for (f, t), a in sorted(by_pair.items(), key=lambda x: -x[1]["count"]):
        avg = a["total_ms"] // a["count"] if a["count"] else 0
        print(f"  {f:30s} -> {t:30s}  count={a['count']:3d}  ok/fail={a['ok']}/{a['fail']}  avg={avg}ms")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: a2a-audit.py {log|tail|stats} ...", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "log":
        args = sys.argv[2:]
        commit = None
        if "--commit" in args:
            idx = args.index("--commit")
            if idx + 1 >= len(args):
                print("usage: --commit needs a SHA", file=sys.stderr)
                sys.exit(2)
            commit = args[idx + 1]
            del args[idx : idx + 2]
        if len(args) < 5:
            print("usage: a2a-audit.py log <from> <to> <prompt_hash> <duration_ms> <state> [<conversation_id>] [--commit SHA]", file=sys.stderr)
            sys.exit(2)
        log_call(
            from_addr=args[0],
            to_addr=args[1],
            prompt_hash=args[2],
            duration_ms=int(args[3]),
            state=args[4],
            conversation_id=args[5] if len(args) > 5 else None,
            commit=commit,
        )
    elif cmd == "tail":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        tail(n)
    elif cmd == "stats":
        stats()
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
