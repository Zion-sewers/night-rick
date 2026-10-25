# Doesnt-Add-Up

## Purpose

When an agent investigates with SQL and returns a number (a percentage, a count,
a rate) that smells wrong against base rates or plain reality, run this before
the number reaches a human. A query that runs is not a query that is right.
The failure modes are boring, not exotic: wrong denominator, fan-out joins,
mixed definitions, silent NULL drops.

Trigger: any reported number derived from SQL, especially percentages, and
especially when the human says "that doesn't add up" or when the number would
change a decision. A human "doesn't add up" is a finding, not a feeling: it
triggers this skill, never a defense of the query.

## Workflow

1. **Restate the claim with all five slots filled.** Numerator, denominator,
   population, time window, exact definition of the measured event. If any slot
   is empty, the number is not reportable yet. "44% of analysts stopped fraud"
   is not a claim until you can say: 44% of WHAT, stopped means WHAT, over
   WHICH window, among WHICH analysts.
2. **Denominator check.** List who is in the denominator and who is excluded.
   A percentage without a stated denominator is not a finding.
3. **Definition check.** One event, one definition, used identically in
   numerator and denominator. Mixed meanings (blocked vs reviewed vs
   confirmed, attempted vs completed) are the most common silent killer.
   Define the event once, in one place, and reuse it (SSOT).
4. **Join fan-out check.** Any one-to-many join between the counted table and
   a dimension table multiplies rows. Re-run with COUNT(DISTINCT grain_id)
   and compare against COUNT(*). If they disagree, the join is the number.
5. **NULL and filter check.** INNER JOINs and WHERE clauses silently drop
   rows. Count rows before and after each filter and account for every
   dropped row.
6. **Reconciliation.** Segments must sum to the whole. If subgroup
   percentages do not sum to 100, or subgroup counts do not sum to the total,
   something overlaps or leaks (MECE: mutually exclusive, collectively
   exhaustive).
7. **Fermi check.** Order-of-magnitude plausibility against known totals. If
   the claim implies an absurd absolute (more stopped cases than total cases
   in the period, more analysts acting than analysts employed), it is dead
   regardless of what the query says.
8. **Independent re-derivation.** Write a second query with a different
   structure (different joins, different aggregation path) for the same claim.
   If the two disagree, neither ships.
9. **Selection check.** Is the population only the cases someone touched?
   Only flagged cases? Only cases with complete data? Selection and
   survivorship manufacture big percentages out of thin denominators.
10. **Subgroup check.** Break the number by one or two obvious dimensions. If
    the aggregate reverses inside subgroups, that is Simpson's paradox:
    report the subgroups, not the aggregate.

## Output Contract

- Claim restated with numerator, denominator, population, window, definition.
- Table of checks run, each PASS/FAIL, with the query or count that settles it.
- Verdict: CONFIRMED / REFUTED / ABSTAINED (same three states as
  triple-verdict). A number that fails any of checks 2-6 is REFUTED, not
  "approximately right". ABSTAINED when the data that would settle it is not
  accessible.
- Never report the number without its denominator, definition, and window in
  the same message.

## Operating Rules

- The agent that wrote the query never grades its own number alone. Step 8
  (re-derivation) or a different model family checks it.
- A pretty query is not evidence. Only counts reconcile.
- Keep the query simple (KISS): every join is a fan-out risk, every filter a
  silent drop. Do not slice the number twelve ways (YAGNI) before it passes
  the smell test.
- Evidence discipline: tag claims as established / adaptation / original
  synthesis / unverified. Never present a SQL output as fact before this
  skill's verdict.

## Worked Example

Claim: "44% of analysts stopped fraud."

- Denominator: 44% of analysts, or of cases, or of attempts? Each gives a
  different number and a different meaning.
- Definition: "stopped" as blocked transaction, analyst decision, or rule
  hit? If the numerator counts rule hits and the denominator counts
  analysts, the percentage is meaningless.
- Fan-out: joining analysts to cases one-to-many, then counting rows,
  inflates the numerator by cases per analyst.
- Fermi: 44% of all analysts stopping fraud would imply a fraud volume
  wildly above the known case volume. If the absolute does not fit the
  known total, the query is wrong, not reality.
