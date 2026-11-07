# RESEARCH PROMPT: Data and persistence layer SOTA, polyglot (2026)

Run in /deep-research (deep). Recency: "now" is July 2026; latest-stable, 2025-2026 sources.
Output lands in work-docs/research/.

## Who is asking (context)
Solo senior engineer, polyglot. Existing ~/docs covers SQL engineering and Text2SQL deeply; this
research targets the DATASTORE-and-access-layer DECISION space around them, not SQL query craft. The
house stance: reach for Postgres by default and add specialized stores only when justified.

## Research questions
PART A. Datastore selection 2026: Postgres as the default and its extensions (pgvector, TimescaleDB,
PostGIS, pg_search), and the concrete signals to add Redis/Valkey (cache/queue), object storage, an OLAP
engine (DuckDB embedded vs ClickHouse), a search engine (Meilisearch, Typesense, OpenSearch), or a
dedicated vector DB. Argue the "just use Postgres until X" discipline and what X actually is.

PART B. Access layer per language, with the tradeoff of ORM vs query-builder vs raw+codegen: Python
(SQLAlchemy 2.x, SQLModel), TypeScript (Drizzle, Prisma, Kysely), Go (sqlc, GORM, sqlx), Rust (sqlx,
SeaORM, diesel). When raw SQL plus codegen (sqlc-style) beats an ORM, and vice versa.

PART C. Schema and migrations: Atlas, sqitch, Alembic, Prisma Migrate, golang-migrate, and zero-downtime
migration patterns (expand/contract). The migration-as-code discipline and how to gate it in CI.

PART D. Data reliability: connection pooling (PgBouncer vs built-in), the outbox pattern and CDC
(Debezium), backup/restore posture, and data-quality gates at the boundary (pandera, Great Expectations,
dbt tests).

## Constraints
- Split POC-grade (SQLite/embedded, single Postgres) vs production-grade (pooling, migrations gate,
  backups, quality checks). Name tools with current versions. Cite external claims (URL); VERIFIED vs CLAIMED.

## Output contract
- A datastore decision matrix (inputs: shape, scale, query pattern, latency -> store).
- A per-language access-layer table: language | ORM | query-builder | raw+codegen | when to pick which.
- A migrations tool table + a zero-downtime migration checklist.
- Full bibliography. Land as work-docs/research/2026-07-data-persistence-stack.md.
