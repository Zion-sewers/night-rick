# RESEARCH PROMPT: Rust vs Python selection + trusted SOTA OSS libraries with metrics (2026)

Run in /deep-research (ultradeep). Recency: "now" is July 2026; only latest-stable releases and
2025-2026 primary sources. Output lands in work-docs/research/. Deep-dive companion to
2026-07-27-polyglot-stack-selection.md.

## Who is asking (context)
Solo senior engineer whose current domain is AI/LLM agents, CS-agent Azure Functions, and data work,
mostly Python today, but explicitly does NOT want to be Python-locked and wants to know exactly when
Rust earns its place. Wants trusted, well-maintained OSS that is SOTA on performance and quality, with
the metrics that justify the claim, not hype.

## Research questions
PART A. Rust-vs-Python decision framework with THRESHOLDS, not vibes. For each workload (web/API,
CLI/daemon, data transform, parsing/serialization, ML/LLM serving, systems/perf-critical, glue), state
use-Python / use-Rust / use-both and the deciding metrics (p50 and p99 latency, throughput, memory
footprint, cold start, dev velocity, ecosystem depth, correctness/safety, solo-maintainability). Give
the concrete signals that flip the decision (e.g., "CPU-bound and p99 must stay under N ms" -> Rust).

PART B. The hybrid pattern (the pragmatic default for a Python shop): accelerate a measured Python hot
path with a Rust extension via PyO3 + maturin instead of rewriting. Document real exemplars that already
prove it (polars, pydantic-core, ruff, uv, orjson, tokenizers, cryptography) with their published
benchmark deltas. State when a Rust extension is worth it and when a rewrite is over-reach.

PART C. Trusted SOTA OSS libraries 2025-2026, per language, each with the metric it leads on, a benchmark
source, and a maintenance/trust signal (release cadence, backing org, stars):
  - Rust: async runtime (tokio), web (axum), serialization (serde), DB (sqlx / SeaORM), dataframes
    (polars core), parallelism (rayon), CLI (clap), TUI (ratatui), HTTP (reqwest), bench (criterion),
    Python-bindings (pyo3 + maturin), tracing.
  - Python: uv, ruff, ty / pyright, pydantic v2, FastAPI / Litestar, polars, httpx, structlog,
    pytest + hypothesis, msgspec, orjson.
  For each: leads-on-metric, benchmark citation, and stability read.

PART D. Anti-patterns, with evidence: rewriting working Python in Rust with no measured bottleneck,
premature Rust adoption, ignoring compile-time and cognitive cost, and choosing an immature Rust crate
over a proven one. Include the cost side honestly.

## Constraints
- Every performance claim needs a metric and a benchmark citation (URL). Separate VERIFIED (fetched)
  from CLAIMED. Only trusted, actively-maintained crates/packages; flag maturity or lock-in risk.
- Distinguish POC-grade vs production-grade choices.

## Output contract
- A Rust-vs-Python decision matrix with numeric thresholds/signals per workload.
- A "hybrid playbook": how to profile, then wrap the hot path in Rust via PyO3/maturin, with exemplars.
- Two "trusted SOTA libs" tables (Rust, Python): lib | leads on metric | benchmark citation | maturity.
- An anti-pattern list. Full bibliography. Land as work-docs/research/2026-07-rust-vs-python.md.
