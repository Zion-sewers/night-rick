#!/bin/bash
set -eu

# /codex-ci orchestration script
# Usage: bash run.sh <mode> [args...]
# Modes: fix | review | review-remote | mutate | tdd | tdd-green

MODE="${1:-fix}"
shift || true
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROJECT_NAME="$(basename "$PROJECT_ROOT")"
CONFIG="$SCRIPT_DIR/projects.json"
TMP_DIR="/tmp/codex-ci"
REPORT_DIR="$PROJECT_ROOT/qa_reports/codex-review"
mkdir -p "$TMP_DIR" "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Load project config via bun (fast JSON parse)
get_config() {
  local field="$1"
  local default="$2"
  bun -e "try{const c=JSON.parse(require('fs').readFileSync('$CONFIG','utf8'));console.log(c['$PROJECT_NAME']?.${field}||'$default')}catch{console.log('$default')}"
}

TEST_CMD="$(get_config test_cmd 'bun test')"
FULL_TEST_CMD="$(get_config full_test_cmd 'bun test')"
CONSTRAINTS="$(get_config constraints '')"
MUTATION_TARGETS="$(get_config mutation_targets 'src/')"

echo "=== CODEX-CI: mode=$MODE project=$PROJECT_NAME ==="
echo "--- Project root: $PROJECT_ROOT"
echo "--- Test command: $TEST_CMD"
echo ""

case "$MODE" in

  fix)
    echo "--- Running tests to capture failures..."
    cd "$PROJECT_ROOT"
    set +e
    eval "$TEST_CMD" 2>&1 | tail -80 > "$TMP_DIR/failures.txt"
    TEST_EXIT=$?
    set -e

    if [ "$TEST_EXIT" -eq 0 ]; then
      echo "All tests pass. Nothing to fix."
      cat "$TMP_DIR/failures.txt"
      exit 0
    fi

    echo "--- Tests failed (exit $TEST_EXIT). Feeding to Codex..."
    echo ""
    cat "$TMP_DIR/failures.txt"
    echo ""
    echo "--- Codex fix proposal:"
    OUTFILE="$TMP_DIR/fix-proposal-$TIMESTAMP.txt"
    codex exec \
      -o "$OUTFILE" \
      --sandbox read-only \
      "You are a senior engineer fixing test failures.

Read the test output below. Fix the ROOT CAUSE in source code only.
Do NOT modify test files. Do NOT add mocks.

Project constraints: $CONSTRAINTS

Test output:
$(cat "$TMP_DIR/failures.txt")

Show the exact file changes needed as a unified diff."
    cat "$OUTFILE"
    ;;

  review)
    cd "$PROJECT_ROOT"
    echo "--- Running Codex local review..."

    # Detect review scope
    BASE_BRANCH="main"
    if ! git rev-parse --verify main >/dev/null 2>&1; then
      BASE_BRANCH="master"
    fi

    OUTFILE="$REPORT_DIR/review-local-$TIMESTAMP.md"

    # codex review writes to stdout, pipe to file
    # Note: codex review does not accept -o or a prompt with --uncommitted/--base
    if git diff --quiet && git diff --cached --quiet; then
      echo "--- No uncommitted changes, reviewing branch diff against $BASE_BRANCH..."
      codex review --base "$BASE_BRANCH" 2>&1 | tee "$OUTFILE"
    else
      echo "--- Reviewing uncommitted changes..."
      codex review --uncommitted 2>&1 | tee "$OUTFILE"
    fi

    if [ -s "$OUTFILE" ]; then
      echo ""
      echo "--- Review output:"
      cat "$OUTFILE"
      echo ""
      echo "--- Saved to: $OUTFILE"
    else
      echo "--- WARNING: Codex review produced no output to $OUTFILE"
      echo "--- This may be a Codex CLI output routing issue."
    fi
    ;;

  review-remote)
    cd "$PROJECT_ROOT"
    echo "--- Running remote review via Azure Foundry..."

    # Load Azure credentials
    VAULT_NAME="${VAULT_NAME:-}"
    ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"
    KEY="${AZURE_OPENAI_KEY:-}"

    if [ -z "$ENDPOINT" ] || [ -z "$KEY" ]; then
      VAULT_NAME="${VAULT_NAME:?set VAULT_NAME to your key vault name, or set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_KEY directly}"
      ENDPOINT=$(az keyvault secret show --vault-name "$VAULT_NAME" --name "AzureAIFoundry-Endpoint" --query value -o tsv 2>/dev/null) || true
      KEY=$(az keyvault secret show --vault-name "$VAULT_NAME" --name "AzureOpenAI-Key" --query value -o tsv 2>/dev/null) || true
    fi

    if [ -z "$ENDPOINT" ] || [ -z "$KEY" ]; then
      echo "ERROR: Azure Foundry credentials not available."
      echo "Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_KEY, or ensure 'az login' is active."
      echo "Falling back to local review..."
      exec "$0" review "$@"
    fi

    DEPLOYMENT="${AZURE_CODEX_DEPLOYMENT:?set AZURE_CODEX_DEPLOYMENT to your review-deployment name}"

    # Capture diff
    DIFF_CONTENT=$(git diff HEAD --no-color 2>/dev/null | head -3000)
    if [ -z "$DIFF_CONTENT" ]; then
      BASE_BRANCH="main"
      git rev-parse --verify main >/dev/null 2>&1 || BASE_BRANCH="master"
      DIFF_CONTENT=$(git diff "$BASE_BRANCH...HEAD" --no-color 2>/dev/null | head -3000)
    fi

    if [ -z "$DIFF_CONTENT" ]; then
      echo "--- No diff to review."
      exit 0
    fi

    REVIEW_PROMPT="You are a senior code reviewer (Codex CI Reviewer).
