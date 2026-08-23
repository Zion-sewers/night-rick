---
name: plant-task
description: Write a task for a future Codex session to pick up. Routes to ~/.Codex/TODO.md (global platform work) or ~/projects/<name>/.Codex/TODO.md (project work). Surfaced automatically on SessionStart by the bootstrap hooks. Use when you notice leftover work, a gap your current scope won't cover, or a concrete follow-up you want preserved across sessions without relying on memory.
---

# Plant a task for future Codex

## When to use

- You finished a task and noticed leftover work outside your scope.
- The user asked for X and you saw Y also needs fixing, but Y is separate.
- You discovered a gap (broken hook, stale plan, missing test) during another task.
- You decided on an approach but shipping it needs a clean session.

Do NOT use for:
- In-session reminders — use TaskCreate + TaskUpdate for the current session.
- Durable facts ("KV uses AzureCLI@2") — those go in memory, not a TODO.
- The user's current prompt — address it directly, don't route to future-self.

## Where tasks go

| Scope | File | Surfaced on session start when... |
|---|---|---|
| `global` (platform, hooks, rules, skills) | `~/.Codex/TODO.md` | Codex opens outside `~/projects/<name>/` |
| `<project-name>` (any of your own projects under `~/projects/`) | `~/projects/<project-name>/.Codex/TODO.md` | Codex opens under that project's dir |

The SessionStart hooks `session-global-bootstrap.sh` and `session-project-bootstrap.sh` read these files and inject the open tasks into the next session's context.

## Write format (strict — so the bootstrap can count and surface)

Append one block per task to the right TODO.md:

```markdown
## [P0|P1|P2] — <one-line title>

**Intent:** why this exists, in one sentence.

**Acceptance:**
- [ ] testable item 1
- [ ] testable item 2

**Notes:** anything future-Codex needs — file paths, commands, gotchas, links to memory.

**Planted:** YYYY-MM-DD by <session or /skill name>
```

Rules:
- Priority `P0` = blocker (must address before other work), `P1` = next up, `P2` = later.
- Title must be one line, no trailing period.
- Acceptance must be testable checkboxes (`- [ ]`), not prose.
- `**Planted:**` is required — helps future-Codex recognize stale tasks.

## Lifecycle

1. **Plant:** append a block to the right TODO.md.
2. **Surface:** bootstrap hook shows it on session start — counts + first 3-5 titles.
3. **Pick up:** future session reads the full block, works on it.
4. **Complete:** delete the entire block. Git history preserves it.
5. **Blocked:** add a `**Blocked by:** <reason>` line — do NOT delete.
6. **Stale (>30 days untouched):** `context-hygiene` flags it. Decide: still valid → refresh the date, no longer valid → delete.

## Anti-patterns (reject)

- A task with no `Acceptance:` block — it's just a wish, not a task.
- Copy-pasting a plan file into TODO.md — plans live in `.Codex/plans/` or `docs/specs/`, TODO.md links to them.
- Tasks that say "do X sometime" without a priority or acceptance — pick P0/P1/P2 or don't plant.
- Multi-project tasks in one block — split. One TODO.md per scope.

## Quick examples

**Global (platform):**

```markdown
## [P1] — Wire post-compact-reinject.sh or delete it

**Intent:** Hook exists but isn't registered. Either it's needed (wire to SessionStart) or dead code (delete).

**Acceptance:**
- [ ] Decision made; committed with reason in message
- [ ] If wired: hook fires on /compact and emits the expected context reinjection
- [ ] If deleted: no other file references it (grep-verified)

**Planted:** 2026-04-19 by /plant-task
```

**Project (a customer-service agent project):**

```markdown
## [P0] — Fix exception swallowing in get_messages()

**Intent:** `woolly-honking-pebble.md` bug #2 — swallowed exceptions in Chatwoot polling cause silent data loss.

**Acceptance:**
- [ ] RED test reproduces a swallowed exception causing missed message
- [ ] Fix in `chatwoot_handler/__init__.py` propagates to caller
- [ ] GREEN test passes; no regression in surrounding deepeval suite

**Notes:** Don't widen ESCALATION_KEYWORDS as part of this — separate concern. See `lesson_escalation_v39_design.md`.

**Planted:** 2026-04-19 by /plant-task
```

## Related

- `project-state` skill — for rich session handover docs (plans + resume prompts). Use that for deep-context handoffs; TODO.md is for discrete tasks.
- `~/.Codex/plans/PROJECT_PLAN_MAP.md` — long-form plans pointer.
- `~/.Codex/docs/GLOBAL_PLANS_INDEX.md` — strategic plans index.
- `context-hygiene` skill — flags stale TODOs (>30 days untouched).
