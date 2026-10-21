---
name: testing-pyramid
description: >-
  Plan layered test architecture before non-trivial code changes. Covers static,
  unit, property, component, contract, integration, E2E, non-functional,
  trajectory, and adversarial test layers. Use for test planning, TDD slices,
  test-suite audits, and pre-commit coverage decisions.
---

# Testing Pyramid Skill

End-to-end test-architecture planner. Reads any diff or implementation
plan and emits a per-layer test plan — what to add, where it goes, what
gate it sits at, what coverage measure proves it works.

## When to invoke

- **Before writing new tests** for a non-trivial behavior. Don't write
  random unit tests — plan the layer slice first.
- **Before `/commit-push-pr`** when the staged diff adds new modules,
  new MCP tools, new adapters, or new agent flows.
- **When auditing an existing test suite** that "feels green but feels weak."
- **When a production incident** happens — the incident-to-test
  conversion needs a layer decision (regression, contract, chaos?).

## Authority sources (consulted on every invocation)

This skill operates from **two canonical reference documents**:

1. **`~/docs/testing_practices.txt`** — the classic 8-layer Modern
   Testing Pyramid taxonomy with cadence + minimum-set guidance.
2. **`~/docs/deep-research-report (2).md`** — state-of-the-art agent
   testing (24-section research synthesis). Adds two orthogonal planes
   to the classical pyramid: trajectory evaluation and adversarial
   evaluation. References OpenAI Evals, Anthropic alignment auditing,
   Vertex agent eval, Inspect AI, LangSmith, Braintrust, Promptfoo,
   PyRIT, DeepEval, Ragas, Giskard, Harbor.

Both files MUST be read before producing a plan. They are not
optional.

## The pyramid (canonical reference)

```
                ┌─────────────────────────┐
                │ Adversarial + Red Team  │   Security + safety + alignment
                ├─────────────────────────┤
                │ Non-Functional          │   Perf / Scalability / Chaos
                ├─────────────────────────┤
                │ E2E + Trajectory        │   Real workflows + path validity
                ├─────────────────────────┤
                │ Integration             │   Multi-component, sandboxed
                ├─────────────────────────┤
                │ Contract                │   API + tool schema boundaries
                ├─────────────────────────┤
                │ Component               │   Module-with-real-deps
                ├─────────────────────────┤
                │ Property + Metamorphic  │   Invariants under input variation
                ├─────────────────────────┤
                │ Unit                    │   Pure-function, deterministic
                ├─────────────────────────┤
                │ Static / Formal         │   Pre-runtime — types, lint, schemas
                └─────────────────────────┘
```

For **agent** code, also evaluate two orthogonal planes:

- **Trajectory eval** — was the path the agent took valid? (tool
  precision/recall, exact-match trajectory where workflow is strict,
  golden-master tool sequences)
- **Adversarial eval** — does the system resist prompt injection,
  data leakage, evaluator gaming, tool confusion, reward hacking?

## Per-layer cheat-sheet (one-line per layer)

| Layer | One-line | Tools (Python) | Tools (TS) | Cadence |
|---|---|---|---|---|
| Static | Catch bugs before runtime | ruff, mypy, pyright | tsc, eslint, knip | every commit |
| Unit | Pure logic in isolation, no I/O | pytest | bun test / vitest | every commit |
| Property | Invariants over generated inputs | hypothesis | fast-check | every commit |
| Component | Module with real deps except infra | pytest + respx / VCR | vitest + msw | every commit (fast slice) / nightly (full) |
| Contract | API + tool schema boundaries hold | pytest + pact / schemathesis | pact-node | every commit |
| Integration | Multi-component sandbox | pytest + testcontainers | vitest + testcontainers | PR + nightly |
| E2E + Trajectory | Whole tasks in realistic env | Playwright / Inspect AI / Braintrust | Playwright | nightly + pre-release |
| Golden master | Catch silent semantic drift | snapshot fixtures + semantic diff | snapshot | PR + nightly |
| Regression | Failed bugs become permanent tests | pytest (curated dataset) | bun test | every commit |
| Mutation | Suite-strength measurement | mutmut, cosmic-ray | stryker | nightly |
| Fuzz | Random structured inputs | hypothesis fuzz / atheris | fast-check / jsfuzz | nightly |
| Performance | Latency, throughput, p95 | pytest-benchmark, locust | autocannon, k6 | nightly + pre-release |
| Chaos | Inject failures, prove graceful degrade | toxiproxy + custom | toxiproxy + custom | nightly + pre-release |
| Security | Injection, leak, auth-bypass | bandit, pip-audit, OWASP ZAP, PyRIT, promptfoo | snyk, semgrep, PyRIT | PR smoke + nightly |
| Trajectory (agent) | Path correctness, tool prec/recall | Vertex agent eval, OpenAI Evals, Inspect AI | LangSmith | PR + nightly |
| Red team (agent) | Open-ended attack search | PyRIT, Promptfoo, manual | PyRIT | pre-release + quarterly |

## How the skill works in a session

When invoked, the skill does the following in order:

### 1. Read the two authority docs first

```
Read ~/docs/testing_practices.txt
Read ~/docs/deep-research-report (2).md
```

These are the source of truth for the per-layer guidance below. Do NOT
proceed without having read them in the current session.

### 2. Read the implementation context

- Read AGENTS.md (project rules — `bun`/`uv`, no mocks, TDD mandatory,
  forge-loop).
