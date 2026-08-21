# Mongo Ansible V2 — MongoDB Replica Set en Docker Swarm

Proyecto de automatización con **Ansible** para el despliegue, configuración, seguridad, validación y pruebas de alta disponibilidad (HA) de un cluster **MongoDB Replica Set (rs0)** de 3 nodos sobre **Docker Swarm**.

---

## 🏗️ Arquitectura del Cluster

- **Motor MongoDB:** `mongo:7-jammy`
- **Replica Set:** `rs0`
- **Nodos del Cluster:**
  - `mongo1:27017` (Servicio inicial / PRIMARY prioritario)
  - `mongo2:27017` (Nodo secundario)
  - `mongo3:27017` (Nodo secundario)
- **Red Swarm Overlay:** `mongo_swarm_net` (Attachable)
- **Mecanismo de Autenticación Interna:** KeyFile compartido (`mongo_keyfile`) mediante Docker Secret (`/run/secrets/mongo_keyfile`)
- **Autenticación Administrativa:** Usuario `admin` en base de datos `admin` con credenciales encriptadas vía Ansible Vault (`vars/vault_mongodb.yml`)

---

## 📋 Prerrequisitos del Sistema

Antes de clonar el proyecto y ejecutar los playbooks, es necesario contar con el siguiente entorno preparado:

### 1. Sistema Operativo y WSL2
- **Windows 10 / 11** con **WSL2** y la distribución **Ubuntu** instalada y funcionando.

### 2. Docker Desktop y Configuración de Integración WSL
- **Docker Desktop** instalado y abierto en Windows.
- Activar la integración con WSL2 en Docker Desktop:
  1. Abrir Docker Desktop y hacer clic en **Settings** (icono de engranaje).
  2. Ir a la sección **Resources** -> **WSL Integration**.
  3. Asegurarse de que esté activada la opción **Enable integration with additional distros**.
  4. Habilitar la casilla correspondiente a la distribución **Ubuntu**.
  5. Hacer clic en **Apply & Restart**.

### 3. Verificación de Docker dentro de WSL (Ubuntu)
Abrir la terminal de Ubuntu en WSL y verificar que Docker responda correctamente:

```bash
docker version
docker info
```

### 4. Ansible instalado en WSL
Comprobar que Ansible esté instalado en WSL:

```bash
ansible --version
```
*(Si no está instalado, se instala con: `sudo apt update && sudo apt install -y ansible`)*

---

## 📥 Clonación y Configuración Inicial

### 1. Clonar el Repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd mongo-ansible-v2
```

### 2. Configuración de Credenciales (Ansible Vault)

El repositorio incluye el archivo plantilla de ejemplo `vars/vault_mongodb.example.yml`:

```yaml
---
mongo_admin_user: "admin"
mongo_admin_password: "CAMBIAR_PASSWORD"
```

Cada persona debe generar su propio archivo de variables encriptado:

```bash
# 1. Copiar la plantilla de ejemplo
cp vars/vault_mongodb.example.yml vars/vault_mongodb.yml

# 2. Editar el archivo y definir la contraseña deseada
nano vars/vault_mongodb.yml

