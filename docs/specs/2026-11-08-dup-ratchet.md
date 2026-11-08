# Changed-Line Duplication Reporting with New-Code Ratchet

**Date:** 2026-11-08
**Status:** done
**Tool:** tools/audit/dup_ratchet.py
**Issue:** night-rick#376
**Source:** Perplexity corpus, Code Reuse / Deduplication / DRY AHA WET Balance (§3f)

## Problem

Duplication was reported, when it was reported at all, as a repo-wide legacy
debt dump. That shape punishes the author for debt they did not create and
teaches everyone to ignore the report. Three things were missing at once:
reporting scoped to the lines a change actually adds, a ratchet that stops
new duplication from growing, and a gate that requires regression tests
before duplicated code is extracted into a shared home.

## Solution

A new tool `tools/audit/dup_ratchet.py` with three subcommands, wired as a
required `dup_ratchet` domain in quality-contract.json (no workflow change:
the ship-gate `gate` job runs it through `gate.py run`, the same way the
coverage_map domain was added in 2026-08-19):

- `check [--project .]`: diff base...HEAD plus the working-tree diff, added
  lines only. FAIL when duplicated added lines exceed the baseline in
  `state/dup-ratchet.json` (0 at ship), or when the diff extracts a repeated
  block into another file without a test in the diff that calls the
  destination module, or when the baseline file is malformed, deleted,
  or raised without a recorded reason, a future expiry, or an owner, or
  when the diff cannot be obtained at all (not a git repository,
  unresolvable base ref, git failure: "cannot measure", exit 1). The
  report lists every location of every duplicate block (first occurrence
  included) and the source and destination line numbers of every
  extraction hit, and every FAIL names the fix and points here. One
  exception to "cannot measure": when the base ref resolves to HEAD
  (running `check` on main, which ship-gate does on main pushes), the
  diff is empty and the check passes vacuously; diff-scoped checks in
  this repo share that convention.
- `report [--project .]`: repo-wide legacy duplication count with the same
  detector. Informational only, never fails. Legacy debt is tracked
  separately and never blocks.
- `selftest`: plants duplication, extraction, baseline and empty-diff cases
  in throwaway git repos and verifies detection.

## What counts as a duplicate

An exact repeat, not a similarity score. After normalization (blank lines
dropped, full-line comments dropped, import lines and bare docstring fences
dropped, whitespace collapsed), a run of 6 consecutive added lines that
appears at 2 or more places is a duplicate block. A place is a maximal run
of identical lines, not a window start: twelve identical lines in one file
are one place, not seven overlapping windows, so a single file holding
twelve identical lines counts 0 duplicated lines. Consecutive means
consecutive in the file: the 6 lines must have consecutive line numbers,
so lines added in two separate hunks, or split by a dropped blank or
comment line, never form a block that never existed. The count is the
number of distinct added lines inside duplicate blocks beyond the first
occurrence, net of moves: a repeat whose added occurrences are fully
covered by removed occurrences does not count, because moving legacy debt
is not creating it, and a pure move of a function containing an internal
repeat passes both gates. The threshold (6) was calibrated against real
merged diffs (see the table below): N=6 fires on the repo's copy-pasted
corpus-profile blocks and stays silent on clean code diffs.

Same-looking code that is not textually identical does NOT fire, and that
narrowing is explicit, not an accident of the detector. The issue's
criterion 3 says same-looking code may encode different concepts and
abstraction needs a shared-meaning justification; a similarity score would
fire exactly on the matches the issue says need human judgement.
Similar-but-not-identical matches are out of scope by design. For
byte-identical blocks the tool does not decide whether the copies share
meaning either: before extracting, the author records why the copies
share meaning (same concept, same future changes) in the PR description,
where a human reviewer sees it. No tool in this repo reads a PR
description (panel.py takes only a project, a base, and an output path,
and gate.py has no PR-body input), so the printed reminder is the whole
mechanism: the gate enforces the choice, not the judgement. Extract
with an asserting regression test, or keep the duplication and raise the
baseline with a recorded reason. The "abstraction needs a shared-meaning
justification" line on each reported group is the reminder of that
requirement, not a gate. The tool never suggests an extraction.

