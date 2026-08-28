# Alta Disponibilidad y Backups de MongoDB con Ansible y Docker Swarm

Proyecto de automatización para desplegar, proteger, validar y probar un clúster MongoDB con alta disponibilidad, replicación, TLS, autenticación, respaldo y recuperación, utilizando **Ansible**, **Docker Swarm** y **MongoDB Replica Set**.

La solución fue diseñada para que el ciclo técnico completo pueda ejecutarse de forma reproducible desde playbooks y scripts, evitando configuraciones manuales sobre los nodos MongoDB. La guía operativa completa para preparar el repositorio, desplegar el entorno y ejecutar todas las pruebas se encuentra en:

> **[AltadisponibilidadBackups.md](./AltadisponibilidadBackups.md)**

Este README describe la arquitectura, los componentes, los mecanismos de seguridad, la estrategia de alta disponibilidad y el sistema de backup/restore implementados. No contiene la secuencia paso a paso de ejecución.

---

## Objetivo del proyecto

El objetivo principal es disponer de una solución automatizada para MongoDB que cubra dos áreas críticas:

### Alta disponibilidad

- Replica Set de tres nodos.
- Elección automática de PRIMARY.
- Nodos SECONDARY preparados para asumir el servicio.
- Prueba automatizada de failover.
- Recuperación y reincorporación del nodo.
- Persistencia mediante volúmenes Docker.
- Configuración de prioridades de elección.
- Validación automática de la topología del clúster.

### Respaldo y recuperación

- Backups completos automatizados.
- Uso de herramientas oficiales de MongoDB.
- Compresión de respaldos.
- Checksum SHA-256.
- Bitácoras.
- Retención.
- Automatización mediante cron.
- Restauración controlada.
- Prueba de disaster recovery.

La solución se complementa con **Ansible Vault**, **KeyFile**, **PKI**, **TLS**, **Docker Secrets** y validaciones automáticas.

---

## Arquitectura general

La arquitectura está compuesta por tres servicios MongoDB ejecutados sobre Docker Swarm:

```text
                         CLIENTES
                 Compass / mongosh / Tools
                           |
                           |
                          TLS
                           |
                           v
                 localhost:27017
                           |
                           v
                    +-------------+
                    |   mongo1    |
                    | priority=2  |
                    +-------------+
                       /       \
                      /         \
                     /           \
                    v             v
             +-------------+ +-------------+
             |   mongo2    | |   mongo3    |
             | priority=1  | | priority=1  |
             +-------------+ +-------------+
                    \             /
                     \           /
                      \         /
                       Replica Set
                           rs0
```

Características principales:

- **MongoDB:** `mongo:7-jammy`
- **Replica Set:** `rs0`
- **Nodos:** `mongo1`, `mongo2`, `mongo3`
- **Red Swarm:** overlay
- **Red lógica:** `mongo_swarm_net`
- **Persistencia:** volumen independiente por nodo
- **Autenticación interna:** KeyFile
- **Credenciales:** Ansible Vault
- **Cifrado de transporte:** TLS
- **Certificados:** PKI local
- **Distribución de secretos:** Docker Secrets
- **Automatización:** Ansible
- **Backups:** `mongodump`
- **Restore:** `mongorestore`

---

## Alta disponibilidad

MongoDB se configura como un Replica Set de tres miembros.

Estado esperado:

```text
mongo1   PRIMARY
mongo2   SECONDARY
mongo3   SECONDARY
```

Prioridades:

```text
mongo1 = 2
mongo2 = 1
mongo3 = 1
```

`mongo1` tiene mayor preferencia electoral, mientras que `mongo2` y `mongo3` pueden participar en elecciones y asumir el rol PRIMARY cuando sea necesario.

### Replica Set

Replica Set:

```text
rs0
```

Miembros:

```text
mongo1:27017
mongo2:27017
mongo3:27017
```

MongoDB replica automáticamente las operaciones realizadas en el PRIMARY hacia los SECONDARY.

### Failover

El proyecto incluye una prueba automatizada que:

