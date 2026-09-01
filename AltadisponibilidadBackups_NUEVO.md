# INSTALACIÓN, CONFIGURACIÓN Y VALIDACIÓN DE MONGODB EN ALTA DISPONIBILIDAD

---

### Historial de cambios

| Autores | Fecha de publicación | Descripción |
| --- | --- | --- |
| Equipo de desarrollo | 01/09/2026 | Reestructuración de la guía técnica de despliegue, validación, backup y restore de MongoDB HA. |

---

## 1. Introducción

MongoDB es un sistema de base de datos NoSQL orientado a documentos que almacena la información en estructuras BSON. Para proporcionar Alta Disponibilidad, MongoDB utiliza Replica Sets, donde varios nodos mantienen copias sincronizadas de la información y uno de ellos actúa como PRIMARY mientras los demás operan como SECONDARY.

La solución implementada utiliza tres nodos MongoDB dentro de Docker Swarm, autenticación interna mediante KeyFile, autenticación de usuarios, cifrado de conexiones mediante TLS, configuración de prioridades del Replica Set, validaciones de replicación y failover, y mecanismos automatizados de backup y restore mediante MongoDB Database Tools y Ansible.

El presente documento establece la secuencia técnica para preparar, desplegar, configurar, validar, operar y probar la solución MongoDB en Alta Disponibilidad en el ambiente LOCAL. También incluye los mecanismos de respaldo, restauración, recuperación ante desastre y validación de la ejecución automática mediante cron.

### 1.1 Puertos utilizados

En el ambiente LOCAL los servicios MongoDB publican puertos independientes en el host para permitir la conexión desde herramientas externas, como MongoDB Compass.

| Puerto | Protocolo | Componente | Descripción |
| ---: | :---: | --- | --- |
| **27017** | TCP/TLS | `mongo1` | Puerto publicado para el nodo MongoDB con mayor prioridad electoral. |
| **27018** | TCP/TLS | `mongo2` | Puerto publicado para el segundo nodo MongoDB. |
| **27019** | TCP/TLS | `mongo3` | Puerto publicado para el tercer nodo MongoDB. |

Dentro de la red de Docker Swarm, los tres servicios se comunican utilizando el puerto interno `27017`.

### 1.2 Convenciones sobre el documento

* Por convención, los ejemplos utilizan el ambiente `local` con fines de validación técnica.
* Las configuraciones deberán parametrizarse para los ambientes de Desarrollo, Calidad o Producción cuando corresponda.
* Los comandos deberán ejecutarse desde la raíz del repositorio.
* Las credenciales y secretos no deberán escribirse directamente en scripts, documentación, capturas de pantalla o commits.
* Los archivos contenidos en `secrets/`, `backups/` y `logs/` son artefactos locales y no deberán formar parte del control de versiones.
* El término **deberá** expresa un requisito de cumplimiento.
* El término **queda prohibido** expresa una restricción.
* Los términos **podrá** o **se recomienda** expresan opciones o buenas prácticas.
* Cada etapa deberá finalizar correctamente antes de continuar con la siguiente, salvo que se indique expresamente lo contrario.

---

## 2. Instalación y configuración

### 2.1 Prerequisitos

#### 2.1.1 Infraestructura mínima

La siguiente infraestructura corresponde al ambiente LOCAL utilizado para validar la solución. Para ambientes superiores, el dimensionamiento definitivo deberá ser establecido por el área de Infraestructura de acuerdo con la carga, capacidad, almacenamiento y políticas institucionales.

| Componente | Rol | Hostname / Servicio | Sistema Operativo / Plataforma | Recursos mínimos referenciales | Observación |
| --- | --- | --- | --- | --- | --- |
| Nodo de Control | Ejecución de Ansible y scripts | `localhost` | Ubuntu/WSL | 4 vCPU, 8 GB RAM, 20 GB libres | Debe disponer de Ansible, Git, OpenSSL y acceso a Docker Desktop. |
| Docker Host | Ejecución del clúster LOCAL | `docker-desktop` | Docker Desktop + WSL | 4 vCPU, 8 GB RAM | Ejecuta Docker Swarm y los tres servicios MongoDB. |
| MongoDB Nodo 1 | PRIMARY preferente | `mongo1` | Contenedor `mongo:7-jammy` | Compartido con Docker Host | Prioridad electoral `2`. Puerto publicado `27017`. |
| MongoDB Nodo 2 | SECONDARY | `mongo2` | Contenedor `mongo:7-jammy` | Compartido con Docker Host | Prioridad electoral `1`. Puerto publicado `27018`. |
| MongoDB Nodo 3 | SECONDARY | `mongo3` | Contenedor `mongo:7-jammy` | Compartido con Docker Host | Prioridad electoral `1`. Puerto publicado `27019`. |

