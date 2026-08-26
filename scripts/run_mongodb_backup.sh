#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LOCK_FILE="${PROJECT_ROOT}/logs/mongodb_backup.lock"
VAULT_PASSWORD_FILE="${PROJECT_ROOT}/secrets/vault_password"

if [[ ! -f "$VAULT_PASSWORD_FILE" ]]; then
  echo "[ERROR] No se encontro el archivo de clave Vault: ${VAULT_PASSWORD_FILE}" >&2
  exit 1
fi

mkdir -p "${PROJECT_ROOT}/logs"

exec flock -n "$LOCK_FILE" \
  ansible-playbook \
    "${PROJECT_ROOT}/playbooks/backup/backup_process.yml" \
    --vault-password-file "$VAULT_PASSWORD_FILE" \
    "$@"
