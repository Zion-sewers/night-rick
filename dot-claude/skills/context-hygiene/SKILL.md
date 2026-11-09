---
name: context-hygiene
description: Detect and prevent context, memory, skills, and session bloat. Scans for duplicates, stale entries, oversize files, and broken references. Proposes cleanups, never auto-deletes.
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

Read-only by construction. Contract: never auto-deletes; fix commands are emitted for the
user to paste. The `--fix-safe` flag is limited to zero-risk removals (`.writetest`
droppings, stale snapshots) and only runs on explicit invocation.


# Context Hygiene

Run weekly, before clearing context, after a big refactor, when session usage feels high, or when the memory curator has not run in more than 14 days. Designed pair with `memory-curator`: this skill is the structural scan, the curator is the semantic review.

## What it checks

### 1. Rules dir bloat (loads every session, direct token tax)
- Total size of `~/.claude/rules/*.md` (target under 35KB, alert over 50KB)
- Files prefixed `.archive-*` still inside `rules/` (they load unless moved into `rules/archive/`)
- Hooks referencing rule files that do not exist

### 2. Memory store health
- Taxonomy drift: filename prefix (`feedback_`, `project_`, `lesson_`) vs declared frontmatter `type:` field
- Action-items masquerading as memories: entries whose body starts with a verb of intent ("Consider", "Should", "Plan to", "Need to", "Must", "Will"). These belong in a task list, not memory
- Stale `project_*` memories older than 21 days
- High word-overlap across descriptions (merge candidates)

### 3. Skills inventory
- SKILL.md files referencing scripts (`.sh`, `.py`) that do not exist on disk
- Skills listed in docs but missing from `~/.claude/skills` (cross-tree drift)

### 4. Sessions
- Session record size and row count
- Project-key fragmentation (git-root keys vs project-dir keys, the known recall bug)

### 5. Project file hygiene
- Projects missing ignore files for their stack
- Projects missing an orientation file (`INDEX.md`, `AGENTS.md`, or `CLAUDE.md`) at root
- Root clutter per project (top-level `.md`, `.txt`, `.png` counts, preserving filenames containing `api` or `ref`)
- Files over 500 LOC in project `src/` dirs

### 6. Tree snapshot diff
- Directory tree snapshot per project, truncated to 40 lines
- Compared against the last snapshot in `~/.claude/cache/tree-snapshots/`
- Net-new top-level dirs or files are flagged, usually clutter

## How to run

```bash
bash ~/.claude/skills/context-hygiene/run.sh [--project NAME] [--write-report]
```

Flags:
- `--project NAME`: scope the scan to one project under `~/workspace/`
- `--write-report`: write to `~/.claude/cache/hygiene/<date>.md` instead of stdout

## Output format

```
CONTEXT HYGIENE REPORT — <date>
=== RULES ===
  load size: 45KB across 11 files
  [CRITICAL] .archive file still loading: rules/.archive-x.md → mv to rules/archive/
  [HIGH]     broken rules ref: ~/.claude/rules/no-emojis.md

=== MEMORY ===
  34 files, 713 lines total
  [LOW]      taxonomy: lesson_x named lesson_* but type=project
  [MEDIUM]   action-item masquerading as memory: project_x.md
  [LOW]      stale (24 days): project_y.md

=== SKILLS ===
  installed: 26
  [CRITICAL] broken entrypoint in some-skill/SKILL.md: ~/.claude/skills/some-skill/missing.sh

=== PROJECTS ===
    my-project:  no-claudeignore  root-clutter=203  big-files=4

=== TREE DELTA ===
    my-project: +3 new entries since last snapshot
```

## Rules that apply

- **Never auto-delete.** Output the `rm` / `mv` command; the user executes it.
- **Preserve `api`/`ref` filename matches.** Always considered important, excluded from clutter counts.
- **Respect ignore files.** Do not read matched files as content.
- **Respect the `.archive-` prefix convention.** `rules/.archive-*.md` means "intended for archive but still in load path". The fix is moving it into `rules/archive/`.
- **Surface read-only mount blockers immediately.** If a fix needs a path on a read-only mount, print the blocker and the exact command, do not retry.

## Reflection (mandatory)

Every hygiene loop ends with a verification pass over its own findings:
- Re-run each flagged check before proposing the fix command, confirm the file or condition still exists
- Confirm every proposed `rm`/`mv` target path resolves (no typos in the command the user will paste)
- Preserve the report as evidence alongside the proposal

## Related

- `memory-curator`: semantic review of memory; pairs with this skill (structural)
- `plant-task`: flags stale TODOs (untouched >30 days)
