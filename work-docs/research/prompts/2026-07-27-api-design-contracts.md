# RESEARCH PROMPT: API design and contracts SOTA (2026)

Run in /deep-research (deep). Recency: "now" is July 2026; latest-stable, 2025-2026 sources.
Output lands in work-docs/research/.

## Who is asking (context)
Solo senior engineer, polyglot, building HTTP/RPC/event and agent-tool APIs. The house already has a
boundary-contracts rule (typed DTOs both ways, validate upstream, fail closed, typed errors, test the
five cases); this research should EXTEND it to paradigm selection, contract-first workflow, and the
production details, not restate it.

## Research questions
PART A. API paradigm selection 2026: REST + OpenAPI 3.1, gRPC + Buf, GraphQL, tRPC, async/event
(AsyncAPI/Kafka/NATS), and MCP for agent/tool APIs. When each is the right call, and how they compose.
Include polyglot codegen quality for each.

PART B. Contract-first workflow: OpenAPI/Protobuf/AsyncAPI as the source of truth, codegen per language,
consumer-driven contract testing (Pact, Schemathesis), and automated breaking-change detection (Buf,
oasdiff). Show the loop from spec to generated client/server to contract test in CI.

PART C. The production details that bite: versioning strategy (URI vs header vs content negotiation),
error model (RFC 9457 problem+json), pagination (keyset/cursor over offset), idempotency keys, rate
limiting + quotas, authN/authZ (OAuth 2.1 + PKCE, OIDC, PATs, mTLS, scopes), and request validation +
fail-closed at the boundary.

PART D. Lightweight API governance for a solo dev: linting (Spectral for OpenAPI, Buf lint), a minimal
style guide, and the smallest set of gates that actually prevents drift.

## Constraints
- Distinguish POC-grade (a typed handler + OpenAPI) vs production-grade (contract tests, breaking-change
  gate, auth, rate limit). Cite external claims (URL); separate VERIFIED from CLAIMED.

## Output contract
- A paradigm decision matrix (inputs: consumers, latency, streaming, type-sharing -> REST/gRPC/GraphQL/
  tRPC/events/MCP).
- A "production API checklist" (versioning, errors, pagination, idempotency, auth, rate limit, validation).
- A tool/lib table with current versions per language + citations.
- Full bibliography. Land as work-docs/research/2026-07-api-design-contracts.md.
