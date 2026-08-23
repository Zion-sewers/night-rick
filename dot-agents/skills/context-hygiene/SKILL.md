---
name: context-hygiene
description: Detect and prevent context/memory/skills/DB bloat. Scans ~/.Codex, ~/projects/*, and the memory store for duplicates, archive-files-that-still-load, stale entries, broken rule references, oversize files, and missing .claudeignore coverage. Proposes cleanups — never auto-deletes. Run weekly, before /clear, after a big refactor, or when session usage limits feel high.
---

# Context Hygiene

## When to run

- Weekly, as a cadence check.
- Before `/clear` — sanity-check what the next session will inherit.
- After a big refactor that added or moved many files.
- When session usage limits feel high and you want to know why.
- When the memory curator hasn't run in more than 14 days.

## What it checks (and why each matters)

### 1. Rules dir bloat (loads every session — direct token tax)
- Total size of `~/.Codex/rules/*.md` (target under 35KB, alert over 50KB).
- Files prefixed `.archive-*` still inside `rules/` — they load unless moved into `rules/archive/` subdir.
- Hooks referencing `~/.Codex/rules/*.md` files that don't exist.

### 2. Memory store health
- Taxonomy drift: filename prefix (`feedback_`, `project_`, `lesson_`) vs declared frontmatter `type:` field.
- Action-items masquerading as memories — entries whose body starts with a verb of intent ("Consider", "Should", "Plan to", "Need to", "Must", "Will"). These belong in a task list, not memory.
- Stale `project_*` memories older than 21 days.
- High word-overlap across descriptions (signal for merge candidates).

### 3. Skills inventory
- SKILL.md files referencing scripts (`.sh`, `.py`) that don't exist on disk.
- Skills listed in `AGENTS.md` / `~/.codex/skills` but missing from `~/.Codex/skills` (cross-runtime drift).

### 4. DB / sessions
- `sessions.db` size and row count.
- Project-key fragmentation (git-root keys vs project-dir keys — the known recall bug).

### 5. Project file hygiene
- Projects missing `.claudeignore`.
- Projects missing `INDEX.md` and `AGENTS.md` at root (no orientation file).
- Root clutter at each project (top-level `.md`, `.txt`, `.png` counts, preserving any filename containing `api` or `ref`).
- Files over 500 LOC in project `src/` dirs.

### 6. Tree snapshot diff
- `tree -L 2 -a` (or `find` fallback) truncated to 40 lines per project.
- Compared against last snapshot in `~/.Codex/cache/tree-snapshots/<project>.txt`.
- Net-new top-level dirs or files are flagged — usually clutter.

## How to run

```bash
bash ~/.Codex/skills/context-hygiene/run.sh [--project NAME] [--write-report]
```

Flags:
- `--project NAME` — scope the scan to one project under `~/projects/`.
- `--write-report` — write to `~/.Codex/cache/hygiene/<date>.md` instead of stdout (falls back to stdout if the mount is read-only).

## Output format

```
CONTEXT HYGIENE REPORT — <date>
=== RULES ===
  load size: 45KB across 11 files
  [CRITICAL] .archive file still loading: rules/.archive-project-intake.md → mv to rules/archive/
  [HIGH]     broken rules ref: ~/.Codex/rules/no-emojis.md

=== MEMORY ===
  34 files, 713 lines total
  [LOW]      taxonomy: lesson_prompt_versioning named lesson_* but type=project
  [MEDIUM]   action-item masquerading as memory: project_qc_transcription_update.md
  [LOW]      stale (24 days): project_<project-name>_v39_status.md

=== SKILLS ===
  installed: 26
  [CRITICAL] broken entrypoint in azure-devops/SKILL.md: ~/.Codex/skills/azure-devops/azure-devops.sh

=== SESSIONS DB ===
  sessions.db: 8MB
  rows: 628  |  distinct project keys: 16
  [HIGH]     project key fragmentation (expected <8, got 16) — recall bug active

=== PROJECTS ===
    <project-a>:  no-claudeignore  root-clutter=203  big-files=4
    <project-b>:  (clean)

=== TREE DELTA ===
    <project-a>: +3 new entries since last snapshot
```

## Rules that apply

- **Never auto-delete.** Output the `rm` / `mv` command; user executes it.
- **Preserve `api`/`ref` filename matches.** These are always considered important and excluded from clutter counts.
- **Respect `.claudeignore`.** Don't read matched files as content.
- **Respect the `.archive-` prefix convention.** `rules/.archive-*.md` means "intended for archive but still in load path" — the fix is to move the file into a `rules/archive/` subdir so the rules loader stops picking it up.
- **Surface read-only mount blockers immediately.** If a fix requires writing to a path on a `ro` mount, print the blocker and the exact command — do not retry.

## Related skills and hooks

- `memory-curator` — semantic review of memory; pairs with this skill (structural).
- `pre-ship-clean` — project-level hygiene as a ship gate.
- `file-guard` hook — enforces `.claudeignore` at read time.
- `rtk-rewrite` hook — execution-layer token hygiene.