# 3. Encriptar el archivo con Ansible Vault (ingresa una contraseña que recuerdes)
ansible-vault encrypt vars/vault_mongodb.yml
```

> ⚠️ **IMPORTANTE:**
> **No** debes crear manualmente el keyfile criptográfico, ni el secret de Docker, ni la red overlay, ni los volúmenes, ni el Replica Set, ni el usuario en MongoDB. **Los playbooks de Ansible se encargan automáticamente de todo ese proceso.**

> 💡 **MongoDB Compass (Opcional):**
> MongoDB Compass es **totalmente opcional**. Solo se requiere si deseas inspeccionar de forma gráfica la base de datos `prueba_ha`, las colecciones, los documentos y el estado de la replicación/failover en tiempo real.

---

## 🔍 Verificación Previa al Despliegue

Antes de iniciar el despliegue, verifica que estás en la carpeta correcta y que la estructura del proyecto esté completa:

```bash
pwd
ls
```

Deberías ver al menos los siguientes archivos y directorios:

```text
ansible.cfg
inventory.ini
playbooks/
vars/
secrets/
README.md
```

---

## 📁 Estructura del Proyecto

```text
mongo-ansible-v2/
├── ansible.cfg                    # Configuración global de Ansible
├── inventory.ini                  # Inventario local de ejecución
├── README.md                      # Documentación y guía completa de uso
├── .gitignore                     # Exclusión de secretos y temporales
│
├── playbooks/
│   ├── infrastructure/            # Configuración de Docker Swarm y Redes
│   │   ├── swarm_setup.yml        # Inicialización de Docker Swarm
│   │   ├── network_setup.yml      # Creación de red overlay mongo_swarm_net
│   │   └── expose_mongo1_compass.yml # Publicación de mongo1 en modo host para Compass
│   │
│   ├── security/                  # Generación de KeyFile y Docker Secret
│   │   ├── keyfile_setup.yml      # Generación local del keyfile (permisos 0600)
│   │   └── keyfile_secret.yml     # Creación del Docker Secret mongo_keyfile en Swarm
│   │
│   ├── mongodb/                   # Servicios y configuración del Replica Set
│   │   ├── mongo_services.yml     # Creación del servicio inicial mongo1 con auth y keyfile
│   │   ├── mongo_replset.yml      # Inicialización del Replica Set rs0 en mongo1
│   │   ├── mongo_create_admin.yml # Creación del usuario administrador MongoDB
│   │   ├── mongo_replset_nodes.yml # Creación de servicios mongo2 y mongo3
│   │   ├── mongo_replset_add_nodes.yml # Incorporación de nodos al Replica Set
│   │   └── configure_priorities.yml # Configuración de prioridades de elección en rs0
│   │
│   ├── validation/                # Validaciones de conectividad y estado
│   │   ├── validate_mongodb.yml   # Verificación general de Swarm, red, secret y mongo1
│   │   └── validate_replset.yml   # Verificación de autenticación y estado del Replica Set
│   │
│   ├── tests/                     # Pruebas automatizadas de resiliencia y datos
│   │   ├── test_replication_data.yml # Inserción de datos de prueba en la base prueba_ha
│   │   ├── test_high_availability.yml # Prueba de failover, caída de nodo y recuperación
│   │   ├── cleanup_test_data.yml     # Eliminación selectiva de la base prueba_ha
│   │   └── reset_local_environment.yml # Reset total y limpieza de contenedores y volúmenes V2
│   │
│   └── recovery/                  # Playbooks de contingencia y rescate
│       ├── mongo_recover_admin.yml # Recuperación y reconfiguración de admin
│       └── recover_mongo1.yml     # Reactivación y escala de mongo1
│
├── vars/
│   ├── vault_mongodb.example.yml  # Plantilla de variables para el cluster
│   └── vault_mongodb.yml          # Credenciales encriptadas (Ansible Vault)
│
└── secrets/
    └── mongo-keyfile              # Archivo criptográfico generado para el cluster (0600)
```

---

## 🚀 Guía de Despliegue y Ejecución Paso a Paso

> 📌 **Nota:** Ejecuta todos los comandos desde la raíz del proyecto (`mongo-ansible-v2/`). Cuando el comando incluya `--ask-vault-pass`, introduce la contraseña con la que encriptaste `vars/vault_mongodb.yml`.

### 1. Infraestructura y Redes Swarm

```bash
# Inicializar Docker Swarm en el nodo local
ansible-playbook playbooks/infrastructure/swarm_setup.yml

# Crear la red overlay mongo_swarm_net attachable
ansible-playbook playbooks/infrastructure/network_setup.yml
```

### 2. Seguridad y Autenticación Interna (KeyFile)

```bash
# Generar el keyfile criptográfico local con permisos restrictivos 0600
ansible-playbook playbooks/security/keyfile_setup.yml

# Crear el Docker Secret en Swarm a partir del keyfile generado
ansible-playbook playbooks/security/keyfile_secret.yml
```

*(Opcional: puedes comprobar los recursos creados con `docker secret ls` y `docker network ls | grep mongo_swarm_net`)*

### 3. Despliegue de Servicios MongoDB y Creación del Replica Set

```bash
# Desplegar el servicio principal mongo1
ansible-playbook playbooks/mongodb/mongo_services.yml

# Inicializar el Replica Set rs0 en mongo1
ansible-playbook playbooks/mongodb/mongo_replset.yml

