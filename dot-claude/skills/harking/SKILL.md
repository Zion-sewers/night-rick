# HARKing

Hypothesizing After the Results are Known.

## Purpose

Tuning a query until a juicy number appears, then presenting it as if it was
the hypothesis all along, manufactures findings. The striking number is 1 of
N tries, and N is part of the result.

## Trigger

An exploratory session produces a striking number, or the question changed
mid-investigation, or a slice was chosen because it looks dramatic.

## Procedure

1. **Write the original question down** before running the next query. One
   sentence, as it stood before the striking number appeared.
2. **Count the tries.** How many slices, filters, windows, and variants were
   tried before this number showed up? Report N next to the number. A 44%
   found on try 27 is a different claim than a 44% found on try 1.
3. **Hold-out check.** The number must survive a fresh slice it was not tuned
   on: a different time window, a different subgroup, or a re-derivation with
   a different query structure. If it does not survive, it was tuned noise.
4. **Report the search, not just the hit.** Original question, variants
   tried, hold-out result.

## Output Contract

- Original question (pre-number).
- Variants tried (N) and the winning variant.
- Hold-out result: survived or not, with the numbers.
- Verdict: CONFIRMED / REFUTED / ABSTAINED. A number that only exists in
  the slice it was tuned on is REFUTED.

## Operating Rules

- Choosing a slice because it looks dramatic is allowed in exploration and
  forbidden in reporting, unless N and the hold-out are attached.
- "I found it by exploring" is honest. "The data shows" after 27 silent
  tries is not.
- Pairs with doesnt-add-up: this skill covers step 8 of that skill's
  checklist in depth.