> Los recursos anteriores son referenciales para laboratorio LOCAL. No constituyen el dimensionamiento definitivo para DEV o PROD.

La topología utilizada es:

```text
                                      Clientes / Herramientas
                              MongoDB Compass / mongosh / Database Tools
                                                 │
                                                 │ TLS
                                                 ▼
                                         Replica Set: rs0
                                                 │
                     ┌───────────────────────────┼───────────────────────────┐
                     │                           │                           │
                     ▼                           ▼                           ▼
                ┌───────────┐               ┌───────────┐               ┌───────────┐
                │  mongo1   │               │  mongo2   │               │  mongo3   │
                │ priority2 │               │ priority1 │               │ priority1 │
                │ 27017     │               │ 27018     │               │ 27019     │
                └───────────┘               └───────────┘               └───────────┘
                     ▲                           ▲                           ▲
                     └───────────────────────────┴───────────────────────────┘
                                      Docker Swarm Overlay Network
                                                 ▲
                                                 │
                                         Nodo de Control
                                             Ansible
```

| Componente | Descripción |
| --- | --- |
| **Nodo de Control** | Equipo desde el cual se ejecutan Ansible, scripts de automatización y validaciones. |
| **Docker Swarm** | Orquestador utilizado para desplegar los servicios MongoDB y gestionar redes y secretos. |
| **Replica Set `rs0`** | Grupo lógico de nodos MongoDB que proporciona replicación y elección automática de PRIMARY. |
| **mongo1** | Nodo configurado con prioridad `2`; es el PRIMARY preferente cuando está disponible. |
| **mongo2** | Nodo configurado con prioridad `1`; opera normalmente como SECONDARY. |
| **mongo3** | Nodo configurado con prioridad `1`; opera normalmente como SECONDARY. |
| **KeyFile** | Mecanismo utilizado para autenticación interna entre los miembros del Replica Set. |
| **TLS / PKI** | Capa de cifrado y validación de identidad utilizada para las conexiones MongoDB. |
| **MongoDB Database Tools** | Herramientas oficiales utilizadas para `mongodump` y `mongorestore`. |
| **Ansible Vault** | Mecanismo utilizado para proteger credenciales sensibles. |

#### 2.1.2 Herramientas y configuraciones previas

Antes de ejecutar el despliegue deberán verificarse los siguientes prerrequisitos:

* Docker Desktop instalado.
* Integración de Docker Desktop con WSL habilitada.
* Docker Engine disponible.
* Docker Compose Plugin disponible.
* Docker Swarm disponible.
* Ansible instalado en el Nodo de Control.
* Git instalado.
* OpenSSL instalado.
* `curl`, `jq`, `coreutils` y `util-linux` instalados.
* MongoDB Database Tools disponibles mediante el proyecto.
* Acceso de lectura/escritura al repositorio local.
* Archivo de contraseña de Ansible Vault disponible localmente.
* Carpeta `secrets/` creada con permisos restrictivos.

Versiones utilizadas durante la implementación LOCAL:

| Componente | Versión / Imagen |
| --- | --- |
| MongoDB | `7.0.40` |
| Imagen MongoDB | `mongo:7-jammy` |
| MongoDB Shell | `mongosh 2.10.0` |
| MongoDB Database Tools | `100.18.0` |
| Docker Desktop | `4.69.0` |
| Docker Engine | `29.4.0` |
| Docker Compose | `v5.1.1` |
| Orquestador | Docker Swarm |
| Automatización | Ansible |
| Criptografía | OpenSSL |

