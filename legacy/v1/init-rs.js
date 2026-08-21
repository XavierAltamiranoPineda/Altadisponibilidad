/**
 * init-rs.js
 * Script de inicialización y configuración automatizada e idempotente
 * para el Replica Set rs0 en MongoDB 7.
 *
 * Topología:
 * - mongo1:27017 -> PRIMARY (priority: 2)
 * - mongo2:27017 -> SECONDARY
 * - mongo3:27017 -> ARBITER
 */

const RS_NAME = "rs0";
const PRIMARY_HOST = "mongo1:27017";
const SECONDARY_HOST = "mongo2:27017";
const ARBITER_HOST = "mongo3:27017";
const ALL_NODES = [PRIMARY_HOST, SECONDARY_HOST, ARBITER_HOST];

const TIMEOUT_NODES_MS = 120000;      // 120 segundos para disponibilidad de nodos
const TIMEOUT_PRIMARY_MS = 60000;     // 60 segundos para elección de Primary
const TIMEOUT_STABILIZE_MS = 30000;   // 30 segundos para estabilización final
const RETRY_INTERVAL_MS = 2000;       // 2 segundos entre reintentos

const username = (typeof process !== "undefined" && process.env && process.env.MONGO_INITDB_ROOT_USERNAME) || "mongo_user";
const password = (typeof process !== "undefined" && process.env && process.env.MONGO_INITDB_ROOT_PASSWORD) || "mongo_password";
const authDb = "admin";

console.log("================================================================================");
console.log("   INICIANDO AUTOMATIZACIÓN DE REPLICA SET MONGODB (" + RS_NAME + ")   ");
console.log("================================================================================");

/**
 * Verifica si un nodo responde a comandos ping de MongoDB
 */
function isNodeHealthy(host) {
  try {
    const uri = `mongodb://${encodeURIComponent(username)}:${encodeURIComponent(password)}@${host}/${authDb}?directConnection=true&serverSelectionTimeoutMS=2000`;
    const conn = new Mongo(uri);
    const res = conn.getDB(authDb).runCommand({ ping: 1 });
    conn.close();
    return res && res.ok === 1;
  } catch (e) {
    try {
      const uriNoAuth = `mongodb://${host}/${authDb}?directConnection=true&serverSelectionTimeoutMS=2000`;
      const connNoAuth = new Mongo(uriNoAuth);
      const resNoAuth = connNoAuth.getDB(authDb).runCommand({ ping: 1 });
      connNoAuth.close();
      return resNoAuth && resNoAuth.ok === 1;
    } catch (err) {
      return false;
    }
  }
}

/**
 * Espera con timeout a que todos los nodos requeridos estén disponibles
 */
function waitForAllNodes(nodes, timeoutMs, intervalMs) {
  console.log(`[INFO] Verificando disponibilidad de red y servicio en los nodos: ${nodes.join(", ")}`);
  for (const node of nodes) {
    const start = Date.now();
    let ready = false;
    console.log(`[INFO] Esperando a que el nodo '${node}' esté disponible (timeout: ${timeoutMs / 1000}s)...`);
    while (Date.now() - start < timeoutMs) {
      if (isNodeHealthy(node)) {
        console.log(`[OK] Nodo '${node}' está disponible y respondiendo.`);
        ready = true;
        break;
      }
      sleep(intervalMs);
    }
    if (!ready) {
      console.error(`[ERROR] Timeout alcanzado (${timeoutMs / 1000}s) esperando al nodo '${node}'.`);
      return false;
    }
  }
  return true;
}

/**
 * Obtiene el estado actual del Replica Set de forma segura
 */
function getReplSetStatus() {
  try {
    return rs.status();
  } catch (err) {
    return null;
  }
}

/**
 * Espera a que el cluster tenga un nodo PRIMARY activo y listo para escrituras
 */
