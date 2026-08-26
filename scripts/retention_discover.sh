#!/usr/bin/env bash
# ============================================================
# retention_discover.sh
# Descubre archivos de respaldo (tanto .archive.gz como .archive.gz.age)
# y genera un JSON array de metadatos ordenado por timestamp YYYYMMDD_HHMMSS ASC.
# ============================================================
set -uo pipefail

DB_ROOT="$1"
DB="$2"
EXT="${3:-.archive.gz}"

sortable=()
while IFS= read -r -d '' FPATH; do
  FNAME=$(basename "$FPATH")

  # Extraer componentes del timestamp (soporta .archive.gz y .archive.gz.age)
  if [[ "$FNAME" =~ ^${DB}_([0-9]{4})([0-9]{2})([0-9]{2})_([0-9]{6})\.archive\.gz(\.age)?$ ]]; then
    YYYY="${BASH_REMATCH[1]}"
    MM="${BASH_REMATCH[2]}"
    DD="${BASH_REMATCH[3]}"
    HHMMSS="${BASH_REMATCH[4]}"
    TS="${YYYY}${MM}${DD}_${HHMMSS}"
    DATE_VAL="${YYYY}${MM}${DD}"
    MONTH_VAL="${YYYY}-${MM}"
    JSON="{\"filename\":\"${FNAME}\",\"path\":\"${FPATH}\",\"timestamp\":\"${TS}\",\"date\":\"${DATE_VAL}\",\"month\":\"${MONTH_VAL}\"}"
    sortable+=("${TS}::${JSON}")
  fi
done < <(find "$DB_ROOT" -type f \( -name "${DB}_*.archive.gz" -o -name "${DB}_*.archive.gz.age" \) -print0 | sort -z)

if [[ ${#sortable[@]} -eq 0 ]]; then
  echo "[]"
else
  items=()
  while IFS= read -r line; do
    items+=("${line#*::}")
  done < <(printf '%s\n' "${sortable[@]}" | sort)

  (IFS=','; printf '[%s]\n' "${items[*]}")
fi
