# Red Team Rules - TDD & Code Quality

paths:
- "**/*.test.js"
- "**/*.test.ts"
- "tests/**/*.py"
- "src/**/*.js"
- "src/**/*.ts"

## Must Follow: Test-Driven Development

### Test-First Workflow (MANDATORY)

**Pattern:**
```
1. Write failing test (RED)
2. Run test, verify it fails
3. Write minimal implementation (GREEN)
4. Run test, verify it passes
5. Refactor if needed (REFACTOR)
```

**Verification:**
- [ ] Test written BEFORE code commit
- [ ] Failing test shown first in PR
- [ ] Implementation is minimal (YAGNI)
- [ ] No code without tests

### Coverage Requirements

**JavaScript/TypeScript:**
- Target: >80%
- Enforce: `bun run test && npm run coverage`

**Python:**
- Target: >90%
- Enforce: `uv run pytest --cov-fail-under=90`

### Test Quality Metrics

**Mutation Testing (Measure test strength):**
```bash
# Run nightly
bun run test:mutation  # JavaScript
uv run mutmut run      # Python

# Target: >80% mutation score
# If mutants survive, tests are weak
```

**Property-Based Tests (Not just examples):**
```javascript
// ❌ Weak: Just examples
test('sorting works', () => {
  expect(sort([3,1,2])).toEqual([1,2,3]);
});

// ✅ Strong: Invariants
test('sort always preserves length and order', () => {
  fc.assert(fc.property(fc.array(fc.integer()), arr => {
    const sorted = sort(arr);
    expect(sorted.length).toBe(arr.length);
    expect(isSorted(sorted)).toBe(true);
  }));
});
```

### Regression Discipline

**Every production bug MUST:**
1. Have a failing test FIRST
2. Show test failure in PR
3. Fix implementation (minimal)
4. Test passes
5. Test added to permanent regression suite

```bash
# Workflow example:
1. Create test: tests/regression/bug-45-logo-distortion.test.js (FAILS)
2. Fix code: src/domain/geometry/aspect-ratio-lock.js
3. Run test: (PASSES)
4. Commit: "fix(geometry): prevent logo distortion in layout"
   - Regression test in commit
   - Never removed
```

### Functional Correctness Checklist

Before merging ANY code:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All contract tests pass (APIs, schemas)
- [ ] Coverage >80% (JS) or >90% (Python)
- [ ] No tests skipped (@skip, .only, pending)
- [ ] Linting passes (ESLint, Ruff)
- [ ] Type checking passes (tsc, mypy)
- [ ] Performance not regressed
- [ ] New code has matching tests

### SOTA Test Types (From testing_best_practices.md)

**Every project MUST have:**
1. ✅ Unit tests (pure logic, no IO)
2. ✅ Property-based tests (invariants, not examples)
3. ✅ Integration tests (real components together)
4. ✅ Regression suite (every prod bug → permanent test)
5. ✅ Performance baseline tests

**By context:**
- External input (parsing, APIs) → Fuzz tests
- Algorithm-heavy (layout, compilation) → Model-based tests
- Distributed systems (microservices) → Contract + Chaos tests

### Red Team Audit Questions

When reviewing code:

1. **Test-First?** Are tests written before implementation?
2. **Coverage?** Is coverage >80% JS / >90% Python?
3. **Quality?** Mutation testing strength >80%?
4. **Regression?** Does every bug have a permanent test?
5. **Functional?** Do all tests pass? Are any skipped?
6. **Architecture?** Tests verify system invariants?
7. **Determinism?** Tests use fixed seeds, frozen time?
8. **Isolation?** Tests reset mocks, don't pollute global state?

### Red Team Output Format

```markdown
## Test Coverage Audit

### Coverage Metrics
- JavaScript: 87% (target: >80%) ✅
- Python: 92% (target: >90%) ✅

### Test Types Implemented
- Unit tests: ✅ (45 tests)
- Property tests: ✅ (12 tests, via fast-check)
- Integration tests: ⚠️ (3 tests, add 5 more)
- Regression suite: ✅ (28 permanent bug tests)
- Performance: ✅ (4 baselines)

### Mutation Testing
- Score: 78% (target: >80%) ⚠️
- Surviving mutants: 8 (need stronger tests)
- Recommendation: Add property tests for edge cases

### Code Quality
- ESLint: ✅ (0 errors, 2 warnings)
- Type checking: ✅ (tsc --noEmit clean)
- Knip (dead code): ✅ (0 unused)

### Functional Status
- All tests passing: ✅
- No skipped tests: ✅
- Coverage gaps: None identified

### Grade: A- (Excellent test discipline)

### Recommendations
1. Add 5 integration tests for cross-module flows
2. Implement mutation testing in nightly CI
3. Increase property test coverage for invariants
```

### References

- SOTA Testing: `projects/<ts-project-with-tiers>/test/testing_best_practices.md`
- TDD: Kent Beck, "Test Driven Development: By Example"
- Property-Based Testing: Hypothesis docs, fast-check docs
- Mutation Testing: Stryker, mutmut documentation