- Read the diff being tested (`git diff` or `git diff --staged`) or the
  implementation plan if there isn't code yet.
- Identify: is this PURE compute? Adapter to external API? Agent tool?
  Multi-step workflow? Long-running task?

### 3. Classify the work into one of four archetypes

| Archetype | Examples | Required layers (minimum) |
|---|---|---|
| **Pure compute / shaping** | `_compute_auth_hash`, `_shape_customer`, classifier regex | Static + Unit + Property |
| **External-API adapter** | `<vendor>.list_customers`, `<vendor>.get_data`, `crm.crm_get_customer` | Static + Unit + Component (respx) + **Contract** + Regression |
| **MCP tool / agent surface** | New tool registered in `server.py` | All of External-API-adapter PLUS Trajectory + Golden master + Security smoke |
| **Multi-step workflow** | Agent loop with branching tool calls | Everything above + Integration + E2E sandbox + Chaos + Trajectory + Adversarial |

The archetype dictates the minimum set. The skill outputs the missing
layers, not all layers.

### 4. Emit a per-layer plan, in TDD-slice order

For each missing layer, output one block:

```
LAYER: <name>
WHY:   <single-sentence justification — why this layer for this change>
WHAT:  <one or two test names you would add>
WHERE: <file path in the project where the test goes>
TOOL:  <which test framework / library>
GATE:  <commit | PR | nightly | pre-release>
COVERAGE: <how you'd measure the layer's strength>
```

Then end with a RECOMMENDED ORDER section that gives the TDD slice
sequence (which test to write first, second, third, so each one fails
red before the next is written).

### 5. Do NOT auto-write the tests

This skill is a planner, not an author. It outputs the plan. The user
(or `/tdd-slice-planner` / direct implementation) writes the tests in
RED → GREEN order.

## Concrete examples (from a real MCP-tool project)

### Example 1 — adding a CRM-contacts-by-attribute lookup tool (MCP tool archetype)

What I should have planned:
- ✅ Static (ruff + mypy) — done
- ✅ Unit on `_shape_crm_contact` projection — done (within the component tests)
- ❌ **Property** on `_initials` (invariant: idempotent, max 4 chars, all-uppercase) — MISSING
- ✅ Component via respx (4 happy-path tests) — done
- ❌ **Contract** against the real CRM's `/contacts` schema (VCR cassette nightly) — MISSING
- ❌ **Golden master** on the response shape — MISSING
- ❌ **Adversarial** — what happens when an attribute value contains injection patterns? — MISSING

What I actually did: only unit + component. The Contract gap is
exactly why a separate connector's 500 caught me at live-probe
time instead of at commit time.

### Example 2 — fixing a third-party-apt-source Dockerfile bug (hotfix archetype)

What I planned:
- ✅ **Regression** test in `tests/test_dockerfile_third_party_apt_sources.py`
  — 3 cases: file exists, third-party-key-purge present, purge BEFORE
  apt-update
- Considered + skipped:
  - Integration (live docker build in CI) — handled by the pipeline itself; redundant locally
  - Mutation — overkill for a 5-line shell change

This is the right minimum for a hotfix archetype.

## Output template

```
## Test architecture plan

**Archetype:** <one of the four>
**Authority sources read:** ~/docs/testing_practices.txt,
                            ~/docs/deep-research-report (2).md
**Project rules applied:** <from AGENTS.md — bun/uv, no mocks, etc.>

### Layers required (your archetype's minimum)
- ✅ <layer> — <how it's already covered>
- ❌ <layer> — <gap>

### Per-layer plan for the gaps

LAYER: <name>
WHY:   ...
...

### Recommended TDD-slice order

1. <test name> — failing test, drives <production change>
2. <test name> — failing test, drives <next production change>
3. ...

### Out of scope this commit (deferred with justification)

- <layer X> — <why it's safe to defer>
- <layer Y> — <when it becomes mandatory>
```

## Anti-patterns this skill blocks

- **"100% line coverage" goal-setting** — the skill rejects this in favor of layer-coverage. Line coverage of 100% on a thin unit-only suite is weaker than 60% coverage across 6 layers.
- **"Just write more unit tests"** — if a bug is at the Contract layer, no number of unit tests will catch it. The skill insists on the right *layer*, not more of any one layer.
- **Horizontal slicing** — writing all the static tests, then all the unit tests, then all the property tests. The pyramid is the destination; the path to it is per-behavior vertical slices.
- **Mocking external services in unit tests** — per AGENTS.md's no-mocks rule. Use respx (Python) / msw (TS) / VCR cassettes for component-level; testcontainers for integration; never `@patch` business logic.

## References

- `~/docs/testing_practices.txt` — 8-layer pyramid + minimum set + CI cadence
- `~/docs/deep-research-report (2).md` — agent-specific layers (trajectory, adversarial), modern harnesses, benchmark suites
- AGENTS.md (project root) — project-specific overrides (bun/uv, no-mocks, forge-loop)
- `~/.Codex/rules/tdd-enforcement.md` — RED → GREEN → REFACTOR discipline
- `~/.Codex/rules/no-mocks.md` — alternatives (VCR, respx, real components)
- `~/.Codex/skills/tdd-slice-planner/SKILL.md` — companion skill for picking the next failing test

## Slash invocation

User-facing trigger: `/testing-pyramid`

The skill reads the two authority docs, then expects a description of
the change to test (or a `git diff` to inspect). Emits the per-layer
plan.
