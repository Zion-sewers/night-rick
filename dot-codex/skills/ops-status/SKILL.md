---
name: ops-status
description: "Ops Status — System State Snapshot Skill"
---

# Ops Status — System State Snapshot Skill

**Invocation:** `/ops` or when user asks about system state, deployment status

## Purpose

Provide a compact snapshot of the current operational state across projects
without requiring multi-file reads. This skill replaces expensive ad-hoc
system exploration with pre-defined health checks.

## When to Activate

- Session start (when user asks "what's the state of things?")
- Before deploying or merging
- After incident investigation
- When switching between projects

## Status Checks

### Git Status (All Projects)

```bash
for dir in ~/projects/*/; do
  name=$(basename "$dir")
  branch=$(git -C "$dir" branch --show-current 2>/dev/null || echo "no-git")
  dirty=$(git -C "$dir" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  last=$(git -C "$dir" log -1 --format="%h %s" 2>/dev/null || echo "no commits")
  echo "[$name] branch=$branch dirty=$dirty last=$last"
done
```

### Process Health

```bash
# Check for runaway node/python processes
ps aux | grep -E '(node|python|bun)' | grep -v grep | awk '{print $11, $2, $10}'
```

### Disk Usage

```bash
du -sh ~/projects/*/
du -sh ~/.codex ~/.gemini ~/.agent
```

## How to Report

Present as a compact table:

```
| Project | Branch | Dirty | Last Commit |
|---------|--------|-------|-------------|
| api-svc | main   | 0     | abc1234 fix gates |
| web-app | feature/v3 | 3 | def5678 layout engine |
```

Keep report under 15 lines. No verbose output.

## Integration

This skill complements:

- **SessionStart hook:** Auto-injects git state
- **Workspace brain:** Provides project metadata
- **Eval runner:** Shows test status per project

Together they form the "ops-aware agent" layer:
Claude always knows where it is, what state things are in, and what constraints apply.
