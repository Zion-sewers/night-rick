---
name: azure-keyvault-secrets
description: Load MCP and project secrets from Azure Key Vault into runtime dotenv files for Codex sessions.
allowed-tools: ["Bash", "Read", "Write"]
---

## When to use
- MCP/API keys are missing in the current session.
- You need consistent secrets loading across your global config and multiple per-project scopes.
- You want lazy loading (fetch only when needed) instead of manual ad-hoc exports.

## Runtime Components
- Sync utility: `~/.codex/bin/codex-secrets-sync`
- Vault config: `~/.codex/secrets/keyvault.conf`
- Global map: `~/.codex/secrets/global.map`
- Per-project map: `~/projects/<project-name>/.codex/secrets.map` (one per project that needs secrets)

## Common Commands
- MCP keys only (auto scope): `~/.codex/bin/codex-secrets-sync --project auto --mcp-only`
- Per-project full scope: `~/.codex/bin/codex-secrets-sync --project <project-name>`
- Require specific vars: `~/.codex/bin/codex-secrets-sync --project auto --require PERPLEXITY_API_KEY --require APIFY_API_KEY`

## Notes
- `codex-with-mcp` and `mcp-smoke-check` call this utility lazily when MCP key vars are missing.
- No secret values are printed.
- If `az` is not logged in, run `az login` first.