Instalar dependencias base en Ubuntu/WSL:

```bash
sudo apt update
sudo apt install -y ansible git openssl curl jq coreutils util-linux
```

Verificar:

```bash
ansible --version
git --version
openssl version
docker --version
docker compose version
```

Docker Desktop deberá encontrarse iniciado y la integración con WSL deberá estar habilitada antes de continuar.

### 2.2 Estructura de archivos y carpetas

La solución organiza las automatizaciones por responsabilidad. La estructura principal utilizada en esta guía es:

```text
Altadisponibilidad/
├── playbooks/
│   ├── backup/
│   │   ├── backup_create_users.yml
│   │   ├── cleanup_backup_files.yml
│   │   ├── restore_create_user.yml
│   │   ├── restore_disaster_test.yml
│   │   └── restore_test.yml
│   ├── infrastructure/
│   │   ├── network_setup.yml
│   │   └── swarm_setup.yml
│   ├── mongodb/
│   │   ├── configure_priorities.yml
│   │   ├── mongo_create_admin.yml
│   │   ├── mongo_replset.yml
│   │   ├── mongo_replset_add_nodes.yml
│   │   ├── mongo_replset_nodes.yml
│   │   └── mongo_services.yml
│   ├── security/
│   │   ├── keyfile_secret.yml
│   │   ├── keyfile_setup.yml
│   │   ├── tls_local_pki.yml
│   │   ├── tls_secrets.yml
│   │   └── validate_tls_pki.yml
│   ├── tests/
│   │   ├── reset_local_environment.yml
│   │   ├── test_backup_cron_execution.yml
│   │   ├── test_high_availability.yml
│   │   └── test_replication_data.yml
│   └── validation/
│       ├── validate_mongodb.yml
│       ├── validate_mongodb_tls.yml
│       └── validate_replset.yml
├── scripts/
│   ├── run_mongodb_backup.sh
│   └── run_tls_rollout.sh
├── tools/
│   └── mongodb-database-tools/
│       └── 100.18.0/
├── vars/
│   └── vault_mongodb.yml
├── secrets/
├── backups/
└── logs/
```

| Directorio | Descripción |
| --- | --- |
| `playbooks/infrastructure/` | Preparación de Docker Swarm y red. |
| `playbooks/security/` | KeyFile, PKI, TLS y Docker Secrets. |
| `playbooks/mongodb/` | Servicios MongoDB, Replica Set, usuarios y prioridades. |
| `playbooks/backup/` | Backup, restore, usuarios y limpieza de respaldos. |
| `playbooks/tests/` | Pruebas de replicación, HA, cron y reseteo LOCAL. |
| `playbooks/validation/` | Comprobaciones de MongoDB, Replica Set y TLS. |
| `scripts/` | Wrappers operativos utilizados por la automatización. |
| `tools/` | MongoDB Database Tools controlados por el proyecto. |
| `vars/` | Variables y credenciales protegidas mediante Ansible Vault. |
| `secrets/` | Material sensible generado localmente. |
| `backups/` | Respaldos generados durante las pruebas. |
| `logs/` | Bitácoras de las automatizaciones. |

### 2.3 Instalación

La solución se implementa mediante un proceso automatizado con Ansible y Docker Swarm. La preparación comprende infraestructura, seguridad interna, PKI, servicios MongoDB, inicialización del Replica Set, creación de usuarios, activación de TLS y configuración de prioridades.

El proceso de aprovisionamiento comprende las siguientes etapas:

1. Descargar y preparar el repositorio.
2. Crear la estructura local de secretos.
3. Inicializar Docker Swarm y la red de servicios.
4. Generar el KeyFile de autenticación interna.
5. Generar y validar la PKI TLS.
6. Crear los Docker Secrets.
7. Crear los servicios MongoDB.
8. Inicializar el Replica Set.
9. Crear el usuario administrador.
10. Incorporar los nodos al Replica Set.
11. Activar `requireTLS`.
12. Configurar prioridades.
13. Validar el estado final.

#### 2.3.1 Descargar el proyecto desde GitHub a una PC local

