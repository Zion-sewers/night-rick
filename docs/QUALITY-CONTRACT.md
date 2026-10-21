# Why quality-contract.json says what it says

Rationale for each domain in `quality-contract.json`. Not status. For status run
`python tools/gate/gate.py run --project .`

The contract used to carry its measured result inside each domain's `_comment`.
By 2026-07-25 four of the ten were false: `security` and `pipeline` had both been
fixed and the comments still said FAIL, `unit` named three test failures, `review`
named a stale verdict. A file that states its own result is out of date the first
time somebody fixes something and does not think to edit the prose. So the
comments in the JSON are one line each and hold no result, and the durable half
lives here.

Same rule as `docs/CODEBASE-MAP.md`: what is measurable is generated, what is
judgement is written down once.

## Scope of each domain

| domain | what it runs | why that scope |
| --- | --- | --- |
| build | `uv sync --frozen` in `intent-control-plane` | the only subproject with an installable manifest. The flat `tools/` toolkit has no manifest anywhere and its four protected oracles import stdlib only, so there is nothing to install; `types` and `unit` cover it instead. |
| unit | root pytest, `gate.py selftest`, `panel.py selftest`, `intent-control-plane` pytest | every automated-test entrypoint that exists, chained. The two selftests are in the list because a gate whose own oracle is not run is a gate nobody has checked. |
| types | `compileall` repo-wide, then ruff and mypy in `intent-control-plane` | `compileall` is this gate's documented fallback where no lint config exists at root, which is the case for `tools/`. `intent-control-plane` configures ruff and strict mypy, so it gets the real thing. |
| e2e | nothing, `na_reason` | `tools/e2e/flow.py` and `tools/browser/cdp.py` drive OTHER repositories' running UIs from whichever contract is being evaluated. claude-setup serves no app of its own, so there is no route to click. Every `.html` in the tree is a static export. |
| a11y_ux | nothing, `na_reason` | reads the e2e report at a stricter threshold and there is no e2e report, for the reason above. If any part of this repo grows a served UI, both move to a real `cmd`. |
| security | builtin `secret_scan` | value-shaped patterns plus one name-shaped rule, and a named allowlist for vendors' published test vectors. The blind spot is written into `gate.py` beside the patterns rather than left to be discovered. |
| docs | builtin `docs_touched` | `TODO.md` is in the path list because this repo demonstrably describes changes there and in `docs/analysis/`, not in `CHANGELOG.md`. |
| pipeline | builtin `ci_runs_gate` | local-green and CI-green have to be about the same thing. This is the check that they are. |
| review | `panel.py run`, artifact per commit | the panel writes a verdict per commit sha; only pass/approve/lgtm counts. Known oracle behaviour: the artifact is matched by sha, not by tree, so an artifact written against a dirty tree keeps reading as current for that commit after further edits. |
| perf | nothing, `na_reason` | no budget is declared for this repo. Every budget-shaped hit in the tree belongs to another project's historical audit or reports p95 without enforcing a threshold. Nobody has set a number, and saying so is more honest than inventing one. |
| codemap | builtin `dir_map`, runs `tools/map/codemap.py check` | every tracked directory states its purpose somewhere a reader will find it, and `docs/CODEBASE-MAP.md` matches the tree. |
| prior_art | builtin `prior_art`, runs `tools/map/codemap.py prior-art` | every component over 300 lines of Python carries an unexpired record naming what else could do its job. |

## codemap: where a purpose is allowed to live

Resolution order, first hit wins: the directory's own `SKILL.md` `description:`,
`README.md` first prose line, `AGENTS.md`, `CLAUDE.md`, then a row in
`docs/dir-purpose.txt`.

A registry row for a directory that already self-documents is an error, not an
override. Two copies of a purpose string means one of them is the copy that goes
stale, and the check refuses to let that happen quietly.

A `README.md` with no prose or a `SKILL.md` with no `description:` documents
nothing. That is why 181 directories lacking all four files came out as 194
undocumented.

`docs/CODEBASE-MAP.md` excludes itself from its own inventory, carries no
timestamp, no commit sha and no line counts. Any of those would make the file
drift against itself on the next commit and turn every one-line edit into a
documentation failure.

## prior_art: what a record has to contain

The obligation set is derived, not listed: any directory with 300+ lines of
Python owes a record. A hand-maintained list would let new code be born exempt.

`docs/prior-art/<name>.json` needs `reviewed`, `recheck_after`, a non-empty
`alternatives` list with real names, `verdict`, `why`, `evidence`, and a
`recheck` command. It expires like a waiver: past `recheck_after` is a failure,
not a warning.

An empty `alternatives` list fails. "There is no alternative" is the cheapest
claim to type and the most expensive to justify.

