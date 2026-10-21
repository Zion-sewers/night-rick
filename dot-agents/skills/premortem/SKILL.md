---
name: premortem
description: Force a 5-failure-mode section into any /plan output before code is written. Triggers on "/plan", "/premortem", "let's design", "before we build", "design X", or whenever the user explicitly asks for a plan. This skill enforces the PREMORTEM axis of Shoval's forge loop (currently scoring near zero in the weekly a09 audit). Use it as the gating step between /reground and TDD.
model: sonnet
---

# Premortem — 5 failure modes before code

## When to invoke

- The user said "/plan" or "/premortem"
- The user asked for a design / plan / approach / strategy
- I'm about to start an implementation but haven't surfaced what could go wrong
- We're at step 2 of Path A (the standing implementation workflow)

## Why this exists

Shoval's forge loop has 8 axes scored weekly. **PREMORTEM** is one of the three most-missed (last 4-week avg: 2.06/8 — REFACTOR + COVERAGE + PREMORTEM are the gap). The audit prompt at `~/.codex/automations/prompts/a09-forge-loop-compliance-score.md` looks for "5 failure modes listed in the spec" as the binary signal.

This skill makes that signal trivially producible — no excuse to skip.

## Output shape

Inside the plan, surface a section labeled `## Failure modes` containing **exactly 5 items**, each:

1. Concrete (a real thing that can happen, not "the spec is wrong")
2. Specific (names a file / interface / data path / dependency / human / clock)
3. Mitigated (one short sentence per mode saying how the plan defends against it)

Order them by **likelihood × blast radius**, highest first.

## Format template

```markdown
## Failure modes (premortem)

1. **<short title>** — <what happens, in one sentence>
   *Mitigation:* <how the current plan handles it>

2. **<short title>** — ...
   *Mitigation:* ...

3-5. <same shape>
```

## Rules

- **Never fewer than 5.** If only 3 real failure modes come to mind, the plan is too thin — go back and re-think the design until 5 distinct modes surface.
- **Never more than 5 in the body.** If 7+ exist, list 5 in the body and put "additional considered modes" in a footnote. The forge audit grades binary on "5 listed", and visual scan parity matters.
- **Modes must be heterogeneous.** Don't list "test fails", "test fails on edge case A", "test fails on edge case B". Spread across: data correctness, performance, security, ops/deploy, human/process, dependency/upstream, user error.
- **Mitigation lines are mandatory.** A failure mode without a mitigation is just FUD. If the plan doesn't defend against it, that's a planning gap to surface explicitly: "Mitigation: NONE — open question, must be answered before coding."
- This skill is **read-only on intent**. It does not modify code or files. It augments the plan that the user/Codex is already building.

## Integration with Path A

Path A step 2 is `/plan`. This skill runs *during* that step:

```
1. /reground
2. /plan ← premortem fires here, produces the failure-modes section
3. TDD ← only proceed once 5 modes are listed
4-7. (rest of path A)
```

If Path A step 2 produces a plan without a failure-modes section, that's a forge-loop violation — flag it before step 3.

## Anti-patterns to avoid

- Listing "AI hallucinations" or "model bias" as a failure mode (too generic, not actionable)
- Listing implementation bugs as the ONLY mode type (skews toward dev-time, ignores ops/runtime)
- Listing risks the plan already explicitly handles (defeats the point — premortem surfaces *unknowns*)
- Filler modes to hit the count of 5 — better to admit "could only think of 4 — design needs more depth"

## Examples (good vs bad)

### Bad — generic, no mitigation, not heterogeneous

> 1. The agent might fail
> 2. Tests might fail
> 3. The code might have bugs

### Good — concrete, mitigated, spread across categories

> 1. **Stale Foundry token at run time** — `az cognitiveservices account keys list` returns a key that's been rotated since session start; `deploy_agent_prompt.py` 401s mid-run.
>    *Mitigation:* fetch token immediately before the API call, not at script start; retry once on 401.
>
> 2. **Backing database outage during deploy** — agent prompt change requires KB sanity test; if the DB is down at deploy time, the test passes vacuously and the bad prompt ships.
>    *Mitigation:* test connector returns BLOCKED status (not PASS) when DB is unreachable; deploy gate treats BLOCKED as fail.
>
> 3. **Helpdesk department ID still placeholder** — `ticket_categories.py` has `""` for some departments; escalation silently no-ops.
>    *Mitigation:* `pre-ship-clean` hook greps for empty department IDs and blocks deploy if any escalation tier is unwired.
>
> 4. **Multilingual OTP message renders RTL incorrectly in the messaging channel** — Hebrew OTP gets mirrored, customer can't read the code.
>    *Mitigation:* qa_scenarios includes RTL-rendering test against the actual messaging sandbox; manual visual check in PR if scenario file changed.
>
> 5. **A teammate changes Foundry agent config concurrently** — model swap or vector store update lands while my deploy is mid-flight; merge clobbers their change.
>    *Mitigation:* fetch agent state immediately before update, diff vs my plan; abort if diff includes fields outside my scope.
