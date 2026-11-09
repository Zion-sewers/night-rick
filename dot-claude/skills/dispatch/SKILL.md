---
name: dispatch
description: Sync agent-to-agent dispatch from Claude orchestrator to a registered peer (Codex executor on gpt-5.5, Foundry agents seekapa/AxiaCS, future bridges). Triggers on /dispatch, "ask seekapa", "have AxiaCS check", "send to codex for review", "second-opinion from gpt-5.5". Default timeout 60s, sync only in v1, one peer per call. Logs every call to ~/.claude/cache/a2a/audit.jsonl.
model: sonnet
allowed-tools: ["Bash($HOME/.claude/bin/a2a-codex-call.sh *)", "Bash($HOME/.claude/bin/a2a-foundry-call.py *)", "Bash($HOME/.claude/bin/a2a-audit.py *)"]
---

# /dispatch — sync A2A bridge to one peer

## Address scheme

```
codex:home                  Codex CLI (gpt-5.5, ChatGPT subscription, $0 marginal)
foundry:seekapa             Azure Foundry seekapa agent (Azure billing — uses your tenant)
foundry:AxiaCS              Azure Foundry AxiaCS agent (same)
foundry:<any-other>         Any other agent in the seekapa_ai project (auto-supported)
```

Future addresses (NOT supported in v1):
- `kilocode:siu/<agent>` — Kilocode runtime bridge (deferred per refined plan)
- `claude:<project>` — cross-Claude-session dispatch (deferred until inboxes exist)

## v1 semantics — exactly these

- **Sync only.** Claude calls, blocks until response, then continues. No async, no streaming.
- **One peer per `/dispatch`.** Parallel dispatch is a v2 concern.
- **60s default timeout.** Configurable via `--timeout N`.
- **No retry.** If a call times out or fails, surface the error and let the user decide whether to re-dispatch.
- **Returns `{state, response_text, duration_ms, error?}`.** state ∈ {completed, timeout, failed}.
- **Every call logged.** `~/.claude/cache/a2a/audit.jsonl` is the canonical record.

## Invocation patterns

### Codex (gpt-5.5 second opinion, code review, batch generation — free)

```bash
~/.claude/bin/a2a-codex-call.sh "review src/handler.py for SQL injection" --effort high
~/.claude/bin/a2a-codex-call.sh "generate property-based tests for validators.py" --effort medium
~/.claude/bin/a2a-codex-call.sh "summarize this 200-line file in 5 bullets" --effort low
```

### Foundry seekapa / AxiaCS (production agent KB queries — Azure billing)

```bash
~/.claude/bin/a2a-foundry-call.py seekapa "what is the OTP send rate limit?"
~/.claude/bin/a2a-foundry-call.py AxiaCS "explain KYC tier 2 requirements" --timeout 45
~/.claude/bin/a2a-foundry-call.py seekapa "<prompt>" --responses-api    # raw API for tool calls
```

### Audit / observability

```bash
~/.claude/bin/a2a-audit.py tail 20         # last 20 calls
~/.claude/bin/a2a-audit.py stats           # aggregate by pair / state / latency
```

Every record carries the commit the dispatch was made for (HEAD of the repo
under review is authoritative; a valid `--commit` or `$A2A_COMMIT` hint that
disagrees with HEAD loses to HEAD and is recorded as `commit_hint_mismatch`).
This is a log-presence check for the agreement gate, not the gate itself:
`python tools/audit/a2a_dispatch_oracle.py check --commit <sha>` exits
non-zero unless audit.jsonl holds a completed call recorded for that commit.
PASS proves a completed dispatch is recorded, not that the second model
agreed with anything. Run it from the repo root, before writing any
`_provenance` block that claims agreement and before merge, passing the
reviewer and prompt hash from the claim when the claim names them:
`check --commit <sha> --to <reviewer> --prompt-hash <hash>`. Manual-only
until the gate contract enforces it; the ship-gate `a2a_dispatch` domain
runs the same check warn-only.

