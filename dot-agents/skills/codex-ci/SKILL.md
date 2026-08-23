---
name: codex-ci
description: AI-augmented CI workflows for local fix/review, mutation checks, and TDD assistance, with optional Azure Foundry remote review.
---

# /codex-ci -- AI-Augmented CI

**Invocation:** `/codex-ci <mode> [args]`

## Modes

| Mode | Engine | What It Does |
|------|--------|-------------|
| `fix` | Codex CLI (local) | Captures test failures, proposes source fixes |
| `review` | Codex CLI (local) | Reviews uncommitted/branch diff locally |
| `review-remote` | Azure Foundry (cloud) | Reviews diff via a dedicated cloud reviewer deployment |
| `mutate` | Codex CLI (local) | Generates semantic mutants to test suite gaps |
| `tdd <spec>` | Codex CLI (local) | Generates failing test, then minimal implementation |
| `tdd-green` | Codex CLI (local) | Generates implementation for existing TDD test |

## How to Execute

```bash
bash ~/.Codex/skills/codex-ci/run.sh <mode> [args...]
```

## Local Modes (Codex CLI)

### fix

Runs project tests. On failure, feeds output to `codex exec` for fix proposal.

### review

Uses `codex review --uncommitted` (or `--base main`) with `-o` for output capture.
Reviews for: security, architecture, risk, quality. Output saved to `qa_reports/codex-review/`.

### mutate

Identifies changed files, generates 5 semantic mutations per file via `codex exec`.
Surviving mutants = test suite gaps.

### tdd / tdd-green

TDD RED: `codex exec` generates a failing test from spec.
TDD GREEN: `codex exec` generates minimal implementation to pass.

## Remote Mode (Azure Foundry)

### review-remote

Sends diff to a dedicated Azure Foundry review deployment (name it in your own
`projects.json`). Runs two passes: code review + safety audit. Auth via `az login` + Azure KV (`<your-key-vault-name>`).
Falls back to local `review` if credentials unavailable.

## Project Config

Per-project settings in `~/.Codex/skills/codex-ci/projects.json`.
Auto-detects project from `git rev-parse --show-toplevel`.

Fields: `test_cmd`, `full_test_cmd`, `lint_cmd`, `constraints`, `mutation_targets`.

## Bin Script

`~/.Codex/bin/codex-ci-review.sh` provides a standalone wrapper:
- `--local`: Delegates to `run.sh review`
- `--cloud`: Delegates to `run.sh review-remote`
- `--intake`: Project intake audit (cloud or local)
- Default: auto-detect based on `az login` status

## Post-Execution

Every mode prints: `CODEX-CI COMPLETE. Run /reflect before claiming done.`

## Security

- Local: `codex exec --sandbox read-only` (no writes)
- Cloud: Azure KV for API keys, never in CLI args
- Never auto-merges, never auto-commits, never pushes
