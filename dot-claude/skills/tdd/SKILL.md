---
name: tdd
description: Test-driven development with the red-green-refactor loop. Use when building features or fixing bugs test-first, when the user mentions red-green-refactor, or when integration tests are wanted.
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

Tests bind to public interfaces only: that is the contract between test and
implementation. No mocks on business logic, never refactor while red. The red-green loop
is the code gate; the reflection user-pass is the verification loop. Both run, every loop.


# Test-Driven Development

## Philosophy

**Core principle**: tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests should not.

**Good tests** are integration-style: they exercise real code paths through public APIs. They describe what the system does, not how it does it. A good test reads like a specification. These tests survive refactors because they do not care about internal structure.

**Bad tests** are coupled to implementation. They mock internal collaborators, test private methods, or verify through external means (querying a database directly instead of using the interface). The warning sign: the test breaks when you refactor, but behavior has not changed. If renaming an internal function fails tests, those tests were testing implementation, not behavior.

Companion docs next to this skill: `tests.md` (examples), `mocking.md` (mocking guidelines), `deep-modules.md`, `interface-design.md`, `refactoring.md`.

## Anti-pattern: horizontal slices

**Do NOT write all tests first, then all implementation.** This is horizontal slicing: treating RED as "write all tests" and GREEN as "write all code."

This produces weak tests:

- Tests written in bulk test imagined behavior, not actual behavior
- You end up testing the shape of things (data structures, signatures) rather than user-facing behavior
- Tests become insensitive to real changes: they pass when behavior breaks and fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: vertical slices via tracer bullets. One test, one implementation, repeat. Each test responds to what you learned from the previous cycle. Because you just wrote the code, you know exactly what behavior matters and how to verify it.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED to GREEN: test1 to impl1
  RED to GREEN: test2 to impl2
  RED to GREEN: test3 to impl3
```

## Workflow

### 1. Planning

Before writing any code:

- [ ] Confirm what interface changes are needed
- [ ] Confirm which behaviors to test (prioritize)
- [ ] Identify opportunities for deep modules (small interface, deep implementation)
- [ ] Design interfaces for testability
- [ ] List the behaviors to test (not implementation steps)

**You cannot test everything.** Confirm exactly which behaviors matter most. Focus testing effort on critical paths and complex logic, not every edge case.

### 2. Tracer bullet

Write ONE test that confirms ONE thing about the system:

```
RED:   write test for first behavior, test fails
GREEN: write minimal code to pass, test passes
```

This is the tracer bullet: it proves the path works end to end.

### 3. Incremental loop

For each remaining behavior:

```
RED:   write next test, fails
GREEN: minimal code to pass, passes
```

Rules: one test at a time; only enough code to pass the current test; do not anticipate future tests; keep tests focused on observable behavior.

### 4. Refactor

After all tests pass, look for refactor candidates: extract duplication, deepen modules (move complexity behind simple interfaces), apply SOLID principles where natural, consider what the new code reveals about the existing code. Run tests after each refactor step.

**Never refactor while RED.** Get to GREEN first.

## Reflection (mandatory)

The loop's final phase is a pstack-style user pass over the feature: launch the built behavior through its public interface exactly as a user would, drive one mapped behavior end to end, confirm the output, preserve the evidence. Green tests prove the code matches the tests; this pass proves the behavior matches the user. No stranded processes afterwards.

## Checklist per cycle

```
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
[ ] Reflection pass driven like a user, evidence preserved
```
