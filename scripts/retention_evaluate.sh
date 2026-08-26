#!/usr/bin/env bash
# ============================================================
# retention_evaluate.sh
# Evalua si un candidato a eliminar tiene al menos un backup
# posterior cronologicamente integro (sea .archive.gz o .archive.gz.age).
# ============================================================
set -uo pipefail

DB_ROOT="$1"
DB="$2"
EXT="$3"
CANDIDATE_TS="$4"
CHECKSUM_ALGO="$5"
CHECKSUM_CMD="${CHECKSUM_ALGO}sum"

AUTHORIZED="false"
NEWER_VALID=""

while IFS= read -r -d '' BACKUP_PATH; do
  BACKUP_FNAME=$(basename "$BACKUP_PATH")

  [[ "$BACKUP_FNAME" =~ ^${DB}_([0-9]{8}_[0-9]{6})\.archive\.gz(\.age)?$ ]] || continue
  BACKUP_TS="${BASH_REMATCH[1]}"

  [[ "$BACKUP_TS" > "$CANDIDATE_TS" ]] || continue

  # a. Archivo principal existe y size > 0
  [[ -f "$BACKUP_PATH" ]] || continue
  FSIZE=$(stat -c%s "$BACKUP_PATH" 2>/dev/null) || continue
  [[ "$FSIZE" -gt 0 ]] || continue

  # b. Archivo sha256 existe y size > 0
  SHA_PATH="${BACKUP_PATH}.sha256"
  [[ -f "$SHA_PATH" ]] || continue
  SSIZE=$(stat -c%s "$SHA_PATH" 2>/dev/null) || continue
  [[ "$SSIZE" -gt 0 ]] || continue

  # c. Integridad: verificar con el algoritmo configurado
  (cd "$(dirname "$BACKUP_PATH")" && \
    "${CHECKSUM_CMD}" -c "$(basename "$SHA_PATH")" --quiet 2>/dev/null) || continue

  AUTHORIZED="true"
  NEWER_VALID="$BACKUP_FNAME"
  break

done < <(find "$DB_ROOT" -type f \( -name "${DB}_*.archive.gz" -o -name "${DB}_*.archive.gz.age" \) -print0 | sort -z)

echo "authorized=${AUTHORIZED}"
echo "newer_valid=${NEWER_VALID}"
