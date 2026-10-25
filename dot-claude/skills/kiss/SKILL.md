---
name: kiss
description: The simplest query that answers the question. Every join is a fan-out risk, every filter a silent drop.
license: MIT
---

# KISS

Keep It Simple, Stupid.

## Purpose

The simplest query that answers the question. Every join is a fan-out risk,
every filter a silent drop, every CASE a definition fork. Complexity in a
query is not sophistication, it is unexamined behavior.

## Trigger

A query with 3 or more joins, nested subqueries, or CASE-heavy logic that
produces a number about to be reported.

## Procedure

1. **Restate the question in one sentence.** If the question needs two
   sentences, the query is answering two questions and the number mixes
   them.
2. **Rewrite at minimum complexity.** Drop every join, filter, and CASE
   branch that does not serve exactly that sentence. The simple query is
   the reference implementation.
3. **Compare.** Run the simple query and the complex query side by side. If
   they agree, ship the simple one. If they differ, the complexity is doing
   something unexamined: find what, and either justify it in the question
   or delete it.
4. **Name every remaining join's risk.** For each join left, state its
   cardinality (one-to-one, one-to-many) and what it does to the count.

## Output Contract

- One-sentence question.
- Simple query and its result.
- Comparison with the complex query's result, with any difference
  explained or removed.
- Verdict: CONFIRMED / REFUTED / ABSTAINED. An unexplained difference
  between simple and complex is REFUTED.

## Operating Rules

- A query nobody can explain in one sentence is not ready to produce a
  number for a human.
- Complexity added "just in case" is the most common source of silent
  fan-out. Delete it and watch whether the number moves.
- Pairs with doesnt-add-up: this skill covers step 4 of that skill's
  checklist in depth.
