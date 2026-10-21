---
name: agent-team
description: Agent team coordination protocol, spawn rules, worktree isolation, handoff protocol, quality checkpoints. Use when spawning multiple agents for parallel work.
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

Spawned agents are isolated (worktree); the lead's reflection pass is the handoff boundary.
The red flags are structural anomaly signals: "done" without test output is the
tautological-test pattern, same-file edits by two agents is a coordination failure.


# /agent-team

Structured agent coordination with quality gates at every handoff.

## Spawn template

Always include in agent prompts: no mocks, no files over 500 LOC, no functions over 50 LOC, no new dependencies without documenting why, test everything, paste output. Use worktree isolation for agents that write code.

## Task size

Under 200 LOC per task. Split if larger.

## Handoff protocol

Agent A completes, the lead verifies, then Agent B reads A's files before starting. A handoff is not complete when Agent A says done. It is complete when the lead has verified A's output against the acceptance criteria.

## Reflection (mandatory)

The lead's verification is a pstack-style pass, not a read-through: launch what Agent A built, drive one mapped behavior the way a user would, confirm the evidence, check no stranded processes. Paste the output. "Verified" without a run is prose, not verification.

## Red flags

- Agent says "done" without test output
- Modified files outside scope
- Added undocumented dependencies
- Two agents modified the same file
- Handoff accepted without the reflection pass above
