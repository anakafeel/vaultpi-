#!/bin/bash
# VaultPi weekly Docker cleanup: prune unused images/build cache (never volumes),
# log the result, and post a summary to Discord.
set -uo pipefail

VAULT_DIR="$HOME/vaultpi"
LOG_DIR="$VAULT_DIR/logs"
LOG_FILE="$LOG_DIR/prune.log"
WEBHOOK_FILE="$VAULT_DIR/.discord_webhook"
MAX_LOG_LINES=1000

mkdir -p "$LOG_DIR"

TS="$(date '+%Y-%m-%d %H:%M:%S %Z')"
DF_BEFORE="$(df -h / | awk 'NR==2{print $4" free ("$5" used)"}')"

PRUNE_OUTPUT="$(docker system prune -af --volumes=false 2>&1)"
PRUNE_EXIT=$?

DF_AFTER="$(df -h / | awk 'NR==2{print $4" free ("$5" used)"}')"

RECLAIMED="$(printf '%s\n' "$PRUNE_OUTPUT" | grep -i "Total reclaimed space" | tail -1)"
if [ -z "$RECLAIMED" ]; then
  RECLAIMED="Total reclaimed space: 0B"
fi

{
  echo "=== $TS (exit $PRUNE_EXIT) ==="
  printf '%s\n' "$PRUNE_OUTPUT"
  echo "$RECLAIMED"
  echo "Disk before: $DF_BEFORE"
  echo "Disk after:  $DF_AFTER"
  echo
} >> "$LOG_FILE"

if [ "$(wc -l < "$LOG_FILE")" -gt "$MAX_LOG_LINES" ]; then
  tail -n "$MAX_LOG_LINES" "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

if [ -f "$WEBHOOK_FILE" ]; then
  WEBHOOK_URL="$(cat "$WEBHOOK_FILE")"
  DISCORD_MSG="VaultPi weekly Docker prune - $TS
$RECLAIMED
Disk: $DF_BEFORE -> $DF_AFTER"

  PAYLOAD="$(python3 -c '
import json, sys
print(json.dumps({"content": sys.argv[1]}))
' "$DISCORD_MSG")"

  HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' -H "Content-Type: application/json" -X POST -d "$PAYLOAD" "$WEBHOOK_URL")"
  if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
    echo "[$TS] Discord notification sent (HTTP $HTTP_CODE)" >> "$LOG_FILE"
  else
    echo "[$TS] Discord notification FAILED (HTTP $HTTP_CODE)" >> "$LOG_FILE"
  fi
else
  echo "[$TS] Discord webhook file not found at $WEBHOOK_FILE, skipping notification" >> "$LOG_FILE"
fi