Review the following diff for project '$PROJECT_NAME'.
Check: architecture (separation of concerns, file sizes <500 LOC), risk (security, secrets, destructive ops),
quality (dead code, TODOs in production, test gaps), and compliance ($CONSTRAINTS).
Output format: CRITICAL / HIGH / MEDIUM findings with file:line references.
Be concise. No fluff.

DIFF:
$DIFF_CONTENT"

    SAFETY_PROMPT="You are a safety auditor for project '$PROJECT_NAME'.
Analyze the diff for: secrets exposure, injection vulnerabilities, missing input validation,
destructive operations without confirmation, missing error handling on external calls.
Output: SAFE / WARN / BLOCK with specific file:line references.

DIFF:
$DIFF_CONTENT"

    REVIEW_FILE="$REPORT_DIR/review-remote-$TIMESTAMP.md"
    SAFETY_FILE="$REPORT_DIR/safety-remote-$TIMESTAMP.md"

    # Send to Azure Foundry
    for prompt_var in REVIEW_PROMPT SAFETY_PROMPT; do
      if [ "$prompt_var" = "REVIEW_PROMPT" ]; then
        PROMPT_TEXT="$REVIEW_PROMPT"
        OUT_FILE="$REVIEW_FILE"
        LABEL="Code review"
      else
        PROMPT_TEXT="$SAFETY_PROMPT"
        OUT_FILE="$SAFETY_FILE"
        LABEL="Safety audit"
      fi

      echo "--- Sending $LABEL to Azure Foundry ($DEPLOYMENT)..."
      curl -s -X POST \
        "${ENDPOINT}/openai/deployments/${DEPLOYMENT}/chat/completions?api-version=2024-12-01-preview" \
        -H "Content-Type: application/json" \
        -H "api-key: ${KEY}" \
        -d "$(python3 -c "
import json, sys
prompt = sys.stdin.read()
print(json.dumps({
    'messages': [{'role': 'user', 'content': prompt}],
    'max_tokens': 4000,
    'temperature': 0.1
}))
" <<< "$PROMPT_TEXT")" \
        | python3 -c "
import json, sys
try:
    resp = json.load(sys.stdin)
    content = resp['choices'][0]['message']['content']
    print(content)
except KeyError as e:
    print(f'ERROR: {e}')
    print(json.dumps(resp, indent=2))
except Exception as e:
    print(f'ERROR: {e}')
