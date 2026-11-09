---
name: yagni
description: Do not slice, dashboard, or drill into a number before the core number passes the smell test.
license: MIT
---

# YAGNI

You Aren't Gonna Need It.

## Purpose

Do not build slices, dashboards, or breakdowns before the core number passes
the smell test. Slicing a broken number twelve ways produces twelve broken
numbers and the illusion of rigor.

## Trigger

A request to slice, dice, visualize, or drill into a number that has not
passed the doesnt-add-up checks, or a growing list of breakdowns nobody
asked a decision with.

## Procedure

1. **Gate on the core number.** The core number passes doesnt-add-up first.
   No slices before that. A slice of a REFUTED number is REFUTED.
2. **One decision per slice.** For each requested slice, ask: what decision
   does this slice change? If none, skip it. "Interesting" is not a decision.
3. **Build only what changes a decision.** List slices built and slices
   skipped, each with the decision it serves or the reason it was skipped.
4. **Stop at the decision.** Once the decision is served, stop slicing.
   Further breakdowns are where tuned numbers (see harking) are born.

## Output Contract

- Core number with its doesnt-add-up verdict (must be CONFIRMED to proceed).
- Slice list: built vs skipped, each with its decision or skip reason.
- Verdict: CONFIRMED / REFUTED / ABSTAINED for the sliced view as a whole.

## Operating Rules

- A dashboard of a number nobody verified is a monument to the number's
  author, not evidence.
- "While we're at it" is how a one-number check becomes a twenty-slice
  fishing expedition. Decline it until the core number is CONFIRMED.
- Pairs with doesnt-add-up: this skill is the gate in front of that skill's
  step 10.
