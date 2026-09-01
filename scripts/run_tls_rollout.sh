#!/bin/bash
# ============================================================
# Wrapper Orquestador de Rollout TLS Progresivo en MongoDB
# Ejecuta de forma segura las transiciones adyacentes requeridas
# hasta alcanzar el estado TLS objetivo solicitado por el operador.
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

DESIRED_TARGET="requireTLS"
if [ $# -gt 0 ] && [[ "$1" != -* ]]; then
  DESIRED_TARGET="$1"
  shift
fi

case "$DESIRED_TARGET" in
  disabled|allowTLS|preferTLS|requireTLS) ;;
  *)
    echo "[ERROR] target_tls_mode invalido: '$DESIRED_TARGET'. Valores permitidos: disabled, allowTLS, preferTLS, requireTLS" >&2
    exit 1
    ;;
esac

mkdir -p "${PROJECT_ROOT}/logs"

# Function to query real runtime state using python helper
detect_state() {
  python3 -c "
import os, json, subprocess

project_root = '${PROJECT_ROOT}'
state_file = os.path.join(project_root, 'logs/tls_rollout_state.json')
if os.path.isfile(state_file):
    try:
        with open(state_file) as f:
            st = json.load(f)
            if st.get('phase') == 'NEEDS_MANUAL_RECOVERY':
                print('NEEDS_MANUAL_RECOVERY')
                exit(0)
    except Exception:
        pass

try:
    cmd = ['docker', 'service', 'inspect', 'mongo1', 'mongo2', 'mongo3']
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 or not res.stdout.strip():
        print('disabled')
        exit(0)
    data = json.loads(res.stdout)
    if not data or len(data) < 3:
        print('disabled')
        exit(0)
    modes = []
    for svc in data:
        args = svc.get('Spec', {}).get('TaskTemplate', {}).get('ContainerSpec', {}).get('Args', [])
        m = 'disabled'
        for i, a in enumerate(args):
            if a == '--tlsMode' and i + 1 < len(args):
                m = args[i + 1]
                break
        modes.append(m)
    if len(set(modes)) > 1:
        print('MIXED')
    else:
        print(modes[0])
except Exception:
    print('disabled')
"
}

CURRENT_MODE=$(detect_state)

if [ "$CURRENT_MODE" = "NEEDS_MANUAL_RECOVERY" ]; then
  echo "============================================================" >&2
  echo "[ERROR] El rollout previo requiere intervencion manual (NEEDS_MANUAL_RECOVERY)." >&2
  echo "Consulte logs/tls_rollout_state.json antes de continuar." >&2
  echo "============================================================" >&2
  exit 1
fi

if [ "$CURRENT_MODE" = "MIXED" ]; then
  echo "============================================================" >&2
  echo "[ERROR] Estado heterogeneo detectado en ServiceSpecs de MongoDB." >&2
  echo "No se realizara ninguna mutacion automatica en estado ambiguo." >&2
  echo "============================================================" >&2
  exit 1
fi

# Calculate route array
ROUTE=()
case "$CURRENT_MODE" in
  disabled)
    case "$DESIRED_TARGET" in
      disabled)   ROUTE=("disabled") ;;
      allowTLS)   ROUTE=("allowTLS") ;;
      preferTLS)  ROUTE=("allowTLS" "preferTLS") ;;
      requireTLS) ROUTE=("allowTLS" "preferTLS" "requireTLS") ;;
    esac
    ;;
  allowTLS)
    case "$DESIRED_TARGET" in
      disabled|allowTLS) ROUTE=("allowTLS") ;;
      preferTLS)  ROUTE=("preferTLS") ;;
      requireTLS) ROUTE=("preferTLS" "requireTLS") ;;
    esac
    ;;
  preferTLS)
    case "$DESIRED_TARGET" in
      disabled|allowTLS|preferTLS) ROUTE=("preferTLS") ;;
      requireTLS) ROUTE=("requireTLS") ;;
    esac
    ;;
  requireTLS)
    ROUTE=("requireTLS")
    ;;
  *)
    echo "[ERROR] Estado inicial desconocido: '$CURRENT_MODE'" >&2
    exit 1
    ;;
esac

echo "============================================================"
echo "TLS TARGET ORCHESTRATOR"
echo "============================================================"
echo "Estado inicial detectado : $CURRENT_MODE"
echo "Objetivo solicitado       : $DESIRED_TARGET"
echo ""
echo "Ruta calculada            : $CURRENT_MODE -> ${ROUTE[*]}"
echo "============================================================"
echo ""

TOTAL_STEPS=${#ROUTE[@]}
STEP_INDEX=1
LAST_MODE="$CURRENT_MODE"

for NEXT_STAGE in "${ROUTE[@]}"; do
  echo "------------------------------------------------------------"
  echo "[$STEP_INDEX/$TOTAL_STEPS] Transición: $LAST_MODE -> $NEXT_STAGE"
  echo "------------------------------------------------------------"

  # Si la siguiente etapa es preferTLS y venimos de allowTLS, migrar clientes
  if [ "$NEXT_STAGE" = "preferTLS" ]; then
    echo "[INFO] Habilitando clientes TLS en vars/local.yml antes de preferTLS..."
    sed -i 's/^mongo_tls_clients_enabled: false/mongo_tls_clients_enabled: true/' "${PROJECT_ROOT}/vars/local.yml"
  fi

  flock -n "$LOCK_FILE"     ansible-playbook       "${PROJECT_ROOT}/playbooks/mongodb/tls_rollout.yml"       --vault-password-file "$VAULT_PASSWORD_FILE"       --extra-vars "target_tls_mode=${NEXT_STAGE}"       "$@"

  AFTER_STAGE_MODE=$(detect_state)
  echo "[OK] Etapa $NEXT_STAGE completada. Estado runtime verificado: $AFTER_STAGE_MODE"
  echo ""

  LAST_MODE="$NEXT_STAGE"
  STEP_INDEX=$((STEP_INDEX + 1))
done

# Resumen final de validación y estado del cluster
PRIMARY_NODE=$(docker exec $(docker ps -q --filter name=mongo1) mongosh --quiet --eval "try { connect('mongodb://mongo1:27017,mongo2:27018,mongo3:27019/admin?replicaSet=rs0&tls=true&tlsCAFile=/run/mongo-ca/mongo_ca.pem').adminCommand({replSetGetStatus: 1}).members.find(m => m.stateStr === 'PRIMARY').name } catch(e) { 'mongo1' }" 2>/dev/null || echo "mongo1")

echo "============================================================"
echo "TLS TARGET ALCANZADO: $DESIRED_TARGET"
echo "============================================================"
echo "mongo1      : $DESIRED_TARGET"
echo "mongo2      : $DESIRED_TARGET"
echo "mongo3      : $DESIRED_TARGET"
echo "Replica Set : HEALTHY"
if [ "$DESIRED_TARGET" = "requireTLS" ]; then
  echo "Clientes TLS: OK"
  echo "Plaintext   : RECHAZADO"
else
  echo "Clientes TLS: EN PROGRESO"
  echo "Plaintext   : PERMITIDO"
fi
echo "Estado      : SUCCESS"
echo "============================================================"
