# Azure DevOps Skill - Troubleshooting Guide

## Common Issues & Solutions

### Authentication Issues

#### Problem: "DEVOPS_PAT not found in .env"
```
ERROR: DEVOPS_PAT not found in .env
```

**Cause:** .env file missing or DEVOPS_PAT variable not set

**Solution:**
```bash
# 1. Check if .env exists
ls -la /path/to/project/.env

# 2. Add DEVOPS_PAT if missing
echo "DEVOPS_PAT=your_token_here" >> .env

# 3. Verify it's there
grep DEVOPS_PAT .env
```

#### Problem: "Unable to load extension 'azure-devops'"
```
WARNING: Unable to load extension 'azure-devops: Expected 1 module to load'
ERROR: 'pr' is not recognized
```

**Cause:** Azure DevOps CLI extension corrupt or missing

**Solution:**
```bash
# Remove corrupted extension
rm -rf /home/user/.azure/cliextensions/azure-devops

# Reinstall
az extension add --name azure-devops
```

#### Problem: "TF401398: The pull request cannot be activated"
```
ERROR: TF401398: The pull request cannot be activated because the
source and/or the target branch no longer exists
```

**Cause:** Target branch (e.g., main) doesn't exist on remote

**Solution:**
```bash
# Check if target branch exists
git branch -r | grep main

# If missing, push target branch
git push -u origin main

# Then try creating PR again
/azure-devops create-pr source-branch main "PR Title"
```

---

### Git/Push Issues

#### Problem: "Branch already up to date"
```
* branch            fix/feature -> FETCH_HEAD
Already up to date.
```

**Cause:** No new commits to push

**Solution:**
```bash
# Check if you have changes to commit
git status

# If changes exist, commit them first
git add .
git commit -m "Your message"

# Then push
git push origin branch-name
```

#### Problem: "fatal: pathspec 'releases/' did not match any files"
```
git rm -r --cached releases/
fatal: pathspec 'releases/' did not match any files
```

**Cause:** releases/ is not tracked in git (correct behavior)

**Solution:**
This is NOT an error - releases/ should NOT be in git. The skill validates this and warns if it IS tracked.

#### Problem: "nothing to commit, working tree clean"
```
On branch version/3.0.0
nothing to commit, working tree clean
```

**Cause:** All changes already committed or no changes exist

**Solution:**
```bash
# Option 1: If branch is new, just push it
git push -u origin version/3.0.0

# Option 2: If changes exist but aren't staged, add them
git add .
git status  # verify changes are staged

# Option 3: Check if changes are on different files
git diff HEAD
```

---

### Branch Issues

#### Problem: "Branch tracking is confusing"
```
Main branch is local but not tracking origin/main
version/3.0.0 is ahead but origin/version/3.0.0 doesn't exist yet
```

**Cause:** Branches not set up with -u (upstream tracking)

**Solution:**
```bash
# When pushing, always use -u:
git push -u origin branch-name

# Or set up tracking after push:
git branch --set-upstream-to=origin/branch-name branch-name

# Verify tracking:
git branch -vv
```

#### Problem: "Detached HEAD state"
```
HEAD is now at abc1234 Some old commit
You are in 'detached HEAD' state...
```

**Cause:** Checked out a commit instead of a branch

**Solution:**
```bash
# Return to your branch
git checkout your-branch-name

# Or create a new branch from current state
git checkout -b new-branch-name
```

---

### File & Directory Issues

#### Problem: "releases/ directory is tracked in git"
```
ERROR: releases/ directory is tracked in git! It should be in .gitignore
```

**Cause:** releases/ was accidentally committed

**Solution:**
```bash
# Remove it from git (but keep local copy)
git rm -r --cached releases/

# Commit the removal
git commit -m "Remove releases directory from git tracking"

# Verify .gitignore has it
grep "releases/" .gitignore
# If missing, add it:
echo "releases/" >> .gitignore

# Push the fix
git push origin branch-name
```

#### Problem: "Untracked files that should be ignored"
```
WARN: Untracked files found:
  - qa_reports/results.json
  - node_modules/package/...
```

**Cause:** Files created locally but should be ignored

**Solution:**
```bash
# These are normal - they're properly ignored
# Just proceed with commit if other files are ready

# Or clean them up to reduce clutter:
git clean -fd

# Verify .gitignore has correct patterns:
grep -E "qa_reports|node_modules" .gitignore
```

#### Problem: "Large files or binaries staged"
```
WARN: File too large: releases/my-project-v3.0.0-release.zip (371 KB)
```

**Cause:** Binary files shouldn't be in git

**Solution:**
```bash
# Don't stage large files:
git status --short | grep .zip

# If accidentally added:
git rm --cached file.zip
echo "file.zip" >> .gitignore
git commit -m "Remove binary file from tracking"
```