- identifica el PRIMARY;
- detiene temporalmente el nodo principal;
- comprueba su indisponibilidad;
- espera una nueva elección;
- valida la aparición de un nuevo PRIMARY;
- comprueba continuidad de datos;
- recupera el nodo detenido;
- espera su reincorporación;
- valida nuevamente la salud del Replica Set.

### Failback y prioridades

Después de recuperar un nodo, MongoDB lo reincorpora al Replica Set.

Las prioridades permiten definir preferencia electoral sin forzar permanentemente elecciones artificiales.

---

## Docker Swarm

Docker Swarm administra los servicios:

```text
mongo1
mongo2
mongo3
```

Cada servicio utiliza:

- imagen MongoDB;
- red overlay;
- volumen persistente;
- Docker Secrets;
- configuración de Replica Set;
- autenticación;
- TLS.

### Persistencia

Conceptualmente:

```text
mongo1 -> mongo1_data
mongo2 -> mongo2_data
mongo3 -> mongo3_data
```

Los datos no dependen del ciclo de vida de un contenedor individual.

### Red

Los nodos se comunican sobre:

```text
mongo_swarm_net
```

Los nombres de servicio actúan como endpoints internos estables:

```text
mongo1
mongo2
mongo3
```

---

## Automatización con Ansible

Ansible es el componente central del proyecto.

La solución separa responsabilidades por áreas:

```text
playbooks/
├── infrastructure/
├── security/
├── mongodb/
├── validation/
├── tests/
├── backup/
└── recovery/
```

### Infraestructura

Prepara:

- Docker Swarm;
- red overlay;
- recursos requeridos por MongoDB;
- exposición controlada de `mongo1` para administración local.

### Seguridad

Gestiona:

- KeyFile;
- Docker Secret del KeyFile;
- CA;
- certificados TLS;
- certificados por nodo;
- Docker Secrets TLS;
- validación de PKI.

### MongoDB

Automatiza:

- creación de servicios;
- inicialización de `rs0`;
- despliegue de nodos;
- creación del usuario administrador;
- incorporación de miembros;
- configuración de prioridades;
- rollout TLS.

### Validación

Comprueba:

- servicios;
- autenticación;
- Replica Set;
- PRIMARY/SECONDARY;
- salud;
- TLS;
- certificados;
- conectividad.

### Pruebas

Incluye pruebas de:

- replicación;
- failover;
- failback;
- datos;
- backup;
- restore;
- disaster recovery;
- cron.

---

## Seguridad

La solución implementa varias capas:

```text
Credenciales
    |
    v
Ansible Vault

Autenticación interna
    |
    v
KeyFile

Transporte
    |
    v
TLS

Identidad de nodos
    |
    v
Certificados X.509

Distribución segura
    |
    v
Docker Secrets
```

---

## Ansible Vault

Las credenciales se almacenan cifradas en:

```text
vars/vault_mongodb.yml
```

Puede contener:

```yaml
mongo_admin_user: ...
mongo_admin_password: ...

mongo_backup_user: ...
mongo_backup_password: ...

mongo_restore_user: ...
mongo_restore_password: ...
```

La contraseña del Vault se mantiene localmente en:

```text
secrets/vault_password
```

Este archivo no debe versionarse.

---

## KeyFile

El Replica Set utiliza KeyFile para autenticación interna entre nodos.

Flujo:

```text
Ansible
   |
   v
mongo-keyfile
   |
   v
Docker Secret
   |
   v
mongo1 / mongo2 / mongo3
```

Esto permite que los miembros se reconozcan como nodos autorizados del clúster.

---

## PKI

El proyecto genera una PKI local para TLS.

Se generan:

- CA local;
- clave privada de CA;
- certificado de CA;
- clave privada por nodo;
- CSR por nodo;
- certificado por nodo;
- PEM por nodo.

Conceptualmente:

```text
CA local
├── firma mongo1
├── firma mongo2
└── firma mongo3
```

Estructura:

```text
secrets/
└── mongodb-tls/
    └── local/
        ├── ca/
        └── v1/
            ├── mongo1/
            ├── mongo2/
            ├── mongo3/
            └── mongo_ca.pem
```

Los secretos criptográficos deben mantenerse fuera del repositorio.

---

## TLS

El estado final esperado es:

