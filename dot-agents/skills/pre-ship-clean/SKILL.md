---
name: pre-ship-clean
description: Pre-ship codebase hygiene — dead code audit (knip/ruff/vulture), .gitignore security hardening, SOTA README + Wiki update with mermaid/flow diagrams, directory cleanup, code review verification. Runs as gate before /commit-push-pr. Never auto-deletes — examines first.
---

# /pre-ship-clean

Full codebase hygiene pass before shipping. Audits dead code, hardens .gitignore, updates README/Wiki to SOTA standard, cleans directories, and verifies code review best practices.

## Triggers

- Automatically before `/commit-push-pr` (wired as step 0)
- Manually when codebase needs cleanup
- Before major releases or demos

## When NOT to Use

- Abbreviated mode (<3 files, <20 LOC) — skip unless explicitly invoked
- Mid-implementation — finish the feature first, then clean

## Usage

```
/pre-ship-clean [--skip-readme] [--skip-wiki] [--full]
```

- `--skip-readme`: Skip README generation/update
- `--skip-wiki`: Skip Wiki update
- `--full`: Run all phases including slow analysis (vulture, deep knip)

## Instructions

Run phases sequentially. Each phase produces a report section. At the end, present a unified report and ask for approval before applying destructive changes.

---

### Phase 0: Detect Project Stack

Determine project type from CWD:

| CWD matches | Stack | Dead code tool | Lint tool |
|-------------|-------|---------------|-----------|
| `*/<agent-project>*` | Python | `ruff check --select F401,F811,F841` | `ruff check .` |
| `*/<python-project>*` | Python + JS | ruff (Python) + knip (JS) | `ruff check src/` + `bun run lint` |
| `*/<ts-project-with-tiers>*` | JS/TS | `bunx knip` | `bun run lint` |
| `*/<qc-project>*` | Python | `ruff check --select F401,F811,F841` | `ruff check .` |
| `package.json` found | JS/TS | `npx knip` | `npx eslint .` |
| `pyproject.toml` found | Python | `ruff check --select F401,F811,F841` | `ruff check .` |

Store detected stack for use in subsequent phases.

---

### Phase 1: Dead Code Audit

**Principle: NEVER auto-delete. Every line of code was written for a reason. Examine, classify, report.**

#### 1a. Automated detection

Run the appropriate tool for detected stack:

**Python projects:**
```bash
# Unused imports
ruff check --select F401 --output-format json . 2>/dev/null || true

# Unused variables
ruff check --select F841 --output-format json . 2>/dev/null || true

# Redefined unused
ruff check --select F811 --output-format json . 2>/dev/null || true

# If --full flag: deep unused code detection
# pip install vulture && vulture . --min-confidence 80
```

**JS/TS projects:**
```bash
# Knip: unused files, exports, dependencies, types
npx knip --reporter compact 2>/dev/null || bunx knip --reporter compact 2>/dev/null || true
```

#### 1b. Manual pattern scan (all projects)

Search changed source files for dead code signals:

```bash
# Commented-out code blocks (>3 consecutive lines)
git diff --name-only HEAD | xargs grep -n '^\s*#.*=\|^\s*//.*{' 2>/dev/null | head -30

# Unreachable code after return/raise
grep -rn 'return\|raise' --include='*.py' --include='*.ts' --include='*.js' src/ | head -20

# Functions defined but never called (check imports/references)
# For each function in changed files, grep for usage elsewhere
```

#### 1c. Classification

For EACH finding, classify as:

| Category | Action | Example |
|----------|--------|---------|
| **Truly dead** | Safe to remove (with approval) | Import never used, variable assigned but never read |
| **Potentially refactorable** | Keep, but flag for refactor | Function used in 1 place, could be inlined |
| **Needs investigation** | Keep, ask user | Looks unused but may be called dynamically, via reflection, or from external system |
| **False positive** | Ignore | Framework magic, decorators, `__all__` exports, test fixtures |

**Output format for report:**
```
DEAD CODE AUDIT
===============
Truly dead (safe to remove):
  - src/foo.py:12 — unused import `os` (F401)
  - src/bar.py:45 — variable `tmp` assigned, never used (F841)

Potentially refactorable:
  - src/utils.py:88 — `format_date()` called only from `handler.py:23`, consider inlining

Needs investigation:
  - src/router.py:55 — `_legacy_handler()` appears unused but name suggests backward compat

False positives (ignored):
  - src/models.py:10 — `__all__` export (framework pattern)
```

---

### Phase 2: .gitignore Security Hardening

Read the template at `~/.Codex/skills/pre-ship-clean/templates/gitignore-security.txt`.

