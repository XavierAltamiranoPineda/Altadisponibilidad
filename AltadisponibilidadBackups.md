============================================================

0. PREPARAR REPOSITORIO LOCAL DESPUÉS DE CLONAR

============================================================

0.1. Clonar el repositorio

git clone https://github.com/XavierAltamiranoPineda/Altadisponibilidad.git
cd Altadisponibilidad

0.2. Instalar dependencias base

En Ubuntu/WSL:

sudo apt update
sudo apt install -y ansible git openssl curl jq coreutils util-linux

Verificar:

ansible --version
git --version
openssl version
docker --version
docker compose version

Docker Desktop debe estar instalado y la integración con WSL habilitada antes de continuar.

0.3. Dar permisos de ejecución a los scripts

chmod -R u+rwX .
find scripts -type f -name '*.sh' -exec chmod u+x {} +

Verificar:

find scripts -type f -name '*.sh' -exec ls -l {} +

0.4. Crear la carpeta secrets/ antes de ejecutar Ansible

La carpeta secrets/ no debe depender de Git para existir. Los playbooks generan dentro de ella el keyfile, la PKI TLS y otros secretos, por lo que debe crearse manualmente después de clonar el repositorio:

mkdir -p secrets
chmod 700 secrets

La estructura terminará siendo similar a:

secrets/
├── backup-encryption
│   └── local
│       ├── backup_age.key
│       └── backup_age.pub
├── mongo-keyfile
├── mongodb-tls
│   └── local
│       ├── ca
│       │   ├── mongo_local_root_ca.csr
│       │   └── mongo_local_root_ca.key
│       └── v1
│           ├── mongo1
│           │   ├── mongo1.crt
│           │   ├── mongo1.csr
│           │   ├── mongo1.key
│           │   └── mongo1.pem
│           ├── mongo2
│           │   ├── mongo2.crt
│           │   ├── mongo2.csr
│           │   ├── mongo2.key
│           │   └── mongo2.pem
│           ├── mongo3
│           │   ├── mongo3.crt
│           │   ├── mongo3.csr
│           │   ├── mongo3.key
│           │   └── mongo3.pem
│           └── mongo_ca.pem
└── vault_password

No crees manualmente mongo-keyfile, certificados, claves privadas o archivos PEM. Esos archivos los generan los playbooks. Solo crea la carpeta secrets/ y el archivo vault_password cuando corresponda.

0.5. Crear el archivo de contraseña de Ansible Vault

nano secrets/vault_password
chmod 600 secrets/vault_password

El archivo debe contener únicamente la contraseña utilizada para abrir vars/vault_mongodb.yml. No debe subirse a Git.

0.6. Verificar .gitignore

Asegúrate de que .gitignore contenga, como mínimo:

# Secretos y material criptográfico
secrets/

# Backups y logs generados
backups/
logs/

# Archivos temporales
*.tmp
*.log

Verifica que Git no intente rastrear secretos:

git status --ignored

Nunca deben aparecer como archivos versionados:

