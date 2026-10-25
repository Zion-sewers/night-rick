# MECE

Mutually Exclusive, Collectively Exhaustive.

## Purpose

A breakdown that is not MECE lies with a straight face. Overlapping segments
double-count. Missing segments hide the rest. If the parts do not sum to the
whole, the breakdown is broken, not "approximately right".

## Trigger

Any breakdown, segmentation, funnel, or set of percentages that is about to
be reported or compared.

## Procedure

1. **Exclusivity check.** Can one row land in two segments? Suspects:
   overlapping CASE conditions, multiple tags per row, many-to-many joins,
   "other" buckets defined by exclusion that still overlap.
2. **Exhaustiveness check.** Is there an explicit unknown/other bucket? Does
   every row land somewhere? Count rows with no segment assigned.
3. **Reconcile.** Sum of segment counts vs total count. Sum of segment
   percentages vs 100. Any gap is a leak or an overlap: find it, do not
   round it away.
4. **Fix at the definition.** Overlap means the segment definitions are
   wrong. Redefine them so each row has exactly one home, then re-run.

## Output Contract

- Segment table with counts and percentages.
- Sum check: parts vs whole, in counts and in percentages, with the gap
  stated exactly (0 or explained).
- Verdict: CONFIRMED / REFUTED / ABSTAINED. A nonzero unexplained gap is
  REFUTED.

## Operating Rules

- Rounding explains gaps of 0.1, never gaps of 5.
- "Other" is a real segment with a real definition, not a rug to sweep rows
  under.
- Pairs with doesnt-add-up: this skill covers step 6 of that skill's
  checklist in depth.
