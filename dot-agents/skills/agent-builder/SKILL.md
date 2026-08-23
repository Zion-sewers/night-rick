---
name: agent-builder
description: Author and deploy AI agents on Microsoft + Azure platforms — Azure AI Foundry agent CRUD (azure-ai-projects SDK), Microsoft 365 Agents SDK projects (TS via bun, C# via dotnet — agents callable from Teams + Copilot + standalone), and Copilot Studio export/import via pac CLI. Authoring time, not runtime. Triggers on "/agent-builder", "create foundry agent", "new m365 agent", "scaffold copilot agent", "update agent instructions", "deploy agent to teams", "create teams bot", "version bump agent", "register tool with agent". SKIP when calling already-deployed agents (use azure-runtime), evaluating agents (use eval-runner), or working with OpenAI's platform.openai.com Assistants/AgentKit (no key, not supported here).
model: opus
---

# Agent Builder — author Microsoft/Azure agents

**Invocation:** `/agent-builder` or any task that creates, updates, versions, or deploys AI agents on Microsoft platforms.

## Auth — no keys

`DefaultAzureCredential` (`az login`). Don't handle keys; don't write tokens to files.

## Three platforms

### 1. Azure AI Foundry Agents

Agents that run inside an Azure AI Foundry project.

**Create:**
```bash
uv run --quiet --with "azure-ai-projects>=1.0" --with "azure-identity>=1.21" python <<'PY'
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

p = AIProjectClient(
    endpoint="https://<foundry-account>.services.ai.azure.com/api/projects/<project-name>",
    credential=DefaultAzureCredential(),
)
agent = p.agents.create_agent(
    model="gpt-5.5",                        # deployment name (NOT model family)
    name="my-new-agent",
    instructions=open("prompts/agent.md").read(),  # commit prompts to git
    tools=[],                               # add code_interpreter / file_search / functions
)
print(agent.id)
PY
```

**Update instructions (creates a new version `:N`):**
```python
p.agents.update_agent(agent_id, instructions=new_text)
```

**Versioning convention:** Foundry auto-bumps `:N` on every update. Tag the git commit that produced each version: `git tag agent/<name>/v<N>`.

**List / get / delete:**
```python
p.agents.list_agents()
p.agents.get_agent("my-agent")          # latest
p.agents.get_agent("my-agent:7")        # pinned
p.agents.delete_agent(agent_id)                   # DESTRUCTIVE — explicit operator OK
```

### 2. Microsoft 365 Agents SDK

Agents callable from Teams, Microsoft 365 Copilot, or standalone web. Newer SDK (replaces older Bot Framework SDK for new builds).

**Scaffold (TypeScript via bun — preferred per house style):**
```bash
mkdir my-m365-agent && cd my-m365-agent
bun init -y
bun add @microsoft/agents-hosting @microsoft/agents-bot-hosting
# Teams flavor:
bun add @microsoft/agents-hosting-teams
# AI integration (calls Azure OpenAI / Foundry under the hood):
bun add @microsoft/agents-extensions-ai
```

Write `src/index.ts` extending `ActivityHandler`. Auth flows through Azure Bot Service — provision separately:
```bash
az bot create --resource-group <resource-group> --name my-m365-agent-bot \
  --kind azurebot --sku F0 --app-type SingleTenant
```

**Scaffold (C# via dotnet, official template path):**
```bash
dotnet new -i Microsoft.Agents.Templates    # one-time
dotnet new agent --name MyAgent
```

**Deploy targets:**
- Azure Bot Service + App Service / Container App (the runtime)
- Teams app package: `manifest.json` + icons → `.zip` → upload via Teams Admin Center or Developer Portal
- Copilot integration via `botType: "Microsoft.Copilot"` in manifest declaration

### 3. Copilot Studio (low-code) — import/export only

For agents authored in the Copilot Studio web UI. Limited programmatic control; lifecycle managed via Power Platform CLI.

```bash
# One-time install of pac CLI
dotnet tool install --global Microsoft.PowerApps.CLI.Tool

pac auth create --environment <env-id>
pac copilot list --environment <env-id>
pac copilot export --copilot-id <id> --path ./agent.zip      # .zip is a Solution package
pac copilot import --path ./agent.zip --environment <env-id>
```

Source-control the unpacked solution to track instruction/topic changes.

## House conventions for every new agent

1. **System prompt in git** — `prompts/<agent-name>.md`, never inline strings
2. **Tool catalog file** — `tools/<agent-name>.toml` listing each tool's schema, expected output, side effects, and tier (`R` / `W-soft` / `W-hard`)
3. **Eval set** — minimum 10 smoke rows compatible with `eval-runner` skill before first deploy
4. **Versioning** — Foundry: `:N` suffix; M365: package semver; Copilot: solution version
5. **HITL by default** for any write-tool — dry-run first, explicit operator OK before writes
6. **Forge Loop axes** — SPEC + PREMORTEM + RED→GREEN + REFLECT before declaring an agent shipped

## Boundaries

- **Runtime calls** to existing agents → `azure-runtime` skill
- **Evals** → `eval-runner` skill
- **Destructive ops** (delete agent, drop deployment, force-publish over existing version) → explicit operator OK each time, per AGENTS.md authorization rules
- **OpenAI's Assistants/AgentKit** on platform.openai.com → not supported (no key)

## Adjacent (mention if asked, not core)

- **Semantic Kernel** — orchestration of multiple agents from your own runtime
- **AutoGen** — multi-agent conversation framework
- **LangChain / LangGraph** — community framework, not Microsoft-blessed for production
- These fit when you're building an *agent system in your own process*, not authoring a hosted agent
