---
name: triage-tests
description: "/triage-tests"
---

# /triage-tests

Pre-filter test output (never ingest full logs), extract failure index (name, error, root cause), diagnose one at a time.

## When to Use

- Tests are failing and you need to fix them
- Want condensed failure summary (not raw test output)
- Need to prioritize which test to fix first

## When NOT to Use

- Want to see full test output (use `log-filter` CLI tool manually instead)
- Tests are passing (no need to triage)
- Running a full test suite for confirmation (just run `bun test` or `uv run pytest`)

## Args

- `[project]` — optional: name of the subproject to target (auto-detect from cwd)
- `[test-name]` — optional: specific test to investigate

## Steps

1. **Detect project** from cwd or arg. Determine runner from the project's own
   test config (e.g. a `package.json` script or a documented pytest path):
   - JS/TS project with a dedicated fast-path script (e.g. `test:p0`): `bun run test:p0`
   - JS/TS project with a standard test script: `bun test`
   - Python project: `uv run pytest tests/unit/ -x --tb=short`

2. **Run tests with minimal output** (short traceback, no captures):
```bash
# Python
uv run pytest tests/unit/ -x --tb=short -q 2>&1 | tail -50

# JS/TS
bun test --reporter=default 2>&1 | tail -50
```

3. **If failures found**, extract per failure:
   - Test name + file:line
   - Error class / assertion message
   - Last 3 relevant stack lines

4. **Build failure index** — compact summary:
```
FAILURES (3/47 tests):
1. test_normalize_meta_post [test_apify.py:42] — KeyError: 'engagement_rate'
2. test_quality_gate_blocks [test_gates.py:118] — AssertionError: gate passed but should block
3. ...
```

5. **Diagnose** root causes from the failure index. Read only the specific source files referenced.

6. **Propose fixes** — minimal, targeted. One fix per failure.

## Rules

- Never read full log files. Filter first, read snippets.
- Never send >50 lines of test output to context.
- If >10 failures, group by error type first, then triage top group.
- For flaky tests: check if `flaky-tests.md` exists in project, reference history.
- After fixing, re-run only the specific failing test to verify.
