# RESEARCH PROMPT: System architecture and design patterns SOTA (2026)

Run in /deep-research (ultradeep). Recency: "now" is July 2026; latest-stable, 2025-2026 sources.
Output lands in work-docs/research/.

## Who is asking (context)
Solo senior engineer / small team, polyglot, building services that must scale from POC to production
without accidental complexity. The Principal Engineer Curriculum in ~/docs covers architecture at a high
level; target the DECISION FRAMEWORK and the ENFORCEMENT tooling gaps, not a re-survey. The house stance
biases to the simplest architecture that meets the requirement.

## Research questions
PART A. Macro-architecture decision framework 2026: modular monolith vs microservices vs
serverless/functions vs event-driven vs actor/stateful. For a solo/small team, when is each justified,
and what are the cost, latency, and operational-burden tradeoffs? Include the "monolith-first" and
"microservices as a last resort" positions and the concrete signals that justify splitting.

PART B. Internal structure patterns: hexagonal / ports-and-adapters, vertical slice, clean/onion,
classic layered. When each fits, how they interact with a boundary-contract discipline (typed DTOs at
every seam, validate + fail-closed), and their testability implications.

PART C. Distributed concerns for when you DO split: data-per-service, saga vs outbox vs CDC, idempotency,
eventual consistency, API gateway vs BFF, service discovery. Keep it grounded in what a small team can
actually operate.

PART D. Enforcement so architecture does not rot: ADRs (adr-tools, log4brains), fitness functions in CI
(import-linter for Python, dependency-cruiser for TS, ArchUnit for JVM, go-arch-lint, custom), and C4 +
Structurizr / diagrams-as-code. Which minimal set pays off for a solo dev.

## Constraints
- Bias to simplest-that-works; explicitly flag where a pattern is premature complexity for a small team.
- Cite external claims (URL); separate VERIFIED from CLAIMED. Polyglot enforcement tooling.

## Output contract
- A macro-architecture decision tree (inputs: team size, scale, latency, domain volatility -> choice).
- A pattern catalog table: pattern | when to use | avoid when | enforcement tool | citation.
- A "minimal architecture-governance kit for a solo dev" (ADR + one fitness function + one diagram tool).
- Full bibliography. Land as work-docs/research/2026-07-architecture-patterns.md.
