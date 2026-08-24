#!/usr/bin/env bash
# ============================================================
# retention_evaluate.sh
# Evalua si un candidato a eliminar tiene al menos un backup
# posterior cronologicamente integro.
#
# Argumentos:
#   $1  DB_ROOT        - ruta raiz de la base de datos
#   $2  DB             - nombre de la base de datos (mongo_database)
#   $3  EXT            - extension del respaldo (backup_extension)
#   $4  CANDIDATE_TS   - timestamp del candidato: YYYYMMDD_HHMMSS
#   $5  CHECKSUM_ALGO  - algoritmo (backup_checksum_algorithm): sha256
#
# Salida stdout (dos lineas):
#   authorized=true|false
#   newer_valid=<filename>|<vacio>
#
# Logica:
#   Recorre todos los archivos del directorio en orden cronologico.
#   Para cada archivo con timestamp > CANDIDATE_TS verifica:
#     a. .archive.gz existe y size > 0
#     b. .sha256 existe y size > 0
#     c. <checksum_algo>sum -c --quiet pasa
#   Al primer archivo posterior integro encontrado: authorized=true.
#   Si ninguno supera todas las validaciones: authorized=false.
# ============================================================
set -uo pipefail

DB_ROOT="$1"
DB="$2"
EXT="$3"
CANDIDATE_TS="$4"
CHECKSUM_ALGO="$5"
CHECKSUM_CMD="${CHECKSUM_ALGO}sum"

# Escapar extension para regex bash
EXT_BASH="${EXT//./\\.}"

AUTHORIZED="false"
NEWER_VALID=""

while IFS= read -r -d '' BACKUP_PATH; do
  BACKUP_FNAME=$(basename "$BACKUP_PATH")

  # Extraer timestamp usando bash regex - sin hardcodear la extension
  [[ "$BACKUP_FNAME" =~ ^${DB}_([0-9]{8}_[0-9]{6})${EXT_BASH}$ ]] || continue
  BACKUP_TS="${BASH_REMATCH[1]}"

  # Solo backups cronologicamente posteriores al candidato
  # Comparacion lexicografica: YYYYMMDD_HHMMSS garantiza orden correcto
  [[ "$BACKUP_TS" > "$CANDIDATE_TS" ]] || continue

  # a. Archivo principal: existe y size > 0
  [[ -f "$BACKUP_PATH" ]] || continue
  FSIZE=$(stat -c%s "$BACKUP_PATH" 2>/dev/null) || continue
  [[ "$FSIZE" -gt 0 ]] || continue

  # b. Archivo sha256: existe y size > 0
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

done < <(find "$DB_ROOT" -type f -name "${DB}_*${EXT}" -print0 | sort -z)

echo "authorized=${AUTHORIZED}"
echo "newer_valid=${NEWER_VALID}"