---
name: deploy-prod
description: Guided pre-flight checklist for safe production deployment via CI pipeline.
---

## Purpose

Safe deployment workflow. Guides through the proper CI-based path:
`feature -> stage -> main` (pipeline deploys on main merge).

This skill does NOT run `func publish` or `az functionapp deployment`.
It generates PR commands and reminds the user that the pipeline handles deployment.

## Workflow

### Step 1: Current State

Run and show output:
```bash
git branch --show-current
git status --short
git log --oneline -5
```

### Step 2: Verify Tests

Run the project's test command:
- **A customer-service agent project:** `cd <agent-project> && python -m pytest tests/ -k "not deepeval" -x -q`
- **A telephony/API project:** `uv run pytest tests/ -x -q`
- **Other:** Check project AGENTS.md for test command

Show evidence (pass/fail counts).

### Step 3: Verify Lint

Run the project's lint command:
- **Python:** `uv run ruff check src/` or `ruff check .`
- **JS/TS:** `bun run lint`

Show evidence (0 errors required).

### Step 4: Diff Summary

```bash
git diff --stat HEAD~1..HEAD
```

Show files changed, insertions, deletions.

### Step 5: Deployment Path

Based on current branch, show the correct next step:

- **On `feature/*`:** "Push and create PR to `stage`"
  ```bash
  git push -u origin <branch>
  az repos pr create --source-branch <branch> --target-branch stage --title "<title>"
  ```
- **On `stage`:** "Create PR to `main` (triggers deploy pipeline)"
  ```bash
  az repos pr create --source-branch stage --target-branch main --title "Deploy: <summary>"
  ```
- **On `main`:** "STOP. Never push directly to main. Create a feature branch."

### Step 6: Remind

> Merge to main triggers automatic deployment via CI pipeline.
> The pipeline runs Tier 1 gates, deploys, and verifies health.
> Do NOT run `func publish` or `az functionapp deployment` manually.

## Notes

- Always run tests before creating a PR
- The hook `~/.Codex/hooks/protect-azure-prod.sh` blocks direct deploy commands
- Azure DevOps branch policies enforce PR requirements
- See `~/.Codex/rules/production-safety.md` for full policy
