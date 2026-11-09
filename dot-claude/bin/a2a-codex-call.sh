#!/usr/bin/env bash
# a2a-codex-call.sh — synchronous bridge from Claude → Codex CLI (gpt-5.5).
#
# Wraps `codex exec --full-auto` with timeout, audit logging, and the
# A2A response shape (JSON to stdout matching a2a-foundry-call.py).
#
# Auth: chatgpt subscription (auth_mode=chatgpt). $0 marginal cost.
#
# Usage:
#     a2a-codex-call.sh "<prompt>" [--timeout 180] [--effort medium] [--model gpt-5.5]
#     a2a-codex-call.sh "review src/handler.py for SQL injection" --effort high
#
# Output: JSON to stdout: {state, response_text, duration_ms, error?}
# Audit:  ~/.claude/cache/a2a/audit.jsonl
# Exit:   0 = completed, 1 = failed/timeout, 2 = config error

set -euo pipefail

PROMPT=""
TIMEOUT=180
EFFORT="medium"
MODEL=""
SANDBOX=""
FROM_ADDR="claude:home"
TO_ADDR="codex:home"
CONV_ID=""

while [ $# -gt 0 ]; do
    case "$1" in
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --effort) EFFORT="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --sandbox) SANDBOX="$2"; shift 2 ;;
        --from-addr) FROM_ADDR="$2"; shift 2 ;;
        --conversation-id) CONV_ID="$2"; shift 2 ;;
        --help) echo "usage: a2a-codex-call.sh \"<prompt>\" [--timeout N] [--effort low|medium|high|xhigh] [--model gpt-5.5]"; exit 0 ;;
        *)
            if [ -z "$PROMPT" ]; then PROMPT="$1"; shift
            else echo "unknown arg: $1" >&2; exit 2
            fi
            ;;
    esac
done

if [ -z "$PROMPT" ]; then
    echo '{"state":"failed","error":"empty prompt"}'
    exit 2
fi

if ! command -v codex >/dev/null 2>&1; then
    echo '{"state":"failed","error":"codex CLI not on PATH"}'
    exit 2
fi

# Audit prep
PROMPT_HASH=$(echo -n "$PROMPT" | sha1sum | cut -c1-12)
TMPOUT=$(mktemp)
trap "rm -f $TMPOUT" EXIT

# Build codex args. Default --full-auto (workspace-write) keeps existing callers unchanged;
# pass --sandbox read-only for review/analysis calls that must not edit the working tree.
if [ -n "$SANDBOX" ]; then
    CODEX_ARGS=(exec -s "$SANDBOX" --skip-git-repo-check -C "$PWD" --output-last-message "$TMPOUT")
else
    CODEX_ARGS=(exec --full-auto --skip-git-repo-check -C "$PWD" --output-last-message "$TMPOUT")
fi
[ -n "$MODEL" ] && CODEX_ARGS+=(-m "$MODEL")
[ -n "$EFFORT" ] && CODEX_ARGS+=(-c "model_reasoning_effort=$EFFORT")

# Time the call (millisecond precision)
T_START=$(date +%s%3N 2>/dev/null || date +%s)
TMPERR=$(mktemp)
trap "rm -f $TMPOUT $TMPERR" EXIT

# Run codex with timeout. Capture stderr so we can surface real errors
# (rate limits, auth failures, sandbox issues) instead of swallowing them.
if timeout --signal=TERM "${TIMEOUT}s" codex "${CODEX_ARGS[@]}" - <<<"$PROMPT" >/dev/null 2>"$TMPERR"; then
    STATE="completed"
else
    EXIT_CODE=$?
    STATE="failed"
    [ "$EXIT_CODE" -eq 124 ] && STATE="timeout"
fi

T_END=$(date +%s%3N 2>/dev/null || date +%s)
DURATION_MS=$((T_END - T_START))

