---
PRD: none
Ticket: #372
Status: active
Date: 2026-10-09
Provenance: backfilled 2026-10-09. The implementation landed on 2026-10-09
(commit 70e535e) before any spec record existed; the ship-gate `spec_linked`
domain flagged the absence (4 source files changed, over the threshold of 3)
and this file closes that record. It describes the mechanism as shipped,
not as proposed.
---

# Spec: Tiered memoized review decisions + trigger-conditioned persona execution

## Goal

Stop re-paying the cost of re-reviewing an unchanged (or barely changed) PR.
Two mechanisms, adapted from AIGUIDE ch.11 ("From Compute to Cost"), applied to
this repo's review pipeline:

1. **Tiered decision cache** (`tools/review/review_cache.py`, class
   `TieredDecisionCache`): memoize review decisions across three lookup tiers —
   exact, normalized, semantic: so a re-run on an unchanged PR replays the
   decision instead of re-invoking the orchestration.
2. **Trigger-conditioned aspect execution**: cheap deterministic checks are the
   "100%" guardrails row and always run; expensive external-actor aspects run
   only when an explicit trigger predicate fires.

## Why this shape

Review cost is dominated by re-reviews: a PR reviewed N times pays N reviews
even when the diff barely moved between them. Memoizing planner decisions with
context guards (adaptation of AIGUIDE ch.11) turns the Nth review into a cache
lookup when the conditioning holds. Expected cost is accounted, not asserted,
via the chapter's Table 11-3 form:

    expected_calls = P(triggered) x calls_when_triggered x (1 - memoized)

## Design (as shipped)

### Conditioning tuple (fail-closed)

Every lookup key carries the full conditioning tuple: registry fingerprint,
file-type context, external-backend mode, prior findings. Any mismatch is a
**miss**, never a replay. A cache miss costs a live run, never a wrong verdict
(established: canonicalization before hashing).

### Tiers

- **exact**: full key match. A hit replays the stored decision.
- **normalized**: key after normalization. Replay counter increments per
  normalized/semantic replay.
- **semantic**: token-multiset similarity in place of the chapter's embedding
  similarity (no embedding dependency by design; adaptation). **Opt-in,
  disabled by default**: a mis-memoized review verdict is a hallucinated
  approval, which is the chapter's own warning about too-low tau.

### Anti-loop guard

`MAX_REPLAYS = 3`: after 3 consecutive non-exact replays of one entry, the
guard forces a live run. Replayed decisions that stop producing new findings
across re-reviews of an evolving PR must not run forever (adaptation of the
ch.11 callout).

### Trigger predicates (`evaluate_triggers`)

Explicit named triggers over diff signals: file-type, diff-size (>=200 lines),
risk (high-correctness / high-security findings), test-gap (code without test).
No single trigger names a backend or a model; the persona/actor mapping stays
in `panel.py` / `actors.json`.

### Cost accounting

`expected_calls_table` is emitted per review so the cost of the review itself is
visible: per-aspect `p_triggered`, `calls_when_triggered`, `memoized` fraction,
`expected_calls`. The 47% call-avoidance figure in ch.11 is the book's
illustrative run, not measured here (unverified).

## Wiring

- `panel.py` `cmd_run` consults the cache before the external-actor leg and
  skips untriggered expensive aspects; measured actuals land in the cost table.
- Persistence: JSON store, `CACHE_MAX_ENTRIES = 500`, eviction on overflow,
  `CACHE_VERSION = 2`.
- Prior art: `docs/prior-art/review-cache.json` (verdict: keep-ours).

## Acceptance

`tests/test_review_cache_tiers.py` pins the tier lookup chain, the full
conditioning tuple (a conditioning mismatch is a miss), the anti-loop guard
(forced live run at `MAX_REPLAYS`), trigger predicates, and the Table 11-3
accounting shape.

## Premortem (failure modes → mitigations)

1. **Stale replay under changed conditioning** → conditioning tuple is part of
   every key; any mismatch misses. (established: fail-closed lookup)
2. **Replay loop on an evolving PR** → `MAX_REPLAYS = 3` forces a live run.
3. **Semantic-tier false hit approves bad code** → semantic tier opt-in and
   default-off; a live run is always one flag away.
4. **Concurrent panel runs clobber each other's JSON store** → last write wins;
   failure mode costs at most a lost cache entry (fail-open to a live run),
   never a wrong verdict. Revisit if concurrent runs become common.
