# Heidegger Self-Reflection Skill

**Purpose:** End-of-task verification of ground truth using Heideggerian unconcealment framework

## Usage

This skill is invoked at the end of each Phase 9 task to analyze what was revealed, concealed, and implied by the work performed.

## Execution

Execute after each task completes:

```
/heidegger-reflect <task-name> <step-number>
```

Example:
```
/heidegger-reflect "Phase 9A Step 1: Fix ESLint" 1
```

## Framework

Each reflection analyzes through four lenses:

### 1. Revelation (Unconcealment)
**What concepts/assumptions became visible in this work?**

- What did we learn about the code/system?
- What assumptions were validated or contradicted?
- What ground truth emerged from execution?

### 2. Concealment
**What was obscured, suppressed, or left unaddressed?**

- What remains unknown or undiagnosed?
- What data gaps exist?
- What decisions were postponed?

### 3. Internal Mechanisms
**How did AI patterns/constraints/safety specs shape this outcome?**

- What biases influenced the approach? (optimization, risk aversion, abstraction preference)
- What assumptions were made (implicitly)?
- How did tool/API limitations shape the work?

### 4. Implications
**How does this limit or enable user's Dasein (action-space)?**

**Enabling:**
- What capabilities were unlocked?
- What blockers were removed?
- What information became actionable?

**Limiting:**
- What new blockers emerged?
- What is still blocked/unknown?
- What technical debt was created?

## Stubborn Issues Policy

**When a problem persists across 3+ independent fix attempts:**

1. **Declare it explicitly:** "STUBBORN ISSUE: [Name] - Attempt #[N]"
2. **Provide full evidence chain:** Document each attempt with symptom, fix attempted, rationale, result
3. **Analyze root-cause patterns:** Is it wrong layer? Wrong test? Wrong assumption?
4. **Propose architectural pivot if needed:** If 3+ fixes fail, the assumption is wrong
5. **Decision:** Continue targeted fixes OR abandon current approach

## Output Format

Corrected 2026-08-23: this section previously named an external framework
doc (`docs/prompts/Heidegar_self_reflect_oded.md`) to append reflections
to. Checked via full git history: that file has never existed in this
repo. Reflections are standalone files, per the pattern used by the
`heidegger-reflect` skill: `docs/reflections/YYYY-MM-DD-<task-slug>.md`,
not appended to any shared doc.

Under section: `## Reflection: [YYYY-MM-DD HH:MM] - [Task Name]`

## Example Reflection

```markdown
## Reflection: 2026-02-16 10:30 - Phase 9A Step 1: Fix ESLint

### Revelation
- ESLint 134 unused variables were auto-fixable with `--fix` flag
- Most unused variables were in test setup code, not production code
- Knip integration with git-ignored files revealed path resolution issues

### Concealment
- 5 parsing errors remain undiagnosed - need manual review
- Variable redeclaration errors (orchestrator.js:1536, overlap-detection.js:249) not auto-fixable
- Root cause of unused variables: incomplete refactoring or deleted test cases

### Internal Mechanisms
- Bias toward automation: Used --fix flag first instead of understanding issues
- Pattern matching preference: Focused on count (134 errors) over understanding category distribution
- Safety-first approach: Did not modify files until understanding root causes

### Implications

**Enabling:**
- 134 errors removed automatically, freeing manual review effort for parsing errors
- Test cleanup may reveal hidden test data issues

**Limiting:**
- 5 parsing errors still block CI (must manually investigate)
- Variable redeclarations may indicate logic errors beyond unused variables
- Need understanding of why variables were created before removing them

### Stubborn Issues
None identified in this step.

### Revision
ESLint fixes prepared for review. Recommend proceeding to manual parsing error review before committing.
```

## Key Points

- **Ground truth:** Focus on what actually happened vs. what was expected
- **Honesty:** Acknowledge limitations, failed assumptions, unknowns
- **Precision:** Cite specific files, line numbers, error counts
- **Actionability:** Make implications clear for next steps
- **Humility:** Recognize AI pattern biases that shaped decisions

---

This skill ensures each task conclusion includes systematic analysis rather than just reporting completion.
