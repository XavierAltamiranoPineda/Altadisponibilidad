#!/bin/bash
# ============================================================
# Wrapper seguro para rollout de TLS en MongoDB
# Adquiere lock no bloqueante via flock y ejecuta el playbook
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOCK_FILE="${PROJECT_ROOT}/logs/mongodb_backup.lock"
VAULT_PASSWORD_FILE="${PROJECT_ROOT}/secrets/vault_password"

if [ ! -f "$VAULT_PASSWORD_FILE" ]; then
  echo "ERROR: vault_password no encontrado en $VAULT_PASSWORD_FILE" >&2
  exit 1
fi

TARGET_MODE="preferTLS"
if [ $# -gt 0 ] && [[ "$1" != -* ]]; then
  TARGET_MODE="$1"
  shift
fi

case "$TARGET_MODE" in
  disabled|allowTLS|preferTLS|requireTLS) ;;
  *)
    echo "[ERROR] target_tls_mode invalido: '$TARGET_MODE'. Valores permitidos: disabled, allowTLS, preferTLS, requireTLS" >&2
    exit 1
    ;;
esac

mkdir -p "${PROJECT_ROOT}/logs"

exec flock -n "$LOCK_FILE"   ansible-playbook     "${PROJECT_ROOT}/playbooks/mongodb/tls_rollout.yml"     --vault-password-file "$VAULT_PASSWORD_FILE"     --extra-vars "target_tls_mode=${TARGET_MODE}"     "$@"
