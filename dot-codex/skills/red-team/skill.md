# Red Team Skill - Test-Driven Development Enforcement

**Focus:** Code quality and functional correctness through TDD, NOT security testing.

## Purpose

Verify that:
1. Code is developed test-first (failing tests → implementation)
2. Tests are comprehensive and follow SOTA patterns
3. Code meets functional requirements
4. Implementation is production-ready

## How to Invoke

```bash
/red-team

# In Claude Code, describe what needs review:
Review the ingestion pipeline for test coverage gaps
Ensure aspect ratio lock is fully tested before deployment
Audit test quality using mutation testing metrics
Check that all 10 system invariants have property tests
```

## What Red Team Checks

### 1. Test-First Discipline
- [ ] Tests written BEFORE implementation
- [ ] Failing tests shown first, then passing fix
- [ ] No code without corresponding tests
- [ ] Regression tests for every bug fix

### 2. Test Coverage & Quality
- [ ] >80% code coverage (JavaScript)
- [ ] >90% code coverage (Python)
- [ ] Property-based tests for invariants
- [ ] No skipped/commented tests
- [ ] Mutation testing score >80%

### 3. Functional Correctness
- [ ] Unit tests pass (fast, no IO)
- [ ] Integration tests pass (real components)
- [ ] Contract tests validate APIs
- [ ] Performance baselines not regressed
- [ ] Golden master tests for complex outputs

### 4. SOTA Testing Standards
Reference: `projects/<ts-project-with-tiers>/test/testing_best_practices.md`

**Required test types:**
- Type checking & linting (static)
- Unit tests (pure logic)
- Property-based tests (invariants)
- Component tests (real deps)
- Integration tests (full stack)
- Regression suite (prod bugs)

**By context:**
- External input → Fuzz tests
- Algorithm-heavy → Model-based tests
- Distributed → Contract + Chaos tests

### 5. Code Implementation Quality
- [ ] ES2017 compliance (project-specific target)
- [ ] Clean architecture patterns followed
- [ ] No dead code (knip passes)
- [ ] Linting clean (ESLint, Ruff)
- [ ] Type checking passes (tsc, mypy)

## Output

Red team provides:
- ✅ Tests that pass vs ❌ tests that fail
- Coverage metrics and gaps
- Mutation testing results (test strength)
- Recommendations for TDD improvements
- Code quality score (A-F)

## NOT in Scope

- Security testing / penetration testing
- OWASP vulnerability scanning
- Authorization/authentication bypass
- Network security concerns
- Secret detection
- Adversarial testing

(These are handled by separate security processes)

## Example Session

```
User: /red-team

Red Team: I'll audit test coverage and TDD discipline for the project.

Checking:
1. Test-first workflow (failing tests shown first?)
2. Coverage gaps (target >90% for Python, >80% for JS)
3. SOTA test types implemented
4. Mutation testing strength
5. Functional correctness (all tests passing)

Report:
- Coverage: 78% (Python) - Gap: need +12%
- Test types: Unit ✅, Property ✅, Integration ⚠️ (only 3 tests)
- Mutation score: 72% (good, target >80%)
- Functional: ✅ All tests passing
- Grade: B+ (strong coverage, add more integration tests)

Recommendations:
1. Add 5 integration tests for cross-module flows
2. Implement mutation testing in CI (nightly)
3. Add property tests for normalization invariants
```

## CI Integration

Red team checks run:
- **Per PR:** Coverage + test types
- **Nightly:** Mutation testing, performance baselines
- **Pre-release:** Full regression, functional verification