`docs/prior-art/out-of-scope.txt` is `prefix | reason`. An unlisted prefix is IN
scope, so new code is audited by default and has to be argued out. A bare prefix
with no reason does not count. `codemap.py` prints every exclusion with its line
count and reason on both the passing and the failing path, because the failing
path is exactly when a reader is deciding whether the audit is honest.

## Waivers: two ways one goes bad, and the gate now checks both

A waiver needs `reason` and `until`. Past `until` it is a failure rather than a
skip, on the same argument the prior-art records use: a permanent exemption is a
disabled check that reads like a live one.

`until` catches only the waiver that ran out. It cannot catch the waiver that
stopped being true, and that is the more common failure, because a waiver is a
claim about a measurement and the measurement keeps moving underneath it.

Measured 2026-08-07. The `skills` waiver ended with its own falsifier written as
prose: expect `DRIFT: 51`, and if the checker prints anything else the waiver is
stale. A gate run printed that sentence as the domain's evidence, reported
WAIVED, and returned `VERDICT: PASS`. Run by hand ninety seconds later the
checker printed `DRIFT: 29` and exited 1. Nothing in the run was false. The
output simply asserted more than the run had measured, which is the class this
whole contract exists to catch, appearing inside the contract's own machinery.

So a waiver may also carry `confirm`, a string the domain's command must still
print. The gate runs that command even though the domain is waived, and fails
the domain if the string is gone. Two details are deliberate:

- The command's exit code is ignored. A waived domain's command is expected to
  fail, since that is usually why it was waived. What is under test is whether
  the waiver still describes the failure.
- A `confirm` on a domain with no `cmd` is a failure, not a pass. Otherwise
  deleting the command is the cheapest way to make the confirmation unrunnable,
  and an unrunnable confirmation would be indistinguishable from one that held.

Write the number into `confirm`, not only into the prose. Prose is read by
whoever is already suspicious; `confirm` is read on every run.

A waiver may also carry `command`, a dedicated falsifier whose exit code
decides whether the waiver's claim still holds. See
[specs/2026-08-30-waiver-falsifier.md](specs/2026-08-30-waiver-falsifier.md)
for the schema and interaction with `confirm`.

## Blast radius

The `blast_radius` domain builds the intra-repo Python import graph and reports,
for each changed `.py` file, how many modules import it transitively. The domain
is informational (always PASS) but flags wide-radius changes so review tooling
can widen the reviewer set. See
[specs/2026-08-30-blast-radius-gate.md](specs/2026-08-30-blast-radius-gate.md).

## Rules enforcement

The `rules_enforcement` domain runs mechanical predicates declared in rule file
frontmatter. Each rule in `dot-claude/rules/` may carry a YAML `enforce:` block
with a `deny_pattern` (grep) or `cmd` (shell command) check. Rules without
frontmatter are prose-only and skipped. See
[specs/2026-08-30-rules-enforcement-gate.md](specs/2026-08-30-rules-enforcement-gate.md).


## Lane enforcement

The `lane_enforcement` domain reads the most recent row from
`state/claims.jsonl` and fails the gate if the claimed lane is not A (the
harness lane). Cross-lane work is the most frequently logged lesson; this
domain makes the violation mechanical rather than retrospective. See
[specs/2026-08-30-lane-enforcement-gate.md](specs/2026-08-30-lane-enforcement-gate.md).


## TODO inbox

The `todo_inbox` domain verifies that TODO.md's generated prompt-inbox block
matches the intent store (`~/.intent/intent.db`). Reports N/A on runners
without the store, FAIL when the block is stale. The tool
(`tools/intent/render_todo.py`) existed with a selftest and a `check`
subcommand; this domain is the enforcement half. See
[specs/2026-08-30-todo-inbox-gate.md](specs/2026-08-30-todo-inbox-gate.md).


## Refute

The `refute` domain runs every claim's own falsifier via
`tools/refute/refute.py run`. Any REFUTED or BROKEN verdict fails the gate.
Claims whose preconditions are not met (e.g. no deployed `~/.claude` on a CI
runner) report cannot-measure and do not count toward the exit code. The tool
and its selftest already existed; this domain is the enforcement half. See
[specs/2026-08-30-refute-gate.md](specs/2026-08-30-refute-gate.md).


## Bus integrity

The `bus_integrity` domain verifies the hash chain of `state/bus.jsonl` via
`tools/bus/bus.py verify`. Every chained row's hash covers its content plus
the previous hash, so any edit, deletion, or reordering is detectable.
Pre-chain rows carry no hash and are reported but not failed. See
[specs/2026-08-30-bus-integrity-gate.md](specs/2026-08-30-bus-integrity-gate.md).


## Skilleval

The `skilleval` domain runs `tools/skilleval/run.py scan`, which grades skill
routing quality: given a prompt from a skill's routing fixture, does the right
skill win? Skills without fixtures are counted as uncovered but do not fail.
A skill whose fixture routes to the wrong skill fails the gate. See
[specs/2026-08-30-skilleval-gate.md](specs/2026-08-30-skilleval-gate.md).


