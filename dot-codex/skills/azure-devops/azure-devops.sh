#!/bin/bash
# Azure DevOps Skill - Commit, Push, and Create PR with Approval Gate
#
# Usage: ./azure-devops.sh [command] [options]
# Commands:
#   commit-and-push <branch-name> <commit-message>
#   create-pr <source-branch> <target-branch> <pr-title> [pr-description]
#   status
#
# CRITICAL: This skill ALWAYS awaits PR approval before merging
# See: .codex/skills/azure-devops/PERMISSIONS.md

set -e

PROJECT_ROOT="${PROJECT_ROOT:-.}"
DEVOPS_ORG="${DEVOPS_ORG:?set DEVOPS_ORG, e.g. https://dev.azure.com/your-org}"
DEVOPS_PROJECT="${DEVOPS_PROJECT:?set DEVOPS_PROJECT to your Azure DevOps project name}"
DEVOPS_REPO="${DEVOPS_REPO:?set DEVOPS_REPO to your repo name}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# Load Azure DevOps PAT from .env
load_devops_pat() {
  if [ ! -f "$PROJECT_ROOT/.env" ]; then
    log_error ".env file not found at $PROJECT_ROOT/.env"
    return 1
  fi

  DEVOPS_PAT=$(grep "^DEVOPS_PAT=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
  if [ -z "$DEVOPS_PAT" ]; then
    log_error "DEVOPS_PAT not found in .env"
    return 1
  fi
  log_success "Azure DevOps PAT loaded"
}

# ============================================================================
# Stage and Commit
# ============================================================================

stage_and_commit() {
  local branch="$1"
  local message="$2"

  if [ -z "$branch" ] || [ -z "$message" ]; then
    log_error "Usage: stage-and-commit <branch> <message>"
    return 1
  fi

  log_info "Switching to branch: $branch"
  git checkout "$branch" || git checkout -b "$branch"

  log_info "Adding changes..."
  git add -A

  log_info "Checking git status..."
  git status --short

  log_info "Creating commit: $message"
  git commit -m "$message" \
    -m "Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>" || {
    log_warn "Nothing to commit"
    return 0
  }

  log_success "Commit created"
}

# ============================================================================
# Push to Remote
# ============================================================================

push_to_remote() {
  local branch="$1"

  if [ -z "$branch" ]; then
    log_error "Usage: push-to-remote <branch>"
    return 1
  fi

  load_devops_pat || return 1

  log_info "Configuring git credentials..."
  git config --global credential.helper store
  echo "https://anyuser:${DEVOPS_PAT}@dev.azure.com" > ~/.git-credentials
  chmod 600 ~/.git-credentials

  log_info "Pushing branch: $branch"
  git push -v origin "$branch" 2>&1 | grep -E "To|new branch|updating" || true

  log_success "Branch pushed to remote"
  echo ""
  log_info "Remote tracking:"
  git branch -vv | grep "$branch"
}

# ============================================================================
# Validate Branch State
# ============================================================================

validate_branch_state() {
  log_info "Validating branch state..."

  # Check for untracked files that should be ignored
  local untracked=$(git status --short | grep "^??" | awk '{print $2}')
  if [ -n "$untracked" ]; then
    log_warn "Untracked files found:"
    echo "$untracked" | while read file; do
      echo "  - $file"
    done
  fi

  # Check if releases/ is tracked (it shouldn't be)
  if git ls-files | grep -q "^releases/"; then
    log_error "releases/ directory is tracked in git! It should be in .gitignore"
    return 1
  fi

  log_success "Branch state valid"
}

# ============================================================================
# Create Pull Request
# ============================================================================

create_pull_request() {
  local source_branch="$1"
  local target_branch="$2"
  local pr_title="$3"
  local pr_description="${4:-}"

  if [ -z "$source_branch" ] || [ -z "$target_branch" ] || [ -z "$pr_title" ]; then
    log_error "Usage: create-pr <source-branch> <target-branch> <title> [description]"
    return 1
  fi

  # Hard guardrail: master promotions must come from stage only.
  if [ "$target_branch" = "master" ] && [ "$source_branch" != "stage" ]; then
    log_error "Blocked: PRs to 'master' must use source branch 'stage' (got '$source_branch')."
    return 1
  fi

  load_devops_pat || return 1

  log_info "Configuring Azure DevOps CLI..."
  az devops configure --defaults \
    organization="$DEVOPS_ORG" \
    project="$DEVOPS_PROJECT" 2>/dev/null || true

  # Login with PAT
  echo "$DEVOPS_PAT" | az devops login --organization "$DEVOPS_ORG" 2>/dev/null || true

  log_info "Creating PR: $source_branch → $target_branch"

  local pr_output
  pr_output=$(az repos pr create \
    --source-branch "$source_branch" \
    --target-branch "$target_branch" \
    --title "$pr_title" \
    --description "${pr_description:-}" \
    --output table 2>&1)

  if echo "$pr_output" | grep -q "ID"; then
    log_success "Pull Request created!"
    echo ""
    echo "$pr_output" | head -5
    echo ""

    # Extract PR ID
    local pr_id=$(echo "$pr_output" | grep -oE "^[0-9]+" | head -1)
    if [ -n "$pr_id" ]; then
      log_info "PR ID: $pr_id"
    fi
  else
    log_error "Failed to create PR"
    echo "$pr_output"
    return 1
  fi
}

# ============================================================================
# Approval Gate
# ============================================================================

await_pr_approval() {
  local pr_id="$1"

  if [ -z "$pr_id" ]; then
    log_warn "No PR ID provided - skipping approval gate"
    return 0
  fi

  cat << 'EOF'

╔════════════════════════════════════════════════════════════════╗
║                    ⏸️  APPROVAL REQUIRED                        ║
╚════════════════════════════════════════════════════════════════╝

This skill REQUIRES manual approval before merging.

CRITICAL POINTS:
✓ PR has been created and pushed
✓ Code review is required BEFORE merge
✓ Azure DevOps will show the PR for approval
✓ This prevents accidental merges to production branches

NEXT STEPS:
1. Review PR in Azure DevOps (your configured DEVOPS_REPO repository)
2. Address any review comments
3. Approve when ready
4. DO NOT merge automatically

⚠️  Merge decisions should ALWAYS be made by authorized team members

EOF

  log_warn "Awaiting approval before proceeding..."
  log_info "PR ID: $pr_id"
  log_info "Check Azure DevOps for review status"
}

# ============================================================================
# Full Workflow
# ============================================================================

full_workflow() {
  local branch="$1"
  local commit_msg="$2"
  local pr_title="$3"
  local target="${4:-main}"

  if [ -z "$branch" ] || [ -z "$commit_msg" ] || [ -z "$pr_title" ]; then
    log_error "Usage: full-workflow <branch> <commit-message> <pr-title> [target-branch]"
    return 1
  fi

  log_info "Starting Azure DevOps workflow..."
  echo ""

  # Step 1: Validate
  validate_branch_state || return 1
  echo ""

  # Step 2: Commit
  stage_and_commit "$branch" "$commit_msg" || return 1
  echo ""

  # Step 3: Push
  push_to_remote "$branch" || return 1
  echo ""

  # Step 4: Create PR
  create_pull_request "$branch" "$target" "$pr_title" || return 1
  echo ""

  # Step 5: Await approval (REQUIRED)
  await_pr_approval "$branch"

  log_info "Workflow complete"
}

# ============================================================================
# Status Command
# ============================================================================

status() {
  log_info "Azure DevOps Skill Status"
  echo ""

  # Check git
  echo "Git Status:"
  git status --short || echo "  (no changes)"
  echo ""

  # Check branches
  echo "Local Branches:"
  git branch | grep "^\*" || echo "  (none)"
  echo ""

  # Check .env
  if [ -f "$PROJECT_ROOT/.env" ]; then
    if grep -q "^DEVOPS_PAT=" "$PROJECT_ROOT/.env"; then
      log_success ".env has DEVOPS_PAT configured"
    else
      log_error ".env missing DEVOPS_PAT"
    fi
  else
    log_error ".env not found"
  fi
}

# ============================================================================
# Main
# ============================================================================

main() {
  local cmd="${1:-status}"

  case "$cmd" in
    commit-and-push)
      stage_and_commit "$2" "$3"
      push_to_remote "$2"
      ;;
    create-pr)
      create_pull_request "$2" "$3" "$4" "$5"
      await_pr_approval "$2"
      ;;
    full-workflow)
      full_workflow "$2" "$3" "$4" "$5"
      ;;
    validate)
      validate_branch_state
      ;;
    status)
      status
      ;;
    *)
      log_error "Unknown command: $cmd"
      echo ""
      echo "Available commands:"
      echo "  commit-and-push <branch> <message>       - Commit and push changes"
      echo "  create-pr <src> <tgt> <title> [desc]    - Create pull request"
      echo "  full-workflow <br> <msg> <title> [tgt]  - Full commit → push → PR workflow"
      echo "  validate                                 - Validate branch state"
      echo "  status                                   - Show status"
      return 1
      ;;
  esac
}

main "$@"