## Calibration (measured 2026-11-08 on real merged diffs)

The threshold was set from data, not guessed. The shipped detector ran over
code-heavy merged commits with import lines and docstring fences excluded:

| diff | added lines | N=6 blocks / dup lines | N=8 | N=10 |
| --- | --- | --- | --- | --- |
| 019f03c (8 corpus profile siblings) | 2113 | 39 / 336 | 11 / 124 | 6 / 76 |
| c3e0329 (enrichment_lag_profile) | 377 | 1 / 6 | 0 / 0 | 0 / 0 |
| d36308d (edge_source_temporal_lag) | 305 | 0 / 0 | 0 / 0 | 0 / 0 |
| 854357d (source_enrichment_completeness) | 322 | 1 / 7 | 0 / 0 | 0 / 0 |
| 6f83d76 (simhash_edge_profile) | 296 | 2 / 13 | 0 / 0 | 0 / 0 |
| 17d2c94 (version-source-profile) | 310 | 3 / 22 | 1 / 8 | 0 / 0 |
| b01ee4a (cross_table_outlier_detector) | 344 | 0 / 0 | 0 / 0 | 0 / 0 |
| 7045cee (E-0001..E-0003) | 365 | 0 / 0 | 0 / 0 | 0 / 0 |
| 42c833d (version-fts-coverage) | 297 | 0 / 0 | 0 / 0 | 0 / 0 |
| 0847fc8 (fts-edge-reachability) | 296 | 0 / 0 | 0 / 0 | 0 / 0 |
| 7dc288d (edge text correlation) | 281 | 0 / 0 | 0 / 0 | 0 / 0 |
| 771eb08 (publisher citation profile) | 284 | 0 / 0 | 0 / 0 | 0 / 0 |

Counting rule: blocks are maximal merged repeats; dup lines are distinct
added lines beyond the first occurrence, exactly as counted by
`tools/audit/dup_ratchet.py` (the `find_blocks` marked set). An earlier
version of this table used prototype numbers that counted each overlapping
window separately; those inflated the magnitudes and were replaced with the
shipped detector's numbers in the third review round. The "added lines"
column counts every added normalized line including test files; the N
columns exclude test files (for example 7045cee: 365 added lines, 238 of
them non-test).

N=6 fires on the repo's copy-pasted corpus-profile blocks and stays silent
on clean code diffs: 5 of 12 measured diffs fire, 7 stay silent, and every
firing diff is a corpus-profile sibling. The six clean diffs are five
corpus-profile tools plus one anatomy E-rows diff (7045cee, with one test
file); none of the twelve diffs touches `tools/audit`, so no audit-family
diff is in the set, and the sample is 11 of 12 corpus-profile diffs. The
seventh silent diff is d36308d, a corpus-profile sibling whose only repeat
is a SQL fragment whose six normalized lines are split by a closing
docstring fence: the strict contiguity rule trades that block for the
elimination of phantom windows, and the numbers above are the price of
that trade (the pre-contiguity detector counted it at 2 / 13). N=8
would miss c3e0329, 854357d, and 6f83d76 entirely, and N=10 would miss all
but the largest diff, so N=6 is kept.

N=6 also fires on ordinary boilerplate: two CLI entry points sharing a
6-line argument-parsing idiom fail the gate, and the block grows past the
idiom because the identical `def main():` and `return run(args)` lines
join it. That is the gate working as designed, not a false positive: the
block really is duplicated new code. When it fires on boilerplate, the
author's options in order are: extract the shared idiom into a helper
(the extraction gate then requires an asserting test that calls the
extracted symbol); restructure so
the repeated lines differ; or record a bounded baseline raise with reason,
expiry, and owner. Prefer extraction: a raise is global until its expiry,
so it permits the same count in every area. The first non-corpus PR to
trip the gate is still the real calibration test, and its remedy is now
written down here instead of discovered live.

## The ratchet

