---
name: azd
description: Azure Developer CLI (`azd`) workflow — init, provision, deploy, teardown. Use for projects with `azure.yaml` (infra-as-code + app deploy bundled). Complements `azure-devops` (ADO CLI) and `azure-foundry` (agent ops). Includes install helper if azd missing.
---

# Azure Developer CLI (`azd`)

`azd` is Microsoft's end-to-end developer workflow tool: one command takes a template + bicep/terraform + app code and provisions + deploys to Azure. Useful for spinning up Container Apps, Function Apps, or Foundry projects with IaC in one shot.

Docs: https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/

## When to use

- A project has `azure.yaml` at the root — `azd` is the intended workflow.
- Creating a new Azure-hosted project from a template.
- Local `azd up` for a full dev-environment spin-up.
- Tearing down test environments safely.

## When NOT to use

- Production deploys — those go through CI (Azure DevOps pipelines). `azd deploy` is for dev/test environments.
- Projects without `azure.yaml` — use `az` CLI directly.

## Install (one-time)

```bash
# Linux / WSL2
curl -fsSL https://aka.ms/install-azd.sh | bash

# Verify
azd version
```

If the install script was downloaded but not executed:

```bash
ls /tmp/install-azd.sh 2>/dev/null && bash /tmp/install-azd.sh
```

Hook: `self-heal-check.sh` will nudge if `azd` is missing and `azure.yaml` is in the project root.

## Core flow

```bash
# First time in a project with azure.yaml
azd auth login --use-device-code

# Provision + deploy
azd up                  # provision infra + deploy code + start services
azd provision           # infra only
azd deploy              # code only
azd monitor             # watch logs

# Teardown
azd down                # prompts before destroying
azd down --force        # skip prompts (careful)
```

## Environments

```bash
azd env list
azd env new dev         # create env 'dev'
azd env select dev
azd env set KEY value   # set env var
azd env get-values      # dump to stdout (careful with secrets)
```

Environment state lives under `.azure/<env-name>/`. Do NOT commit `.azure/` — add to `.gitignore` if missing.

## Safety rules

- `azd down` on a prod-like environment is destructive. Always `azd env select <name>` first and confirm you're on dev/test.
- `azd up` creates resources that cost money. Run `azd provision --preview` first on unfamiliar templates.
- `azd auth` uses the same token cache as `az`. If `az login` MFA timed out, `azd` will too — re-auth once, both are back.

## Integration with our own deploy patterns

- Our production deploys go through **Azure DevOps pipelines**, not `azd`. Use `azd` for local/dev iteration.
- Projects that DO use azd: none in production scope today. Candidates: new Foundry agent projects, a future Container App migration.
- Service connections for ADO (name your own deploy connection and KV connection) are NOT used by `azd` — azd uses your `az login` identity directly.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `azd: command not found` | not installed or not on PATH | `curl -fsSL https://aka.ms/install-azd.sh \| bash`, then `hash -r` |
| `ERROR: fetching current principal` | `az login` expired | `az login --use-device-code` |
| `ERROR: No infrastructure provider found` | missing `infra/` folder or bad `azure.yaml` | check `azure.yaml` `services.<name>.host` and `infra` settings |
| `ResourceNotFound` on `azd deploy` | infra not provisioned yet | `azd provision` first |
| hangs on `Running hooks` | user hook script waiting for input | check `.azure/hooks/*` for `read` / prompts |

## Related

- `azure-devops` skill — for PR + CI workflows (production path).
- `azure-foundry` skill — for Foundry agent ops (separate from azd).
- `deploy-prod` skill — pre-flight checklist for production deploys (always via CI, never azd).
