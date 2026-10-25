---
name: ssot
description: One metric, one definition, one place. Reconcile divergent definitions before comparing numbers.
license: MIT
---

# SSOT

Single Source of Truth.

## Purpose

One metric, one definition, one place. If "stopped" means blocked in one
query, reviewed in another, and confirmed in a third, every comparison
between them is fake, and every percentage built on them is meaningless.

## Trigger

A metric used in more than one query or report, or any term whose meaning is
assumed rather than written down.

## Procedure

1. **Write the definition card.** Event, grain (one row = what?), population,
   time window, inclusions, exclusions. Five lines, no adjectives.
2. **Hunt for other uses.** Search for the same term in other queries,
   dashboards, and reports. If any use differs from the card, stop: the
   metric is currently defined twice, and both numbers are suspect.
3. **Reconcile to one.** Pick the correct definition, rewrite the divergent
   uses to match, and record the change where the definition lives.
4. **Point all future queries at the card.** Changes go through the
   definition, never through per-query edits that silently fork it.

## Output Contract

- Definition card (event, grain, population, window, inclusions, exclusions).
- List of usages found, each marked aligned or divergent, with divergent
  ones fixed or flagged.
- Verdict: CONFIRMED / REFUTED / ABSTAINED. A term with two live
  definitions is REFUTED until reconciled.

## Operating Rules

- A metric without a written definition does not exist. It is a word.
- Never "adjust" a definition inside a query to make a number look better.
  That is forking, and it is how two teams report different truths.
- Pairs with doesnt-add-up: this skill covers step 3 of that skill's
  checklist in depth.