```bash
git clone https://github.com/XavierAltamiranoPineda/Altadisponibilidad.git
cd Altadisponibilidad
```

#### 2.3.2 Preparar permisos de los scripts

```bash
chmod -R u+rwX .
find scripts -type f -name '*.sh' -exec chmod u+x {} +
```

Verificar:

```bash
find scripts -type f -name '*.sh' -exec ls -l {} +
```

#### 2.3.3 Crear la carpeta local `secrets/`

La carpeta no depende de Git y deberá crearse antes de ejecutar los playbooks que generan material criptográfico.

```bash
mkdir -p secrets
chmod 700 secrets
```

No se deberán crear manualmente `mongo-keyfile`, certificados, claves privadas ni archivos PEM.

#### 2.3.4 Crear el archivo de contraseña de Ansible Vault

```bash
nano secrets/vault_password
chmod 600 secrets/vault_password
```

El archivo deberá contener únicamente la contraseña utilizada para descifrar:

```text
vars/vault_mongodb.yml
```

Queda prohibido subir `secrets/vault_password` al repositorio.

#### 2.3.5 Verificar `.gitignore`

El archivo `.gitignore` deberá incluir, como mínimo:

```gitignore
# Secretos y material criptográfico
secrets/

# Backups y logs generados
backups/
logs/

# Archivos temporales
*.tmp
*.log
```

Verificar:

```bash
git status --ignored
```

Nunca deberán versionarse:

```text
secrets/mongo-keyfile
secrets/vault_password
secrets/mongodb-tls/**
secrets/backup-encryption/**
```

#### 2.3.6 Eliminar backups anteriores

Esta operación es opcional y deberá ejecutarse únicamente cuando se necesite comenzar una prueba sin respaldos previos.

```bash
ansible-playbook \
  playbooks/backup/cleanup_backup_files.yml
```

#### 2.3.7 Restablecer el ambiente LOCAL

Esta operación elimina MongoDB y sus bases del ambiente de pruebas. Deberá utilizarse únicamente cuando se requiera reconstruir completamente el entorno.

```bash
ansible-playbook \
  playbooks/tests/reset_local_environment.yml
```

#### 2.3.8 Construir la infraestructura base

Inicializar Docker Swarm:

```bash
ansible-playbook \
  playbooks/infrastructure/swarm_setup.yml
```

Crear la red:

```bash
ansible-playbook \
  playbooks/infrastructure/network_setup.yml
```

#### 2.3.9 Generar el KeyFile de autenticación

Generar el KeyFile:

```bash
ansible-playbook \
  playbooks/security/keyfile_setup.yml
```

Crear el Docker Secret:

```bash
ansible-playbook \
  playbooks/security/keyfile_secret.yml
```

#### 2.3.10 Generar y validar certificados TLS / PKI

Generar la PKI LOCAL:

```bash
ansible-playbook \
  playbooks/security/tls_local_pki.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

Validar la PKI:

```bash
ansible-playbook \
  playbooks/security/validate_tls_pki.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

Crear los Docker Secrets TLS:

```bash
ansible-playbook \
  playbooks/security/tls_secrets.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

La validación de PKI deberá finalizar sin errores antes de continuar.

#### 2.3.11 Crear los servicios MongoDB

```bash
ansible-playbook \
  playbooks/mongodb/mongo_services.yml \
  -e target_environment=local
```

#### 2.3.12 Inicializar el Replica Set

```bash
ansible-playbook \
  playbooks/mongodb/mongo_replset.yml \
  -e target_environment=local
```

Preparar los nodos:

```bash
ansible-playbook \
  playbooks/mongodb/mongo_replset_nodes.yml \
  -e target_environment=local
```

#### 2.3.13 Crear el usuario administrador

```bash
ansible-playbook \
  playbooks/mongodb/mongo_create_admin.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

#### 2.3.14 Agregar los nodos al Replica Set

```bash
ansible-playbook \
  playbooks/mongodb/mongo_replset_add_nodes.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

#### 2.3.15 Activar TLS obligatorio

Ejecutar el wrapper de rollout hasta alcanzar el estado final:

```bash
./scripts/run_tls_rollout.sh \
  requireTLS \
  -e target_environment=local
