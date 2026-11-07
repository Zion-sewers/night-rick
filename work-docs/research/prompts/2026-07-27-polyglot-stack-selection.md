# RESEARCH PROMPT: Polyglot stack selection + per-stack SOTA libraries (2026)

Run in /deep-research (ultradeep). Recency: treat "now" as July 2026; only latest-stable releases
and 2025-2026 primary sources. Output lands in work-docs/research/.

## Who is asking (context, do not re-explain)
Solo senior solution engineer, comfortable polyglot, explicitly does NOT want to be locked to Python.
Builds systems from POC to production. Needs, for any new system: (1) a decision framework to pick the
right language/runtime for the workload, and (2) the mature production stack plus the SOTA libraries of
that stack. Existing ~/docs already covers testing, SQL, and UI/UX SOTA; do not duplicate those.

## Research questions
PART A. Language/runtime selection framework. For each common workload, recommend the 2026 primary
choice and the runner-up, with the deciding criteria (raw performance, concurrency model, ecosystem
maturity, type-safety, iteration speed, deployment footprint, solo-maintainability, hiring):
  web/API service; CLI tool; data/ETL pipeline; real-time/streaming; systems/perf-critical; glue/
  scripting/automation; ML/LLM serving; desktop/local app. Cover Python 3.13+, TypeScript on
  Node/Bun/Deno, Go, Rust, and call out where JVM/Kotlin, .NET, or Elixir/BEAM clearly win.

PART B. Per-language MATURE stack + SOTA libs (name + current stable version + maintenance signal).
For each of Python, TypeScript, Go, Rust give the 2026 reach-for-these defaults across: web framework,
data validation/serialization, DB access (ORM vs query-builder vs codegen), HTTP client, async/
concurrency, testing, lint+format, packaging/build/deps, config, structured logging. Flag anything
that is trendy-but-immature versus boring-and-proven.

PART C. Polyglot in one system. When mixing languages is justified, interop options (gRPC/Buf, FFI,
subprocess, shared schemas) and their cost, and the "one boring language unless proven otherwise"
discipline to avoid accidental sprawl.

## Constraints
- For every recommendation, split POC-grade (optimize iteration speed) vs production-grade (optimize
  maturity, types, operability). Say which is which.
- Name specific libraries with current stable versions and a maturity read (stars/release cadence/
  backing). Cite every external claim with a URL. Separate VERIFIED (fetched) from CLAIMED.
- Bias to mature and native over trendy; explicitly flag maturity/lock-in risk.

## Output contract
- A workload x language decision matrix.
- Per-language "reach-for-these defaults" tables: concern | library | version | POC or prod | why | citation.
- A one-page "if unsure, start here" shortlist per language.
- Full bibliography, no placeholder citations. Land as work-docs/research/2026-07-polyglot-stack-selection.md.
