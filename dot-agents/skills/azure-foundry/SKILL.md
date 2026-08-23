---
name: azure-foundry
description: Azure AI Foundry agent operations — list/inspect agents, deploy via `deploy_agent.py` pattern, inspect runs, manage agent memory, sync prompts, verify SDK install (Foundry SDK 2.x / OpenAI SDK / Microsoft Agent Framework). Use when working with Foundry agent repos (your own agent projects) or when prompt versions diverge between git and Foundry.
---

# Azure AI Foundry

## When to use

- Checking which prompt version is live on a Foundry agent vs git.
- Deploying an agent after a prompt or tool-definition change.
- Inspecting a run that failed (tool calls, error trace, message log).
- Enabling/inspecting the Foundry Memory feature for an agent.
- Comparing two agent versions before merging.
- Verifying which Foundry SDKs are installed in a project venv (see "SDK matrix" below).

## SDK matrix

| SDK | PyPI package | Endpoint | Use for |
|---|---|---|---|
| Foundry SDK (2.x) | `azure-ai-projects>=2.0.0` | `https://<resource>.services.ai.azure.com/api/projects/<project>` | Agents, evaluations, tracing, fine-tuning, Responses API, Foundry-direct models |
| OpenAI SDK | `openai>=2.0` | `https://<resource>.openai.azure.com/openai/v1/` | Max OpenAI compat, Chat Completions for Foundry-direct models (no agents/evals) |
| Microsoft Agent Framework | `agent-framework` (MAF 1.0) | Uses Foundry SDK endpoint | Multi-agent local orchestration; cloud-agnostic |
| Foundry Tools (Vision/Speech/Language/Translator) | `azure-ai-<service>` per service | `https://<resource>.cognitiveservices.azure.com/` | Prebuilt point solutions |
| Azure AI Evaluation | `azure-ai-evaluation>=1.16` | Uses Foundry SDK endpoint | Eval gate pipelines (see each project's own eval-agent-plan.md) |

**Auth:** Microsoft Entra ID via `DefaultAzureCredential` (prefer). API key works on `/openai/v1`.

**Rule per `rules/agent-framework.md`:** MAF 1.0 applies to NEW agents only. Do NOT migrate an existing production agent to MAF without a dedicated migration plan.

## SDK verify (run in project venv)

```bash
# In any uv-managed Foundry project:
cd "$PROJECT"
uv pip list 2>/dev/null | grep -iE "azure-ai-projects|azure-ai-evaluation|azure-identity|openai|agent-framework"

# Expected in a Foundry-backed project:
#   azure-ai-projects   >= 2.0.0
#   azure-identity      >= 1.16
#   openai              >= 2.0
#   agent-framework     (any)           # new-agent work only
#   azure-ai-evaluation >= 1.16         # eval gate pipelines
```

If any are missing, install via uv (never pip):

```bash
# Project with pyproject.toml + dev group:
uv add --dev azure-ai-projects azure-identity openai agent-framework azure-ai-evaluation

# Project with requirements.txt only:
uv pip install azure-ai-projects azure-identity openai agent-framework azure-ai-evaluation
```

## Project client bootstrap (Foundry SDK 2.x)

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

project_client = AIProjectClient(
    endpoint="https://<resource>.services.ai.azure.com/api/projects/<project>",
    credential=DefaultAzureCredential(),
)

# OpenAI-compatible client (Responses API, agents, evals, fine-tuning, Foundry-direct models)
with project_client.get_openai_client() as openai_client:
    response = openai_client.responses.create(
        model="gpt-5.2",
        input="ping",
    )
    print(response.output_text)
```

Endpoint comes from `AZURE_AI_PROJECT` env (already loaded by `session-start-azure-secrets.sh`). Never hardcode.

## Required state

- `az login --use-device-code` active. Scope the KV calls to `<your-key-vault-name>`.
- `az extension add -n ml` (installs Azure ML extension — used for Foundry resources).
- Environment secrets via `~/.Codex/skills/azure-keyvault-secrets` (never inline).

## Common flows

### 1. Check live agent version vs git

```bash
# agent id lives in the project's deploy_agent.py or .env
AGENT_ID=$(grep -E '^AGENT_ID' "$PROJECT/.env" | cut -d= -f2- | tr -d '"')
FOUNDRY_RG="${FOUNDRY_RG:?set FOUNDRY_RG to your resource group}"
FOUNDRY_PROJECT="${FOUNDRY_PROJECT:?set FOUNDRY_PROJECT to your Foundry account}"

# Fetch live prompt version
az rest --method GET \
  --url "https://${FOUNDRY_PROJECT}.services.ai.azure.com/api/projects/${FOUNDRY_RG}/assistants/${AGENT_ID}?api-version=2025-05-01" \
  --query "{name:name, instructions_len:length(instructions), tools:length(tools)}"

# Compare against git
grep -c '^' "$PROJECT/agent_prompt_*.md"
```

If git and Foundry diverge, remember: Foundry often has many more versions than git (v97+ vs v10). Check `lesson_prompt_versioning.md` in memory for the root cause pattern.

### 2. Deploy an agent (via project's deploy_agent.py)

```bash
cd "$PROJECT"
# Always run the repo's deploy script — never call Foundry API directly from Codex
python deploy_agent.py --dry-run
python deploy_agent.py            # only after dry-run reviewed
```

This deploy-script pattern applies to any Foundry agent project you maintain. CI invokes the same script — keeping parity matters.

### 3. Inspect a failed run

```bash
az rest --method GET \
  --url "https://${FOUNDRY_PROJECT}.services.ai.azure.com/api/projects/${FOUNDRY_RG}/threads/${THREAD_ID}/runs/${RUN_ID}?api-version=2025-05-01" \
  | jq '{status, last_error, required_action, usage}'

# Message log
az rest --method GET \
  --url "https://${FOUNDRY_PROJECT}.services.ai.azure.com/api/projects/${FOUNDRY_RG}/threads/${THREAD_ID}/messages?api-version=2025-05-01" \
  | jq '.data[] | {role, content: .content[0].text.value[0:200]}'
```

### 4. Memory feature

The Foundry agent Memory feature retains conversation context across sessions. Confirm with:

```bash
az rest --method GET \
  --url "https://${FOUNDRY_PROJECT}.services.ai.azure.com/api/projects/${FOUNDRY_RG}/assistants/${AGENT_ID}?api-version=2025-05-01" \
  --query "tool_resources.memory"
```

See memory entry `project_foundry_agent_memory.md` for rollout history on any agent you've enabled Memory for.

## Agents we know about

| Repo | Agent purpose | Uses Memory | Deploy |
|---|---|---|---|
| `<agent-project-a>` | domain-specific Q&A over an internal data source | ? | `deploy_agent.py` via CI |
| `<agent-project-b>` | data-fetch agent over a business dataset | no | `deploy_agent.py` via CI |
| `<agent-project-c>` | customer-support bot | yes | CI pipeline (not deploy_agent.py) |

## Common pitfalls (from real Foundry-agent PR history)

- **401 on Foundry Responses endpoint** — KV has a static API key but the endpoint needs a live AAD bearer token. Use `AzureCLI@2` task in CI (name your own service connection), not static key.
- **Prompt version drift** — Foundry auto-increments on every deploy. Git version bumps are manual. Don't assume git version == live. Always query live before editing.
- **Tool schema discovery lag** — new tool fields (e.g., `realmId`, `layer_scores`) are discovered post-deploy via 400/404s. Integration-test tool schemas against Foundry before merging.

## Related

- `azure-keyvault-secrets` — never inline KV values.
- `ado-auth-mfa-nudge.sh` hook — catches MFA timeouts.
- `lesson_prompt_versioning.md` (memory) — git vs Foundry version divergence pattern.