secrets/mongo-keyfile
secrets/vault_password
secrets/mongodb-tls/**
secrets/backup-encryption/**

Si alguno ya fue agregado al índice de Git por error, retíralo del índice sin borrar el archivo local:

git rm -r --cached secrets

Después confirma:

git status


# ============================================================
# 1. ELIMINAR BACKUPS
# ============================================================

ansible-playbook \
  playbooks/backup/cleanup_backup_files.yml


# ============================================================
# 2. ELIMINAR MONGODB Y SUS BASES (RESET COMPLETO A BOOTSTRAP)
# ============================================================

ansible-playbook \
  playbooks/tests/reset_local_environment.yml


# ============================================================
# 3. CONSTRUIR INFRAESTRUCTURA BASE
# ============================================================

ansible-playbook playbooks/infrastructure/swarm_setup.yml

ansible-playbook playbooks/infrastructure/network_setup.yml


# ============================================================
# 4. KEYFILE DE AUTENTICACION
# ============================================================

ansible-playbook playbooks/security/keyfile_setup.yml

ansible-playbook playbooks/security/keyfile_secret.yml


# ============================================================
# 5. CERTIFICADOS TLS / PKI Y DOCKER SECRETS
# ============================================================

ansible-playbook \
  playbooks/security/tls_local_pki.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

ansible-playbook \
  playbooks/security/validate_tls_pki.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

ansible-playbook \
  playbooks/security/tls_secrets.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


# ============================================================
# 6. CREAR SERVICIOS MONGODB (MODO INICIAL: disabled)
# ============================================================

ansible-playbook \
  playbooks/mongodb/mongo_services.yml \
  -e target_environment=local


# ============================================================
# 7. INICIALIZAR REPLICA SET Y USUARIO ADMIN
# ============================================================

ansible-playbook \
  playbooks/mongodb/mongo_replset.yml \
  -e target_environment=local

ansible-playbook \
  playbooks/mongodb/mongo_replset_nodes.yml \
  -e target_environment=local

ansible-playbook \
  playbooks/mongodb/mongo_create_admin.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

ansible-playbook \
  playbooks/mongodb/mongo_replset_add_nodes.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


# ============================================================
# 8. ROLLOUT TLS PROGRESIVO (TRANSICIONES ADYACENTES)
# ============================================================

#  Transición 3: preferTLS -> requireTLS (Servidores exigen exclusivamente TLS)
./scripts/run_tls_rollout.sh \
  requireTLS \
  -e target_environment=local


# ============================================================
# 9. CONFIGURAR PRIORIDADES (HA: mongo1=2, mongo2=1, mongo3=1)
# ============================================================

ansible-playbook \
  playbooks/mongodb/configure_priorities.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


# ============================================================
# 10. VALIDAR REPLICA SET EN MODO requireTLS
# ============================================================

ansible-playbook \
  playbooks/validation/validate_replset.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

ansible-playbook \
  playbooks/validation/validate_mongodb_tls.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

# ============================================================
# 10.1 CONFIGURACION COMPASS
# ============================================================

# 1. Verificar que mongo1 publica el puerto

docker service ls

Debe verse:

mongo1   replicated   1/1   mongo:7-jammy   *:27017->27017/tcp


# 2. Verificar CA publica

ls -l secrets/mongodb-tls/local/v1/mongo_ca.pem


# 3. Copiar CA a Windows

cp secrets/mongodb-tls/local/v1/mongo_ca.pem \
  /mnt/c/Users/Usuario01/Documents/mongo_ca.pem


# 4. Obtener usuario admin

ansible-vault view \
  vars/vault_mongodb.yml \
  --vault-password-file secrets/vault_password \
  | grep '^mongo_admin_user:'


# 5. Obtener password admin

ansible-vault view \
  vars/vault_mongodb.yml \
  --vault-password-file secrets/vault_password \
  | grep '^mongo_admin_password:'


# 6. Usar URI

mongodb://localhost:27017/?directConnection=true&tls=true&authSource=admin


# 7. Configurar Authentication

Username:
admin

Password:
<password obtenido del Vault>

Authentication Database:
admin


# 8. Configurar TLS/SSL

TLS/SSL:
On

Importar el certificado CA en MongoDB Compass:
Certificate Authority File:
C:\Users\Usuario01\Documents\mongo_ca.pem

Client Certificate:
ninguno

Allow invalid certificates:
OFF

Allow invalid hostnames:
OFF


# 9. Conectar

Presionar:

Connect


# ============================================================

# 11. CREAR DATOS DE PRUEBA

# ============================================================

ansible-playbook \
  playbooks/tests/test_replication_data.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


# ============================================================

# 12. PRUEBA DE ALTA DISPONIBILIDAD

# ============================================================

ansible-playbook \
  playbooks/tests/test_high_availability.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


# ============================================================

# 13. BACKUP REAL

# ============================================================

# 1. Aprovisionar / verificar idempotentemente el usuario de respaldo
ansible-playbook \
  playbooks/backup/backup_create_users.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local
# 2. Aprovisionar / verificar idempotentemente el usuario de restauración
ansible-playbook \
  playbooks/backup/restore_create_user.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local

./scripts/run_mongodb_backup.sh \
  -e target_environment=local


VER AHORA EN BACKUPS
find backups/mongodb/prueba_ha -type f | sort

Debes ver:

prueba_ha_YYYYMMDD_HHMMSS.archive.gz
prueba_ha_YYYYMMDD_HHMMSS.archive.gz.sha256

# ============================================================

# 14. RESTORE DE PRUEBA

# ============================================================

ansible-playbook \
  playbooks/backup/restore_test.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


# ============================================================

# 15. DISASTER RECOVERY VISUAL

# ============================================================

Abre prueba_ha en Compass antes de ejecutar:

ansible-playbook \
  playbooks/backup/restore_disaster_test.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


MIRAR COMPASS DURANTE LA PAUSA


# ============================================================

# 16. PRUEBA DEL CRON

# ============================================================

ansible-playbook \
  playbooks/tests/test_backup_cron_execution.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


# ============================================================

# 17. VALIDACION FINAL

# ============================================================

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
