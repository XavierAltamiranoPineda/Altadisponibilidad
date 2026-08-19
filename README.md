# Alta Disponibilidad de MongoDB con Replica Set y Docker Compose

Este proyecto documenta la implementación, configuración y validación de una arquitectura de **Alta Disponibilidad (HA)** basada en un **Replica Set de MongoDB 7 (rs0)** utilizando **Docker Compose**. El objetivo de esta práctica es garantizar la tolerancia a fallos, la replicación de datos en tiempo real, la elección automática de un nuevo nodo primario (*failover*) ante la caída de un servidor y la posterior resincronización transparente de los datos.

---

## 1. Arquitectura del Replica Set

La topología implementada consta de tres contenedores basados en la imagen oficial `mongo:7-jammy`, interconectados en una red puente (*bridge*) dedicada:

* **`mongo1` (PRIMARY)**: Nodo principal de lectura y escritura (`priority: 2`). Almacena los datos y replica las operaciones a través del *oplog*.
* **`mongo2` (SECONDARY)**: Nodo secundario de replicación. Mantiene una copia idéntica de los datos y está preparado para asumir el rol de primario si `mongo1` falla.
* **`mongo3` (ARBITER)**: Nodo árbitro (`priority: 0`, `votes: 1`). No almacena datos ni replica información; su único propósito es participar en el quórum electoral para desempatar y garantizar la mayoría de votos requerida.

```
                         ┌─────────────────────┐
                         │       mongo1        │
                         │       PRIMARY       │
                         │     27017:27017     │
                         └──────────┬──────────┘
                                    │
                              Replicación
                                    │
                         ┌──────────▼──────────┐
                         │       mongo2        │
                         │      SECONDARY      │
                         │     27018:27017     │
                         └─────────────────────┘

                         ┌─────────────────────┐
                         │       mongo3        │
                         │       ARBITER       │
                         │     27019:27017     │
                         └─────────────────────┘
```

### Rol del Árbitro en MongoDB
* **Participación en elecciones**: Aporta un voto en el proceso de elección cuando el nodo primario no está disponible.
* **Ahorro de recursos**: No almacena colecciones ni requiere almacenamiento persistente significativo.
* **Mantenimiento del quórum**: En un clúster con 2 nodos de datos (número par), la pérdida de 1 nodo dejaría solo 1 voto de 2 (50%, sin mayoría estricta > 50%). Con el árbitro, se cuenta con un total de 3 votos; si cae un nodo de datos, quedan 2 votos de 3 (66.6%), permitiendo elegir un nuevo primario.

---

## 2. Requisitos Previos

Antes de desplegar el entorno, verifique el cumplimiento de los siguientes requisitos en el sistema anfitrión:

* **Docker Engine** (versión 24.x o superior).
* **Docker Compose** (v2 integrado).
* **Terminal / Consola** (PowerShell en Windows o Bash en Linux/macOS).
* **Puertos disponibles en el host**: `27017`, `27018` y `27019`.

### Verificación del Entorno

Compruebe la instalación de Docker y Docker Compose ejecutando:

```bash
docker --version
docker compose version
```

---

## 3. Estructura del Proyecto

El espacio de trabajo debe contener los siguientes archivos:

```
mongo_altadispnobilidad/
├── docker-compose.yml    # Definición de servicios, volúmenes, red, healthchecks y servicio de inicialización
├── init-rs.js            # Script automatizado e idempotente de inicialización del Replica Set
├── mongo-keyfile         # Archivo de clave compartida para la autenticación interna del cluster
└── README.md             # Guía paso a paso y documentación técnica
```

> **Nota sobre seguridad**: El archivo `mongo-keyfile` es utilizado por MongoDB para la autenticación entre miembros del Replica Set (`--keyFile`). El comando de inicio de cada contenedor ajusta automáticamente sus permisos a `chmod 400` antes de iniciar `mongod`.

---

## 4. Parámetros de Configuración y Despliegue

La siguiente tabla resume los parámetros exactos utilizados en el archivo `docker-compose.yml`:

