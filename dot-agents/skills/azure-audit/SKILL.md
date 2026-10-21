---
name: azure-audit
description: Weekly dormancy + cost audit of Azure (functions, web apps, container apps, storage), Azure DevOps repos + wikis, and Foundry agents. Produces a dated markdown report under ~/docs/audits/, never deletes anything autonomously.
---

# azure-audit

Run this skill weekly (cron: Sun 09:00 IST) to detect Azure resource drift and surface deletion candidates for human review. **The skill never deletes anything**; it writes a dated audit report and pings the user with the diff vs the previous report.

## When to use

- Auto-fired on the weekly schedule.
- Manual: user types `/azure-audit` or asks "run the dormancy audit".
- After a major cleanup, to confirm what actually got deprovisioned.

## Inputs

None. Subscription + DevOps org are read from the active `az`/`az devops configure --list` profile. If neither is logged in, fail loudly with the recovery command.

## Outputs

1. `~/docs/audits/YYYY-MM-DD-dormancy-audit.md` — full report (same format as `2026-05-03-dormancy-audit.md`).
2. Console summary: counts of confirmed dormants + diff vs last report (which resources/repos newly went dormant or came back to life).
3. Suggested next step: usually "review the report; per-action OK required to deprovision".

## Procedure

### 0. Pre-flight

```bash
az account show --query name -o tsv  # fail if empty
az devops configure --list           # fail if no organization/project defaults
```

If either fails, stop and tell the user to run `az login` and `az devops configure --defaults organization=https://dev.azure.com/<devops-org> project=<devops-project>`.

### 1. Resource snapshot

For the subscription's RGs (today only `<resource-group>` matters, but iterate `az group list`):

```bash
SUB=$(az account show --query id -o tsv)
RG=<resource-group>
az functionapp list -g $RG -o json
az webapp list -g $RG -o json
az containerapp list -g $RG -o json
az storage account list -g $RG -o json
az resource list -g $RG -o json   # umbrella
```

### 2. Usage metrics (30-day window)

For each function app, query `FunctionExecutionCount` (Total, P1D) over the last 30 days. Also pull `Requests` (Total) and `Http5xx` (Total) for context.

For each web app, pull `Requests` (Total).
For each storage account, pull `Transactions` (Total) and `UsedCapacity` (Average, last point).
For each container app, pull `Requests` if available.

```bash
SINCE=$(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ)
az monitor metrics list \
  --resource "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Web/sites/<fn>" \
  --metric FunctionExecutionCount --interval P1D --start-time "$SINCE" \
  --aggregation Total --query "value[0].timeseries[0].data[].total" -o tsv | awk '{s+=$1} END {print s+0}'
```

Health-probe floor is ~11–12 `Requests`/30d on every site — discount that.

### 3. Storage backing map

Map every function app to its `AzureWebJobsStorage` account so the report can warn about shared storage (today: 12 of 13 funcs share `<shared-storage-account>` — MUST NOT delete that storage).

```bash
for fn in $(az functionapp list -g $RG --query "[].name" -o tsv); do
  blob=$(az functionapp config appsettings list -g $RG -n $fn \
    --query "[?name=='AzureWebJobsStorage'].value | [0]" -o tsv)
  echo "$fn -> $(echo "$blob" | grep -oE 'AccountName=[^;]*')"
done
```

### 4. DevOps repos

For both `<devops-project>` and `<devops-org>`, list every repo and the timestamp of the latest commit on the default branch. Flag repos with last commit > 180 days ago. Also list size-0 repos (placeholders).

```bash
ORG=https://dev.azure.com/<devops-org>
TOKEN=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)
az repos list --project <devops-project> --query "sort_by([], &name) | [].[id,name]" -o tsv | while IFS=$'\t' read -r id name; do
  date=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$ORG/<devops-project>/_apis/git/repositories/$id/commits?searchCriteria.%24top=1&api-version=7.1" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); v=d.get('value',[{}])[0]; print(v.get('committer',{}).get('date','-'))" 2>/dev/null)
  printf "%-45s %s\n" "$name" "$date"
done
```

### 5. Wiki activity

Wiki repo IDs equal the wiki IDs. Query the same `commits?$top=1` endpoint against `repositoryId` = wiki id. Wikis themselves rarely go dormant; instead look for whole subtrees prefixed `/Archived/`, `/<teammate> - Archived work/`, etc., and report them as candidates for export-and-delete.

### 6. Foundry agents

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://<foundry-account>.services.ai.azure.com/api/projects/<foundry-project>/assistants?api-version=v1"
```

For every agent, capture: id, name, model, `created_at`. If user's AGENTS.md mentions named prod agents that are absent from the listing, flag the gap.

### 7. Diff vs previous report

Find the most recent prior `~/docs/audits/*-dormancy-audit.md`. Diff the "verdict = DELETE" / "verdict = review" sections. Highlight in the new report:

- **Newly dormant** since last week (new entries).
- **Came back to life** (was dormant, now active).
- **Still on the deletion list** (week-over-week — escalate).

### 8. Write the report

Same template as `~/docs/audits/2026-05-03-dormancy-audit.md`. End every recommendation with the Phase X command block, but do **not** execute it. Always include the section:

> **Hard rules (do not violate)**
> - Never delete `<shared-storage-account>` — shared backing store for 12 prod function apps.
> - Never delete `<container-registry>` — pulled by multiple prod apps (name them from the current audit).
> - Never delete `<key-vault-name>`.
> - Per-action explicit OK required for every deletion.

### 9. Notify

Print to console the path of the new report plus the diff summary. If any "still on deletion list 2 weeks running" item exists, prefix the summary with `⚠️ ESCALATION:` and the user can decide. Do not auto-message Slack/email.

## Dormancy thresholds (current)

| Signal | Dormant if |
|---|---|
| Function app | `FunctionExecutionCount` = 0 over 30d AND only HTTP triggers AND `Requests` ≤ 12/30d |
| Web app | `state = Stopped` OR `Requests` ≤ 12/30d for 60 consecutive days |
| Container app | `runningStatus != Running` OR no replicas for 30d |
| Storage | `Transactions` = 0 for 30d AND not referenced as `AzureWebJobsStorage` of any live function |
| DevOps repo | Last commit on default branch > 180d ago |
| Wiki page subtree | Already named `Archived` OR not edited in 365d |
| Foundry agent | Not invoked in 30d (when invocation telemetry is wired up) |

Adjust thresholds inline in this file as policy evolves.

## Failure modes

- `az` token expired → run `az login`.
- `az repos list` fails with 401 → run `az devops login` (it asks for a PAT; do not store).
- Foundry endpoint returns 401 → token resource is `https://ai.azure.com`, not `https://management.azure.com`.
- Subscription scoping changed → re-confirm `az account show` matches the expected subscription name.

## Related

- Master plan: `~/Codex-MASTER-PLAN-2026-05-03.md`
- Last audit: `~/docs/audits/2026-05-03-dormancy-audit.md`
- Foundry endpoint: `https://<foundry-account>.services.ai.azure.com/api/projects/<foundry-project>`