function waitForPrimary(timeoutMs, intervalMs) {
  const start = Date.now();
  console.log(`[INFO] Esperando a que un nodo asuma el rol PRIMARY (timeout: ${timeoutMs / 1000}s)...`);
  while (Date.now() - start < timeoutMs) {
    try {
      const hello = db.hello();
      if (hello && (hello.isWritablePrimary || hello.ismaster)) {
        console.log(`[OK] Nodo actual (${hello.me || PRIMARY_HOST}) es PRIMARY y listo para escrituras.`);
        return true;
      }
    } catch (e) {
      // Ignorar error transitorio durante negociación de roles
    }

    try {
      const status = rs.status();
      if (status && status.ok === 1 && status.members) {
        const primary = status.members.find(m => m.stateStr === "PRIMARY");
        if (primary) {
          console.log(`[OK] Se detectó PRIMARY activo: ${primary.name}`);
          return true;
        }
      }
    } catch (e) {
      // Ignorar error transitorio
    }
    sleep(intervalMs);
  }
  console.error(`[ERROR] Timeout alcanzado (${timeoutMs / 1000}s) esperando a un PRIMARY activo.`);
  return false;
}

// -----------------------------------------------------------------------------
// 1. ESPERA Y VALIDACIÓN DE DISPONIBILIDAD DE NODOS
// -----------------------------------------------------------------------------
if (!waitForAllNodes(ALL_NODES, TIMEOUT_NODES_MS, RETRY_INTERVAL_MS)) {
  console.error("[FATAL] No todos los nodos de MongoDB respondieron a tiempo. Abortando.");
  quit(1);
}

// -----------------------------------------------------------------------------
// 2. INICIALIZACIÓN IDEMPOTENTE DEL REPLICA SET
// -----------------------------------------------------------------------------
let currentStatus = getReplSetStatus();

if (!currentStatus || currentStatus.ok !== 1) {
  console.log(`[INFO] El Replica Set '${RS_NAME}' no está inicializado. Ejecutando rs.initiate()...`);
  const initConfig = {
    _id: RS_NAME,
    members: [
      {
        _id: 0,
        host: PRIMARY_HOST,
        priority: 2
      }
    ]
  };

  const initRes = rs.initiate(initConfig);
  if (initRes.ok !== 1) {
    // Si otro proceso o nodo lo inició concurrentemente, reintentar verificación
    currentStatus = getReplSetStatus();
    if (!currentStatus || currentStatus.ok !== 1) {
      console.error("[ERROR] Falló rs.initiate():", JSON.stringify(initRes));
      quit(1);
    }
    console.log("[INFO] Replica Set fue inicializado concurrentemente.");
  } else {
    console.log("[OK] rs.initiate() ejecutado exitosamente en mongo1.");
  }
} else {
  console.log(`[INFO] Replica Set '${currentStatus.set}' ya se encuentra inicializado.`);
}

// -----------------------------------------------------------------------------
// 3. ESPERAR A QUE MONGO1 SEA PRIMARY
// -----------------------------------------------------------------------------
if (!waitForPrimary(TIMEOUT_PRIMARY_MS, RETRY_INTERVAL_MS)) {
  console.error("[FATAL] No se logró el estado PRIMARY en el cluster.");
  quit(1);
}

// -----------------------------------------------------------------------------
// 4. INCORPORACIÓN IDEMPOTENTE DE MONGO2 (SECONDARY)
// -----------------------------------------------------------------------------
currentStatus = getReplSetStatus();
let existingMemberNames = (currentStatus && currentStatus.members)
  ? currentStatus.members.map(m => m.name)
  : [];

if (!existingMemberNames.includes(SECONDARY_HOST)) {
  console.log(`[INFO] Agregando nodo secundario '${SECONDARY_HOST}' al Replica Set...`);
  const addRes = rs.add(SECONDARY_HOST);
  if (addRes.ok !== 1) {
    console.error(`[ERROR] No se pudo agregar '${SECONDARY_HOST}':`, JSON.stringify(addRes));
    quit(1);
  }
  console.log(`[OK] Nodo secundario '${SECONDARY_HOST}' agregado correctamente.`);
} else {
  console.log(`[INFO] Nodo secundario '${SECONDARY_HOST}' ya es miembro del Replica Set.`);
}

// -----------------------------------------------------------------------------
// 5. CONFIGURACIÓN IDEMPOTENTE DE WRITE CONCERN GLOBAL
// -----------------------------------------------------------------------------
console.log("[INFO] Verificando configuración de Write Concern global...");
let defaultRWConcern = null;
try {
  defaultRWConcern = db.adminCommand({ getDefaultRWConcern: 1 });
} catch (e) {
  console.log("[WARN] No se pudo consultar getDefaultRWConcern:", e.message);
}

const isMajorityConfigured = defaultRWConcern &&
  defaultRWConcern.defaultWriteConcern &&
  defaultRWConcern.defaultWriteConcern.w === "majority" &&
  defaultRWConcern.defaultWriteConcernSource === "global";

