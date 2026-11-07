# Research prompt 3: coding EFFORT, CRAFT, and COMPLETION (the axis the standard + fixes miss)

Companion to prompt 1 (the quality standard) and prompt 2 (the fix playbook). Those two cover
CORRECTNESS. This one covers the two axes a working programmer sees but linters/type-checkers/tests do
NOT: (A) craft/effort (correct-but-lazy vs correct-and-crafted) and (B) completion (actually-done-and-
wired vs commit-made-and-declared-done). The motivating failures: an agent made commits in widgora and
claimed "shipped" while the UI/UX was unwired and non-functional; and in the harness itself, 5 modules
were committed with tests green while 4 had zero callers (fake-completion). Target: build coding
PERSONAS that code with a senior's effort and cannot fake-complete. Output lands in work-docs/research/ as dated `.md`,
primary-sourced with dates. For each Q: the concept, primary source(s), a measurable/enforceable
mechanism, and how to wire it into an agent loop (rubric + gate + iterate).

## Q1 - Definition of Done that makes fake-completion impossible

Research the SOTA "definition of done" for agent-written code that prevents claimed-but-not-working.
Cover: done = the real user workflow PROVEN (live-smoke / e2e / screenshot-diff for UI), not commit +
unit-tests-green; the "merged + deployed + live-smoked" discipline; wired-not-scaffold (a new module
must have a live caller before done, detectable via vulture/import-graph); the anti-patterns of
premature "done" and how agent frameworks detect them. How do the best 2026 coding agents (and their
harnesses) GATE completion on workflow-proof rather than test-proof? Give an enforceable done-checklist
an agent must satisfy + attach evidence for, before it may say "done".

## Q2 - Code craft / effort: the observable tells of lazy vs crafted

What distinguishes a correct-but-lazy implementation from a crafted one, in ways a reviewer (or a
scoring agent) can name and check? Cover: idiomatic Python (Effective Python, Fluent Python) - when a
comprehension / generator / `itertools` / `functools` / stdlib data structure is the right move vs a
hand-rolled loop; the right data structure and the right abstraction (not over- or under-abstracted);
over-defensive code smell (`dict.get()` chains, blanket try/except, defensive copies everywhere)
signalling a missing type/design; cargo-cult OOP vs designed classes; DRY-vs-WET judgment; naming.
Ground it in refactoring / code-smell literature (Fowler) and idiomatic-Python sources. Produce a CRAFT
RUBRIC of observable tells (each: the lazy form, the crafted form, how a reviewer detects it) that is
distinct from correctness - two implementations that both pass tests, one grades A on craft, one C.

## Q3 - Why LLM coding agents skip effort, and what counters it

Research WHY agents optimize to "the check passed" and stop (reward is the checkable proxy: tests
green, commit made), and the mechanisms that counter it: critique-and-iterate / Reflexion, generate-N-
and-select-most-crafted, self-consistency, a separate CRAFT critic (not a correctness critic), depth/
effort scoring, and RL/pass@k's bias toward passes-check over craft. Cite the primary work (Reflexion,
self-refine, LLM-as-judge for code quality, the "reward hacking on tests" literature). What actually
moves an agent from correct-lazy to correct-crafted, empirically?

## Q4 - Building a coding PERSONA that codes with effort

Synthesize Q1-Q3 into how to construct an agent persona that codes like a senior with effort: the
persona contract (what it holds itself to), a craft rubric + a completion/workflow-proof done-gate,
wired into an iterate loop (draft -> craft-critique -> revise until it clears the bar; done only when
workflow-proven AND wired AND craft-graded). Distinguish the CRAFT critic (a strong model asked only
"is this what a senior would write with effort, or the first thing that passed?") from the correctness
gate (tests/types/lint). How do the best 2026 agent systems encode a "senior engineer" persona that
produces effortful code, and how is effort verified rather than trusted?

## Q5 - Detecting fake-completion and lazy tells mechanically

What can be measured/automated vs what needs a judging model? Cover: zero-caller detection (vulture),
edit-survival / code-churn as a lazy-signal (GitClear), diff-quality heuristics, workflow-proof
artifacts (screenshot-diff, e2e pass, live-smoke output) as required completion evidence, and a
"claimed-done vs actually-works" verification pass. Which lazy/fake-done tells are mechanically
detectable, and which require a craft-critic model?

## Q6 - Can effort be quantified?

Research whether "effort" is measurable: iterations-to-convergence, craft-score delta across the
iterate loop, edit-survival at 14/30 days, rework/fix-commit rate on the agent's own diffs, mutation-
kill on the agent's own tests. Tie to a depth/effort engine that scores CRAFT + COMPLETION (not just
correctness) and iterates until both clear the bar. Give a concrete effort metric an agent loop can
optimize.

## Required output

Per Q: concept, primary source(s) with dates, a measurable/enforceable mechanism, and how to wire it
into the agent loop (persona contract + craft rubric + workflow-proof done-gate + iterate). End with
(a) the CRAFT RUBRIC from Q2 (lazy form / crafted form / detection, per tell) and (b) the DONE-GATE
CHECKLIST from Q1 (the evidence an agent must attach before "done" is accepted). These two become the
missing axes I add to the harness so a coding persona codes with effort and cannot fake-complete.