```

El estado final esperado es:

```text
tlsMode = requireTLS
```

#### 2.3.16 Configurar prioridades del Replica Set

```bash
ansible-playbook \
  playbooks/mongodb/configure_priorities.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

Configuración esperada:

| Nodo | Prioridad |
| --- | ---: |
| `mongo1` | 2 |
| `mongo2` | 1 |
| `mongo3` | 1 |

#### 2.3.17 Revisar el despliegue

Validar Replica Set:

```bash
ansible-playbook \
  playbooks/validation/validate_replset.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

Validar TLS:

```bash
ansible-playbook \
  playbooks/validation/validate_mongodb_tls.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

Verificar servicios:

```bash
docker service ls
```

### 2.4 Configuración

#### 2.4.1 Configurar MongoDB Compass para su conexión al Replica Set

MongoDB Compass se utiliza para verificar visualmente el estado del Replica Set, los datos almacenados y los cambios producidos durante las pruebas de failover y recuperación.

Editar en Windows, como Administrador:

```text
C:\Windows\System32\drivers\etc\hosts
```

Agregar:

```text
127.0.0.1  mongo1
127.0.0.1  mongo2
127.0.0.1  mongo3
```

Verificar puertos publicados:

```bash
docker service ls
```

Salida esperada:

```text
mongo1 -> *:27017->27017/tcp
mongo2 -> *:27018->27018/tcp
mongo3 -> *:27019->27019/tcp
```

Verificar la CA pública:

```bash
ls -l secrets/mongodb-tls/local/v1/mongo_ca.pem
```

Copiar la CA a Windows:

```bash
cp secrets/mongodb-tls/local/v1/mongo_ca.pem \
  /mnt/c/Users/Usuario01/Documents/mongo_ca.pem
```

Consultar las credenciales administrativas protegidas con Ansible Vault:

```bash
ansible-vault view \
  vars/vault_mongodb.yml \
  --vault-password-file secrets/vault_password \
  | grep -E '^(mongo_admin_user|mongo_admin_password):'
```

> La salida anterior contiene información sensible y no deberá incluirse en evidencias, capturas o commits.

URI del Replica Set:

```text
mongodb://mongo1:27017,mongo2:27018,mongo3:27019/?replicaSet=rs0&tls=true&authSource=admin
```

Configuración TLS/SSL en Compass:

| Parámetro | Valor |
| --- | --- |
| TLS/SSL | `On` |
| Certificate Authority File | `C:\Users\Usuario01\Documents\mongo_ca.pem` |
| Client Certificate | Ninguno |
| Allow invalid certificates | `OFF` |
| Allow invalid hostnames | `OFF` |

Al conectarse, Compass deberá mostrar el Replica Set `rs0`.

---

## 3. Validaciones

### 3.1 Validación de la replicación de datos

Crear datos de prueba:

```bash
ansible-playbook \
  playbooks/tests/test_replication_data.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

La prueba deberá validar que los datos escritos en el PRIMARY se encuentren disponibles a través del Replica Set y sean replicados hacia los nodos secundarios.

### 3.2 Validación de la Alta Disponibilidad

#### 3.2.1 Simulación de una caída controlada

Ejecutar:

```bash
ansible-playbook \
  playbooks/tests/test_high_availability.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

La prueba deberá:

1. Identificar el PRIMARY actual.
2. Simular la indisponibilidad del nodo PRIMARY.
3. Esperar la elección de un nuevo PRIMARY.
4. Validar la continuidad del Replica Set.
5. Restaurar el nodo afectado.
6. Comprobar su reintegración como SECONDARY.

Durante la prueba podrá utilizarse MongoDB Compass para observar visualmente el cambio de PRIMARY.

#### 3.2.2 Validación del Replica Set

```bash
ansible-playbook \
  playbooks/validation/validate_replset.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

El resultado deberá confirmar que los tres miembros forman parte de `rs0` y que existe un PRIMARY disponible.

#### 3.2.3 Validación TLS

```bash
ansible-playbook \
  playbooks/validation/validate_mongodb_tls.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

La prueba deberá confirmar el uso obligatorio de TLS y el rechazo de conexiones no permitidas por la configuración final.

