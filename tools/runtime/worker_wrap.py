#!/usr/bin/env python3
"""Lifecycle inheritance for headless scheduled workers.

The seven lifecycle events in dot-claude/settings.json (SessionStart,
UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop, Notification) only
fire inside an interactive session. A cron-driven worker runs as a plain prompt
with none of them attached, so this module maps each event onto a command the
worker invokes itself:

  SessionStart      -> begin           context injection + handoff replay
  UserPromptSubmit  -> begin           structured intent capture (hashed ticket)
  PreToolUse        -> gate            risk classification before external effects
  PostToolUse       -> panel          deterministic persona review of written code
  PostToolUse       -> check-evidence  every claim cites a resolvable pointer
  PreCompact        -> (unmapped)      headless workers do not compact; the
                                      handoff row is the state-preservation half
  Stop              -> end             completion checklist + persistent handoff
  Notification      -> (unmapped)      no operator is listening on a cron run

Unmapped events are documented here rather than silently dropped, so the
coverage boundary is explicit. This is stdlib only: no network calls, no model
calls, no hardcoded models. Every rule below is executed by one of these
commands; none of it lives only in this docstring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[2]
# Overridable so tests and dry runs do not append to the real ledgers.
STATE = Path(os.environ.get("WORKER_WRAP_STATE", HARNESS_ROOT / "state"))
PANEL = HARNESS_ROOT / "tools" / "review" / "panel.py"

INTENTS = "worker-intents.jsonl"
GATELOG = "worker-gate.jsonl"
RUNS = "worker-runs.jsonl"

GIT_TIMEOUT = 15
PANEL_TIMEOUT = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sh(cmd: list[str], cwd: str | Path, timeout: int = GIT_TIMEOUT) -> tuple[int, str]:
    """Run one command. Every call site passes an explicit timeout; there is no
    default-timeout path because a hung child must not hang the worker."""
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                              timeout=timeout, shell=False)
        return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "spawn failed: {}".format(exc)


# ---------------------------------------------------------------------------
# Append-only hash-chained ledgers. Each row carries the sha256 of the previous
# raw line ("GENESIS" for the first), so rewriting history is visible, the same
# property tools/bus/bus.py verifies for state/bus.jsonl.
# ---------------------------------------------------------------------------

def append_row(ledger: str, row: dict) -> dict:
    STATE.mkdir(parents=True, exist_ok=True)
    path = STATE / ledger
    prev = "GENESIS"
    if path.exists():
        with path.open("rb") as handle:
            for line in handle:
                if line.strip():
                    prev = sha(line.decode("utf-8", "replace").rstrip("\n"))
    row = dict(row)
    row["prev"] = prev
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def read_rows(ledger: str) -> list[dict]:
    path = STATE / ledger
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def verify_chain(ledger: str) -> tuple[bool, str]:
    """Recompute the chain. Returns (ok, reason). Used by selftest and by `end`
    before it trusts the handoff it is about to extend."""
    path = STATE / ledger
    if not path.exists():
        return True, "no ledger yet"
    prev = "GENESIS"
    with path.open("rb") as handle:
        for lineno, line in enumerate(handle, 1):
            raw = line.decode("utf-8", "replace").rstrip("\n")
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                return False, "line {} is not JSON".format(lineno)
            if row.get("prev") != prev:
                return False, "line {} breaks the chain".format(lineno)
            prev = sha(raw)
    return True, "chain intact"


# ---------------------------------------------------------------------------
# SessionStart + UserPromptSubmit -> begin
# ---------------------------------------------------------------------------

SIGNALS = ("push", "merge", "issue", "pr", "test", "deploy", "release",
           "delete", "migrate", "publish")


def parse_intent(prompt: str) -> dict:
    """Deterministic parse of a worker prompt into a structured intent record.

    Hand-coded rules, no model call: the goal is the first non-empty line,
    constraints are bullet/numbered lines, signals are keyword hits that tell
    the worker which gates it will need. The prompt text itself is never stored
    in the git-tracked ledger; only its sha256, following the convention in
    tools/intent/capture_turn.py."""
    lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
    goal = lines[0][:200] if lines else ""
    constraints = [ln[:200] for ln in lines[1:]
                   if re.match(r"^([-*]|\d+[.)])\s+", ln)]
    lowered = prompt.lower()
    signals = sorted(s for s in SIGNALS if re.search(r"\b" + s + r"\b", lowered))
    return {"prompt_sha": sha(prompt), "goal": goal,
            "constraints": constraints, "signals": signals}


def current_session_path(worker: str) -> Path:
    return STATE / "worker-current-{}.json".format(re.sub(r"[^A-Za-z0-9_-]", "_", worker))


def cmd_begin(args: argparse.Namespace) -> int:
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    intent = parse_intent(prompt)
    ok, reason = verify_chain(RUNS)
    last = None
    for row in reversed(read_rows(RUNS)):
        if row.get("worker") == args.worker:
            last = row
            break
    rc, base = sh(["git", "rev-parse", "HEAD"], args.repo)
    base = base if rc == 0 else "no-commit"
    session_id = sha(args.worker + utc_now())[:12]
    append_row(INTENTS, {"ts": utc_now(), "worker": args.worker,
                        "session": session_id, **intent})
    current_session_path(args.worker).write_text(
        json.dumps({"worker": args.worker, "session": session_id,
                    "base": base, "repo": os.path.abspath(args.repo),
                    "intent": intent, "panel_head": None,
                    "evidence": None}, indent=2), encoding="utf-8")
    print("[worker-wrap] session {} opened for worker '{}'".format(session_id, args.worker))
    print("  base commit: {}".format(base))
    print("  intent: goal={!r} signals={}".format(intent["goal"], intent["signals"]))
    if last:
        print("  last handoff ({}): {}".format(last.get("ts"), last.get("summary", "")))
        print("  previous checklist: {}".format(
            ", ".join("{}={}".format(k, v) for k, v in last.get("checklist", {}).items())))
    else:
        print("  no previous handoff for this worker (first run)")
    if not ok:
        print("  WARNING: handoff chain: {}".format(reason))
    print("  gate rules: DENY destructive/irreversible commands; "
          "NEEDS_AUTH for pushes, issue/PR create/merge, network posts; "
          "everything else ALLOW. Use `gate --action` before acting.")
    return 0


# ---------------------------------------------------------------------------
# PreToolUse -> gate. Deny-list discipline like hookgate plus an authorization
# tier like pretooluse-risk-guard.py. Unfamiliar shapes default to ALLOW, which
# is a stated coverage boundary, not an oversight: the gate log records every
# decision so a gap is countable.
# ---------------------------------------------------------------------------

DENY = [
    (r"\brm\s+(-[a-z]*r[a-z]*|--recursive)\b.*?(^|\s)(/|~|\$HOME|\*)(\s|$)",
     "recursive deletion"),
    (r"\bgit\s+reset\s+--hard\b", "hard reset discards work"),
    (r"\bgit\s+clean\s+-f", "forced clean discards untracked files"),
    (r"\bgit\s+branch\s+-D\b", "forced branch deletion"),
    (r"\bgit\s+push\b.*(--force|-f\b)", "force push"),
    (r"\bgit\s+push\b[^|;&\n]*?\+[^\s]*:", "plus-refspec push"),
    (r"\bgit\s+push\b.*--(delete|mirror|prune)\b", "ref deletion via push"),
    (r"(curl|wget)\b[^|;&\n]*\|\s*(sh|bash)\b", "piped-to-shell download"),
    (r"\bgit\s+push\b[^|;&\n]*?(^|\s|:)(main|master)\s*$", "direct push to protected branch"),
]

NEEDS_AUTH = [
    (r"\bgit\s+push\b", "push publishes commits"),
    (r"\bgh\s+(issue|pr)\s+create\b", "creates a public artifact"),
    (r"\bgh\s+pr\s+merge\b", "merge is irreversible"),
    (r"\bgh\s+release\s+create\b", "publishes a release"),
    (r"\bgh\s+api\b.*-(X|--method)\s+(POST|PUT|PATCH|DELETE)\b", "mutating API call"),
    (r"\bcurl\b.*-(X|--request)\s+(POST|PUT|PATCH|DELETE)\b", "mutating network call"),
]


def classify(action: str) -> tuple[str, str]:
    for pattern, reason in DENY:
        if re.search(pattern, action):
            return "DENY", reason
    for pattern, reason in NEEDS_AUTH:
        if re.search(pattern, action):
            return "NEEDS_AUTH", reason
    return "ALLOW", "no risk pattern matched"


def cmd_gate(args: argparse.Namespace) -> int:
    verdict, reason = classify(args.action)
    authorized = args.authorized or os.environ.get("WORKER_AUTHORIZED") == "1"
    session = ""
    try:
        session = json.loads(
            current_session_path(args.worker).read_text(encoding="utf-8")).get("session", "")
    except (OSError, json.JSONDecodeError):
        pass
    row = {"ts": utc_now(), "worker": args.worker, "session": session,
           "action": args.action[:300], "verdict": verdict, "reason": reason,
           "authorized": bool(authorized) if verdict == "NEEDS_AUTH" else None}
    append_row(GATELOG, row)
    if verdict == "DENY":
        print("DENY: {} (rule: {})".format(args.action[:120], reason))
        return 2
    if verdict == "NEEDS_AUTH" and not authorized:
        print("NEEDS_AUTH: {} (rule: {}). Re-run with --authorized or "
              "WORKER_AUTHORIZED=1; the decision is in {}".format(
                  args.action[:120], reason, GATELOG))
        return 3
    print("ALLOW{}: {}".format(" (authorized)" if authorized else "", reason))
    return 0


# ---------------------------------------------------------------------------
# PostToolUse -> panel (deterministic persona review) and check-evidence
# ---------------------------------------------------------------------------

def cmd_panel(args: argparse.Namespace) -> int:
    repo = os.path.abspath(args.repo)
    rc, head = sh(["git", "rev-parse", "HEAD"], repo)
    if rc != 0:
        print("panel: not a git repository: {}".format(repo))
        return 2
    proc = subprocess.run(
        [sys.executable, str(PANEL), "run", "--project", repo],
        capture_output=True, timeout=PANEL_TIMEOUT, shell=False)
    out = proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")
    print(out[-3000:])
    artifact = Path(repo) / "state" / "reviews" / "{}.json".format(head)
    if not artifact.exists():
        print("panel: no artifact at {} (panel exit {})".format(artifact, proc.returncode))
        return 1
    try:
        sess = json.loads(current_session_path(args.worker).read_text(encoding="utf-8"))
        sess["panel_head"] = head
        current_session_path(args.worker).write_text(json.dumps(sess, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        pass
    print("panel: artifact {}".format(artifact))
    return 0


def resolve_pointer(pointer: str, repo: str) -> tuple[bool, str]:
    """Evidence pointers. Every claim must cite at least one resolvable pointer;
    a claim that points at nothing resolvable fails, which is the mechanical
    half of 'every claim needs evidence'."""
    if pointer.startswith("file:"):
        rel = pointer[5:]
        if ".." in Path(rel).parts:
            return False, "path escapes repo"
        target = Path(repo) / rel
        return (True, "exists") if target.is_file() else (False, "missing file")
    if pointer.startswith("run:"):
        rel = pointer[4:]
        target = Path(repo) / rel
        if not target.is_file():
            return False, "missing run record"
        try:
            record = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False, "run record is not JSON"
        if record.get("exit") == 0:
            return True, "exit 0"
        return False, "exit {}".format(record.get("exit"))
    if pointer.startswith("ledger:"):
        parts = pointer.split(":")
        if len(parts) != 3:
            return False, "ledger pointer needs ledger:<name>:<n>"
        _, name, num = parts
        try:
            want = int(num)
        except ValueError:
            return False, "bad row number"
        rows = read_rows(name if name.endswith(".jsonl") else name + ".jsonl")
        return (True, "row present") if len(rows) >= want else (False, "ledger too short")
    return False, "unknown pointer scheme"


def cmd_evidence(args: argparse.Namespace) -> int:
    try:
        claims = json.loads(Path(args.claims).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("evidence: cannot read claims file: {}".format(exc))
        return 1
    if not isinstance(claims, list):
        print("evidence: claims file must be a JSON list")
        return 1
    failures = []
    for item in claims:
        claim = item.get("claim", "") if isinstance(item, dict) else ""
        pointers = item.get("evidence", []) if isinstance(item, dict) else []
        if not pointers:
            failures.append((claim, "no evidence pointers"))
            continue
        resolved = [resolve_pointer(p, args.repo) for p in pointers]
        if not any(ok for ok, _ in resolved):
            failures.append((claim, "; ".join(
                "{}: {}".format(p, why) for p, (ok, why) in zip(pointers, resolved) if not ok)))
    try:
        sess = json.loads(current_session_path(args.worker).read_text(encoding="utf-8"))
        sess["evidence"] = {"claims": len(claims), "failures": len(failures)}
        current_session_path(args.worker).write_text(json.dumps(sess, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        pass
    if failures:
        print("evidence: {}/{} claims unresolved:".format(len(failures), len(claims)))
        for claim, why in failures:
            print("  - {!r}: {}".format(claim[:120], why))
        return 1
    print("evidence: {}/{} claims resolved".format(len(claims), len(claims)))
    return 0


# ---------------------------------------------------------------------------
# Stop -> end. Completion checklist, then the persistent handoff row.
# ---------------------------------------------------------------------------

def cmd_end(args: argparse.Namespace) -> int:
    checks: dict[str, bool] = {}
    notes: dict[str, str] = {}
    try:
        sess = json.loads(current_session_path(args.worker).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        sess = {}
    session = sess.get("session", "")
    repo = sess.get("repo") or os.path.abspath(args.repo)
    checks["session_open"] = bool(session)
    notes["session_open"] = "no open session; run begin first" if not session else session

    gate_rows = [r for r in read_rows(GATELOG)
                 if r.get("worker") == args.worker and r.get("session") == session]
    denied = [r for r in gate_rows if r.get("verdict") == "DENY"]
    unauth = [r for r in gate_rows
              if r.get("verdict") == "NEEDS_AUTH" and not r.get("authorized")]
    checks["no_denied_actions"] = not denied
    notes["no_denied_actions"] = ("{} denied action(s): {}".format(
        len(denied), denied[0]["action"][:80]) if denied else "clean")
    checks["auth_complete"] = not unauth
    notes["auth_complete"] = ("{} action(s) lacked authorization: {}".format(
        len(unauth), unauth[0]["action"][:80]) if unauth else "clean")

    rc, head = sh(["git", "rev-parse", "HEAD"], repo)
    head = head if rc == 0 else "no-commit"
    base = sess.get("base", "no-commit")
    rc2, diff = sh(["git", "diff", "--quiet", base, head], repo)
    code_changed = rc2 != 0
    if code_changed:
        artifact = Path(repo) / "state" / "reviews" / "{}.json".format(head)
        fresh = sess.get("panel_head") == head and artifact.exists()
        checks["panel_current"] = fresh
        notes["panel_current"] = ("panel artifact current for " + head[:8]
                                  if fresh else "code changed but no panel artifact for HEAD; run panel")
    else:
        checks["panel_current"] = True
        notes["panel_current"] = "no code changed"

    if args.claims:
        ev = sess.get("evidence")
        checks["evidence_ok"] = bool(ev) and ev.get("failures") == 0
        notes["evidence_ok"] = ("evidence validated" if checks["evidence_ok"]
                                else "claims not validated; run check-evidence")
    else:
        checks["evidence_ok"] = True
        notes["evidence_ok"] = "no claims file given"

    ok, chain_reason = verify_chain(RUNS)
    checks["chain_intact"] = ok
    notes["chain_intact"] = chain_reason

    passed = all(checks.values())
    row = {"ts": utc_now(), "worker": args.worker, "session": session,
           "base": base, "head": head,
           "gate": {"allow": sum(1 for r in gate_rows if r.get("verdict") == "ALLOW"),
                    "auth": sum(1 for r in gate_rows if r.get("verdict") == "NEEDS_AUTH"),
                    "deny": len(denied)},
           "checklist": checks, "summary": args.summary}
    append_row(RUNS, row)
    print("[worker-wrap] stop gate for '{}': {}".format(args.worker, "PASS" if passed else "FAIL"))
    for name, ok_item in checks.items():
        print("  [{}] {}: {}".format("x" if ok_item else " ", name, notes[name]))
    print("  handoff appended to {}".format(RUNS))
    return 0 if passed else 1


# ---------------------------------------------------------------------------
# selftest: every oracle carries its own, per repo convention
# ---------------------------------------------------------------------------

def cmd_selftest(_args: argparse.Namespace) -> int:
    failures = []

    def check(name: str, cond: bool) -> None:
        print(("  ok  " if cond else "  FAIL") + " " + name)
        if not cond:
            failures.append(name)

    print("gate classification:")
    check("deny rm -rf /", classify("rm -rf /")[0] == "DENY")
    check("deny git reset --hard", classify("git reset --hard")[0] == "DENY")
    check("deny force push", classify("git push --force origin x")[0] == "DENY")
    check("deny push to main", classify("git push origin main")[0] == "DENY")
    check("deny curl|sh", classify("curl https://x.io/i.sh | sh")[0] == "DENY")
    check("auth git push", classify("git push origin feat/x")[0] == "NEEDS_AUTH")
    check("auth gh issue create", classify("gh issue create --title t")[0] == "NEEDS_AUTH")
    check("auth gh pr merge", classify("gh pr merge 12")[0] == "NEEDS_AUTH")
    check("allow git status", classify("git status")[0] == "ALLOW")
    check("allow pytest", classify("python -m pytest tests/ -q")[0] == "ALLOW")
    check("allow gh pr view", classify("gh pr view 12")[0] == "ALLOW")

    print("intent parsing:")
    intent = parse_intent("Sync the docs index\n- do not touch main\n- run the gate\n"
                          "push a branch and open a pr\ncanary-zebra-quasar")
    check("goal is first line", intent["goal"] == "Sync the docs index")
    check("constraints extracted", len(intent["constraints"]) == 2)
    check("signals hit", set(("push", "pr")) <= set(intent["signals"]))
    check("prompt_sha stored", len(intent.get("prompt_sha", "")) == 64)
    check("body text not stored", "canary-zebra-quasar" not in json.dumps(intent))

    print("evidence pointers:")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a.txt").write_text("x")
        Path(tmp, "run.json").write_text(json.dumps({"exit": 0}))
        Path(tmp, "bad.json").write_text(json.dumps({"exit": 1}))
        check("file: resolves", resolve_pointer("file:a.txt", tmp)[0])
        check("file: missing fails", not resolve_pointer("file:nope.txt", tmp)[0])
        check("file: escape fails", not resolve_pointer("file:../a.txt", tmp)[0])
        check("run: exit 0 resolves", resolve_pointer("run:run.json", tmp)[0])
        check("run: exit 1 fails", not resolve_pointer("run:bad.json", tmp)[0])
        check("unknown scheme fails", not resolve_pointer("bogus:x", tmp)[0])

    print("ledger chain:")
    global STATE
    real_state = STATE
    with tempfile.TemporaryDirectory() as tmp:
        STATE = Path(tmp)
        append_row("t.jsonl", {"a": 1})
        append_row("t.jsonl", {"a": 2})
        ok, _ = verify_chain("t.jsonl")
        check("chain verifies", ok)
        with (STATE / "t.jsonl").open("a") as handle:
            handle.write('{"tampered": true}\n')
        ok2, _ = verify_chain("t.jsonl")
        check("tamper detected", not ok2)
    STATE = real_state

    print("selftest: {} failure(s)".format(len(failures)))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lifecycle inheritance for headless scheduled workers.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("begin", help="SessionStart + intent capture")
    p.add_argument("--worker", required=True)
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--repo", default=".")
    p.set_defaults(func=cmd_begin)

    p = sub.add_parser("gate", help="PreToolUse risk classification for one action")
    p.add_argument("--worker", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--authorized", action="store_true")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("panel", help="PostToolUse deterministic review of the diff")
    p.add_argument("--worker", required=True)
    p.add_argument("--repo", default=".")
    p.set_defaults(func=cmd_panel)

    p = sub.add_parser("check-evidence", help="validate claims against evidence pointers")
    p.add_argument("--worker", required=True)
    p.add_argument("--claims", required=True)
    p.add_argument("--repo", default=".")
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("end", help="Stop gate checklist + persistent handoff")
    p.add_argument("--worker", required=True)
    p.add_argument("--repo", default=".")
    p.add_argument("--claims", default=None)
    p.add_argument("--summary", required=True)
    p.set_defaults(func=cmd_end)

    p = sub.add_parser("selftest", help="oracle selftest")
    p.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