Deploy first, or nothing on the dispatching machine changes: the bridges read
the audit writer from `~/.claude/bin`, not from this repo. From the repo root
run `bash dot-claude/bin/deploy-setup.sh --only 'bin/a2a-*'` for a dry run,
then `--apply` to copy the bridge files, and confirm with
`~/.claude/bin/a2a-audit.py tail 5` after a real dispatch. A deployed writer
that predates the commit seam logs records with no commit, and the bridges
warn on stderr when that happens.

When the check fails, do this, per reason: `LOG_MISSING` means no dispatch
has ever been recorded, deploy the payload and run a real dispatch, then
re-run the check; `LOG_UNREADABLE` means the log cannot be read, fix the
path or permissions, do not claim agreement; `NO_RECORD_FOR_COMMIT` means no
dispatch was made for this commit, do not claim agreement; `NO_COMPLETED_CALL`
means re-run the second review to completion, a failed or timed-out call does
not count; `NO_MATCHING_CALL` means a completed call exists for the commit
but not from the named reviewer or prompt hash, re-run the review the claim
refers to. A failing check blocks the `_provenance` claim, not the merge,
until the contract domain is enforced.

## When to dispatch (decision rules)

| Goal | Use | Rationale |
|---|---|---|
| Get a different model's perspective on a tricky design | `codex:home` with effort=high | Cheap second opinion, gpt-5.5 catches what Claude missed |
| Generate boilerplate (tests, fixtures, mocks-of-fixtures) | `codex:home` with effort=medium | Codex is cheaper for repetitive output |
| Verify a KB answer before drafting customer reply | `foundry:seekapa` | Production agent has the actual KB index |
| Compare Axia and Seekapa policies on same question | both `foundry:AxiaCS` and `foundry:seekapa` | Brand-aware cross-check |
| Long-form research synthesis | use `deep-research` skill, NOT dispatch | Deep-research is multi-source by design |
| Review a PR | `codex review` (built-in subcommand) is preferred over /dispatch | Codex has a dedicated review surface |

## When NOT to dispatch (v1 hard rules)

- **Inside a cron / automation context** (env `CLAUDE_LOOP_MODE`, `CODEX_AUTOMATION_ID`) — those have their own runners.
- **Inside a subagent context** — let the parent orchestrator dispatch, not the child.
- **For sensitive customer data** without explicit user OK — Foundry calls leave your $HOME.
- **When persona-mode is active** — A2A traffic stays sober (per persona skill's hard-block rules).

## Output integration

After a dispatch returns, surface the response inline with a clear attribution line:

```
[via codex:home, gpt-5.5, effort=high, 4.2s]
> Findings:
>   1. Missing input sanitization at handler.py:42 — concatenates raw query string.
>   2. ...
```

Don't paste the full JSON envelope — extract `response_text` and prepend the attribution. The JSON is in the audit log if needed for debugging.

## Cost guidance

- `codex:home` (gpt-5.5 via ChatGPT subscription) — **$0 marginal**, but consumes weekly quota. Use freely.
- `foundry:seekapa` / `foundry:AxiaCS` — Azure billing on your i-sdd tenant. Cheap per call (~$0.001-0.01) but watch for runaway loops.
- Token cost in *this* Claude session: every dispatch response gets injected back into context. Long responses bloat the orchestrator session. Prefer concise dispatch prompts that ask for structured output (JSON, tables, bullet lists) over open-ended ones.

## Future (v2, NOT supported now)

- Async dispatch with task IDs and `tasks/get` polling
- Parallel dispatch to N peers (`/dispatch-team`)
- Streaming (`tasks/sendSubscribe`)
- Push notifications back into Claude's context via inbox files
- Kilocode runtime bridge
- Cross-machine federation (Google A2A HTTP transport)

When v2 lands, the call signatures stay the same — only the back-end transport changes. v1 is the foundation.