#### 3.2.4 Validación final de MongoDB

```bash
ansible-playbook \
  playbooks/validation/validate_mongodb.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

---

## 4. Reversa

La reversa deberá utilizarse únicamente cuando se requiera desmontar el ambiente LOCAL y regresar a un estado de bootstrap.

### 4.1 Eliminar respaldos generados

```bash
ansible-playbook \
  playbooks/backup/cleanup_backup_files.yml
```

### 4.2 Restablecer la infraestructura MongoDB LOCAL

```bash
ansible-playbook \
  playbooks/tests/reset_local_environment.yml
```

> Esta operación es destructiva. No deberá ejecutarse durante pruebas de backup o restore salvo que el objetivo sea reiniciar completamente el laboratorio.

---

## 5. Operación

### 5.1 Comandos de operación y verificación

| Comando | Descripción |
| --- | --- |
| `docker service ls` | Lista los servicios desplegados y permite verificar réplicas y puertos publicados. |
| `docker service ps mongo1` | Muestra las tareas asociadas al servicio `mongo1`. |
| `docker service ps mongo2` | Muestra las tareas asociadas al servicio `mongo2`. |
| `docker service ps mongo3` | Muestra las tareas asociadas al servicio `mongo3`. |
| `docker secret ls` | Lista los Docker Secrets disponibles. |
| `ansible-vault view vars/vault_mongodb.yml --vault-password-file secrets/vault_password` | Permite consultar las variables protegidas. |
| `find backups/mongodb/prueba_ha -type f \| sort` | Lista los artefactos de backup generados. |
| `sha256sum -c <archivo>.sha256` | Valida la integridad de un respaldo. |

### 5.2 Gestión de credenciales

Las credenciales administrativas, de backup y de restore se almacenan cifradas en:

```text
vars/vault_mongodb.yml
```

La contraseña utilizada para abrir el Vault se almacena localmente en:

```text
secrets/vault_password
```

El archivo deberá tener permisos restrictivos:

```bash
chmod 600 secrets/vault_password
```

### 5.3 Monitoreo operativo

Para verificar el estado general:

```bash
docker service ls
```

Para ejecutar las validaciones completas:

```bash
ansible-playbook \
  playbooks/validation/validate_mongodb.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

ansible-playbook \
  playbooks/validation/validate_replset.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

ansible-playbook \
  playbooks/validation/validate_mongodb_tls.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

---

## 6. Backups y Restauración

### 6.1 Backups

La solución utiliza MongoDB Database Tools `100.18.0` y `mongodump` para generar respaldos lógicos completos de la base de datos.

El flujo automatizado comprende:

```text
Validar MongoDB
      ↓
Detectar PRIMARY
      ↓
Validar usuario de backup
      ↓
Ejecutar mongodump
      ↓
Generar archive.gz
      ↓
Generar SHA-256
      ↓
Validar artefactos
      ↓
Registrar resultado
```

#### 6.1.1 Preparar usuarios de backup y restore

Crear o validar el usuario de backup:

```bash
ansible-playbook \
  playbooks/backup/backup_create_users.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

Crear o validar el usuario de restore:

```bash
ansible-playbook \
  playbooks/backup/restore_create_user.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

#### 6.1.2 Ejecutar backup real

```bash
./scripts/run_mongodb_backup.sh \
  -e target_environment=local
```

Verificar:

```bash
find backups/mongodb/prueba_ha -type f | sort
```

Salida esperada:

```text
prueba_ha_YYYYMMDD_HHMMSS.archive.gz
prueba_ha_YYYYMMDD_HHMMSS.archive.gz.sha256
```

#### 6.1.3 Validar integridad SHA-256

Ubicarse en el directorio donde se encuentra el respaldo y ejecutar:

```bash
sha256sum -c \
  prueba_ha_YYYYMMDD_HHMMSS.archive.gz.sha256
```

Resultado esperado:

```text
prueba_ha_YYYYMMDD_HHMMSS.archive.gz: OK
```

#### 6.1.4 Ejecución automática mediante cron

La programación permanente de backup se encuentra definida para ejecución diaria a las `02:00`.