```text
requireTLS
```

MongoDB utiliza parámetros equivalentes a:

```text
--tlsMode requireTLS
--tlsCertificateKeyFile ...
--tlsCAFile ...
```

TLS protege la comunicación en tránsito.

Ejemplos:

```text
Compass -------- TLS --------> MongoDB
mongosh -------- TLS --------> MongoDB
mongodump ------ TLS --------> MongoDB
Ansible -------- TLS --------> MongoDB
```

TLS y autenticación son mecanismos diferentes:

```text
TLS
+
usuario
+
contraseña
```

TLS protege y valida el canal. MongoDB valida identidad y permisos.

---

## MongoDB Compass

Compass se utiliza para ver visualmente el estado y los datos durante las pruebas.

Endpoint local:

```text
localhost:27017
```

URI de referencia:

```text
mongodb://localhost:27017/?directConnection=true&tls=true&authSource=admin
```

Compass utiliza:

```text
usuario
password
authSource=admin
mongo_ca.pem
```

### Función de `mongo_ca.pem`

La CA pública permite validar el certificado presentado por MongoDB.

```text
Compass
   |
   | verifica certificado con mongo_ca.pem
   v
MongoDB
   |
   | valida usuario + password
   v
Acceso
```

No se debe proporcionar a Compass la clave privada de la CA ni las claves privadas de los nodos.

La configuración exacta está documentada en:

**[AltadisponibilidadBackups.md](./AltadisponibilidadBackups.md)**

---

## Backups

El flujo de respaldo es:

```text
MongoDB
   |
   v
Validar conectividad
   |
   v
Detectar PRIMARY
   |
   v
Validar backup_user
   |
   v
mongodump
   |
   v
archive.gz
   |
   v
SHA-256
   |
   v
Validación
   |
   v
Bitácora
```

---

## MongoDB Database Tools

Se utilizan:

```text
mongodump
mongorestore
```

Versión controlada:

```text
100.18.0
```

Estructura:

```text
tools/
└── mongodb-database-tools/
    └── 100.18.0/
        └── bin/
            ├── mongodump
            └── mongorestore
```

Esto evita depender de versiones arbitrarias instaladas globalmente.

---

## Usuario de backup

El proyecto utiliza un usuario específico para respaldo.

Conceptualmente:

```text
backup_user
```

Las credenciales se protegen mediante Ansible Vault.

El flujo valida:

- autenticación;
- acceso a la base;
- lectura;
- acceso a colecciones.

El objetivo es aplicar mínimo privilegio.

---

## Generación de backups

Formato:

```text
<database>_YYYYMMDD_HHMMSS.archive.gz
```

Ejemplo:

```text
prueba_ha_20260828_020000.archive.gz
```

Estructura:

```text
backups/
└── mongodb/
    └── prueba_ha/
        └── YYYY-MM/
            ├── prueba_ha_YYYYMMDD_HHMMSS.archive.gz
            └── prueba_ha_YYYYMMDD_HHMMSS.archive.gz.sha256
```

El formato archive genera un archivo lógico único y gzip reduce su tamaño.

---

## Integridad SHA-256

Por cada backup:

```text
prueba_ha_YYYYMMDD_HHMMSS.archive.gz
```

se genera:

```text
prueba_ha_YYYYMMDD_HHMMSS.archive.gz.sha256
```

El checksum permite detectar:

- corrupción;
- modificación;
- errores de almacenamiento;
- errores de transferencia.

---

## Bitácoras

La solución registra información de ejecución:

- timestamp;
- ambiente;
- base;
- PRIMARY detectado;
- archivo;
- tamaño;
- checksum;
- duración;
- resultado.

Esto permite auditoría y diagnóstico.

---

## Cron

Los respaldos pueden ejecutarse automáticamente mediante cron.

Horario de referencia:

```text
02:00
```

Existe una prueba específica para comprobar que el flujo programado funciona realmente.

---

## Retención

Variables de referencia:

```text
backup_retention_days: 30
backup_monthly_retention_months: 12
```

Conceptualmente:

- diarios: 30 días;
- mensuales: 12 meses.

La limpieza está separada de la generación del respaldo.

