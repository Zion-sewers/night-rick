---
name: plant-task
description: Write a task for a future session to pick up. Routes to a global or per-project TODO.md, surfaced automatically at session start. Use for leftover work, gaps outside current scope, or concrete follow-ups worth preserving across sessions.
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

Append-only by contract: strict block format so the bootstrap can parse it, delete only on
complete, `Blocked by` instead of delete when stuck. Git history is the audit trail.


# Plant a task for a future session

## When to use

- You finished a task and noticed leftover work outside your scope
- The user asked for X and you saw Y also needs fixing, but Y is separate
- You discovered a gap (broken hook, stale plan, missing test) during another task
- You decided on an approach but shipping it needs a clean session

Do NOT use for:
- In-session reminders, use the session task list for the current session
- Durable facts ("the gate runs on the self-hosted runner"), those go in memory, not a TODO
- The user's current prompt, address it directly, do not route to future-self

## Where tasks go

| Scope | File | Surfaced on session start when... |
|---|---|---|
| `global` (platform, hooks, rules, skills) | `~/.claude/TODO.md` | a session opens outside any project dir |
| `<project-name>` (agentgate, mcp-guard, agenteval-bench, claude-setup, sqltok, policykit) | `~/workspace/<project-name>/.claude/TODO.md` | a session opens under that project's dir |

Session-start bootstrap reads these files and injects the open tasks into the next session's context. If the bootstrap hook is not wired yet, the files still serve as the durable queue.

## Write format (strict, so the bootstrap can count and surface)

Append one block per task to the right TODO.md:

```markdown
## [P0|P1|P2] — <one-line title>

**Intent:** why this exists, in one sentence.

**Acceptance:**
- [ ] testable item 1
- [ ] testable item 2

**Notes:** anything the future session needs, file paths, commands, gotchas, links to memory.

**Planted:** YYYY-MM-DD by <session or /skill name>
```

Rules:
- Priority `P0` is a blocker (address before other work), `P1` is next up, `P2` is later
- Title is one line, no trailing period
- Acceptance is testable checkboxes (`- [ ]`), not prose
- `**Planted:**` is required, helps future sessions recognize stale tasks

## Lifecycle

1. **Plant:** append a block to the right TODO.md
2. **Surface:** bootstrap shows it on session start, counts plus first 3 to 5 titles
3. **Pick up:** future session reads the full block and works on it
4. **Complete:** delete the entire block. Git history preserves it
5. **Blocked:** add a `**Blocked by:** <reason>` line, do NOT delete
6. **Stale (untouched >30 days):** `context-hygiene` flags it. Decide: still valid, refresh the date; no longer valid, delete

## Reflection (mandatory)

When a planted task is picked up, its loop ends with a verification pass against its own Acceptance block: each checkbox is proven by a run, not by reading the code. The task is complete only when every acceptance item has evidence. Paste the evidence into the session record before deleting the block.

## Anti-patterns (reject)

- A task with no `Acceptance:` block, it is a wish, not a task
- Copy-pasting a plan file into TODO.md, plans live in `docs/specs/`, TODO.md links to them
- Tasks that say "do X sometime" without a priority or acceptance, pick P0/P1/P2 or do not plant
- Multi-project tasks in one block, split. One TODO.md per scope

## Quick example

```markdown
## [P1] — Wire the nightly consolidation job or delete its cron entry

**Intent:** The cron exists but the job body was never written. Either it runs or it goes.

**Acceptance:**
- [ ] Decision made, committed with reason
- [ ] If wired: job fires on schedule and writes to the ledger
- [ ] If deleted: no other file references it (grep-verified)

**Planted:** 2026-10-10 by /plant-task
```

## Related

- `project-state`: rich session handover docs (plans plus resume prompts). Use that for deep-context handoffs; TODO.md is for discrete tasks
- `context-hygiene`: flags stale TODOs (untouched >30 days)
