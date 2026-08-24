#!/usr/bin/env bash
# ============================================================
# retention_discover.sh
# Descubre archivos de respaldo y genera un JSON array de metadatos
# ordenado por timestamp YYYYMMDD_HHMMSS ASC.
#
# Argumentos:
#   $1  DB_ROOT   - ruta raiz de la base de datos
#   $2  DB        - nombre de la base de datos (mongo_database)
#   $3  EXT       - extension del respaldo (backup_extension)
#
# Salida stdout: JSON array con objetos:
#   { "filename", "path", "timestamp", "date", "month" }
#   Ordenados por timestamp YYYYMMDD_HHMMSS ASC, independientemente
#   de la carpeta fisica donde se encuentre el backup.
#
# Retorna 0 siempre. Si no hay archivos imprime [].
#
# Orden de operaciones:
#   Fase 1: find descubre los archivos (orden no determinista).
#            Para cada uno que cumpla la convencion de nombre,
#            se emite una linea sortable: "<timestamp>::<json>".
#   Fase 2: sort ordena esas lineas por timestamp (campo 1, ASC).
#   Fase 3: se extraen solo los fragmentos JSON y se construye el array.
# ============================================================
set -uo pipefail

DB_ROOT="$1"
DB="$2"
EXT="$3"

# Escapar extension para regex bash (e.g. ".archive.gz" -> "\.archive\.gz")
EXT_BASH="${EXT//./\\.}"

# -------------------------------------------------------
# Fase 1: recopilar entradas sortables timestamp::json
# -------------------------------------------------------
# Cada entrada tiene el formato:
#   YYYYMMDD_HHMMSS::<objeto_json>
# donde '::' no puede aparecer en el timestamp ni en la JSON
# (los paths no contienen '::' en uso normal).
# -------------------------------------------------------
sortable=()
while IFS= read -r -d '' FPATH; do
  FNAME=$(basename "$FPATH")

  # Extraer componentes del timestamp usando bash regex
  # No hardcodea la extension: usa $EXT_BASH construida desde el argumento EXT
  if [[ "$FNAME" =~ ^${DB}_([0-9]{4})([0-9]{2})([0-9]{2})_([0-9]{6})${EXT_BASH}$ ]]; then
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
done < <(find "$DB_ROOT" -type f -name "${DB}_*${EXT}" -print0 | sort -z)
# Nota: el sort -z inicial es por path, pero no determina el orden final.
# El orden definitivo lo impone el sort de la Fase 2 sobre el timestamp.

# -------------------------------------------------------
# Fase 2 y 3: ordenar por timestamp y construir el JSON array
# -------------------------------------------------------
if [[ ${#sortable[@]} -eq 0 ]]; then
  echo "[]"
else
  items=()
  while IFS= read -r line; do
    # Extraer el JSON: todo lo que sigue a la primera ocurrencia de '::'
    items+=("${line#*::}")
  done < <(printf '%s\n' "${sortable[@]}" | sort)
  # sort sin opciones ordena lexicograficamente por la linea completa.
  # Como cada linea comienza con YYYYMMDD_HHMMSS:: (formato fijo),
  # el orden lexicografico equivale exactamente al orden cronologico.

  (IFS=','; printf '[%s]\n' "${items[*]}")
fi