" > "$OUT_FILE" 2>&1

      if [ -s "$OUT_FILE" ] && ! grep -q "^ERROR:" "$OUT_FILE"; then
        echo "--- $LABEL saved: $OUT_FILE"
      else
        echo "--- WARNING: $LABEL failed or empty."
        cat "$OUT_FILE"
      fi
    done

    echo ""
    echo "--- Reports:"
    ls -la "$REPORT_DIR/"*-$TIMESTAMP.md 2>/dev/null
    echo ""
    echo "--- Review:"
    cat "$REVIEW_FILE" 2>/dev/null
    echo ""
    echo "--- Safety:"
    cat "$SAFETY_FILE" 2>/dev/null
    ;;

  mutate)
    cd "$PROJECT_ROOT"
    echo "--- Identifying mutation targets..."

    MUTATE_BASE="main"
    if ! git rev-parse --verify main >/dev/null 2>&1; then
      MUTATE_BASE="master"
    fi
    git diff --name-only "$MUTATE_BASE...HEAD" 2>/dev/null | grep -E '\.(js|mjs|cjs|py)$' > "$TMP_DIR/targets.txt" || true
    if [ ! -s "$TMP_DIR/targets.txt" ]; then
      find "$MUTATION_TARGETS" -maxdepth 3 \( -name '*.js' -o -name '*.py' \) | head -10 > "$TMP_DIR/targets.txt"
    fi

    TARGET_COUNT=$(wc -l < "$TMP_DIR/targets.txt")
    echo "--- $TARGET_COUNT files targeted for semantic mutation."
    cat "$TMP_DIR/targets.txt"
    echo ""

    OUTFILE="$TMP_DIR/mutants-$TIMESTAMP.txt"
    codex exec \
      -o "$OUTFILE" \
      --sandbox read-only \
      "You are a mutation testing expert.

For each file listed below, generate exactly 5 semantic mutations.
These should be realistic logic bugs a developer might introduce:
- Wrong boundary conditions
- Off-by-one errors
- Incorrect null/undefined handling
- Swapped arguments
- Wrong operator precedence

Output each mutation as a unified diff patch that can be applied with 'patch -p1'.
Label each: MUTANT-{N}: {description}

Files:
$(cat "$TMP_DIR/targets.txt")

Read the actual file contents to generate accurate mutations."
    cat "$OUTFILE"
    echo ""
    echo "--- Mutants generated. To validate, apply each patch and run: $TEST_CMD"
    echo "--- Surviving mutants (tests still pass) indicate test suite gaps."
    ;;

  tdd)
    SPEC="$*"
    if [ -z "$SPEC" ]; then
      echo "Usage: bash run.sh tdd \"feature description\""
      exit 1
    fi

    cd "$PROJECT_ROOT"
    echo "--- TDD Step 1: Generating FAILING test for: $SPEC"
    echo ""

    OUTFILE="$TMP_DIR/tdd-test-$TIMESTAMP.txt"
    codex exec \
      -o "$OUTFILE" \
      --sandbox read-only \
      "You are writing a test-first (RED step of TDD).

Write a test that SHOULD FAIL because the feature does not exist yet.
Feature spec: $SPEC

Project constraints: $CONSTRAINTS
Test runner: bun test (use describe/test/expect syntax)
No mocks except global.figma.

Output ONLY the test file content. Include a comment at the top:
// TDD RED: This test should FAIL until the feature is implemented."
    cat "$OUTFILE"
    # Also save for tdd-green
    cp "$OUTFILE" "$TMP_DIR/tdd-test.txt"
    echo ""
    echo "--- Review the test above. If correct, save it and run tests to confirm RED."
    echo "--- Then run: bash run.sh tdd-green to generate minimal implementation."
    ;;

  tdd-green)
    if [ ! -f "$TMP_DIR/tdd-test.txt" ]; then
      echo "No TDD test found. Run 'tdd' mode first."
      exit 1
    fi

    cd "$PROJECT_ROOT"
    echo "--- TDD Step 2: Generating MINIMAL implementation to pass the test"
    echo ""

    OUTFILE="$TMP_DIR/tdd-impl-$TIMESTAMP.txt"
    codex exec \
      -o "$OUTFILE" \
      --sandbox read-only \
      "You are implementing the GREEN step of TDD.

Make this test pass with the MINIMAL code possible.
Do not add extra features, error handling, or optimizations beyond what the test requires.

Project constraints: $CONSTRAINTS

Test:
$(cat "$TMP_DIR/tdd-test.txt")

Output the implementation file content only."
    cat "$OUTFILE"
    ;;

  *)
    echo "Unknown mode: $MODE"
    echo "Usage: bash run.sh <fix|review|review-remote|mutate|tdd|tdd-green> [args...]"
    exit 1
    ;;
esac

echo ""
echo "=== CODEX-CI COMPLETE ==="
echo "--- Run /reflect before claiming done."
