---
name: fermi
description: Order-of-magnitude plausibility. Convert a percentage to an absolute and check it against known totals.
license: MIT
---

# Fermi

Fermi estimation: order-of-magnitude plausibility.

## Purpose

A number that implies an impossible absolute is dead, no matter how clean
the query looks. Before trusting a percentage, convert it to an absolute and
check it against known totals. One significant figure is enough to kill a
fantasy.

## Trigger

Any absolute or percentage that would change a decision, and any number
that "feels" off, even before a reason is articulated.

## Procedure

1. **Convert to an absolute.** Percentage times known total. If the total is
   not known, estimate it from an independent anchor (headcount, case
   volume, days in window).
2. **Round to one significant figure.** Precision here is a trap. The
   question is 10, 100, or 1000, not 437 vs 441.
3. **Compare against known totals.** Does the implied absolute fit inside
   the known total? Is it within 10x of an independent estimate? If the
   implied absolute exceeds the known total, or is off by an order of
   magnitude from every independent anchor, the claim is REFUTED.
4. **Sanity-check the units.** Per analyst, per case, per day, per attempt:
   the rate must be in units that exist. A rate above 100% of a population,
   or a count above the population size, is a definition error, not a
   discovery.

## Output Contract

- Fermi estimate (one significant figure) with its anchor.
- Known total it is compared against.
- Ratio between implied absolute and known total.
- Verdict: CONFIRMED / REFUTED / ABSTAINED. An implied absolute above the
  known total is REFUTED on the spot.

## Operating Rules

- Fermi kills, it does not confirm. Passing Fermi means "not absurd", not
  "true". Confirmation still needs the other checks.
- If no independent anchor exists, say so: the verdict is ABSTAINED, not a
  pass.
- Pairs with doesnt-add-up: this skill covers step 7 of that skill's
  checklist in depth.
