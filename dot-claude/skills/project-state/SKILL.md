---
name: project-state
description: Durable project memory via status.json, handovers, and resume prompts.
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

`status.json` is operational memory, never source of truth. Contract: `testsPass` is set
only after a verification run; handover claims require the reflection evidence. A handover
without a run is a wish, not a record.


# Project State

Use this skill when the user wants durable session memory across runs, a project handover, or a resume prompt, or when bootstrapping per-project state from current repo reality.

## Files

Maintain these files inside each project:
- `.claude/status.json`: current state, blockers, next steps, verification commands
- `.claude/handover-YYYYMMDD-topic.md`: latest session handover
- `.claude/NEXT_SESSION_PROMPT.md`: concise restart prompt

Templates live in `templates/` next to this skill.

## Workflow

1. Read the project authority docs first (AGENTS.md, the spine, the docs index).
2. Read `.claude/status.json` if it exists.
3. Refresh branch, last commit, blockers, in-progress work, and next steps from the real repo (git, not memory).
4. Update verification commands to match the project stack.
5. Write a short handover with: what changed, what is unverified, the exact next command.
6. Refresh `NEXT_SESSION_PROMPT.md` so the next session starts with the right files and commands.

## Reflection (mandatory)

Before writing the handover, run the verification commands and record their real output. Never mark `testsPass: true` unless verification actually ran. Then drive one user-facing behavior end to end the way a user would (launch, exercise, confirm output) and record the evidence in the handover. A handover that claims green without a run is a wish.

## Rules

- `status.json` is operational memory, not source-of-truth architecture.
- Keep handovers short and dated. Prefer one fresh handover over many stale ones.
- For compacted repos, runtime state files may live in `.claude/` even if active policy lives in `AGENTS.md`.