| Parámetro | Valor Configurado |
|---|---|
| **Versión de Imagen** | `mongo:7-jammy` |
| **Nombre del Replica Set** | `rs0` |
| **Red Docker** | `mongo_altadispnobilidad_net-iess` (`net-iess`) |
| **Usuario Administrador** | `mongo_user` |
| **Contraseña** | `mongo_password` |
| **Base de Autenticación** | `admin` |
| **Base de Datos de Pruebas** | `auditoria_iess_db` |
| **Colección de Pruebas** | `prueba_ha` |
| **Contenedor 1** | `ctn-mongo-auditoria-1` (host: `mongo1`, puerto: `27017:27017`) |
| **Contenedor 2** | `ctn-mongo-auditoria-2` (host: `mongo2`, puerto: `27018:27017`) |
| **Contenedor 3** | `ctn-mongo-auditoria-3` (host: `mongo3`, puerto: `27019:27017`) |
| **Contenedor Inicializador** | `ctn-mongo-init` (ejecuta `init-rs.js` contra `mongo1` tras healthchecks) |

---

## 5. Creación de la Infraestructura

### Paso 5.1: Iniciar los Contenedores y la Automatización
Ejecute el siguiente comando para levantar los servicios en segundo plano:

```bash
docker compose up -d
```

### Paso 5.2: Validar el Estado de los Contenedores
Verifique que los tres nodos principales estén en estado activo (`Up`), saludables (`healthy`) y que el contenedor inicializador haya finalizado con éxito (`Exited (0)`):

```bash
docker ps -a
```

*Resultado esperado*:
* `ctn-mongo-auditoria-1`: `Up ... (healthy)`
* `ctn-mongo-auditoria-2`: `Up ... (healthy)`
* `ctn-mongo-auditoria-3`: `Up ... (healthy)`
* `ctn-mongo-init`: `Exited (0)`

### Paso 5.3: Revisar Registros de Inicio e Inicialización (Opcional)
Para confirmar la ejecución automatizada de `init-rs.js`:

```bash
docker logs ctn-mongo-init
```

O para consultar los logs de los nodos individuales:

```bash
docker logs ctn-mongo-auditoria-1
docker logs ctn-mongo-auditoria-2
docker logs ctn-mongo-auditoria-3
```

---

## 6. Acceso a MongoDB (`mongosh`)

Para interactuar con cada instancia de MongoDB a través del cliente `mongosh`, utilice los siguientes comandos autenticados:

* **Acceso al nodo 1 (`mongo1`)**:
  ```bash
  docker exec -it ctn-mongo-auditoria-1 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin
  ```

* **Acceso al nodo 2 (`mongo2`)**:
  ```bash
  docker exec -it ctn-mongo-auditoria-2 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin
  ```

* **Acceso al nodo 3 (`mongo3` - Árbitro)**:
  ```bash
  docker exec -it ctn-mongo-auditoria-3 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin
  ```

> Las operaciones administrativas y de replicación se ejecutan inicialmente conectado a `mongo1`.

---

## 7. Configuración del Replica Set

### Paso 7.1: Inicializar el Replica Set en `mongo1`
Ingrese a la consola interactiva de `mongo1`:

```bash
docker exec -it ctn-mongo-auditoria-1 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin
```

Inicialice el Replica Set `rs0` asignando mayor prioridad a `mongo1`:

```javascript
rs.initiate({
  _id: "rs0",
  members: [
    {
      _id: 0,
      host: "mongo1:27017",
      priority: 2
    }
  ]
})
```

*Resultado esperado*: `{ ok: 1 }`. El prompt cambiará a `rs0 [direct: primary] admin>`.

### Paso 7.2: Verificar el Estado Inicial
Compruebe el estado del conjunto y el rol del nodo:

```javascript
rs.status()
```

O verifique con el comando `hello`:

```javascript
db.hello()
```

*Resultado esperado*: `mongo1:27017` figura con `stateStr: "PRIMARY"` e `isWritablePrimary: true`.

---

## 8. Incorporación del Nodo Secundario (`mongo2`)

Desde la sesión en `mongo1` (PRIMARY), agregue el segundo nodo de datos:

```javascript
rs.add("mongo2:27017")
```

*Resultado esperado*: `{ ok: 1 }`.

### Verificación:
Consulte nuevamente el estado del Replica Set:

```javascript
rs.status()
```

*Resultado esperado*:
* `mongo1:27017` → `PRIMARY`
* `mongo2:27017` → `SECONDARY`
* `votingMembersCount`: `2`
* `writableVotingMembersCount`: `2`

---

## 9. Configuración del Write Concern Global

En MongoDB 7, al incorporar un árbitro en un conjunto que cuenta con un número par de nodos de datos, se genera la validación `NewReplicaSetConfigurationIncompatible` si el *Write Concern* por defecto no está explícitamente configurado para soportar mayorías de nodos escribibles.

