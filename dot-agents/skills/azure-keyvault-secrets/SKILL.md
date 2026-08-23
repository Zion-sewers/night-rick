---
name: azure-keyvault-secrets
description: Sync MCP/project secrets from Azure Key Vault for Codex sessions.
---

## Purpose
Provide one formal secrets path for global + per-project scopes when running Codex.

## Commands
- Auto scope, MCP keys: `~/.Codex/bin/Codex-secrets-sync --project auto --mcp-only`
- Per-project scope: `~/.Codex/bin/Codex-secrets-sync --project <project-name>`

## Files
- `~/.Codex/secrets/keyvault.conf`
- `~/.Codex/secrets/global.map`
- `projects/<project-name>/.Codex/secrets.map` (one per project that needs secrets)

## Notes
- `~/.Codex/bin/perplexity-mcp-launch` lazily calls secret sync if `PERPLEXITY_API_KEY` is missing.
- This wrapper delegates to `~/.codex/bin/codex-secrets-sync` for one source of truth.
