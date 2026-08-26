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

mkdir -p "${PROJECT_ROOT}/logs"

# exec flock -n: el FD del lock pertenece al proceso ansible-playbook.
# Cualquier terminacion (normal, error, SIGTERM, SIGINT) libera el lock en el kernel.
exec flock -n "$LOCK_FILE" \
  ansible-playbook \
    "${PROJECT_ROOT}/playbooks/mongodb/tls_rollout.yml" \
    --vault-password-file "$VAULT_PASSWORD_FILE" \
    --extra-vars "target_tls_mode=allowTLS" \
    "$@"