### Paso 9.1: Consultar el Write Concern Actual
Ejecute en `mongo1`:

```javascript
db.adminCommand({
  getDefaultRWConcern: 1
})
```

### Paso 9.2: Establecer `w: "majority"`
Configure de forma explícita el Write Concern global para evitar bloqueos e incompatibilidades:

```javascript
db.adminCommand({
  setDefaultRWConcern: 1,
  defaultWriteConcern: {
    w: "majority",
    wtimeout: 0
  }
})
```

### Paso 9.3: Confirmar la Configuración
Vuelva a consultar para verificar:

```javascript
db.adminCommand({
  getDefaultRWConcern: 1
})
```

*Resultado esperado*:
```javascript
{
  defaultWriteConcern: { w: 'majority', wtimeout: 0 },
  defaultWriteConcernSource: 'global',
  ok: 1
}
```

---

## 10. Incorporación del Nodo Árbitro (`mongo3`)

Una vez ajustado el Write Concern, proceda a registrar el árbitro desde `mongo1`:

```javascript
rs.addArb("mongo3:27017")
```

*Resultado esperado*: `{ ok: 1 }`.

### Verificación del Conjunto Completo:
Ejecute:

```javascript
rs.status()
```

*Resultado esperado*:
* `mongo1:27017` → `stateStr: "PRIMARY"`
* `mongo2:27017` → `stateStr: "SECONDARY"`
* `mongo3:27017` → `stateStr: "ARBITER"`
* `votingMembersCount`: `3`
* `writableVotingMembersCount`: `2`

---

## 11. Verificación Inicial de Replicación de Datos

### Paso 11.1: Insertar Documento en el PRIMARY (`mongo1`)
Desde `mongo1`, seleccione la base de datos `auditoria_iess_db` e inserte un documento en la colección `prueba_ha`:

```javascript
use auditoria_iess_db

db.prueba_ha.insertOne({
  mensaje: "Prueba de alta disponibilidad",
  fecha: new Date(),
  origen: "mongo1"
})
```

Compruebe la inserción local:

```javascript
db.prueba_ha.find()
```

### Paso 11.2: Validar la Replicación en el SECONDARY (`mongo2`)
Abra una nueva terminal e ingrese a `mongo2`:

```bash
docker exec -it ctn-mongo-auditoria-2 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin
```

Consulte la colección en `mongo2`:

```javascript
use auditoria_iess_db

db.prueba_ha.find()
```

*Resultado esperado*: El documento insertado en `mongo1` se visualiza inmediatamente en `mongo2`.

---

## 12. Inspección del Estado y Métricas de Replicación

### Paso 12.1: Campos Clave de `rs.status()`
Al ejecutar `rs.status()`, preste especial atención a las siguientes propiedades de cada miembro:

* **`name`**: Identificador de host y puerto del nodo (`host:puerto`).
* **`health`**: Estado de salud (`1` = operativo, `0` = inalcanzable).
* **`stateStr`**: Rol actual en el cluster (`PRIMARY`, `SECONDARY`, `ARBITER`).
* **`syncSourceHost`**: Host desde el cual el nodo secundario está replicando operaciones.
* **`optime` / `optimeDate`**: Marca de tiempo del último registro del *oplog* aplicado en el nodo.

### Paso 12.2: Verificar Retraso de Replicación (*Replication Lag*)
Desde `mongo1`, ejecute:

```javascript
rs.printSecondaryReplicationInfo()
```

*Resultado esperado*:
```
source: mongo2:27017
syncedTo: Wed Aug 19 2026 ...
0 secs (0 hrs) behind the primary
```
Un retraso de `0 secs` certifica que el nodo secundario está al día con respecto al primario.

---

## 13. Simulación de Caída del PRIMARY (*Failover*)

Para comprobar la tolerancia a fallos, forzaremos la caída del nodo primario actual.

### Paso 13.1: Confirmar el PRIMARY Actual
En `mongosh`:

```javascript
rs.status()
```
Confirmamos que `mongo1` posee el rol `PRIMARY`. Salga de `mongosh`:

```javascript
exit
```

### Paso 13.2: Detener el Contenedor `mongo1`
Desde la terminal PowerShell / Bash:

```bash
docker stop ctn-mongo-auditoria-1
```

Verifique que el contenedor se detuvo:

```bash
docker ps
```

*Resultado esperado*: Solo `ctn-mongo-auditoria-2` y `ctn-mongo-auditoria-3` permanecen en ejecución.

