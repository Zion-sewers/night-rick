# Azure DevOps Skill

Automate Azure DevOps workflows: commit, push branches, and create pull requests with mandatory approval gating.

**Status:** ✅ Production Ready
**Approval Required:** ⚠️ YES - Always awaits manual PR approval before merge
**Last Updated:** 2026-02-16

## Quick Start

### Full Workflow (Commit → Push → Create PR)
```bash
/azure-devops full-workflow \
  version/3.0.0 \
  "docs: v3.0.0 documentation updates" \
  "Release v3.0.0: Documentation" \
  main
```

**What happens:**
1. ✅ Validates branch state (releases/ not tracked, no sensitive files)
2. ✅ Stages all changes and creates commit
3. ✅ Pushes branch to Azure DevOps
4. ✅ Creates pull request
5. ⏸️ **AWAITS YOUR APPROVAL** (pauses for human review)

### Create PR Only (Branch Already Pushed)
```bash
/azure-devops create-pr \
  version/3.0.0 \
  main \
  "Release v3.0.0" \
  "Comprehensive documentation for v3.0.0 release"
```

### Check Status
```bash
/azure-devops status
```

Shows git status, branches, and .env configuration.

## Key Features

### ✅ Automatic
- Git add & commit
- Push to remote
- Pull request creation
- File validation (.gitignore checks)

### ⏸️ Manual (Approval Gate)
- **PR Merge:** Always requires manual approval
- **Review:** Done in Azure DevOps UI
- **Authorization:** Team lead decision

### 🔒 Security
- DEVOPS_PAT loaded from .env (never logged)
- Git credentials stored securely (chmod 600)
- Co-authored commits with proper attribution
- No secrets in commit messages

## Permissions

This skill requires:
| Permission | Purpose |
|-----------|---------|
| Bash - push code | Upload branches to Azure DevOps |
| Bash - create commits | Stage & commit changes |
| Bash - create pull requests | Create PRs via Azure DevOps CLI |
| Read - .env file | Load DEVOPS_PAT token |

**Important:** These are requested per-use and require explicit approval.

## Approval Gate Explained

### Why Manual Approval?
✓ Prevents accidental merges to main/production
✓ Ensures code review before integration
✓ Maintains branch protection policies
✓ Auditable merge decisions

### Workflow
```
[Commit] → [Push] → [Create PR] → [⏸️ AWAIT APPROVAL] → [Merge]
  auto      auto      auto          MANUAL              MANUAL
```

You write the code and ask Claude to:
1. Create the commit and push
2. Create the PR

Then **you** review and approve in Azure DevOps.

## Files Managed

### Tracked in Git ✅
- Source code (plugin/version2.0/src/)
- Documentation (README.md, CLAUDE.md)
- Tests (test/, tests/)
- Configuration (package.json, etc)

### Ignored from Git ✅
- releases/ (build artifacts)
- qa_reports/ (test results)
- .env (secrets)
- node_modules/ (dependencies)

Skill verifies releases/ is NOT tracked before each commit.

## Examples

### Example 1: Documentation Release
```bash
# User asks:
# "Commit and push v3.0.0 documentation updates, create a PR"

# Claude runs:
/azure-devops full-workflow \
  version/3.0.0 \
  "docs: Update README.md, CLAUDE.md, plugin/README.md

- Update v3.0.0 architecture overview
- Create developer guide
- Update installation instructions" \
  "v3.0.0: Documentation Updates" \
  main

# Output:
# ✓ Branch validated
# ✓ Changes committed
# ✓ Pushed to origin/version/3.0.0
# ✓ PR #28 created
#
# ⏸️  APPROVAL REQUIRED
# Review PR in Azure DevOps before merging
```

### Example 2: Feature Branch with PR
```bash
# User asks:
# "Push the bugfix branch and create a PR to main"

# Claude runs:
/azure-devops create-pr \
  feature/bugfix-123 \
  main \
  "fix: Resolve aspect ratio distortion in images" \
  "Fixes issue where images were stretched instead of resized

Changes:
- Apply aspect ratio lock BEFORE constraint solving
- Add regression test for image preservation
- Verify with QA metrics (VABB)"

# Output:
# ✓ PR created
# ID    Created     Title                    Status
# ----  ----------  -----------------------  ------
# 29    2026-02-16  fix: Aspect ratio...     Active
#
# ⏸️  APPROVAL REQUIRED
# Address any review feedback before merge
```

### Example 3: Emergency Hotfix (Same Approval)
```bash
# Even urgent fixes require approval:
/azure-devops full-workflow \
  hotfix/critical-bug \
  "fix: Critical security patch for v3.0.0" \
  "HOTFIX: Security patch" \
  main

# Output:
# ✓ All steps complete
# ⏸️  APPROVAL REQUIRED - Even hotfixes need review
# (No auto-merge, always manual approval)
```

## Common Workflows

### Release a New Version
```
1. Create branch: version/X.Y.Z
2. Update documentation (README.md, CLAUDE.md)
3. Update package.json version
4. Test locally: bun run test:p0
5. Run: /azure-devops full-workflow version/X.Y.Z "Release vX.Y.Z" "Release vX.Y.Z" main
6. Review & approve PR in Azure DevOps
7. Merge (manual, in Azure DevOps UI)
8. (Optional) Delete branch after merge
```

### Bug Fix Workflow
```
1. Create branch: fix/issue-description
2. Fix code
3. Add regression test
4. Test: bun run test:p0
5. Run: /azure-devops full-workflow fix/... "fix: description" "Fix: description" main
6. Code review in PR
7. Approve & merge
```

### Documentation Update
```
1. Branch: docs/description (or version/X.Y.Z for releases)
2. Update README.md, CLAUDE.md, docs/
3. Run: /azure-devops full-workflow docs/... "docs: description" "Docs: description" main
4. Review changes in PR
5. Approve & merge
```

## Troubleshooting

### "DEVOPS_PAT not found"
```
Fix: Add to .env:
DEVOPS_PAT=your_token_here
```

### "releases/ directory is tracked"
```
Fix: git rm -r --cached releases/
     git commit -m "Remove releases from tracking"
```

### "PR creation failed - branch not found"
```
Fix: Make sure target branch exists on remote:
     git push -u origin main
```

### "Nothing to commit"
```
This is OK - means no changes to stage
Just create a PR if branch already exists
```

## Related Documents

- **Permissions & Security:** `PERMISSIONS.md`
- **Implementation Details:** `azure-devops.sh`
- **Project-specific workflow:** Root `CLAUDE.md` - see git workflow section

## Configuration

### Manifest
File: `manifest.json`
- Declares permissions needed
- Documents workflow steps
- Sets `requireApproval: true` (always)

### Script
File: `azure-devops.sh`
- Executable commands: commit-and-push, create-pr, full-workflow, status, validate
- Helper functions: load PAT, validate branch, await approval
- Error handling with colored output

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-16 | Initial release with approval gate |

## Support

For issues or questions:
1. Check `PERMISSIONS.md` for security details
2. Review this README for examples
3. Check `azure-devops.sh` comments for implementation
4. Ask Claude: "What does the azure-devops skill do?"

---

**Remember:** ⏸️ **This skill always awaits PR approval. No auto-merge.**

Every change is human-reviewed before merging.