---

## Restore

La restauración utiliza:

```text
mongorestore
```

Antes de restaurar se validan:

- existencia del archivo;
- checksum;
- credenciales;
- conectividad;
- destino.

---

## Usuario de restore

Se utiliza un usuario independiente:

```text
restore_user
```

Sus credenciales también se administran con Ansible Vault.

---

## Restore de prueba

La base original:

```text
prueba_ha
```

permanece intacta.

El backup se restaura como:

```text
prueba_ha_restore_test
```

Resultado:

```text
prueba_ha
prueba_ha_restore_test
```

Esto permite comprobar restaurabilidad sin destruir la base original.

---

## Disaster Recovery

El proyecto incluye una prueba controlada:

```text
Validar backup
      |
      v
Contar datos
      |
      v
Eliminar prueba_ha
      |
      v
Confirmar pérdida
      |
      v
mongorestore
      |
      v
Comparar datos
      |
      v
Validar Replica Set
```

La prueba demuestra que el backup no solo existe, sino que puede recuperar la base.

---

## Datos de prueba

Base:

```text
prueba_ha
```

Se utiliza para comprobar:

- escritura;
- replicación;
- failover;
- persistencia;
- backup;
- restore.

---

## Validación final

El estado esperado de Docker es:

```text
mongo1   1/1
mongo2   1/1
mongo3   1/1
```

Estado MongoDB:

```text
1 PRIMARY
2 SECONDARY
```

Además deben quedar validados:

```text
autenticación
TLS
certificados
replicación
failover
backup
SHA-256
restore
cron
```

---

## Directorio `secrets/`

Estructura aproximada:

```text
secrets/
├── backup-encryption/
│   └── local/
├── mongo-keyfile
├── mongodb-tls/
│   └── local/
│       ├── ca/
│       └── v1/
│           ├── mongo1/
│           ├── mongo2/
│           ├── mongo3/
│           └── mongo_ca.pem
└── vault_password
```

Debe existir localmente, pero no debe versionarse.

`.gitignore` debe excluir al menos:

```gitignore
secrets/
backups/
logs/
*.tmp
*.log
```

---

## Ambientes

La solución está parametrizada para:

```text
LOCAL
DESARROLLO
PRODUCCIÓN
```

Variables por ambiente:

```text
vars/local.yml
vars/development.yml
vars/production.yml
```

La lógica principal se reutiliza y los detalles cambian mediante configuración.

### LOCAL

Usado para:

- desarrollo;
- pruebas;
- demostración;
- validación técnica.

### DESARROLLO y PRODUCCIÓN

Deben utilizar los recursos reales definidos por la infraestructura correspondiente:

- endpoints;
- certificados;
- almacenamiento;
- credenciales;
- monitoreo;
- alertamiento;
- políticas de seguridad;
- mecanismos institucionales de cifrado.

---

## TLS frente a cifrado de backups

Son controles distintos.

TLS protege:

```text
datos en tránsito
```

El cifrado de backups protege:

```text
archivo en reposo
```

Por tanto, TLS no reemplaza el cifrado del archivo `.archive.gz`.

---

## Recovery administrativo

El proyecto incluye rutinas de recuperación para casos de contingencia administrativa o recuperación de un nodo.

Estas rutinas están separadas del flujo normal y deben utilizarse únicamente cuando corresponda.

---

## Principios de diseño

### Automatización

Las tareas repetibles se ejecutan mediante Ansible y scripts.

### Idempotencia

Los playbooks verifican el estado antes de modificar cuando corresponde.

### Fail-closed

Las operaciones críticas deben abortar cuando no pueden validar sus precondiciones.

### Separación de responsabilidades

La solución separa:

```text
infraestructura
seguridad
mongodb
validación
tests
backup
recovery
```

### Mínimo privilegio

Backup y restore utilizan cuentas dedicadas.

### Secretos fuera de Git

Credenciales, claves privadas y material criptográfico no deben versionarse.

### Validación posterior

Las operaciones críticas incluyen verificaciones después de ejecutarse.

---

## Tecnologías

