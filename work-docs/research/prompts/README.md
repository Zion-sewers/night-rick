# Research Prompt Pack: Build-Time SOTA (2026)

Dedicated deep-research prompts for the domains missing from `~/docs`, so any system built
(POC or mature) uses the RIGHT mature stack for its maturity level, the SOTA libraries of that
stack, and SOTA architecture / API / design practices. Polyglot by design, not Python-locked.

## How to run
For each file: open `/deep-research` (deep or ultradeep mode) and paste the file's contents, or
point it at the path. Output lands in `work-docs/research/2026-07-<topic>.md`. Run them in any order;
they are independent. Recency anchor inside each: treat "now" as July 2026, latest-stable only.

## The prompts (missing domains)
1. `2026-07-27-polyglot-stack-selection.md` : choose language/runtime by workload + the mature
   stack and SOTA libs per language (Python, TS/Node, Go, Rust, JVM/.NET where they lead).
2. `2026-07-27-code-maturity-ladder.md` : POC to MVP to production rubric, what rigor each stage
   needs, right-sizing (no over-engineered POCs, no POCs shipped to prod).
3. `2026-07-27-code-reuse-dedup-dry.md` : duplication detection tooling, reuse/monorepo strategy,
   DRY vs AHA vs WET (anti-over-abstraction).
4. `2026-07-27-architecture-patterns.md` : macro + internal architecture decision framework and
   the tools that enforce it.
5. `2026-07-27-api-design-contracts.md` : API paradigm selection, contract-first, versioning,
   errors, pagination, auth, governance.
6. `2026-07-27-data-persistence-stack.md` : datastore selection, per-language access layer,
   migrations, data reliability.
7. `2026-07-27-rust-vs-python.md` : Rust vs Python with numeric thresholds, the PyO3/maturin hybrid,
   and trusted performance/quality SOTA OSS 2025-2026 per language, with benchmark citations.

Pack-wide criterion: every library recommendation must be trusted + actively maintained + backed by a
metric/benchmark citation (2025-2026), POC-grade vs production-grade called out, VERIFIED vs CLAIMED.

## Already covered in ~/docs (do not re-research; the prompts reference these)
Production AI & Software Engineering SOTA, Principal Engineer Curriculum, SOTA-TESTING-CRITERIA-2026,
Excellent SQL Engineering, Text2SQL, Next-Gen UI/UX, SOTA Video/Voice Testing, the setup gap-analysis,
and the Claude-to-Codex auto-delegation backlog.

## Further domains you can request as prompts (not yet written)
Observability + SRE (OTel, SLOs, error budgets), security + supply-chain (SBOM, SLSA, OAuth 2.1,
secrets), developer-experience + build tooling, LLM-application stack (RAG, eval, agents),
mobile/cross-platform.
