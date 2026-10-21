# Azure DevOps Skill - Permissions & Approval Gate

**Status:** Production Ready | Approval Required
**Version:** 1.0.0
**Last Updated:** 2026-02-16

## Overview

This skill automates Azure DevOps workflows (commit, push, PR creation) with a **mandatory approval gate**. No code is merged without explicit human review.

## Critical Rule

### ⚠️ ALWAYS AWAIT PR APPROVAL - DO NOT AUTO-MERGE

This skill enforces:
- Commits are created and pushed ✓
- PRs are created and visible in Azure DevOps ✓
- **HUMAN REVIEW REQUIRED** before merge ✗ (automated merge blocked)

**Rationale:** Automated merges to production branches introduce risk. Every change must be reviewed by an authorized team member.

## Permissions Required

### Bash Tool Permissions

| Action | Permission | Reason |
|--------|-----------|--------|
| **push code** | `Bash` | Upload branches to Azure DevOps |
| **create commits** | `Bash` | Stage files and commit changes |
| **create pull requests** | `Bash` | Invoke Azure DevOps CLI for PR creation |
| **read .env** | `Read` | Load DEVOPS_PAT token for authentication |

### Environment Access

- **File:** `.env`
- **Variable:** `DEVOPS_PAT`
- **Purpose:** Azure DevOps personal access token authentication
- **Scope:** Read-only (no modifications to .env)

## Workflow Steps

### 1. Validate Branch State
```bash
git status --short
git ls-files | grep "^releases/"  # Verify releases/ not tracked
```

**Checks:**
- ✅ Untracked files identified
- ✅ releases/ directory properly ignored
- ✅ No sensitive files staged

### 2. Stage & Commit
```bash
git add -A
git commit -m "message" -m "Co-Authored-By: Claude Haiku 4.5"
```

**Ensures:**
- ✅ Clear commit message
- ✅ Proper attribution
- ✅ Single logical commit

### 3. Push to Remote
```bash
git config credential.helper store
git push -v origin <branch>
```

**Security:**
- ✅ PAT from .env (not hardcoded)
- ✅ Credentials stored in ~/.git-credentials (chmod 600)
- ✅ SSH key alternative not supported (use PAT)

### 4. Create Pull Request
```bash
az repos pr create \
  --source-branch <branch> \
  --target-branch <target> \
  --title "PR Title" \
  --description "details"
```

**Output:**
- ✅ PR ID and URL
- ✅ Link to Azure DevOps for review

### 5. Await Approval ⏸️ (REQUIRED)
```
╔════════════════════════════════════════════════════════════════╗
║                    ⏸️  APPROVAL REQUIRED                        ║
╚════════════════════════════════════════════════════════════════╝

NEXT STEPS:
1. Review PR in Azure DevOps
2. Address review comments
3. Approve when ready
4. DO NOT merge automatically

⚠️  Merge decisions must be authorized
```

**This step:**
- ✅ Pauses workflow for human review
- ✅ Provides clear approval instructions
- ✅ Does NOT auto-merge

## Usage Examples

### Example 1: Full Workflow (Commit → Push → PR)
```bash
# Ask Claude to run:
# /azure-devops full-workflow version/3.0.0 "docs: v3.0.0 updates" "Release v3.0.0: Documentation" main

# This will:
# 1. Validate branch state
# 2. Stage and commit changes
# 3. Push to origin/version/3.0.0
# 4. Create PR from version/3.0.0 → main
# 5. WAIT for approval (user must review in Azure DevOps)
```

### Example 2: Create PR Only (Branch Already Pushed)
```bash
# /azure-devops create-pr version/3.0.0 main "Release v3.0.0" "Description here"

# Output:
# ✓ Pull Request created!
# ID    Created     Title              Status
# ----  ----------  -----------------  --------
# 28    2026-02-16  Release v3.0.0     Active
#
# ⏸️  APPROVAL REQUIRED
# (instructions displayed)
```

### Example 3: Check Status
```bash
# /azure-devops status

# Output:
# Git Status: (current changes)
# Local Branches: (list)
# .env status: ✓ DEVOPS_PAT configured
```