La prueba controlada del cron se ejecuta mediante:

```bash
ansible-playbook \
  playbooks/tests/test_backup_cron_execution.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

La prueba deberá confirmar que un nuevo backup puede ser generado automáticamente sin intervención manual.

### 6.2 Restauración

#### 6.2.1 Restore de prueba no destructivo

Ejecutar:

```bash
ansible-playbook \
  playbooks/backup/restore_test.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

La prueba deberá mantener la base original:

```text
prueba_ha
```

y restaurar el respaldo en:

```text
prueba_ha_restore_test
```

Ambas bases deberán poder observarse desde MongoDB Compass.

#### 6.2.2 Disaster Recovery

Abrir previamente la base `prueba_ha` en MongoDB Compass.

Ejecutar:

```bash
ansible-playbook \
  playbooks/backup/restore_disaster_test.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
```

La prueba deberá permitir observar:

```text
ANTES
prueba_ha disponible

DURANTE
prueba_ha eliminada de forma controlada

DESPUÉS
prueba_ha recuperada desde el backup
```

Durante la pausa incluida en el playbook deberá revisarse MongoDB Compass para registrar la evidencia visual.

#### 6.2.3 Política de retención

La política configurada es:

| Tipo de respaldo | Retención |
| --- | ---: |
| Backup diario | 30 días |
| Primer backup mensual | 12 meses |

La limpieza se ejecuta separadamente mediante:

```bash
ansible-playbook \
  playbooks/backup/cleanup_backup_files.yml
```

---

## 7. Ejemplo de consumo

Las aplicaciones y herramientas externas deberán conectarse utilizando la URI del Replica Set y no apuntando exclusivamente al nodo PRIMARY actual.

```text
mongodb://mongo1:27017,mongo2:27018,mongo3:27019/?replicaSet=rs0&tls=true&authSource=admin
```

Flujo:

```text
Aplicación / Compass / Cliente MongoDB
                 │
                 ▼
        URI del Replica Set rs0
                 │
        ┌────────┼────────┐
        │        │        │
        ▼        ▼        ▼
      mongo1   mongo2   mongo3
```

El driver o cliente MongoDB descubre automáticamente el PRIMARY disponible y podrá redirigir las operaciones cuando se produzca una elección dentro del Replica Set.

Para MongoDB Compass deberán mantenerse:

```text
TLS/SSL: On
CA: mongo_ca.pem
Allow invalid certificates: OFF
Allow invalid hostnames: OFF
Authentication Database: admin
```

---

## 8. Estandar

### 8.1 Objetivo

Establecer los lineamientos técnicos para desplegar, validar, operar, respaldar y recuperar una plataforma MongoDB en Alta Disponibilidad, garantizando automatización, autenticación, cifrado de conexiones, replicación, integridad de respaldos y procedimientos verificables de recuperación.

### 8.2 Alcance

El estándar aplica a:

* preparación del entorno;
* despliegue automatizado;
* configuración del Replica Set;
* autenticación interna mediante KeyFile;
* autenticación de usuarios;
* TLS;
* validaciones de replicación;
* pruebas de Alta Disponibilidad;
* backups lógicos;
* validación SHA-256;
* restauración;
* disaster recovery;
* retención;
* programación automática de respaldos.

El ambiente LOCAL se utiliza para validación técnica. Los mecanismos dependientes de infraestructura institucional deberán ajustarse en DEV y PROD.

### 8.3 Principios

La solución deberá cumplir los siguientes principios:

* Automatización mediante Ansible.
* Separación de credenciales administrativas, backup y restore.
* Protección de secretos mediante Ansible Vault.
* Autenticación interna entre nodos.
* Uso obligatorio de TLS en el estado final.
* No almacenar contraseñas en texto plano dentro de scripts.
* Uso de herramientas oficiales de MongoDB para backup y restore.
* Validación de integridad mediante SHA-256.
* Validación real de recuperabilidad mediante restore.
* Ejecución de pruebas de failover.
* Retención controlada.
* Registro de resultados y errores.
* Separación entre artefactos versionados y secretos/respaldos locales.

### 8.4 Estandar del Replica Set