| Tecnología | Función |
|---|---|
| MongoDB 7 | Base de datos |
| Replica Set | Replicación y HA |
| Docker | Contenedores |
| Docker Swarm | Orquestación |
| Docker Secrets | Gestión de secretos |
| Ansible | Automatización |
| Ansible Vault | Credenciales |
| OpenSSL / PKI | Certificados |
| TLS | Protección en tránsito |
| MongoDB Database Tools | Backup/restore |
| mongodump | Backup |
| mongorestore | Restore |
| SHA-256 | Integridad |
| cron | Programación |
| MongoDB Compass | Verificación visual |
| Git | Control de versiones |

---

## Flujo completo

```text
Preparar entorno
      |
      v
Docker Swarm
      |
      v
Red Overlay
      |
      v
KeyFile
      |
      v
PKI + certificados
      |
      v
Docker Secrets
      |
      v
Servicios MongoDB
      |
      v
Replica Set
      |
      v
Admin
      |
      v
Agregar nodos
      |
      v
TLS requireTLS
      |
      v
Prioridades
      |
      v
Validaciones
      |
      +----------------------+
      |                      |
      v                      v
Prueba HA                 Backup
      |                      |
      v                      v
Failover                 SHA-256
      |                      |
      v                      v
Failback                 Restore
                             |
                             v
                     Disaster Recovery
                             |
                             v
                      Validación final
```

---

## Guía de ejecución

La secuencia completa de comandos y pruebas está centralizada en:

> # **[AltadisponibilidadBackups.md](./AltadisponibilidadBackups.md)**

Ese documento contiene:

- clonación y preparación;
- dependencias;
- permisos;
- creación de `secrets/`;
- `.gitignore`;
- Vault;
- limpieza inicial;
- Swarm;
- red;
- KeyFile;
- PKI;
- certificados;
- Docker Secrets;
- servicios;
- Replica Set;
- administrador;
- incorporación de nodos;
- TLS;
- prioridades;
- Compass;
- datos de prueba;
- prueba HA;
- backup;
- restore;
- disaster recovery;
- cron;
- validación final.

**No utilizar este README como guía operativa.**

---

## Resultado final esperado

### MongoDB

```text
Replica Set: rs0
Nodos: 3
PRIMARY: 1
SECONDARY: 2
TLS: requireTLS
Autenticación: habilitada
```

### Alta disponibilidad

```text
Failover: validado
Elección automática: validada
Reincorporación: validada
Persistencia: validada
```

### Seguridad

```text
KeyFile: habilitado
Ansible Vault: habilitado
PKI: generada
Certificados: generados
TLS: obligatorio
Docker Secrets: utilizados
```

### Backups

```text
mongodump: automatizado
archive.gz: generado
SHA-256: validado
logs: generados
cron: probado
retención: configurada
```

### Recuperación

```text
mongorestore: validado
restore de prueba: validado
disaster recovery: probado
```

---

## Alcance

Este repositorio implementa y demuestra:

- despliegue reproducible;
- Replica Set;
- alta disponibilidad;
- failover;
- autenticación;
- KeyFile;
- PKI;
- TLS;
- Docker Secrets;
- backup;
- integridad;
- restore;
- disaster recovery;
- cron;
- validaciones automáticas.

El entorno LOCAL funciona como laboratorio y demostración. Los ambientes superiores deben usar la infraestructura y políticas correspondientes.

---

## Documentación del repositorio

### `README.md`

Describe:

```text
qué se implementó
cómo está organizada la arquitectura
qué mecanismos se utilizaron
qué resultado se espera
```

### `AltadisponibilidadBackups.md`

Describe:

```text
cómo preparar el repositorio
qué comandos ejecutar
en qué orden
cómo configurar Compass
cómo ejecutar todas las pruebas
```

La separación es intencional para evitar duplicar procedimientos.

---



## Resumen

La solución integra en un único proyecto automatizado:

**Docker Swarm + MongoDB Replica Set + HA + failover + autenticación + KeyFile + Ansible Vault + PKI + TLS + Docker Secrets + mongodump + SHA-256 + mongorestore + disaster recovery + cron + validación**.

El objetivo es que cada componente pueda desplegarse, probarse y verificarse de forma repetible y controlada.
