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
  block into another file without a test file in the diff that references
  the destination module, or when the baseline file is malformed, expired,
  or raised without a recorded reason, expiry, or owner. The report lists
  every location of every duplicate block (first occurrence included) and
  the source and destination line numbers of every extraction hit, and
  every FAIL names the fix and points here.
- `report [--project .]`: repo-wide legacy duplication count with the same
  detector. Informational only, never fails. Legacy debt is tracked
  separately and never blocks.
- `selftest`: plants duplication, extraction, baseline and empty-diff cases
  in throwaway git repos and verifies detection.

## What counts as a duplicate

An exact repeat, not a similarity score. After normalization (blank lines
dropped, full-line comments dropped, import lines and bare docstring fences
dropped, whitespace collapsed), a run of 6 consecutive added lines that
appears at 2 or more locations is a duplicate block. The count is the number
of distinct added lines inside duplicate blocks beyond the first occurrence.

Same-looking code that is not textually identical does NOT fire, and that
narrowing is explicit, not an accident of the detector. The issue's
criterion 3 says same-looking code may encode different concepts and
abstraction needs a shared-meaning justification; a similarity score would
fire exactly on the matches the issue says need human judgement. This tool
collects no shared-meaning justification and checks none: similar-but-not-
identical matches are out of scope by design, and the "abstraction needs a
shared-meaning justification" line on each reported group is a reminder,
not a gate. The tool never suggests an extraction.

## Calibration (measured 2026-11-08 on real merged diffs)

The threshold was set from data, not guessed. A prototype detector ran over
code-heavy merged commits with import lines and docstring fences excluded:

| diff | added lines | N=6 groups / dup lines | N=8 | N=10 |
| --- | --- | --- | --- | --- |
| 019f03c (8 corpus profile siblings) | 2113 | 129 / 1338 | 70 / 840 | 41 / 570 |
| c3e0329 (enrichment_lag_profile) | 377 | 4 / 42 | 1 / 16 | 0 / 0 |
| d36308d (edge_source_temporal_lag) | 305 | 3 / 18 | 0 / 0 | 0 / 0 |
| 854357d (source_enrichment_completeness) | 322 | 2 / 12 | 0 / 0 | 0 / 0 |
| 6f83d76 (simhash_edge_profile) | 296 | 3 / 24 | - | - |
| 17d2c94 (version-source-profile) | 310 | 7 / 42 | - | - |
| b01ee4a (cross_table_outlier_detector) | 344 | 0 / 0 | 0 / 0 | 0 / 0 |
| 7045cee (E-0001..E-0003) | 365 | 0 / 0 | 0 / 0 | 0 / 0 |
| 42c833d (version-fts-coverage) | 297 | 0 / 0 | - | - |
| 0847fc8 (fts-edge-reachability) | 296 | 0 / 0 | - | - |
| 7dc288d (edge text correlation) | 281 | 0 / 0 | - | - |
| 771eb08 (publisher citation profile) | 284 | 0 / 0 | - | - |

N=6 fires on the repo's copy-pasted corpus-profile blocks and stays silent
on clean code diffs: 6 of 12 measured diffs fire, 6 stay silent, and every
firing diff is a corpus-profile sibling. The six clean diffs include
test-heavy and audit-family work, so the threshold is not tuned to one
family of clean code. The first non-corpus PR to trip the gate is still the
real calibration test: a false positive trains authors to reach for the
baseline instead of the extraction, which is why the baseline raise is
bounded (expiry, owner, old-baseline rule) rather than free.

## The ratchet

`state/dup-ratchet.json` holds one number, the baseline, plus a reason, an
expiry date, and an owner. `check` fails when duplicated added lines exceed
it. A raise above 0 needs all three: a non-empty reason, a future expiry
date, and an owner. `check` fails once the expiry passes until the baseline
is lowered or re-justified with a new expiry.

Two properties make the ratchet real rather than a self-serve knob. First,
the baseline is judged as it stood at the base ref: a raise inside the very
diff it would silence does not take effect until that raise merges, so a PR
must land the raise first and the duplication second. Second, the expiry
bounds every raise in time. A malformed baseline file (invalid JSON, a
negative or non-integer baseline) fails cleanly with the parse error,
never with a traceback.

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
in a different file (the code moved to a shared home), `check` fails unless
a test file in the diff has added lines referencing the destination module
(its stem, e.g. `shared` for `tools/a/shared.py`): an import of it, or an
assertion calling it. A test file that never names the extracted module
does not exempt, however it is named, and neither does a test that asserts
nothing about it. A reference is necessary, not sufficient, for
characterization: the gate is a floor, not a proof that the test is good.
Deleting duplicated code without adding a shared home is not an extraction
and is not gated. Moving a block inside the same file is not gated either.

## Exclusions, and why each is stated

- tests/ and test files are excluded from the ratchet FAIL: fixture
  repetition is characterized by the test itself. They are still listed in
  the report, so the exclusion is visible, not silent. A block appearing
  once in production code and once in a test file is reported as a
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

- `python tools/audit/dup_ratchet.py selftest` (14 planted checks)
- `python -m pytest tests/test_dup_ratchet.py -q` (20 tests)
- `python tools/audit/mutate.py --spec dup_ratchet` (8 mutations)
- ruff check on tools/audit/dup_ratchet.py and tests/test_dup_ratchet.py;
  mypy --strict on tools/audit/dup_ratchet.py
- The new domain runs in CI through `gate.py run`; no ship-gate.yml change.

## Follow-ups (not merge blockers)

- A shared home for `default_base`: the helper exists three times now
  (gate.py, panel.py, this tool) with the same candidate order and the same
  HEAD~1 fallback. Tools are run as scripts, so there is no importable home
  for it today; extracting one is itself a cross-module extraction under
  this gate and needs regression tests first.
- Per-path baselines, so a raise for the corpus-profile family does not
  permit the same count in every area.
- Re-measure N=6 false positives after the first month of live gating.