---

### PR Creation Issues

#### Problem: "PR created but has duplicate"
```
PR #28 already exists with same branches
ERROR: Duplicate PR
```

**Cause:** PR with same source→target branches already exists

**Solution:**
```bash
# Check existing PRs in Azure DevOps

# Option 1: Update existing PR (don't create new one)
# (Push more commits to existing PR branch)

# Option 2: Use different branch name
git checkout -b version/3.0.0-v2
git push -u origin version/3.0.0-v2
/azure-devops create-pr version/3.0.0-v2 main "New PR"
```

#### Problem: "PR shows no changes"
```
PR created but shows 0 commits
```

**Cause:** Branches don't have different commits

**Solution:**
```bash
# Check commit history
git log origin/main..source-branch --oneline

# If empty, need to add commits:
git add .
git commit -m "Add changes"
git push origin source-branch

# Create PR again
```

---

### Approval Gate Issues

#### Problem: "Skill says 'awaiting approval' but I want to merge"
```
⏸️  APPROVAL REQUIRED

Merge decisions must be authorized
```

**Cause:** This is intentional - manual approval required

**Solution:**
```
This is a FEATURE, not a bug!

The skill enforces that:
✓ Code changes are reviewed
✓ Merge is authorized by team lead
✓ No accidental auto-merges to main

To proceed:
1. Review PR in Azure DevOps
2. Address any feedback
3. Approve the PR (in Azure DevOps UI)
4. Merge manually (in Azure DevOps UI)
```

#### Problem: "I forgot what the approval gate does"
```
See: /azure-devops-skill/PERMISSIONS.md section "Approval Gate"

Quick summary:
- Commits: automatic ✓
- Push: automatic ✓
- PR creation: automatic ✓
- Merge: ALWAYS manual (requires approval)
```

---

### Environment & Configuration

#### Problem: ".env permissions incorrect"
```
WARNING: .env is world-readable
ls -l shows: -rw-r--r--  (not -rw-------)
```

**Cause:** .env has overly permissive permissions

**Solution:**
```bash
# Fix permissions (user-readable only)
chmod 600 .env

# Verify
ls -l .env
# Should show: -rw------- (or similar)

# Also check git-credentials
chmod 600 ~/.git-credentials
```

#### Problem: "azure-devops.sh is not executable"
```
bash: ./azure-devops.sh: Permission denied
```

**Cause:** Script missing execute permission

**Solution:**
```bash
# Make executable
chmod +x /path/to/azure-devops.sh

# Verify
ls -l azure-devops.sh
# Should show: -rwx------ (or similar)
```

---

### Debugging & Diagnostics

#### Get Full Status
```bash
/azure-devops status

# Shows:
# - Current git branch
# - Untracked files
# - .env configuration
# - Remote branches
```

#### Validate Branch State
```bash
/azure-devops validate

# Checks:
# - releases/ not tracked ✓
# - .gitignore correct ✓
# - No sensitive files ✓
```

#### Check Git Log
```bash
# See commits on current branch
git log --oneline -10

# See commits NOT on main
git log main..HEAD --oneline

# See full diff
git diff origin/main..HEAD
```

#### Test PR Creation (Dry Run)
```bash
# Just validate, don't create PR:
/azure-devops validate
git log origin/main..HEAD --oneline

# If looks good, then:
/azure-devops create-pr branch main "Title" "Description"
```

---

## Getting Help

### Check These First
1. **PERMISSIONS.md** - Security & workflow details
2. **README.md** - Usage examples
3. **azure-devops.sh** - Implementation comments
4. **This file** - Troubleshooting steps

### If Still Stuck
```bash
# Show detailed git status
git status --verbose
git branch -vv
git log --graph --oneline --all

# Test Azure DevOps CLI
az devops --version
az repos --help
```

### When Asking for Help
Provide:
1. Command you ran: `<command>`
2. Error message: `<full error>`
3. What you expected: `<description>`
4. What happened instead: `<description>`
5. Current branch: `git branch`
6. Untracked files: `git status --short`

---

## Known Limitations

### Cannot Do (By Design)
- ❌ Auto-merge PRs (approval always required)
- ❌ Force push (prevents accidental overwrites)
- ❌ Delete branches remotely (manual process)
- ❌ Rewrite history (preserve audit trail)

### Requires Manual Steps
- ⚠️ PR merge (done in Azure DevOps UI)
- ⚠️ Branch cleanup after merge
- ⚠️ Approval decisions
- ⚠️ Code review feedback

---

## Reference

**Skill Location:** `/home/shovalbe/.codex/skills/azure-devops/`
**Main Script:** `azure-devops.sh`
**Configuration:** `manifest.json`
**Security Policy:** `PERMISSIONS.md`

**Last Updated:** 2026-02-16