1. Read current `.gitignore`
2. Diff against the security template — find missing patterns
3. **Critical security patterns** (must be present):
   - `*.pem`, `*.key`, `*.p12`, `*.pfx` — private keys
   - `.env`, `.env.*`, `!.env.example` — secrets
   - `credentials.json`, `service-account*.json` — cloud creds
   - `local.settings.json` — Azure Functions secrets
   - `**/*.png`, `**/*.jpg` (with explicit exceptions for tracked logos)
4. Check for files that SHOULD be gitignored but are tracked:
   ```bash
   # Find tracked files that match gitignore patterns
   git ls-files | grep -E '\.(pem|key|p12|env|secret)$' | head -10
   git ls-files | grep -iE '(credential|secret|token|password)' | head -10
   ```
5. Generate a diff showing what lines to add to `.gitignore`
6. **Do NOT auto-apply** — present the diff and ask for approval

**Output format:**
```
.GITIGNORE AUDIT
================
Missing critical patterns:
  + *.pem
  + *.key
  + service-account*.json

Missing recommended patterns:
  + .mypy_cache/
  + .ruff_cache/

Tracked files that should be gitignored:
  ! NONE (clean)

Proposed additions: [N] lines
Apply? [present diff, wait for approval]
```

---

### Phase 3: Directory Hygiene

Scan for directory/file mess:

```bash
# Empty directories
find . -type d -empty -not -path './.git/*' -not -path './node_modules/*' -not -path './.venv/*' 2>/dev/null

# Temp/stale files in project root or src
find . -maxdepth 3 -name '*.tmp' -o -name '*.bak' -o -name '*.orig' -o -name '*.rej' \
  -not -path './.git/*' -not -path './node_modules/*' 2>/dev/null

# Misplaced files (screenshots in src, logs in root)
find . -maxdepth 2 \( -name '*.png' -o -name '*.jpg' -o -name '*.log' \) \
  -not -path './.git/*' -not -name 'ai_department_logo.png' 2>/dev/null

# Orphaned __pycache__ not in .gitignore
find . -type d -name '__pycache__' -not -path './.git/*' -not -path './.venv/*' 2>/dev/null

# Files >500 LOC (project intake standard)
find . -name '*.py' -o -name '*.ts' -o -name '*.js' | \
  grep -v node_modules | grep -v .venv | \
  xargs wc -l 2>/dev/null | awk '$1 > 500 {print}' | sort -rn | head -10
```

**Output format:**
```
DIRECTORY HYGIENE
=================
Empty dirs: [list or NONE]
Temp/stale files: [list or NONE]
Misplaced files: [list or NONE]
Oversized files (>500 LOC): [list or NONE]

Recommended actions:
  - Remove empty dir: tests/fixtures/old/
  - Delete temp file: src/handler.py.bak
```

---

### Phase 4: README Update (skip if --skip-readme)

Read the README template from `~/.Codex/skills/pre-ship-clean/templates/readme-template.md`.
Read the ASCII logo from `~/.Codex/skills/pre-ship-clean/assets/ascii-logo.txt`.

1. **Read current README.md** (if exists)
2. **Auto-detect project metadata:**
   - Project name: from `package.json`, `pyproject.toml`, or directory name
   - Description: from existing README or package metadata
   - Version: from `__version__`, `package.json`, or git tags
   - Runtime: from project files (Azure Functions, Node, Python, etc.)
   - Entry points: from source files
   - API endpoints: grep for route/endpoint definitions
   - Environment variables: grep for `os.environ`, `process.env`, config files
   - Test commands: from project toolchain (see Phase 0)
   - Dependencies: from `requirements.txt`, `pyproject.toml`, `package.json`

3. **Generate mermaid diagrams** by analyzing the code:
   - **Architecture diagram**: module dependencies and data flow
   - **Sequence diagram**: main request/response flow
   - **Deployment flow**: branch strategy and CI/CD pipeline

4. **Fill template sections:**
   - Status table with real values
   - Architecture with accurate mermaid from code analysis
   - Features extracted from module purposes
   - Use Cases derived from entry points and API contracts
   - Quick Start with actual install/run/test commands
   - Flow diagrams reflecting real request processing
   - Configuration table from actual env vars
   - Project structure from actual directory tree
   - Good to Know: gotchas, caveats, prerequisites found during analysis
   - Testing section with actual test commands and approximate runtimes

5. **Preserve existing content** where it's accurate — don't blindly overwrite custom sections
6. **Include both logos**: PNG image tag + ASCII art in `<pre>` block
7. Present the updated README for approval before writing

---

### Phase 5: Wiki Update (skip if --skip-wiki)

Check if `docs/wiki/` exists.

1. Read all existing wiki pages
2. For each page, verify:
   - Links still resolve (internal cross-references)
   - Code examples match current codebase
   - API references match current endpoints
   - Version numbers are current