if (!isMajorityConfigured) {
  console.log("[INFO] Configurando Write Concern global { w: 'majority', wtimeout: 0 }...");
  const setRwRes = db.adminCommand({
    setDefaultRWConcern: 1,
    defaultWriteConcern: {
      w: "majority",
      wtimeout: 0
    }
  });

  if (setRwRes.ok !== 1) {
    console.error("[ERROR] No se pudo configurar setDefaultRWConcern:", JSON.stringify(setRwRes));
    quit(1);
  }
  console.log("[OK] Write Concern global configurado exitosamente a 'majority'.");
} else {
  console.log("[INFO] Write Concern global ya está configurado en 'majority'.");
}

// -----------------------------------------------------------------------------
// 6. INCORPORACIÓN IDEMPOTENTE DE MONGO3 (ARBITER)
// -----------------------------------------------------------------------------
currentStatus = getReplSetStatus();
const membersList = (currentStatus && currentStatus.members) ? currentStatus.members : [];
const arbiterNode = membersList.find(m => m.name === ARBITER_HOST);

if (!arbiterNode) {
  console.log(`[INFO] Agregando nodo árbitro '${ARBITER_HOST}' al Replica Set...`);
  const addArbRes = rs.addArb(ARBITER_HOST);
  if (addArbRes.ok !== 1) {
    console.error(`[ERROR] No se pudo agregar el árbitro '${ARBITER_HOST}':`, JSON.stringify(addArbRes));
    quit(1);
  }
  console.log(`[OK] Árbitro '${ARBITER_HOST}' agregado correctamente.`);
} else {
  console.log(`[INFO] Árbitro '${ARBITER_HOST}' ya está presente con rol: ${arbiterNode.stateStr}.`);
}

// -----------------------------------------------------------------------------
// 7. VERIFICACIÓN Y ESTABILIZACIÓN FINAL
// -----------------------------------------------------------------------------
console.log(`[INFO] Verificando topología final del Replica Set (timeout: ${TIMEOUT_STABILIZE_MS / 1000}s)...`);
let verificationSuccessful = false;
const startVerify = Date.now();

while (Date.now() - startVerify < TIMEOUT_STABILIZE_MS) {
  const finalStatus = getReplSetStatus();
  if (finalStatus && finalStatus.ok === 1 && finalStatus.members) {
    const m1 = finalStatus.members.find(m => m.name === PRIMARY_HOST);
    const m2 = finalStatus.members.find(m => m.name === SECONDARY_HOST);
    const m3 = finalStatus.members.find(m => m.name === ARBITER_HOST);

    const m1Ready = m1 && (m1.stateStr === "PRIMARY" || m1.stateStr === "SECONDARY") && m1.health === 1;
    const m2Ready = m2 && (m2.stateStr === "SECONDARY" || m2.stateStr === "PRIMARY") && m2.health === 1;
    const m3Ready = m3 && m3.stateStr === "ARBITER" && m3.health === 1;

    if (m1Ready && m2Ready && m3Ready) {
      console.log("\n================================================================================");
      console.log("             REPLICA SET CONFIGURADO Y OPERATIVO EXITOSAMENTE                   ");
      console.log("================================================================================");
      console.log(`* Replica Set:                ${finalStatus.set}`);
      console.log(`* Total Miembros Votantes:    ${finalStatus.votingMembersCount}`);
      console.log(`* Nodos Votantes Escribibles: ${finalStatus.writableVotingMembersCount}`);
      console.log(`* ${PRIMARY_HOST.padEnd(16)} -> Estado: ${m1.stateStr.padEnd(10)} | Salud: ${m1.health}`);
      console.log(`* ${SECONDARY_HOST.padEnd(16)} -> Estado: ${m2.stateStr.padEnd(10)} | Salud: ${m2.health}`);
      console.log(`* ${ARBITER_HOST.padEnd(16)} -> Estado: ${m3.stateStr.padEnd(10)} | Salud: ${m3.health}`);
      console.log("================================================================================\n");
      verificationSuccessful = true;
      break;
    }
  }
  sleep(RETRY_INTERVAL_MS);
}

if (!verificationSuccessful) {
  console.error("[ERROR] No se pudo verificar la convergencia completa del Replica Set.");
  quit(1);
}

console.log("[SUCCESS] Proceso de inicialización finalizado con éxito.");
quit(0);