## Files & .gitignore

### Protected from Git Tracking
```
releases/           # Build artifacts (properly ignored)
qa_reports/         # Test results (properly ignored)
.env               # Secrets file (properly ignored)
node_modules/      # Dependencies (properly ignored)
```

### Verified by Skill
- ✅ releases/ not in `git ls-files`
- ✅ .gitignore contains `releases/`
- ✅ .env loaded (not staged)
- ✅ No large binaries in commits

## Authorization & Access

### Who Can Use This Skill?
- ✅ Claude Code (with Bash permission)
- ✅ Authorized developers (with Azure DevOps access)
- ✅ CI/CD pipelines (with stored PAT token)

### What Requires Approval?
| Action | Auto? | Requires Approval? |
|--------|-------|-------------------|
| Commit | ✅ | ❌ (local only) |
| Push | ✅ | ❌ (branch push, not merge) |
| PR Create | ✅ | ✅ (before merge) |
| Merge | ❌ | ✅ (always manual) |

### Access Control
- **DEVOPS_PAT scope:** Minimal (push + PR create only)
- **Git credentials:** Stored securely in ~/.git-credentials (chmod 600)
- **Audit trail:** All commits show `Co-Authored-By` attribution

## Error Handling

### Common Issues

**"DEVOPS_PAT not found in .env"**
- Fix: Add `DEVOPS_PAT=<token>` to .env

**"The pull request cannot be activated"**
- Cause: Target branch not on remote
- Fix: Push target branch first (e.g., git push -u origin main)

**"releases/ directory is tracked in git"**
- Cause: Accidentally committed releases/
- Fix: git rm -r --cached releases/ && git commit

**"Failed to create PR"**
- Cause: Azure DevOps CLI extension not installed
- Fix: az extension add --name azure-devops

## Learning from Implementation

### What We Learned (Feb 16, 2026)

1. **Branch Push & PR Creation Work Separately**
   - ✅ Push succeeds independently of PR
   - ✅ PR can be created after branch exists on remote
   - ❌ Don't assume sequential dependencies

2. **.gitignore Works Properly**
   - ✅ releases/ properly ignored (not in git ls-files)
   - ✅ Untracked files show in git status
   - ❌ Don't force-add ignored directories

3. **Main Branch Tracking**
   - ✅ Use `git push -u origin main` to establish tracking
   - ✅ `origin/main` must exist for PR creation
   - ❌ Don't assume branches track remote automatically

4. **Documentation as Code**
   - ✅ README.md and CLAUDE.md updates work
   - ✅ Files can be part of release commits
   - ✅ Keep docs in version control

## Security Considerations

### Secrets Protection
- ✅ DEVOPS_PAT stored in .env (never committed)
- ✅ git-credentials file: chmod 600 (user-readable only)
- ✅ No PAT token logged in stdout
- ✅ No credentials in commit messages

### Access Control
- ✅ PAT scope limited to the target repo (configured via DEVOPS_REPO)
- ✅ No personal email or credentials in commits
- ✅ Co-authored commits show proper attribution
- ✅ All operations audit-logged by Azure DevOps

### Merge Safety
- ✅ No auto-merge (human approval required)
- ✅ PR review enforced in Azure DevOps
- ✅ Branch protection rules apply (if configured)

## Related Documentation

- **Usage:** See `README.md` in this directory
- **Troubleshooting:** See `TROUBLESHOOTING.md`
- **Implementation:** See `azure-devops.sh` comments
- **Project-specific rules:** See root `CLAUDE.md` for git workflow

## Approval Checklist

Before closing this approval gate, verify:
- [ ] PR title is clear and descriptive
- [ ] PR description includes summary of changes
- [ ] All commits have proper attribution
- [ ] No sensitive files are staged
- [ ] releases/ directory is not tracked
- [ ] Target branch (main/staging) is appropriate
- [ ] Code review guidelines are followed
- [ ] CI/CD gates pass (if configured)

**Then:** Approve the PR in Azure DevOps UI (do not auto-merge)

---

**Last Learned:** 2026-02-16
**Next Review:** When new Azure DevOps feature needed
**Maintainer:** Claude Code
