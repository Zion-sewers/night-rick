---
name: gigo
description: Verify inputs before trusting outputs. Definitions, source tables, joins, and filters, or abstain.
license: MIT
---

# GIGO

Garbage In, Garbage Out.

## Purpose

A reported number is only as good as its inputs: the definitions, the source
tables, the joins, the filters. If any input is wrong, no downstream polish
fixes the output. Check inputs before defending outputs.

## Trigger

Any SQL-derived number before it is reported, and every time a definition is
ambiguous or a source table is new or unverified.

## Procedure

1. **Inventory every input.** Tables, columns, definitions, joins, filters.
   Write them down, not from memory.
2. **Verify each definition at its source.** What does this column actually
   mean? Who writes it? When is it NULL? When did its meaning change?
3. **Verify each filter's effect.** Count rows before and after each filter
   and each INNER JOIN. Account for every dropped row.
4. **Gate on verification.** If any input is unverified, the verdict is
   ABSTAINED, not a number with caveats attached.

## Output Contract

- Input inventory: each input with its verified meaning or marked unverified.
- Row counts before and after each filter/join.
- Verdict: CONFIRMED / REFUTED / ABSTAINED. Unverified input forces ABSTAINED.

## Operating Rules

- "The query ran" is not verification. "The column means X" needs a source.
- A number built on an unverified input is not reported with a footnote. It
  is not reported.
- Pairs with doesnt-add-up: this skill covers step 3 and 5 of that skill's
  checklist in depth.