`state/dup-ratchet.json` holds one number, the baseline, plus a reason, an
expiry date, and an owner. `check` fails when duplicated added lines exceed
it. A raise above 0 needs all three: a non-empty reason, a future expiry
date, and an owner. A raise expiring today fails validation: the expiry
must be strictly future. Owner is attribution, not verification: the tool
checks only that the field is non-empty, and review is the backstop for a
lazy expiry or owner. The same holds for the expiry date itself, which is
self-asserted; nothing in the tool can tell a genuine 90-day exception
from a 2099 placeholder.

Two judgements are split, and the split is the whole mechanism. The count
is judged against the baseline as it stood at the base ref: a raise inside
the very diff it would silence does not take effect until that raise
merges, so a PR must land the raise first and the duplication second. The
metadata (reason, expiry, owner) is judged on the NEW record only. A diff
that lowers an expired baseline to 0, or re-justifies it with a future
expiry, passes: it is not failed by the record it replaces.

Expiry LAPSES the raise instead of locking the repo. Once the expiry
passes, the effective baseline is 0: a clean PR passes, and a PR with
duplication fails on the count against 0 with a note that the raise
lapsed. The record on main stays as written; the next PR that touches the
file must lower it or re-justify it, and every check prints the lapsed
note while it sits there, so the stale record is visible, not silent. The
alternative was a tripwire: fail every PR until someone fixes the file.
That was rejected, because a clean PR adds no new duplication, and the
issue's first mechanism is that legacy debt never blocks. Expiry bounds
the raise's value in time; it does not punish authors who were not the
ones who raised it.

Deleting the baseline file is not an escape: a diff that deletes
`state/dup-ratchet.json` fails closed with a message naming the lowering
path. A malformed baseline file (invalid JSON, a negative or non-integer
baseline) fails cleanly with the parse error, never with a traceback. A
malformed record on main fails every PR until it is fixed: that is a
fail-closed choice, not legacy duplication debt blocking work, and the
repair path is a PR that fixes the file (the new record loads, and the
count is judged against the old baseline of 0).

The global raise is the honest consequence to state plainly: raising the
baseline permits that many duplicated lines in every future PR in every
area until the expiry date, not just in the area that justified the raise.
Per-path baselines would scope the exception; they are not implemented.
The mitigation is the bound, not the scope: expiry, owner, and the
old-baseline rule, with the raise visible in the diff to panel review.

Lowering is the documented happy path. When a PR's count drops below the
baseline, the author may lower the baseline to the new count in the same
PR with reason "lowered after dedup". A lowering PR passes because the
ratchet judges against the old, higher baseline. There is no command that
raises or lowers the baseline: the author edits the file, and review sees
it.

## The extraction gate

Cross-module extraction requires regression tests first. When the diff
removes a repeated 6-line block AND the same block appears as added lines
in a different file, or survives in the base tree in a file the diff
rewires its call sites to (the code moved to a shared home), `check` fails unless
an added test line inside an asserting `test_*` function calls one of the
destination's defined symbols: a top-level function, class, or constant of
the destination file, called directly (`dedup(...)`) or module-qualified
(`helpers.dedup(...)`). An import alone does NOT exempt: a test that
imports and never calls still characterizes nothing. A bare call with no
assertion does not exempt, a call that can never execute does not exempt
(inside `if False:`, inside a helper no test calls), and a call outside a
test function does not exempt. The symbol must appear as a whole
identifier token: `shared_cache`, `ratio` against a stem of `io`, and a
bare assignment such as `shared = 1` do not exempt. String literals and
comments never count: `assert "shared" in "shared_name"` is a mention,
not a test. A call is necessary, not sufficient, for characterization:
the gate is a floor, not a proof that the test is good. A test that
already exists on main does not count: the calling test must be in the
diff. Deleting duplicated code without adding a shared home is not an
extraction and is not gated. Moving a block inside the same file is not
gated either.

