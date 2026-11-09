---
name: memory-curator
description: Periodically review recent sessions for memory-worthy patterns and propose updates to MEMORY.md and individual memory files. Always proposes, never auto-writes.
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

Memory writes cross the agent-to-belief boundary: the agent judges, the user approves.
Contract: propose first, apply only after explicit approval, advance the marker only after
application. Re-running apply on an already-applied proposal is a no-op diff (idempotent).


# /memory-curator

Cross-session learning loop. Reads session records since the last curate marker, compares against current memory, proposes new entries, updates, dedupes, and removals. The user approves before any write. This is the seed mechanism for selective forgetting: memory is curated, never just accumulated.

## When to run

- Manual: `/memory-curator` whenever the user asks
- Recommended cadence: weekly, or after a session that surfaced strong feedback signals
- Optional: chain into the end-of-session memory update step

## Inputs

| Source | What |
|--------|------|
| `~/workspace/goals/github-repo-autonomy/hidden_files/input-log/prompts.jsonl` | Prompt ledger: every prompt with status and delivery evidence |
| `~/memory/*.md` | Daily notes written since the marker |
| `~/.claude/cache/layer7/.last-curate-<project-key>` | Per-project ISO8601 marker (absent means all history) |
| `~/MEMORY.md` and `~/memory/**/*.md` | Current memory index and memory files |

## Outputs

| File | Purpose |
|------|---------|
| `~/.claude/cache/memory-proposals.md` | Transient proposal, the user reviews, then it is applied |
| `~/.claude/cache/layer7/.last-curate-<project-key>` | Updated only AFTER the user accepts the proposal |

## Phases

### Phase 1, load scope

Resolve the project scope and read the marker:

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PROJECT_KEY=$(printf '%s' "$PROJECT_ROOT" | sed 's#/#-#g')
MARKER="$HOME/.claude/cache/layer7/.last-curate-${PROJECT_KEY}"
mkdir -p "$HOME/.claude/cache/layer7"
export PROJECT_ROOT MARKER
LAST=$(cat "$MARKER" 2>/dev/null || echo "1970-01-01T00:00:00+00:00")
echo "Curating project=$PROJECT_ROOT since: $LAST"
```

Collect new signal: prompt-ledger entries and daily notes newer than `$LAST`. If fewer than 3 new sessions worth of signal exist, skip with "not enough new signal, try again after more sessions".

### Phase 2, read current memory

Read `~/MEMORY.md` (the index) and every file it references. Build a map of `{name: (type, description, body)}`.

### Phase 3, analyze (judgment, not script)

Look at session prompts and outputs for these signals:

| Signal | Action |
|--------|--------|
| Recurring user correction not in memory | Propose NEW entry |
| Two memories overlap heavily | Propose DEDUPE (merge) |
| Memory contradicted by recent behavior | Propose UPDATE or REMOVE with evidence |
| Memory mentions a deadline that has passed | Propose REMOVE or UPDATE |
| Reference memory points to a resource no longer used | Propose REMOVE |
| Strong validated approach used in 3+ sessions | Propose NEW entry (validated, not corrected) |
| Memory cites a file path or function name | Verify it still exists; if not, propose UPDATE |

**Do NOT propose:**
- Code-pattern memories (derivable from current code)
- Git history facts (use `git log`)
- Ephemeral task state (belongs in tasks, not memory)
- Anything already in `~/AGENTS.md`
- Restatements of existing memories with cosmetic changes

### Phase 4, write proposal file

Write `~/.claude/cache/memory-proposals.md` in this exact format:

```markdown
# Memory Curation Proposal

**Generated:** {ISO8601}
**Sessions reviewed:** {N} (since {LAST})
**Current memory entries:** {M}

## NEW (proposed additions)

### {file_name}.md
**Type:** {feedback|user|project|reference}
**Description:** {one-line}
**Evidence:** Sessions {ids}, {brief reason}

```markdown
{full proposed file content with frontmatter}
```

## UPDATE (proposed edits to existing)

### {file_name}.md
**Reason:** {what is stale or wrong}
**Evidence:** Sessions {ids}

**Diff:**
```diff
- {old line}
+ {new line}
```

## DEDUPE (proposed merges)

### {file_a}.md + {file_b}.md → {merged_name}.md
**Overlap:** {what is duplicated}
**Proposed merged content:** {summary or full file}

## REMOVE (proposed deletions)

### {file_name}.md
**Reason:** {why stale}
**Evidence:** {what contradicts it}

## SKIP (signals seen but not actionable)

- {signal}: {why not actionable yet, e.g. "only 1 session, need pattern"}
```

### Phase 5, present to user

Print a summary:

```
Memory curation proposal ready: ~/.claude/cache/memory-proposals.md
  NEW:    {N}
  UPDATE: {N}
  DEDUPE: {N}
  REMOVE: {N}

Review and respond:
  - "apply all" → write everything as proposed
  - "apply 1,3,5" → cherry-pick by item number
  - "edit X" → modify before applying
  - "skip" → discard proposal, leave marker untouched
```

**Do NOT touch any memory files until the user responds.**

### Phase 6, apply (only after explicit user approval)

For each accepted item:
1. NEW: write the file
2. UPDATE: apply the diff
3. DEDUPE: write the merged file, delete originals (only after confirming)
4. REMOVE: delete (only after confirming)
5. Update the `~/MEMORY.md` index lines accordingly

Then advance the marker:

```bash
date -u +"%Y-%m-%dT%H:%M:%S+00:00" > "$HOME/.claude/cache/layer7/.last-curate-${PROJECT_KEY}"
```

### Phase 7, reflection (mandatory)

Every curation loop ends with a verification pass over the applied changes, driven the way a user would check them:
- Every NEW file exists on disk and is indexed in `~/MEMORY.md`
- Every UPDATE diff applied cleanly (no leftover conflict markers)
- Every REMOVE target is gone and nothing still references it (grep-verified)
- The marker advanced to the new timestamp

Preserve the proposal file as evidence. If any check fails, report it and do not advance the marker.

## Anti-patterns (reject from your own proposals)

| Pattern | Why reject |
|---------|-----------|
| "User said X once" as evidence | Need pattern, not single instance |
| Proposing memory of code structure | Derivable from code |
| Restating AGENTS.md content | Already loaded |
| Merging memories from different categories | Loses semantic clarity |
| Removing memory based on absence of recent mention | Absence is not obsolescence |
| Generated memory bodies that read like AI summaries | Memories should sound like the user |

## Cost note

This skill runs on session text already stored locally. Skipping below 3 new sessions keeps it cheap.

## Why propose, never auto-write

Memories shape future behavior. A bad memory persists across sessions and can drift the agent. The user is the only authority on what the user actually thinks. Auto-writing creates a loop where the agent convinces itself of patterns the user never validated.