---

## 14. Verificación de la Elección Automática

Acceda a `mongo2` inmediatamente tras la caída de `mongo1`:

```bash
docker exec -it ctn-mongo-auditoria-2 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin
```

Consulte el estado del Replica Set:

```javascript
rs.status()
```

### Análisis del Resultado:
1. **`mongo2` ha sido promovido**: Su `stateStr` pasa a `"PRIMARY"`.
2. **`mongo1` es detectado como inactivo**: Su `health` es `0` y `stateStr` muestra `"(not reachable/healthy)"`.
3. **`mongo3` (Árbitro)**: Permanece como `"ARBITER"` y emitió el voto necesario para que `mongo2` alcanzara la mayoría de votos requerida (2 de 3 votos = 66.7%).

Esto demuestra el mecanismo de **elección automática y failover sin intervención humana**.

---

## 15. Escritura Continua Durante la Caída de `mongo1`

Con `mongo1` aún fuera de servicio, verifique que el clúster sigue aceptando escrituras a través del nuevo nodo primario (`mongo2`).

Desde `mongo2` (PRIMARY):

```javascript
use auditoria_iess_db

db.prueba_ha.insertOne({
  mensaje: "Escritura después de caída de mongo1",
  fecha: new Date(),
  origen: "mongo2"
})
```

Compruebe la colección:

```javascript
db.prueba_ha.find()
```

*Resultado esperado*: Se visualizan tanto el registro original como el nuevo registro creado durante la contingencia.

---

## 16. Recuperación y Reincorporación de `mongo1`

### Paso 16.1: Reiniciar el Contenedor
Salga de `mongosh` en `mongo2` (`exit`) y levante el contenedor `ctn-mongo-auditoria-1` desde la terminal:

```bash
docker start ctn-mongo-auditoria-1
```

Espere entre 5 y 10 segundos para que el servicio inicie y establezca comunicación con la red Docker.

### Paso 16.2: Conectarse a `mongo1`
Acceda nuevamente a `mongo1`:

```bash
docker exec -it ctn-mongo-auditoria-1 mongosh -u mongo_user -p mongo_password --authenticationDatabase admin
```

Ejecute:

```javascript
rs.status()
```

*Resultado esperado*: `mongo1` se reincorpora con éxito al conjunto. Debido a que tiene asignada `priority: 2`, el clúster negociará y devolverá a `mongo1` el rol de `PRIMARY`, mientras que `mongo2` regresará a `SECONDARY`.

---

## 17. Verificación de Resincronización de Datos

Compruebe que los datos escritos en `mongo2` durante el periodo en que `mongo1` estuvo apagado fueron replicados automáticamente a `mongo1`.

Desde `mongo1`:

```javascript
use auditoria_iess_db

db.prueba_ha.find().sort({fecha: 1})
```

*Resultado esperado*: Se listan los dos documentos ordenados cronológicamente:
1. `{"mensaje": "Prueba de alta disponibilidad", "origen": "mongo1"}`
2. `{"mensaje": "Escritura después de caída de mongo1", "origen": "mongo2"}`

### Verificación Final del Replication Lag
Ejecute en `mongo1`:

```javascript
rs.printSecondaryReplicationInfo()
```

*Resultado obtenido*:
```
source: mongo2:27017
syncedTo: Wed Aug 19 2026 ...
0 secs (0 hrs) behind the primary
```

Esto confirma la total consistencia y sincronización del clúster.

---

## 18. Resumen de la Prueba de Alta Disponibilidad

| Etapa | Acción Realizada | Resultado Esperado / Observado | Estado del Cluster |
|:---|:---|:---|:---|
| **1. Despliegue** | `docker compose up -d` | 3 contenedores activos y saludables | Nodos independientes |
| **2. Inicialización** | `rs.initiate(...)` en `mongo1` | `mongo1` asume rol `PRIMARY` | `rs0` (1 nodo) |
| **3. Agregar Secundario** | `rs.add("mongo2:27017")` | `mongo2` se sincroniza como `SECONDARY` | `rs0` (2 nodos de datos) |
| **4. Write Concern** | `setDefaultRWConcern` a `majority` | Configuración global compatible establecida | Write concern validado |
| **5. Agregar Árbitro** | `rs.addArb("mongo3:27017")` | `mongo3` registrado como `ARBITER` | `rs0` (3 nodos / 2 datos + 1 arb) |
| **6. Replicación Inicial** | `insertOne` en `mongo1` | Documento visible en `mongo2` | Replicación activa |
| **7. Fallo del Primario** | `docker stop ctn-mongo-auditoria-1` | `mongo1` queda inalcanzable | Quórum 2/3 disponible |
| **8. Elección Automática** | Verificación en `mongo2` | `mongo2` es electo nuevo `PRIMARY` | Failover completado |
| **9. Escritura en Fallo** | `insertOne` en `mongo2` | Escritura exitosa en nuevo primario | Disponibilidad de escritura |
| **10. Recuperación** | `docker start ctn-mongo-auditoria-1` | `mongo1` se reincorpora al cluster | Sincronización automática |
| **11. Consistencia Final** | `find()` y `rs.printSecondaryReplicationInfo()` | Todos los datos presentes (`replLag = 0s`) | Consistencia restaurada |