El Replica Set deberá identificarse como:

```text
rs0
```

Configuración electoral de referencia:

| Nodo | Prioridad |
| --- | ---: |
| `mongo1` | 2 |
| `mongo2` | 1 |
| `mongo3` | 1 |

El clúster deberá mantener un PRIMARY disponible mientras exista quórum suficiente.

### 8.5 Estandar de seguridad

La configuración final deberá utilizar:

```text
clusterAuthMode = keyFile
tlsMode = requireTLS
```

Los clientes deberán validar la CA correspondiente al ambiente.

Los secretos deberán mantenerse fuera de Git.

### 8.6 Estandar de respaldos

Los backups deberán:

* realizarse sobre la base de datos completa;
* utilizar `mongodump`;
* generar un archivo `.archive.gz`;
* generar checksum SHA-256;
* registrar fecha, ambiente, base, archivo, tamaño, duración y resultado;
* utilizar credenciales dedicadas;
* ejecutarse diariamente;
* conservar respaldos según la política definida;
* ser sometidos a pruebas periódicas de restore.

### 8.7 Frecuencia, retención y recuperación

| Parámetro | Valor |
| --- | --- |
| Frecuencia | Diaria |
| Hora programada | `02:00` |
| Retención diaria | 30 días |
| Retención mensual | 12 meses |
| RPO objetivo | 24 horas |
| RTO objetivo | 4 horas |

El RPO se encuentra alineado con la frecuencia diaria de respaldo.

El RTO corresponde a un objetivo de recuperación y deberá validarse mediante mediciones cronometradas en los ambientes institucionales correspondientes.

### 8.8 Cifrado de respaldos en reposo

TLS protege las conexiones y los datos en tránsito, pero no cifra por sí mismo los archivos `.archive.gz`.

```text
TLS  = cifrado en tránsito
GZIP = compresión
```

El cifrado definitivo de los artefactos almacenados deberá integrarse con el mecanismo institucional aprobado para DEV y PROD.

### 8.9 Validación periódica de recuperación

Los respaldos deberán someterse a pruebas periódicas de restauración.

Para LOCAL se dispone de:

```text
restore_test.yml
restore_disaster_test.yml
test_backup_cron_execution.yml
```

Las pruebas deberán conservar evidencia suficiente para demostrar:

* integridad del backup;
* capacidad de restauración;
* recuperación ante pérdida controlada;
* funcionamiento de la automatización;
* estado final correcto de MongoDB.

---

## 9. Secuencia completa de pruebas

Cuando se requiera validar la solución desde un ambiente limpio, ejecutar las etapas en el siguiente orden:

| Orden | Etapa |
| ---: | --- |
| 1 | Preparar dependencias y repositorio |
| 2 | Crear `secrets/` y `vault_password` |
| 3 | Limpiar backups anteriores, si corresponde |
| 4 | Restablecer ambiente LOCAL, si corresponde |
| 5 | Configurar Swarm |
| 6 | Configurar red |
| 7 | Generar KeyFile |
| 8 | Crear Docker Secret del KeyFile |
| 9 | Generar PKI TLS |
| 10 | Validar PKI |
| 11 | Crear Docker Secrets TLS |
| 12 | Crear servicios MongoDB |
| 13 | Inicializar Replica Set |
| 14 | Crear usuario administrador |
| 15 | Agregar nodos |
| 16 | Activar `requireTLS` |
| 17 | Configurar prioridades |
| 18 | Validar Replica Set y TLS |
| 19 | Configurar MongoDB Compass |
| 20 | Crear datos de prueba |
| 21 | Ejecutar prueba de Alta Disponibilidad |
| 22 | Crear usuarios de backup y restore |
| 23 | Ejecutar backup real |
| 24 | Validar SHA-256 |
| 25 | Ejecutar restore de prueba |
| 26 | Ejecutar Disaster Recovery |
| 27 | Ejecutar prueba de cron |
| 28 | Ejecutar validaciones finales |

Si el ambiente ya se encuentra desplegado y validado, podrán ejecutarse únicamente las pruebas específicas requeridas, siempre que sus prerrequisitos se encuentren satisfechos.