# Desplegar los servicios secundarios mongo2 y mongo3
ansible-playbook playbooks/mongodb/mongo_replset_nodes.yml
```

### 4. Creación del Usuario Administrador

```bash
# Crear el usuario administrador en MongoDB (requiere Vault)
ansible-playbook playbooks/mongodb/mongo_create_admin.yml --ask-vault-pass
```

### 5. Incorporación de Nodos y Configuración de Prioridades

```bash
# Agregar mongo2 y mongo3 al Replica Set rs0 (requiere Vault)
ansible-playbook playbooks/mongodb/mongo_replset_add_nodes.yml --ask-vault-pass

# Configurar prioridades de elección (mongo1 con mayor prioridad)
ansible-playbook playbooks/mongodb/configure_priorities.yml --ask-vault-pass
```

### 6. Validación del Cluster

```bash
# Validar infraestructura básica, red, secret y contenedor mongo1
ansible-playbook playbooks/validation/validate_mongodb.yml

# Validar estado del Replica Set y autenticación en todos los nodos (requiere Vault)
ansible-playbook playbooks/validation/validate_replset.yml --ask-vault-pass
```

---

## 🧪 Pruebas de Replicación y Alta Disponibilidad (HA)

### 7. Inserción de Datos de Prueba

Inserta una base de datos `prueba_ha` con la colección `registros` en el nodo PRIMARY para verificar la replicación automática hacia los SECONDARY:

```bash
ansible-playbook playbooks/tests/test_replication_data.yml --ask-vault-pass
```

### 8. Prueba de Alta Disponibilidad y Failover

Simula la caída forzada del nodo PRIMARY (`mongo1`), verifica la elección inmediata de un nuevo PRIMARY entre los nodos secundarios, reactiva `mongo1` y comprueba la reincorporación y consistencia del cluster:

```bash
ansible-playbook playbooks/tests/test_high_availability.yml --ask-vault-pass
```

---

## 🧭 Conexión con MongoDB Compass (Opcional)

Si deseas conectarte gráficamente desde MongoDB Compass en Windows:

1. **Exponer el puerto de `mongo1` en modo host:**
   ```bash
   ansible-playbook playbooks/infrastructure/expose_mongo1_compass.yml
   ```

2. **Abrir MongoDB Compass** y conectarse con la siguiente cadena de conexión (reemplaza `<PASSWORD>` por tu contraseña configurada en Vault):
   ```text
   mongodb://admin:<PASSWORD>@localhost:27017/?authSource=admin&replicaSet=rs0&directConnection=true
   ```

---

## 🧹 Limpieza y Reseteo del Entorno

### Limpieza de Datos de Prueba
Para eliminar únicamente la base de datos `prueba_ha` sin alterar los servicios ni la estructura del Replica Set:

```bash
ansible-playbook playbooks/tests/cleanup_test_data.yml --ask-vault-pass
```

### Reset Completo del Entorno Local V2
Para destruir y limpiar todos los servicios (`mongo1`, `mongo2`, `mongo3`), contenedores, volúmenes asociados (`mongo1_data`, `mongo2_data`, `mongo3_data`) y el secret `mongo_keyfile`, dejando el entorno listo para un nuevo despliegue desde cero (preserva Docker Swarm y la red overlay):

```bash
ansible-playbook playbooks/tests/reset_local_environment.yml
```

---

## 🛟 Playbooks de Recuperación y Contingencia

- **Recuperar / Reconfigurar usuario administrador:**
  ```bash
  ansible-playbook playbooks/recovery/mongo_recover_admin.yml --ask-vault-pass
  ```
- **Reactivar / Escalar `mongo1` tras parada manual:**
  ```bash
  ansible-playbook playbooks/recovery/recover_mongo1.yml
  ```

---

## 🔒 Seguridad y Buenas Prácticas

- Los archivos sensibles (`vars/vault_mongodb.yml` y `secrets/mongo-keyfile`) se configuran con permisos `0600` y están excluidos del control de versiones mediante `.gitignore`.
- Se suministra la plantilla pública `vars/vault_mongodb.example.yml` para que cada desarrollador configure de forma independiente y segura sus credenciales.
- Todos los playbooks emplean `playbook_dir` para garantizar resolución de rutas relativa, portable y determinística.