# Surface common error patterns from stderr. Only RE-CLASSIFY a generic failure
# (exit != 0 and != 124). A timeout MUST stay "timeout": codex echoes the prompt to
# stderr, so a diff containing "auth"/"401" (e.g. auth.py, res.status===401) would
# otherwise be misread as an auth failure. Patterns are scoped to codex's own error
# phrasings, not bare "auth"/"401" substrings that appear in reviewed code.
ERR_MSG=""
if [ "$STATE" != "completed" ] && [ -s "$TMPERR" ]; then
    if [ "$STATE" = "failed" ] && grep -qiE "usage limit|rate limit|429 too many" "$TMPERR"; then
        ERR_MSG=$(grep -iE "usage limit|rate limit|429 too many" "$TMPERR" | head -1)
        STATE="rate_limited"
    elif [ "$STATE" = "failed" ] && grep -qiE "unauthorized|not logged in|invalid api key|authentication (failed|error)|401 unauthorized" "$TMPERR"; then
        ERR_MSG=$(grep -iE "unauthorized|not logged in|invalid api key|authentication (failed|error)|401 unauthorized" "$TMPERR" | head -1)
        STATE="auth_failed"
    else
        ERR_MSG=$(tail -3 "$TMPERR" | tr '\n' ' ' | head -c 300)
    fi
fi

# Audit log (state may now be rate_limited or auth_failed for clearer diagnostics).
# The commit is passed explicitly: the oracle matches records to the commit the
# dispatch was made for, and the shell knows the checkout better than the
# audit writer's cwd fallback does. Fail-soft to "unknown", never block the call.
# The deployed writer must carry the commit seam (AUDIT_WRITER_SEAM): an older
# writer would read "--commit" as the conversation id, so check first and log
# without it, with a warning, rather than corrupt the record.
COMMIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo unknown)
AUDIT_WRITER="$HOME/.claude/bin/a2a-audit.py"
if grep -q "AUDIT_WRITER_SEAM" "$AUDIT_WRITER" 2>/dev/null; then
    python3 "$AUDIT_WRITER" log \
        "$FROM_ADDR" "$TO_ADDR" "$PROMPT_HASH" "$DURATION_MS" "$STATE" "$CONV_ID" \
        --commit "$COMMIT_SHA" \
        >/dev/null 2>&1 || echo "a2a-audit: logging failed, no record written for this call" >&2
else
    echo "a2a-audit: deployed writer predates the commit seam, record will carry no commit; deploy dot-claude/bin/a2a-audit.py to ~/.claude/bin" >&2
    python3 "$AUDIT_WRITER" log \
        "$FROM_ADDR" "$TO_ADDR" "$PROMPT_HASH" "$DURATION_MS" "$STATE" "$CONV_ID" \
        >/dev/null 2>&1 || echo "a2a-audit: logging failed, no record written for this call" >&2
fi

# Persist the stderr tail to ~/.claude/cache/a2a/codex-errors.log for postmortem
if [ -n "$ERR_MSG" ]; then
    mkdir -p "$HOME/.claude/cache/a2a"
    echo "[$(date -u +%FT%TZ)] codex-call state=$STATE duration=${DURATION_MS}ms err=$ERR_MSG" \
        >> "$HOME/.claude/cache/a2a/codex-errors.log"
fi

# Emit JSON response (now includes error message when not completed)
RESP_TEXT=""
[ "$STATE" = "completed" ] && RESP_TEXT=$(cat "$TMPOUT" 2>/dev/null || echo "")
python3 -c "
import json
out = {
    'state': '$STATE',
    'agent': 'codex',
    'from': '$FROM_ADDR',
    'to': '$TO_ADDR',
    'response_text': '''${RESP_TEXT//\'/\\\'}''',
    'duration_ms': $DURATION_MS,
    'conversation_id': '$CONV_ID' or None,
    'effort': '$EFFORT',
    'model': '$MODEL' or 'gpt-5.5',
}
err = '''${ERR_MSG//\'/\\\'}'''.strip()
if err:
    out['error'] = err
print(json.dumps(out, indent=2, ensure_ascii=False))
"

[ "$STATE" = "completed" ] && exit 0 || exit 1
