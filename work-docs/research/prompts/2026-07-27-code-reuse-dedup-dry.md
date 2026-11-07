# RESEARCH PROMPT: Code reuse, deduplication, and the DRY/AHA/WET balance (2026)

Run in /deep-research (deep). Recency: "now" is July 2026; latest-stable, 2025-2026 sources.
Output lands in work-docs/research/.

## Who is asking (context)
Solo senior engineer, polyglot, who wants to control duplication across a multi-repo/monorepo estate
WITHOUT sliding into over-abstraction. The house stance is minimalism (ponytail/YAGNI): dedup must
reduce real cost, not add speculative indirection. Reference that tension explicitly.

## Research questions
PART A. Duplication detection tooling 2026, polyglot, and how to wire it into CI as a non-blocking
signal first: jscpd, PMD-CPD, semgrep, Sourcegraph, similarity-based detectors, difftastic for review.
Give what each detects (token vs AST vs semantic), false-positive behavior, and language coverage.

PART B. Reuse and sharing strategy: internal shared packages, monorepo tooling (Nx, Turborepo, Bazel,
moon, plus native uv/cargo/go workspaces), private registries, and git submodule vs subtree vs package
dependency. When each is worth it for a small team, and the maintenance cost of each.

PART C. The abstraction discipline, with 2026 and canonical sources: DRY vs AHA (Avoid Hasty
Abstractions, Sandi Metz "duplication is cheaper than the wrong abstraction") vs WET, the rule-of-three,
and a concrete decision procedure for extract-vs-inline. Must argue BOTH directions (when to dedup, and
when leaving duplication is correct).

PART D. Paying down duplication debt safely: characterization tests first, then dedup, then verify; how
to avoid a dedup refactor introducing regressions.

## Constraints
- Do not bias toward maximal DRY; the deliverable must protect against over-abstraction as much as
  against copy-paste sprawl.
- Name tools with current versions + CI wiring snippets. Cite external claims (URL); VERIFIED vs CLAIMED.

## Output contract
- A decision guide: given a duplication instance, dedup now / extract at rule-of-three / leave it.
- Tool table: tool | detects (token/AST/semantic) | languages | CI wiring | citation.
- A short "dedup review checklist" and an "over-abstraction smells" list.
- Full bibliography. Land as work-docs/research/2026-07-code-reuse-dedup-dry.md.