## Prose fit

The `prose_fit` domain runs `tools/audit/prose_fit.py check`, which verifies
that percentile bands have been fitted from the prose-score corpus
(`state/prose-thresholds.json` exists, was fitted from 20+ scores, and is not
stale). `prose_metrics.py` collects density and variance scores but explicitly
defers thresholds (L-2026-07-31-b); this domain ensures the fitting
infrastructure exists so `slop_lint.py` can enforce data-driven bands. See
[specs/2026-08-30-prose-fit-gate.md](specs/2026-08-30-prose-fit-gate.md).


## Skip tracker

The `skip_tracker` domain runs `tools/audit/skip_tracker.py check`, which
parses pytest summary lines for each test suite and compares skip counts
against `state/skip-baseline.json`. A rising skip count fails the gate.
L-2026-07-29-i records the incident this domain exists to prevent: a generator
bug deleted content from 12 shipped files, four tests responded with
`pytest.skip()` instead of failing, and the gate read "89 passed, 4 skipped"
as PASS. The skip count was the signal, and it was invisible. See
[specs/2026-08-30-skip-tracker-gate.md](specs/2026-08-30-skip-tracker-gate.md).


## Branch health

The `branch_health` domain runs `tools/audit/branch_health.py check`, which
finds stale branches (merged into the default branch but not deleted) and
orphaned worktrees (prunable or with missing directories). Both shapes of git
debris have caused gate failures in this repo: the codemap domain excludes
`.claude/worktrees` from compileall because a sibling worktree carried live
conflict markers, and the types domain failed on the same markers. Branches
checked out in an active worktree are excluded from the stale check. See
[specs/2026-08-30-branch-health-gate.md](specs/2026-08-30-branch-health-gate.md).


## Lesson check

The `lesson_check` domain runs `tools/audit/lesson_check.py check`, which
validates the structural integrity of `state/lessons.jsonl`: every row
parses as valid JSON, every row has an `id` field, and IDs use a recognised
format (dated `L-YYYY-MM-DD-x` or legacy `L###`). Schema completeness gaps
(missing `status`, missing timestamp, closed without closure explanation)
are reported as warnings rather than gate failures, because the ledger is
append-only and pre-existing gaps cannot be retroactively fixed. See
[specs/2026-08-30-lesson-check-gate.md](specs/2026-08-30-lesson-check-gate.md).


## Gate health

The `gate_health` domain runs `tools/audit/gate_health.py check`, which
validates the structural integrity of `state/gate-runs.jsonl`: every row
parses as valid JSON, required fields (`ts`, `project`, `commit`, `verdict`,
`domains`) are present, and verdict values are recognised strings. Data
quality issues in existing rows (non-string domain verdicts from a gate.py
builtin handler bug recording exit code 2 instead of `"N/A"`) are warnings
because the ledger is append-only. See
[specs/2026-08-30-gate-health-gate.md](specs/2026-08-30-gate-health-gate.md).


## Known gaps, dated

These were true when measured. Re-measure before relying on them.

- 2026-07-25, `build`: `tools/whatsapp/cdp_driver.py` imports third-party
  `websocket` and `tools/setup_token_pty.py` imports `winpty`. Neither is
  installed on this machine nor declared in any manifest, and both exit 1 with
  ModuleNotFoundError when run directly. `uv sync --frozen` does not cover them.
  This domain does not claim those two scripts build.
- 2026-07-25, `unit`: three tests in `intent-control-plane` fail on Windows
  (`test_codebase_map.py::test_build_codebase_map_walks_and_prunes`,
  `test_local_alpha.py::test_foundry_status_retention_and_hive_sync`,
  `test_local_alpha.py::test_init_creates_local_layout_and_schema`). All three
  open a sqlite connection that is never closed before a
  `tempfile.TemporaryDirectory()` teardown, so Windows raises `PermissionError
  [WinError 32]`. Reproducible, not a flake, deliberately not waived.
- 2026-07-25, `security`: the `assigned secret` rule keys on the variable name,
  so renaming the left side walks out of it, and `\b` does not match before an
  underscore. `SECRET=` fires where `SECRET_NAME=` is silent. Not widened to
  `secret\w*` on purpose: that re-flags every honest `SECRET_NAME` and a rule
  that cries wolf gets waived and then finds nothing at all.
- 2026-10-21, main CI cleanup: `main` was red since 2026-10-13 (strand
  reachability, skilleval routing). Fixing those unmasked latent `gate.py run`
  failures (stale maps, expired prior-art, drifted mutation patterns) plus the
  `night-rick` rename fallout in `render_todo`. Full account in
  [specs/2026-10-21-main-ci-cleanup.md](specs/2026-10-21-main-ci-cleanup.md).
