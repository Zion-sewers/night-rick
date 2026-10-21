# tools/runtime

Lifecycle inheritance for headless scheduled workers.

The seven lifecycle events in `dot-claude/settings.json` (SessionStart,
UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop, Notification) only
fire inside an interactive Claude Code session. Scheduled workers (cron jobs
that run as plain prompts) get none of them: no intent capture, no pre-action
risk gate, no panel review, no evidence check, no stop gate, no handoff.

`worker_wrap.py` maps each event onto a command the worker invokes itself
(`begin`, `gate`, `panel`, `check-evidence`, `end`), so the worker inherits the
mechanism rather than a description of it. State lands in the harness
`state/` ledgers (`worker-intents.jsonl`, `worker-gate.jsonl`,
`worker-runs.jsonl`), all append-only and hash-chained.

See `USAGE.md` for the worker-side contract and `docs/prior-art/tools-runtime-worker-wrap.json`
for why this is hand-built instead of adopted.
