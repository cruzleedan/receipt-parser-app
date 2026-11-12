#!/usr/bin/env bash
# WORK-0013: daily run of the WORK-0012 integration check against production, from cron.
# Logs to ~/receipt-parser-checks/check.log. When ~/.config/receipt-parser-check.env holds
# PING_URL (a Healthchecks.io check URL, mode 600), it pings PING_URL on success and
# PING_URL/fail on failure, so Healthchecks emails the owner; a missing ping also alerts.
set -uo pipefail
cd "$(dirname "$0")/.."
LOG_DIR="${LOG_DIR:-$HOME/receipt-parser-checks}"; mkdir -p "$LOG_DIR"; LOG="$LOG_DIR/check.log"
PING_URL=""
ENV_FILE="$HOME/.config/receipt-parser-check.env"
[ -f "$ENV_FILE" ] && PING_URL=$(grep -E '^PING_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)
OUT=$(scripts/verify-deployment.sh "$@" 2>&1); CODE=$?   # args: optional URL and network (testing)
SUMMARY=$(printf '%s\n' "$OUT" | grep -E 'passed|failed|error' | tail -1)
FAILED=$(printf '%s\n' "$OUT" | grep -E '^FAILED|^E ' | head -5)
printf '%s exit=%s %s\n' "$(date -u +%FT%TZ)" "$CODE" "$SUMMARY" >> "$LOG"
[ "$CODE" -ne 0 ] && printf '%s\n' "$FAILED" | sed 's/^/    /' >> "$LOG"
if [ -n "$PING_URL" ]; then
  if [ "$CODE" -eq 0 ]; then target="$PING_URL"; else target="$PING_URL/fail"; fi
  curl -fsS -m 10 --retry 3 --data-raw "$SUMMARY
$FAILED" "$target" >/dev/null || printf '%s ping failed\n' "$(date -u +%FT%TZ)" >> "$LOG"
fi
exit "$CODE"
