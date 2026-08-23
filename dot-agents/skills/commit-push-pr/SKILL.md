---
name: commit-push-pr
description: Run quality gates, commit (Conventional format), push, open PR, and sweep merged local branches. Auto-detects project stack and remote (GitHub `gh` or Azure DevOps `az`).
---

# /commit-push-pr

Auto-detect stack + remote, run pre-commit gates, commit → push → PR → sweep, in one shot.

## Triggers

- Changes are ready, all local tests pass
- End of a forge-loop iteration (after VERIFY + REFLECT pass)
- After `/codex-ci review` returns clean

## When NOT to Use

- Pre-commit checks failing — fix first, then run this
- On main/master directly — skill auto-creates a branch
- Unsure if changes are done — `/heidegger-reflect` first

## Usage

```
/commit-push-pr [optional commit message]
```

## Instructions

### 1. Detect project + verify gate

Check CWD and run the matching pre-commit gate. Run lint and tests in parallel.

| CWD matches | Static | Runtime |
|-------------|--------|---------|
| `*/<python-project>*` | `uv run ruff check src/ && uv run mypy src/<package-name>/` | `uv run pytest tests/unit/ -x -q` |
| `*/<agent-project>*` | `uv run ruff check . && uv run mypy .` | `python -m pytest tests/ -k "not deepeval" -x -q` |
| `*/<ts-project-with-tiers>*` | `bun run lint && bunx knip` | `bun run test:p0` |
| `*/<qc-project>*` | `uv run ruff check . && uv run mypy .` | `pytest tests/ -x -q` |
| `*/<python-project-b>*` | `cd backend && ruff check .` | `cd backend && python -m pytest tests/ -x -q` |
| `package.json` found | `bunx eslint --fix .` | `bun test` |
| `pyproject.toml` found | `uv run ruff check --fix . && uv run mypy .` | `uv run pytest -x -q` |

**If any check fails: STOP. Report exactly what failed. Do not proceed.**

### 2. Scaffold check

Before staging, verify no scaffold slipped through:
```bash
git diff --name-only HEAD | grep -E '\.(py|ts|js)$' | grep -v test | \
  xargs grep -l 'raise NotImplementedError\|^\s*pass$' 2>/dev/null
```
If any hits: STOP. Report files. Do not proceed.

### 3. Stage

```bash
git status          # show what will be staged
git diff --stat HEAD  # confirm scope
```
Stage only relevant files — no `.env`, credentials, `*.pem`, binaries, screenshots.
If diff is >500 LOC: warn user, ask if scope is correct before continuing.

### 4. Commit

Conventional Commits format: `type(scope): description`

Types: `feat` `fix` `refactor` `test` `docs` `chore` `ci`

If no message arg: generate from staged diff — one line, present tense, <72 chars.

Always append the executing model as co-author:
```
Co-Authored-By: <ModelName> <ModelVersion> <noreply@anthropic.com>
```

Examples:
- `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
- `Co-Authored-By: Codex Sonnet 4.6 <noreply@anthropic.com>`

Never `--no-verify`. Never `--amend` a pushed commit.

### 5. Detect remote + push

```bash
# Detect remote type from the remote URLs.
if git remote -v | grep -qE 'dev\.azure\.com|@ssh\.dev\.azure\.com|visualstudio\.com'; then
  REMOTE_TYPE=azure
  REMOTE_NAME=$(git remote -v | awk '/dev\.azure\.com|visualstudio\.com/{print $1; exit}')
elif git remote -v | grep -qE 'github\.com'; then
  REMOTE_TYPE=github
  REMOTE_NAME=$(git remote -v | awk '/github\.com/{print $1; exit}')
else
  REMOTE_TYPE=unknown
  REMOTE_NAME=$(git remote | head -1)
fi
DEFAULT_BR=$(git symbolic-ref --short "refs/remotes/$REMOTE_NAME/HEAD" 2>/dev/null | cut -d/ -f2 || echo master)
```

If on `$DEFAULT_BR` (typically `main`/`master`):
```bash
git checkout -b "feat/<slug-from-commit>"
```

Push:
```bash
git push -u "$REMOTE_NAME" HEAD
```

### 6. PR

**For GitHub** (`REMOTE_TYPE=github`):
```bash
gh pr create --title "<commit title>" --body "$(cat <<'EOF'
## Summary
- <bullet 1>
- <bullet 2>

## Test plan
- [ ] Pre-commit gate passed (lint + type check + unit tests)
- [ ] Scaffold check clean

## Evidence
<paste RED output line>
<paste GREEN output line>
EOF
)"
```

**For Azure DevOps** (`REMOTE_TYPE=azure`):
```bash
# Parse https://dev.azure.com/<ORG>/<PROJ>/_git/<REPO> from remote URL.
ORG=$(git remote get-url "$REMOTE_NAME" | sed -E 's|.*dev\.azure\.com[:/]+([^/]+)/.*|https://dev.azure.com/\1|; s|.*v3/([^/]+)/.*|https://dev.azure.com/\1|')
PROJ=$(git remote get-url "$REMOTE_NAME" | sed -E 's|.*dev\.azure\.com[:/]+[^/]+/([^/]+)/_git/.*|\1|; s|.*v3/[^/]+/([^/]+)/.*|\1|')
REPO=$(git remote get-url "$REMOTE_NAME" | sed -E 's|.*/_git/([^/]+).*|\1|; s|.*/([^/]+?)(\.git)?$|\1|')

az repos pr create \
  --organization "$ORG" --project "$PROJ" --repository "$REPO" \
  --source-branch "$(git symbolic-ref --short HEAD)" \
  --target-branch "$DEFAULT_BR" \
  --title "<commit title>" \
  --description "$(cat <<'EOF'
## Summary
- <bullet 1>
- <bullet 2>

## Test plan
- [ ] Pre-commit gate passed (lint + type check + unit tests)
- [ ] Scaffold check clean

## Evidence
<paste RED output line>
<paste GREEN output line>
EOF
)"
```

Capture the PR URL.

### 7. Sweep merged local branches

After the PR is open, prune any local branches whose content already lives on the default branch. This catches squash-merged branches that `git branch -d` rejects (squash changes the commit hash, so `--merged` doesn't see them).

```bash
git fetch "$REMOTE_NAME" --prune
SWEPT=()
KEPT=()
for b in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
  # Skip default and currently-checked-out branches.
  [ "$b" = "$DEFAULT_BR" ] && continue
  [ "$b" = "$(git symbolic-ref --short HEAD)" ] && continue
  # Cherry-pick aware: 0 unmerged commits = patches all live in master under different hashes.
  unmerged=$(git log --cherry-pick --right-only --oneline "$REMOTE_NAME/$DEFAULT_BR..$b" 2>/dev/null | wc -l)
  if [ "$unmerged" = "0" ]; then
    git branch -D "$b" >/dev/null 2>&1 && SWEPT+=("$b")
  else
    KEPT+=("$b ($unmerged unmerged)")
  fi
done
echo "Swept: ${SWEPT[*]:-(none)}"
echo "Kept:  ${KEPT[*]:-(none)}"
```

### 8. Report

Return a concise summary:
- PR URL
- New branch + remote
- Branches swept (and any kept with reason)

Done.

## Swarm Safety

Local merges are fine. The push step is guarded: if another active worktree is already on the same branch, the push is blocked to prevent remote conflicts. Each agent pushes its own branch — merging PRs is a human step.

The sweep step is local-only — it never touches remote branches. Only deletes local branches whose patches are content-equivalent to master (cherry-pick detection); never deletes the current branch or the default branch.