The gate matches the extracted symbol, not the file stem: a direct-import
test (`from helpers import dedup`, then `assert dedup(...) == ...`)
exempts, because the symbol is what the test characterizes. When the
destination defines no parseable symbols, the gate falls back to the stem
rule (a call to the module stem). Known limits: the gate cannot resolve
imports, so a stem collision (a test calling the stdlib `io.open(` for a
destination stemmed `io`) can exempt; path-aware matching is not
implemented. Non-Python test files keep the call-only floor: the
test-function rule is implemented on the Python AST. A test that calls
the symbol only inside a helper it defines, and never calls that helper,
does not exempt either: the gate does not trace helper calls. A call
after floor division (`x = a // shared.VALUE`) can also miss the
reference check, because the line sanitizer splits on `//`; that
direction fails closed.

The extraction gate covers the shapes the detector can see. A move that
generalizes two or more lines spread through the block breaks every
6-line window, so no byte-identical repeat survives and the gate does not
fire: that extraction passes with no regression test. A one-line
generalization is still caught. The boundary is the exact-match scope
itself: no byte-identical 6-line repeats beyond the baseline, and no
byte-identical extraction without an asserting test. A generalized
extraction is still reviewable: panel review
sees the move, and the shared-meaning justification above applies to it
the same as to any extraction.

"Repeated" has two shapes. The clean-room shape is a block removed from
two or more places at once, where a place is a maximal run of identical
lines, not a window start: twelve identical lines moved as a unit are one
place, not two sources. The clean-room shape fires only when the
destination holds strictly fewer occurrences of the block than were
removed: a destination that still holds as many copies as were removed
consolidated nothing, so the move is not an extraction. The
partial-migration shape is a block
removed from one place while the block was already duplicated before the
diff: the gate counts the block's occurrences in the base tree (via
`git archive`) and fires when the block occurred twice or more there.
That count covers production code files only: a copy surviving only in a
test file does not count, because the test itself characterizes it, the
same reason test files are excluded from the ratchet FAIL. A
unique block that merely moves (one base-tree occurrence) is not an
extraction. The third shape is the shared home that already exists on
main. A two-PR split defeats the two shapes above: the first PR adds the
helper with no removal, the second rewires the call sites to it with no
added copy of the block, so the added-lines leg sees no destination. The
gate closes that split: a removed window that survives in the base tree
is a destination when the diff's added lines in the removal sources call
that file's symbols (the rewiring). A base location in a removal source
counts only under occurrence accounting: the file must hold more base
occurrences of the window than were removed from it, and only the
surviving occurrence is reported, never a removed copy. The
destination's line numbers are base-tree lines, because the location is
read from the base tree. A pure deletion adds no call, so it does not
fire, and a surviving copy in a file the diff never calls is not a home.
The same exemption applies: an added test in an asserting test
function calling the destination's symbols exempts.
The destination may itself be one of the files the block was
removed from (consolidation into an existing holder file); it is skipped
only when it is the SOLE file the block was removed from.

Test files are excluded from the extraction gate entirely: moving a
fixture block between test files is fixture deduplication, the same
reason test files are excluded from the ratchet FAIL, and the gate stays
silent. Only code files supply test lines, so a document named like a
test (`test_notes.md`) cannot exempt an extraction with a line of prose.

Known limit: a move rewritten past git's rename-detection threshold can
trip both gates (the moved lines appear as removed and added), because
the detector is diff-based and has no rename awareness. The common pure
move, and a move with a one-line touch, do not trip it, including a
moved block that contains an internal repeat: the ratchet counts
net-new duplication, so a repeat fully covered by removed occurrences
does not count, and the extraction gate stays silent when the
destination consolidated nothing.

## Exclusions, and why each is stated

- tests/ and test files are excluded from the ratchet FAIL: fixture
  repetition is characterized by the test itself. A test file is any file
  under `tests/` or `__tests__/`, or named `test_*`, `spec_*`, `*_test.*`,
  `*.test.*`, `*.spec.*`, `*_spec.*`, or literally `test.py`. They are still
  listed in the report, so the exclusion is visible, not silent. A block
  appearing once in production code and once in a test file is reported as a
  cross-copy, also informationally.
- dot-codex/skills/.system/, research-papers/, work-docs/audits/ are
  out of scope, mirroring the codemap out-of-scope list: installed
  payload, corpus evidence, and dated audit scripts.
