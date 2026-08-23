---
name: dispatch
description: Sync agent-to-agent dispatch from Codex orchestrator to a registered peer (Codex executor on gpt-5.5, Foundry agents <agent-a>/<agent-b>, future bridges). Triggers on /dispatch, "ask <agent-a>", "have <agent-b> check", "send to codex for review", "second-opinion from gpt-5.5". Default timeout 60s, sync only in v1, one peer per call. Logs every call to ~/.Codex/cache/a2a/audit.jsonl.
model: sonnet
allowed-tools: ["Bash($HOME/.claude/bin/a2a-codex-call.sh *)", "Bash($HOME/.claude/bin/a2a-foundry-call.py *)", "Bash($HOME/.claude/bin/a2a-audit.py *)"]
---

# /dispatch — sync A2A bridge to one peer

## Address scheme

```
codex:home                  Codex CLI (gpt-5.5, ChatGPT subscription, $0 marginal)
foundry:<agent-a>           Azure Foundry agent (Azure billing — uses your tenant)
foundry:<agent-b>           Azure Foundry agent (same)
foundry:<any-other>         Any other agent in your Foundry project (auto-supported)
```

Future addresses (NOT supported in v1):
- `kilocode:<project>/<agent>` — Kilocode runtime bridge (deferred per refined plan)
- `Codex:<project>` — cross-Codex-session dispatch (deferred until inboxes exist)

## v1 semantics — exactly these

- **Sync only.** Codex calls, blocks until response, then continues. No async, no streaming.
- **One peer per `/dispatch`.** Parallel dispatch is a v2 concern.
- **60s default timeout.** Configurable via `--timeout N`.
- **No retry.** If a call times out or fails, surface the error and let the user decide whether to re-dispatch.
- **Returns `{state, response_text, duration_ms, error?}`.** state ∈ {completed, timeout, failed}.
- **Every call logged.** `~/.Codex/cache/a2a/audit.jsonl` is the canonical record.

## Invocation patterns

### Codex (gpt-5.5 second opinion, code review, batch generation — free)

```bash
~/.Codex/bin/a2a-codex-call.sh "review src/handler.py for SQL injection" --effort high
~/.Codex/bin/a2a-codex-call.sh "generate property-based tests for validators.py" --effort medium
~/.Codex/bin/a2a-codex-call.sh "summarize this 200-line file in 5 bullets" --effort low
```

### Foundry agents (production agent KB queries — Azure billing)

```bash
~/.Codex/bin/a2a-foundry-call.py <agent-a> "what is the rate limit for this endpoint?"
~/.Codex/bin/a2a-foundry-call.py <agent-b> "explain the tier-2 requirements" --timeout 45
~/.Codex/bin/a2a-foundry-call.py <agent-a> "<prompt>" --responses-api    # raw API for tool calls
```

### Audit / observability

```bash
~/.Codex/bin/a2a-audit.py tail 20         # last 20 calls
~/.Codex/bin/a2a-audit.py stats           # aggregate by pair / state / latency
```

## When to dispatch (decision rules)

| Goal | Use | Rationale |
|---|---|---|
| Get a different model's perspective on a tricky design | `codex:home` with effort=high | Cheap second opinion, gpt-5.5 catches what Codex missed |
| Generate boilerplate (tests, fixtures, mocks-of-fixtures) | `codex:home` with effort=medium | Codex is cheaper for repetitive output |
| Verify a KB answer before drafting customer reply | `foundry:<agent-a>` | Production agent has the actual KB index |
| Compare policies across two brands/products on the same question | both `foundry:<agent-b>` and `foundry:<agent-a>` | Brand-aware cross-check |
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
- `foundry:<agent-a>` / `foundry:<agent-b>` — Azure billing on your own tenant. Cheap per call (~$0.001-0.01) but watch for runaway loops.
- Token cost in *this* Codex session: every dispatch response gets injected back into context. Long responses bloat the orchestrator session. Prefer concise dispatch prompts that ask for structured output (JSON, tables, bullet lists) over open-ended ones.

## Future (v2, NOT supported now)

- Async dispatch with task IDs and `tasks/get` polling
- Parallel dispatch to N peers (`/dispatch-team`)
- Streaming (`tasks/sendSubscribe`)
- Push notifications back into Codex's context via inbox files
- Kilocode runtime bridge
- Cross-machine federation (Google A2A HTTP transport)

When v2 lands, the call signatures stay the same — only the back-end transport changes. v1 is the foundation.
