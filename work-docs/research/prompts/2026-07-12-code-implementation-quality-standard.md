# Research prompt: the code implementation quality standard (per-file / per-function / per-line)

Run this as a deep-research pass. Goal: produce a dated, primary-sourced SOTA standard I can grade a
codebase against per-file, per-function, and per-line, and a ready-to-apply rubric + tool commands.
Context: the target is a zero-runtime-dependency Python package (uv + ruff + mypy --strict + pytest),
tree-sitter is the only external dep, single-operator local harness, agent-legible code (agents read
it). Output lands in work-docs/research/ as one or more dated `.md` docs. Prefer primary sources (PEPs, tool docs,
Google/NumPy style guides, arXiv/eng-blogs) with dates; flag anything unverified.

## Q1 - Docstring standard (the level, per scope)

- Per MODULE: what a module-level docstring must contain (purpose, why-it-exists, key contracts). Cite
  PEP 257, Google Python Style Guide, NumPy docstring standard. What is the 2026 AI-native convention
  (docstrings written so an LLM agent can parse intent + wiring, not just humans)?
- Per CLASS / per FUNCTION: when a function REQUIRES a docstring vs when a clear signature suffices
  (the "conditional docstring" rule); required sections (Args / Returns / Raises / Examples) and when
  each is mandatory; how to document invariants, side effects, and failure modes.
- Per LINE: when an inline comment is warranted (the "why not what" rule) vs comment-as-code-smell.
- Tooling to MEASURE docstring coverage + style: `interrogate`, `pydocstyle`, ruff `D` (pydocstyle)
  rules, `darglint` (Args/Returns match signature). Give the exact config + commands to enforce a
  threshold (e.g. 100% public-symbol docstring coverage) and which ruff D-codes to enable.

## Q2 - Type + interface standard

- Full-annotation bar for mypy --strict; when to use typing.Protocol vs ABC; avoiding `Any` abuse and
  `dict[str, Any]` as a lazy DTO; when to promote a dict to a typed struct (dataclass / msgspec /
  pydantic). Cite mypy strict docs + PEP 544 (Protocol). Give the rule for typed DTOs at boundaries.

## Q3 - Error-handling + boundary standard

- Fail-closed at boundaries, no bare `except`, no silently-swallowed errors (best-effort must log),
  typed errors, validate-upstream-return-502. The five canonical boundary tests (valid / invalid-input
  / missing-config / missing-resource / timeout). What separates grade-A error handling from C. Cite
  sources; give a per-line checklist a reviewer applies.

## Q4 - Simplicity / complexity standard

- Cyclomatic + cognitive complexity thresholds (radon `cc`, ruff `C901` max-complexity value the
  field uses), function-length and parameter-count limits, dead-code detection (`vulture`), duplicate-
  builder / speculative-abstraction smells (ponytail). Give the numeric thresholds and the tool
  commands.

## Q5 - Testing standard

- No-mocks-for-business-logic (recorded fixtures / real components), property-based testing
  (hypothesis) where invariants exist, mutation testing (`mutmut` / `cosmic-ray`) target score,
  coverage threshold (diff-coverage vs whole-repo), per-behavior TDD (RED before GREEN, not all-tests-
  then-all-code). What test_grade A vs C looks like per module. Cite sources.

## Q6 - The GRADING RUBRIC (the deliverable I most need)

Synthesize Q1-Q5 into a single measurable A-F rubric that grades a source file on: docstring, types,
error-handling, correctness, simplicity, testing. For each grade band give OBSERVABLE criteria (not
vibes) and the tool that measures it, so two reviewers grade the same file the same. Include a
per-function and per-line checklist a human or agent applies mechanically.

## Q7 - Apply it to this stack

Given zero-dep stdlib Python + one tree-sitter module + mypy --strict: which of the above are
non-negotiable vs nice-to-have here; the exact `pyproject.toml` `[tool.ruff.lint]` (D + C + others) and
mypy config to enforce the standard in CI; and the smallest set of dev tools to add (interrogate,
darglint, radon, vulture, hypothesis, mutmut) with commands, without breaking the zero-RUNTIME-dep rule
(dev deps are fine).

## Required output

For each Q: the standard (concrete rules), primary sources with dates, tool + exact command/config,
and the A/C/F distinction. End with (a) the unified A-F rubric from Q6 and (b) a copy-paste
`pyproject.toml` dev-tooling + ruff/mypy config block from Q7. This becomes the control doc I lift
every module to before it is graded A.
