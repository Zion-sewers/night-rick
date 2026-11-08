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
  block into another file without a test file in the diff, or when the
  baseline was raised without a recorded reason.
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

Same-looking code that is not textually identical does NOT fire. The issue
says same-looking code may encode different concepts and abstraction needs a
shared-meaning justification; a similarity score would fire exactly on the
matches the issue says need human judgement. The tool never suggests an
extraction. Every reported group carries the line "abstraction requires a
shared-meaning justification".

## Calibration (measured 2026-11-08 on real merged diffs)

The threshold was set from data, not guessed. A prototype detector ran over
code-heavy merged commits with import lines and docstring fences excluded:

| diff | added lines | N=6 groups / dup lines | N=8 | N=10 |
| --- | --- | --- | --- | --- |
| 019f03c (8 corpus profile siblings) | 2113 | 129 / 1338 | 70 / 840 | 41 / 570 |
| c3e0329 (enrichment_lag_profile) | 377 | 4 / 42 | 1 / 16 | 0 / 0 |
| d36308d (edge_source_temporal_lag) | 305 | 3 / 18 | 0 / 0 | 0 / 0 |
| 854357d (source_enrichment_completeness) | 322 | 2 / 12 | 0 / 0 | 0 / 0 |
| b01ee4a (cross_table_outlier_detector) | 344 | 0 / 0 | 0 / 0 | 0 / 0 |
| 7045cee (E-0001..E-0003) | 365 | 0 / 0 | 0 / 0 | 0 / 0 |

N=6 fires on the repo's copy-pasted corpus-profile blocks and stays silent
on clean code diffs. The firing diffs are all tools/corpus profile scripts:
per-subcommand query blocks repeated inside one file, and sibling files
sharing the same structure. That repetition is real by the issue's
definition, so N=6 is kept and the escape hatch is a recorded baseline
raise, not a carve-out: the first corpus-profile PR after this gate lands
either extracts the shared query helper or raises the baseline with a
reason in state/dup-ratchet.json, visible in the diff to panel review.

## The ratchet

`state/dup-ratchet.json` holds one number, the baseline, plus a reason and
an update date. `check` fails when duplicated added lines exceed it. The
baseline may only be raised by a reviewed commit to that file carrying a
non-empty reason; a raised baseline without a reason fails the check. The
file is in the diff, so the exception is visible instead of silent. There is
no command that raises the baseline: the author edits the file, and review
sees it.

## The extraction gate

Cross-module extraction requires regression tests first. When the diff
removes a repeated 6-line block AND the same block appears as added lines
in a different file (the code moved to a shared home) with no test file in
the diff, `check` fails. A test file in the diff satisfies it. Deleting
duplicated code without adding a shared home is not an extraction and is
not gated. Moving a block inside the same file is not gated either.

## Exclusions, and why each is stated

- tests/ and test files are excluded from the ratchet FAIL: fixture
  repetition is characterized by the test itself. They are still listed in
  the report, so the exclusion is visible, not silent.
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

- `python tools/audit/dup_ratchet.py selftest` (11 planted cases)
- `python -m pytest tests/test_dup_ratchet.py -q` (17 tests)
- `python tools/audit/mutate.py --spec dup_ratchet` (7 mutations)
- ruff check on tools/audit/dup_ratchet.py and tests/test_dup_ratchet.py;
  mypy --strict on tools/audit/dup_ratchet.py
- The new domain runs in CI through `gate.py run`; no ship-gate.yml change.
