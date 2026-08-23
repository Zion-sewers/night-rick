#!/usr/bin/env bash
# azure-activity-watch — finds stop/delete/restart/scale ops on your resource
# group caused by anyone other than the owner (set via OWNER / --owner).
# Usage: ./run.sh [--since 14d] [--owner you@example.com] [--rg <resource-group>] [--json]

set -euo pipefail

OWNER="${OWNER:-}"
RG="${RG:-}"
SINCE="${SINCE:-7d}"
FORMAT="table"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since) SINCE="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --rg)    RG="$2"; shift 2 ;;
    --json)  FORMAT="json"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

: "${OWNER:?set OWNER env var or pass --owner you@example.com}"
: "${RG:?set RG env var or pass --rg <resource-group>}"

# az activity-log accepts --offset directly (e.g. 14d / 24h). Default --max-events
# is 50, which silently drops older interesting events; raise it.
INTERESTING_OPS=(
  "Microsoft.Web/sites/stop/action"
  "Microsoft.Web/sites/restart/action"
  "Microsoft.Web/sites/delete"
  "Microsoft.Web/serverfarms/delete"
  "Microsoft.Web/serverfarms/write"
  "Microsoft.Web/sites/slots/stop/action"
  "Microsoft.Web/sites/slots/delete"
  "Microsoft.App/containerApps/stop/action"
  "Microsoft.App/containerApps/delete"
  "Microsoft.App/managedEnvironments/delete"
  "Microsoft.Storage/storageAccounts/delete"
  "Microsoft.Cache/Redis/delete"
  "Microsoft.Cache/Redis/stop/action"
  "Microsoft.DocumentDB/databaseAccounts/delete"
  "Microsoft.DBforPostgreSQL/flexibleServers/delete"
  "Microsoft.DBforPostgreSQL/flexibleServers/stop/action"
  "Microsoft.CognitiveServices/accounts/delete"
  "Microsoft.KeyVault/vaults/delete"
  "Microsoft.Insights/components/delete"
  "DeleteWebSite"
  "StopWebSite"
)

JMES_OR=""
for op in "${INTERESTING_OPS[@]}"; do
  [[ -z "$JMES_OR" ]] && JMES_OR="contains(operationName.value,'$op')" || JMES_OR="$JMES_OR || contains(operationName.value,'$op')"
done

QUERY="[?($JMES_OR) && caller != '$OWNER' && eventName.value == 'EndRequest' && status.value == 'Succeeded']"

if [[ "$FORMAT" == "json" ]]; then
  az monitor activity-log list -g "$RG" --offset "$SINCE" --max-events 5000 \
    --query "$QUERY.{when:eventTimestamp, who:caller, ip:httpRequest.clientIpAddress, op:operationName.value, opName:operationName.localizedValue, status:status.value, resource:resourceId, correlationId:correlationId, clientApp:claims.appid, mfa:claims.\"http://schemas.microsoft.com/claims/authnmethodsreferences\"}" \
    -o json
else
  echo "azure-activity-watch | rg=$RG | owner=$OWNER | since=$SINCE"
  echo "(events caused by anyone other than the owner; succeeded EndRequests only)"
  echo
  az monitor activity-log list -g "$RG" --offset "$SINCE" --max-events 5000 \
    --query "$QUERY.{when:eventTimestamp, who:caller, ip:httpRequest.clientIpAddress, op:operationName.localizedValue, resource:resourceId}" \
    -o table
fi
