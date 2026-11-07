# RESEARCH PROMPT: Code maturity ladder, POC to production (2026)

Run in /deep-research (deep). Recency: "now" is July 2026; latest-stable, 2025-2026 sources.
Output lands in work-docs/research/.

## Who is asking (context)
Solo senior engineer who builds at different maturity levels (throwaway POC through hardened
production) and wants to RIGHT-SIZE rigor to the stage: never over-engineer a POC, never ship a POC to
production. Companion to the existing forge-loop discipline and the ponytail/YAGNI stance in ~/docs and
CLAUDE.md. Do not re-research the test pyramid itself (already in SOTA-TESTING-CRITERIA-2026); reference it.

## Research questions
PART A. Define the maturity stages (proof-of-concept, prototype/MVP, production, hardened/regulated) and
the concrete EXIT CRITERIA to graduate each stage. What is legitimately acceptable to skip at POC, and
what must NEVER be skipped even at POC (e.g., secrets handling, destructive-op guards, data loss risk).

PART B. What scales up per stage, as a rubric: which test-pyramid layers, error handling, observability,
CI/CD, docs/ADRs, security posture, performance budgets, data-migration safety, rollback. Show the
delta between adjacent stages, not a flat list.

PART C. The two failure modes, with 2026 evidence and named anti-patterns: over-engineering early
(premature abstraction, microservices-too-soon, gold-plating, speculative generality) and
under-engineering late (the "POC in prod" trap, no observability, no migrations). How practitioners
right-size: monolith-first, walking-skeleton, tracer-bullet, evolutionary architecture, YAGNI.

PART D. A per-stage scorecard I can apply to any repo in minutes, plus a graduation checklist per
transition (POC->MVP, MVP->prod, prod->hardened).

## Constraints
- Practical and opinionated, not a survey. Bias to the simplest thing that clears the stage.
- Cite external claims (URL); separate VERIFIED from CLAIMED. Language-agnostic where possible.

## Output contract
- A stage-by-stage rubric table (stage | testing | errors | observability | CI | security | docs | perf).
- A "must-never-skip even at POC" hard list.
- Two checklists: graduation gates, and a fast repo maturity scorecard (0-5 per axis).
- Full bibliography. Land as work-docs/research/2026-07-code-maturity-ladder.md.