- Only code files are scanned, with the same extension list as gate.py's
  docs_touched builtin.

## Why not adopt an existing detector

jscpd v5 (kucherenko/jscpd, verified 2026-11-08 via its docs on PyPI 5.4.1
and crates.io) is the serious alternative: token-based exact detection,
--min-lines/--min-tokens, and --baseline / --baseline-from-ref
origin/main with --fail-on-new-clones, which is the ratchet in another
shape. PMD CPD (verified via docs.pmd-code.org) covers token-based
detection with --minimum-tokens and --fail-on-violation (exit 4), but has
no baseline or ratchet and no diff scoping: it scans the whole repo, so
legacy debt would either block or need gating disabled entirely. Neither
has an extraction-without-tests gate, and neither reports on added lines
first. Both are binary runtimes (jscpd is Rust via npm/PyPI/crates, PMD
CPD is Java) in a tools/ tree that is stdlib-only Python by design, and
both would add a registry fetch to ship-gate on the self-hosted runner
while the supply-chain job is removed. The custom tool is kept for those
reasons. This reasoning lives here rather than as a new prior-art record
because codemap measures directories, and tools/audit is already covered
by the unexpired docs/prior-art/tools-audit.json record (recheck 2027-01-25).
Recheck at that date: whether jscpd ships a diff-added-lines mode or an
extraction gate, and whether the runner has a pinned-binary install path.

## Verification

- `python tools/audit/dup_ratchet.py selftest` (58 planted checks)
- `python -m pytest tests/test_dup_ratchet.py -q` (93 tests)
- `python tools/audit/mutate.py --spec dup_ratchet` (30 mutations)
- ruff check on tools/audit/dup_ratchet.py and tests/test_dup_ratchet.py;
  mypy --strict on tools/audit/dup_ratchet.py
- The new domain runs in CI through `gate.py run`; no ship-gate.yml change.

A PASS means no NEW byte-identical duplication beyond the baseline, and
no byte-identical extraction without an asserting test. It does not mean
no duplication of any shape: a copied block with one renamed
identifier sails through by design (see the criterion-3 narrowing above),
a repeat within the baseline passes by design, and the verdict line says
the ratchet outcome, not the absence of repeats.

Known measurement limits, all dirty-tree or local-only (CI runs on a
clean checkout, where the second diff is empty): untracked new files are
invisible to `check` (`git diff HEAD` does not show them), so a local
pre-commit run misses a brand-new duplicated file; the two diffs
(`base...HEAD` and `HEAD` working tree) merge by (text, line number), so
a line added in the committed diff and then edited in the working tree
is counted twice in the "added code lines" figure (the verdict rests on
`duplicated_lines`, not that figure, and no phantom duplicate was
observed); the base-tree read (`git archive`, ~66 MB / ~3 s on this
repo, held whole in memory) runs whenever any window is removed (the
base-home leg needs the surviving locations even when nothing is re-added);
destination symbols for base-home files are read with one `git show` per
distinct base-location file not already known from disk, so a
widely-repeated window costs one subprocess call per file holding it,
bounded by the candidate set; a base-tree code file that cannot be decoded as UTF-8
fails the check closed with "cannot measure" instead of silently
skipping the file.

## Follow-ups (not merge blockers)

- A shared home for `default_base`: the helper exists three times now
  (gate.py, panel.py, this tool) with the same candidate order and the same
  HEAD~1 fallback. Tools are run as scripts, so there is no importable home
  for it today; extracting one is itself a cross-module extraction under
  this gate and needs regression tests first. The fail-closed half is done
  in this tool: `git` return codes are checked, a missing repo or an
  unresolvable base ref fails with "cannot measure", and
  `load_baseline_at_ref` checks the ref resolves before reading it. The
  base==HEAD vacuous PASS stays by repo convention (ship-gate runs on
  main pushes, where base==HEAD): when the shared home is built, it
  should keep that convention for diff-scoped checks and fail closed
  only on a diff that cannot be obtained at all.
- Per-path baselines, so a raise for the corpus-profile family does not
  permit the same count in every area.
- Re-measure N=6 false positives after the first month of live gating.