3. Update `docs/wiki/Home.md`:
   - Ensure version/status table is current
   - Architecture diagram matches current code
   - All links to sub-pages work
4. Flag any wiki page that references deleted/renamed code
5. Present changes for approval

---

### Phase 6: SOTA Code Review Verification

Run a checklist of industry best practices against changed files:

```bash
# Get changed files (staged + unstaged)
CHANGED=$(git diff --name-only HEAD 2>/dev/null)
```

| Check | How | Severity |
|-------|-----|----------|
| No TODO/FIXME in production code | `grep -rn 'TODO\|FIXME\|HACK\|XXX' $CHANGED` (exclude test files) | BLOCK |
| No debug artifacts | `grep -rn 'console\.log\|print(\|debugger\|breakpoint()' $CHANGED` (exclude test) | BLOCK |
| No commented-out code (>3 lines) | Pattern scan for consecutive comment lines containing code | WARN |
| No magic numbers | `grep -rn '[^0-9][0-9][0-9][0-9]+[^0-9]' $CHANGED` — check for unnamed constants | WARN |
| No hardcoded secrets | `grep -rn 'password\s*=\|api_key\s*=\|secret\s*=' $CHANGED` (exclude .env.example) | BLOCK |
| No SQL injection | `grep -rn 'f".*SELECT\|\.format.*SELECT\|execute.*\+' $CHANGED` | BLOCK |
| Functions <50 LOC | `wc -l` per function in changed files | WARN |
| Files <500 LOC | `wc -l` per changed file | WARN |
| No `any` type (TS) | `grep -rn ': any\b' $CHANGED --include='*.ts'` | WARN |
| No bare `except:` (Python) | `grep -rn 'except:\|except Exception:.*pass' $CHANGED --include='*.py'` | WARN |
| No god files | Check for files named `utils`, `helpers`, `misc`, `common` in changes | WARN |
| Type annotations present | Changed Python functions have type hints; TS has no implicit any | WARN |
| No duplicate code blocks | Scan for >10 identical consecutive lines across changed files | WARN |

**Output format:**
```
CODE REVIEW VERIFICATION
========================
BLOCKING issues (must fix before ship):
  [x] No TODO/FIXME in production: PASS
  [!] Debug artifact found: src/handler.py:45 — print() statement

Warnings (should fix):
  [~] Magic number: src/config.py:12 — `timeout=30` (consider named constant)

Clean checks:
  [x] No hardcoded secrets
  [x] No SQL injection patterns
  [x] All files <500 LOC
  [x] All functions <50 LOC
```

---

### Phase 7: Unified Report

Present a single consolidated report:

```
╔══════════════════════════════════════════════╗
║         PRE-SHIP CLEAN REPORT                ║
║         {PROJECT_NAME} @ {BRANCH}            ║
╚══════════════════════════════════════════════╝

Phase 1 — Dead Code:      {PASS/WARN/FAIL} ({N} findings)
Phase 2 — .gitignore:     {PASS/WARN/FAIL} ({N} missing patterns)
Phase 3 — Dir Hygiene:    {PASS/WARN/FAIL} ({N} issues)
Phase 4 — README:         {UPDATED/SKIPPED/NO_CHANGES}
Phase 5 — Wiki:           {UPDATED/SKIPPED/NO_CHANGES}
Phase 6 — Code Review:    {PASS/WARN/FAIL} ({N} blocking, {M} warnings)

Overall: {CLEAN / NEEDS_ATTENTION / BLOCKED}

Actions requiring approval:
  1. [Dead code] Remove N unused imports
  2. [.gitignore] Add N security patterns
  3. [Directory] Remove N temp files
  4. [README] Update with current architecture
  5. [Wiki] Update version references
```

**If BLOCKED:** Do not proceed to commit-push-pr. List blocking issues.
**If NEEDS_ATTENTION:** Present warnings, let user decide.
**If CLEAN:** Proceed to commit-push-pr.

Wait for user approval on each action category before applying changes.

---

## Logo Assets

- **PNG logo**: `ai_department_logo.png` (repo root, tracked via .gitignore exception)
- **ASCII logo**: `~/.Codex/skills/pre-ship-clean/assets/ascii-logo.txt`
- Use both in README: PNG as `<img>` tag, ASCII in `<pre>` block
- Reference PNG path relative to README location

## Tool Preferences

| Tool | JS/TS | Python |
|------|-------|--------|
| Dead exports/imports | `knip` | `ruff --select F401,F811` |
| Unused dependencies | `knip` | `pip-autoremove` or manual |
| Unused files | `knip` | `vulture` (--full mode) |
| Unused variables | `knip` | `ruff --select F841` |
| Lint | `eslint` | `ruff check` |
| Type check | `tsc --noEmit` | `mypy` |
