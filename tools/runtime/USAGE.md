# worker_wrap.py usage

A cron worker wraps its run in five calls. The example worker below checks a
documentation site for broken internal links and opens an issue per broken
link. Neutral domain on purpose: no production systems, no personal data.

## The five calls

```bash
WRAP="python3 /path/to/claude-setup/tools/runtime/worker_wrap.py"
REPO=/path/to/docs-site   # the repo the worker changes

# 1. open the session: replays the last handoff, captures intent
$WRAP begin --worker link-check --prompt-file prompt.txt --repo $REPO

# 2. before any external effect, classify the action (exit 0 allow, 2 deny, 3 needs auth)
$WRAP gate --worker link-check --action "gh issue create --title 'broken link: /guide'"
# -> NEEDS_AUTH, exit 3. Re-run authorized:
$WRAP gate --worker link-check --action "gh issue create --title 'broken link: /guide'" --authorized

# 3. after writing code, run the deterministic persona panel on the diff
$WRAP panel --worker link-check --repo $REPO

# 4. validate the claims file: every claim cites a resolvable pointer
$WRAP check-evidence --worker link-check --claims claims.json --repo $REPO

# 5. stop gate: checklist, then the handoff row the next run replays
$WRAP end --worker link-check --repo $REPO --claims claims.json \
  --summary "checked 412 pages, 3 broken links, 3 issues opened, panel clean"
```

## Gate verdicts

- `DENY` (exit 2): recursive deletion, hard reset, forced clean, forced branch
  deletion, force push, ref deletion via push, piped-to-shell downloads, direct
  push to main/master. Never overridden.
- `NEEDS_AUTH` (exit 3): pushes, issue/PR creation, PR merges, releases,
  mutating API or network calls. Pass `--authorized` or set
  `WORKER_AUTHORIZED=1`. The authorization is recorded in the gate log.
- `ALLOW` (exit 0): everything else. Unfamiliar shapes default to allow and
  are recorded in `state/worker-gate.jsonl`, so a gap in the patterns is
  countable rather than silent.

## claims.json

```json
[
  {"claim": "all 412 pages scanned", "evidence": ["run:scan-report.json"]},
  {"claim": "3 issues opened", "evidence": ["ledger:worker-gate.jsonl:12"]},
  {"claim": "link checker script added", "evidence": ["file:tools/linkcheck.py"]}
]
```

Pointer schemes: `file:<relpath>` must exist; `run:<relpath>` must be a JSON
record with `"exit": 0`; `ledger:<name>:<n>` must name a row that exists. A
claim with no resolvable pointer fails the run at `end`.

## State

All lifecycle state lives in the harness `state/` directory:

- `worker-intents.jsonl`: structured intent per run (goal, constraints,
  signals, prompt sha256; never prompt text)
- `worker-gate.jsonl`: every gate decision with its rule and authorization
- `worker-runs.jsonl`: the stop-gate checklist plus the handoff summary,
  hash-chained so the next run can verify history before trusting it

## What is deliberately not inherited

- `PreCompact`: headless workers do not compact. The handoff row is the
  state-preservation half.
- `Notification`: no operator is listening on a cron run.
- Company personas (`dot-claude/agents/`): session-time subagent definitions
  for interactive work. A worker that needs one invokes it explicitly; the
  wrapper does not auto-attach them.