---

## 19. Comandos de Diagnóstico Frecuentes

### Gestión de Contenedores (Docker)
```bash
# Listar contenedores en ejecución
docker ps

# Listar servicios administrados por Compose
docker compose ps

# Visualizar registros en tiempo real de cada nodo
docker logs -f ctn-mongo-auditoria-1
docker logs -f ctn-mongo-auditoria-2
docker logs -f ctn-mongo-auditoria-3
```

### Consultas de Estado en MongoDB (`mongosh`)
```javascript
// Estado detallado de los miembros del Replica Set
rs.status()

// Configuración actual del Replica Set (prioridades, votos, hosts)
rs.conf()

// Resumen del nodo y topología actual
db.hello()

// Diagnóstico de retraso de replicación de nodos secundarios
rs.printSecondaryReplicationInfo()

// Consulta del Write Concern por defecto
db.adminCommand({ getDefaultRWConcern: 1 })
```

---

## 20. Solución de Problemas Comunes

### 1. Error `NewReplicaSetConfigurationIncompatible` al agregar el Árbitro
* **Causa**: MongoDB 7 valida que las opciones de *Write Concern* por defecto satisfagan los requisitos de quórum de nodos con capacidad de escritura. Al agregar un árbitro a un conjunto con 2 nodos de datos, se requiere una definición explícita.
* **Solución**:
  Ejecutar en el PRIMARY antes de agregar el árbitro:
  ```javascript
  db.adminCommand({
    setDefaultRWConcern: 1,
    defaultWriteConcern: {
      w: "majority",
      wtimeout: 0
    }
  })
  ```
  Luego reintentar:
  ```javascript
  rs.addArb("mongo3:27017")
  ```

### 2. Error de Resolución de Nombres de Red (`NodeNotFound` / `HostUnreachable`)
* **Causa**: Uno o más contenedores no pueden resolver los nombres `mongo1:27017`, `mongo2:27017` o `mongo3:27017`.
* **Solución**:
  Verifique que todos los contenedores pertenezcan a la red `net-iess`:
  ```bash
  docker network inspect mongo_altadispnobilidad_net-iess
  ```
  Asegúrese de que los hostnames coincidan con la directiva `hostname` definida en el archivo `docker-compose.yml`.

### 3. Error `permissions on /etc/mongo-keyfile are too open`
* **Causa**: MongoDB exige que el archivo de clave tenga permisos restrictivos (`chmod 400` o `600`) y pertenezca al usuario de ejecución.
* **Solución**:
  Verifique que en `docker-compose.yml` el comando de inicio incluya `chmod 400 /etc/mongo-keyfile` previo a `mongod`, y que el montaje no tenga la directiva `:ro` para permitir el cambio de permisos en el contenedor.

---

## 21. Conclusión

La práctica realizada demostró de manera empírica y reproducible el funcionamiento de la **Alta Disponibilidad en MongoDB 7**:

1. **Tolerancia a fallos**: La caída abrupta del nodo primario no detuvo el servicio ni provocó pérdida de información.
2. **Quórum con árbitro**: La presencia de `mongo3` garantizó una mayoría estricta (2 de 3 votos), permitiendo promover a `mongo2` como nuevo primario sin requerir un tercer nodo de almacenamiento completo.
3. **Continuidad de operaciones**: Las operaciones de lectura y escritura continuaron ejecutándose durante la ventana de contingencia.
4. **Resincronización automática**: Al restablecerse el nodo caído, este se reintegró al Replica Set, aplicó las operaciones pendientes del *oplog* y alcanzó un retraso de replicación de `0 segundos`.
