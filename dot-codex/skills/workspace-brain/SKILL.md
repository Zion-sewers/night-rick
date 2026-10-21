---
name: workspace-brain
description: "Workspace Brain — Cross-Project Knowledge Index"
---

# Workspace Brain — Cross-Project Knowledge Index

**Invocation:** `/workspace-brain` or when user asks cross-project questions

## Purpose

Maintain a compact index of all projects' contracts, invariants, interfaces,
and shared patterns. Answer cross-project questions from the index instead of
expensive multi-file searches across every repo under `~/projects`.

## When to Activate

- User asks "where is X defined across projects?"
- User asks about shared contracts between services
- User needs cross-project impact analysis for a change
- User asks about canonical data models, IDs, or schemas

## Active Hive Rigs

Use `~/.hive/rigs.yaml` as the live active-project list. Each rig
must also have a project-level `.codex/hive.yaml` and `AGENTS.md`. When a
project has `.claude/`, it should include `.claude/hive.yaml` pointing Claude
agents back to the canonical Codex/Hive manifest.

Fill in one section like the templates below per project you actually run,
named after that project's own folder under `~/projects/`.

### \<voice-training-platform\>

- **Location:** `~/projects/<voice-training-platform>`
- **Domain:** Voice-based sales training platform with ElevenLabs agents,
  Azure Functions, PostgreSQL, scoring, reports, and multilingual training.
- **Key Contracts:**
  - The training-app DB user is isolated to its own dedicated database.
  - ElevenLabs sessions complete through timer/webhook sync.
  - User-facing training data and reports are sensitive.
- **Source of Truth:** `AGENTS.md`, `.codex/hive.yaml`, then `CLAUDE.md`
- **Automation Focus:** timers/webhooks, report reliability, HMAC validation,
  Key Vault usage, session-completion regression tests.

### \<agent-project\>

- **Location:** `~/projects/<agent-project>`
- **Domain:** Customer-service agent for production Chatwoot
  channels and Foundry prompt/eval workflows.
- **Key Contracts:**
  - CRM access is read-only.
  - Bot response phrases must not overlap escalation detector keywords.
  - There is no safe test-environment assumption for customer inboxes.
- **Source of Truth:** `AGENTS.md`, `.codex/hive.yaml`, then `CLAUDE.md`
- **Automation Focus:** Foundry prompt drift, Chatwoot/CRM boundaries,
  deterministic classifiers, multilingual evals, output sanitization.

### \<qc-project\>

- **Location:** `~/projects/<qc-project>`
- **Domain:** Azure Functions API for transcript translation and grounded Q&A
  over telephony call segments.
- **Key Contracts:**
  - Q&A and summaries must cite segment evidence.
  - Session memory is process-local and can miss after scale-out or cold start.
  - Deploy through CI only.
- **Source of Truth:** `AGENTS.md`, `.codex/hive.yaml`, then `CLAUDE.md`
- **Automation Focus:** API contracts, `QAResponse` shape, target-language
  behavior, Azure OpenAI/Key Vault drift, no-storage guarantees.

### \<video-project\>

- **Location:** `~/projects/<video-project>`
- **Domain:** Short-form video analysis app: STT, OCR, vision, synthesis, and
  standalone report rendering.
- **Key Contracts:**
  - Uploaded media, frames, transcripts, OCR, and reports are sensitive.
  - Cloud secrets should use managed identity and Key Vault.
  - CI should prefer recorded/no-network fixtures.
- **Source of Truth:** `AGENTS.md`, `.codex/hive.yaml`, then `README.md`
- **Automation Focus:** ACA/Bicep deploy path, Streamlit upload, Telegram bot
  roadmap, no-network tests, render/schema smoke checks.

### \<campaign-scoring-project\>

- **Location:** `~/projects/<campaign-scoring-project>`
- **Domain:** Marketing campaign, CRM/call-analysis, MCP/reporting, workbook,
  Foundry, and evaluation workspace.
- **Key Contracts:**
  - CRM, campaign, call, workbook, and customer data are sensitive.
  - Workbook/report raw-data lineage must be preserved.
  - Public MCP exposure requires APIM/Entra/role-scope review.
- **Source of Truth:** `AGENTS.md`, `.codex/hive.yaml`, then `CLAUDE.md`
- **Automation Focus:** MCP gateway security, report lineage, Foundry prompt
  drift, connector eval gates, workbook regression.

## Cross-Project Patterns

### Shared Tooling Standards

- **JavaScript/TypeScript:** bun, bunx (NEVER npm/npx/yarn unless a project
  explicitly requires it)
- **Python:** uv (NEVER direct pip/poetry/pipenv unless a project explicitly
  requires it)
- **Quality:** ESLint + Knip (JS), Ruff (Python)
- **Policy:** `~/AGENTS.md`

### Shared Testing Standards

- Unit > Integration > Contract > E2E
- Property-based tests for invariants
- Regression suite for every prod bug
- Coverage targets: >90% (Python), >80% (JavaScript)
- Policy: `~/docs/testing_practices.txt`

### Shared Security Policy

- Sandbox ON, network OFF by default
- Secrets isolation, MCP authorization
- DOMPurify for HTML, parameterized SQL only
- Policy: `~/docs/research/2026-05-07-ai-bot-security-best-practices.md`

## How to Use This Skill

When a cross-project question arrives:

1. Check this index FIRST (no file reads needed)
2. If the index covers it, answer directly
3. If the index is insufficient, read the specific project's CLAUDE.md or
   MEMORY.md and then UPDATE this index with the new information
4. Do not scan every repo under `~/projects`; start with the active rigs
   listed above unless the user explicitly widens scope.

## Maintenance

This index should be updated when:

- A new project is added to ~/projects/
- A project's contracts or invariants change materially
- A cross-project dependency is discovered

Update by editing this SKILL.md directly (it IS the index).
