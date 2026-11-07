# Research prompt 2: correct implementation patterns for the exact issues found

Companion to `2026-07-12-code-implementation-quality-standard.md` (the standard) and to the audit
`intent-control-plane/docs/analysis/2026-07-12-implementation-audit.md` (the findings). That first
prompt asked "what is the standard". This one asks "how do I CORRECTLY implement/fix each specific
class of defect the audit found", so the research yields the right pattern + primary source + a
copy-adaptable code example + how to test it. Target stack: zero-RUNTIME-dependency Python package
(uv + ruff + mypy --strict + pytest; tree-sitter is the only external dep; dev deps are fine),
single-operator local harness with multiple concurrent Claude sessions. Output lands in work-docs/research/ as dated `.md`. Primary sources with dates; flag anything unverified. For EACH section: (a) the correct
SOTA pattern, (b) primary source(s), (c) a concrete example adapted to this stack, (d) the test that
proves it (unit / property / concurrency / mutation as fits).

## 1. Concurrency-safe check-then-act on SQLite (TOCTOU)

Finding: a guard reads state on one connection then inserts on another with no transaction/lock, so
two concurrent sessions can both pass an allow-list check and double-advance a state machine. Research:
correct check-then-insert on sqlite for a multi-session single-file DB. `BEGIN IMMEDIATE` vs deferred,
WAL mode, `isolation_level`, a single transaction spanning read+write, UNIQUE-constraint-as-guard,
application advisory locks. How to WRITE A TEST that actually races it (threads/processes) and fails
before the fix. Cite sqlite docs + Python sqlite3 transaction docs.

## 2. Typed data at boundaries: kill `dict[str, Any]` DTOs

Finding: every row builder returns `dict[str, Any]`; downstream reads via `.get()` with no shape
guarantee. Research the decision rule and migration: `typing.TypedDict` (stdlib, zero dep) vs
`@dataclass(slots=True, frozen=True)` vs `msgspec.Struct` vs pydantic; which fits a zero-runtime-dep
package; how to convert a dict-returning API to typed without breaking callers; what mypy --strict
then catches that it doesn't today. Cite PEP 589 (TypedDict), dataclasses docs, msgspec.

## 3. API safety: prevent argument-swap / positional inversion

Finding: `keep_verdict(held_out, held_out_baselines)` are same-typed and positional; a caller swap
silently inverts a gate. Research: keyword-only parameters (PEP 570 `*`), `typing.NewType` for
distinct semantic types, when to force keyword-only, and the "make illegal states unrepresentable"
principle. Example + a test that a swapped call is now a type error or rejected.

## 4. Fail-closed input contracts

Findings: `criteria` without `results` degrades to a pass instead of rejecting; a held-out gate is a
no-op when the baseline list is empty; an unvalidated `exploitation_ratio` out of [0,1] silently
corrupts a slice. Research the fail-closed guard-clause discipline: validate-or-raise at the top of
a function, reject incomplete/partial inputs, never let an out-of-contract input degrade to a
plausible-but-wrong result. The five boundary tests (valid / invalid / missing / empty / out-of-range).

## 5. Order-independent / deterministic selection logic

Finding: `swarm_pass`'s kept-set depends on input order in a way that defeats its stated "keep only
those that beat the running baseline". Research: how to write selection/keep-if-better logic whose
result is order-independent (or how to make order an EXPLICIT, documented, tested contract, e.g.
sort-first), and how to property-test order-invariance (hypothesis permutation strategy).

## 6. Robust heuristic classification (commits, regex screens)

Findings: `classify_commit('Fixed the login bug')` -> 'other' (misses plain-English fixes);
the reward-hacking screen only matches camelCase `continueOnError`. Research: building comprehensive,
tested heuristic classifiers, conventional-commit + natural-language fix detection; regex robustness
(case/hyphen/space variants); table-driven fixtures as the test form; when a heuristic should be
replaced by a small model. Cite conventional-commits spec + SZZ literature.

## 7. Complete tree-sitter symbol + import extraction across grammars

Finding: `extract_symbols` dropped const-arrow functions and const-class expressions (already patched,
but ad hoc). Research the CORRECT, complete way: tree-sitter QUERIES (`.scm` capture patterns) instead
of a hand-maintained node-type allowlist; per-language definition forms (declarations, arrow/const,
exports, methods, decorators); how Aider / Codebase-Memory / tree-sitter-language-pack do it. Give a
reusable query approach + a multi-language test matrix.

## 8. Unwired-scaffold detection + the wire-or-delete discipline

Finding: several modules (`company.persona_scorecard`, `memory.EmbeddingBackend`, all of
`reliability_policy`, `fleet_report`) have zero callers, built + tested but never consumed. Research:
detecting zero-caller/dead code (`vulture`, import-graph, `ruff`), the ponytail "delete or reuse
before adding" discipline, and a CI check that flags a new public symbol with no caller and no
CLI/consumer wiring. When is an interface-only module (a Protocol) legitimately unwired vs a scaffold.

## 9. Observable best-effort error handling

Finding: corrupt/malformed JSONL lines are silently dropped with zero logging, so real ledger
corruption is invisible. Research: best-effort-but-observable handling in a LIBRARY (log/count skipped
records without forcing a logging config on the importer); structlog-vs-stdlib-logging in a library;
the "never silently swallow" rule with a metrics/counter escape hatch.

## 10. Property + mutation testing for these invariants

Finding: tests are happy-path heavy; the entrypoints actually used in production (`spawn_grade._main`,
`fleet_report`) are untested; defensive branches are unexercised. Research: hypothesis strategies for
the specific invariants here (state-machine legality, order-invariance, gate monotonicity, clamp
bounds); mutation testing (`mutmut`/`cosmic-ray`) to PROVE the tests catch the audited bugs; testing a
`__main__`/subprocess entrypoint; a target mutation score.

## Required output

Per section: correct pattern, primary source(s) with dates, a code example adapted to this stack, and
the exact test (with the concurrency/property/mutation cases where noted). This becomes the fix
playbook I apply to close the 16 high-severity findings and lift the mean grade from C to A.
