#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV=""
DB=""
TIMESTAMP=""
REASON=""
CUSTOM_CMD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment)
      ENV="$2"
      shift 2
      ;;
    --database)
      DB="$2"
      shift 2
      ;;
    --timestamp)
      TIMESTAMP="$2"
      shift 2
      ;;
    --reason)
      REASON="$2"
      shift 2
      ;;
    --custom-command)
      CUSTOM_CMD="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] Argumento desconocido: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$TIMESTAMP" ]]; then
  TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
fi

if [[ -z "$ENV" ]]; then
  ENV="unknown"
fi

if [[ -z "$DB" ]]; then
  DB="unknown"
fi

if [[ -z "$REASON" ]]; then
  REASON="Unknown failure during MongoDB backup process"
fi

# Sanitize reason: remove newlines, tabs, carriage returns, and pipe characters
SAFE_REASON="$(printf '%s' "$REASON" | tr '\r\n\t|' '    ' | tr -s ' ' | head -c 500)"

LOG_DIR="${PROJECT_ROOT}/logs"
ALERT_LOG="${LOG_DIR}/mongodb_backup_alert.log"

mkdir -p "$LOG_DIR"

ALERT_LINE="${TIMESTAMP} | severity=ERROR | environment=${ENV} | database=${DB} | reason=${SAFE_REASON} | notification=GENERATED"

# Append alert line to mongodb_backup_alert.log
printf '%s\n' "$ALERT_LINE" >> "$ALERT_LOG"
chmod 0600 "$ALERT_LOG"

# Emit alert to stderr so it is captured in cron log (mongodb_backup_cron.log)
echo "[ALERTA] Backup MongoDB fallido/incompleto: environment=${ENV} database=${DB} timestamp=${TIMESTAMP} reason=${SAFE_REASON}" >&2

# Optional custom notification command
if [[ -n "$CUSTOM_CMD" ]]; then
  export BACKUP_ALERT_ENV="$ENV"
  export BACKUP_ALERT_DB="$DB"
  export BACKUP_ALERT_TIMESTAMP="$TIMESTAMP"
  export BACKUP_ALERT_REASON="$SAFE_REASON"
  eval "$CUSTOM_CMD" || {
    echo "[WARN] Custom notification command failed with exit code $?" >&2
  }
fi
