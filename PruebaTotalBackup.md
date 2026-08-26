# ============================================================
# FASE 2 - BACKUP Y RESTORE DE MONGODB
# ============================================================

# ============================================================
# 0. VERIFICAR VERSIONAMIENTO
# ============================================================

./tools/mongodb-database-tools/100.18.0/bin/mongodump --version

./tools/mongodb-database-tools/100.18.0/bin/mongorestore --version

# ============================================================
# 1. PREPARAR ANSIBLE VAULT
# ============================================================

# Cifrar el archivo de credenciales
ansible-vault encrypt vars/vault_mongodb.yml

# Visualizar las credenciales cifradas
ansible-vault view vars/vault_mongodb.yml

# Editar las credenciales cifradas cuando sea necesario
ansible-vault edit vars/vault_mongodb.yml


# ============================================================
# 2. PREPARAR MONGODB DATABASE TOOLS
# ============================================================

ansible-playbook playbooks/backup/backup_tools_setup.yml


# ============================================================
# 3. CREAR USUARIO DE BACKUP
# ============================================================

ansible-playbook playbooks/backup/backup_create_users.yml --ask-vault-pass


# ============================================================
# 4. EJECUTAR BACKUP
# ============================================================

ansible-playbook playbooks/backup/backup_run.yml --ask-vault-pass


# ============================================================
# 5. VALIDAR BACKUP
# ============================================================

ansible-playbook playbooks/backup/backup_validate.yml


# ============================================================
# 6. CREAR USUARIO DE RESTAURACION
# ============================================================

ansible-playbook playbooks/backup/restore_create_user.yml --ask-vault-pass


# ============================================================
# 7. PRUEBA DE RESTAURACION SEGURA
# ============================================================

# Restaura prueba_ha en:
# prueba_ha_restore_test
#
# No elimina ni modifica la base original.

ansible-playbook playbooks/backup/restore_test.yml --ask-vault-pass


# ============================================================
# 8. PRUEBA FINAL DE RECUPERACION ANTE DESASTRE
# ============================================================

# IMPORTANTE:
# Abrir MongoDB Compass antes de ejecutar este paso.
#
# El playbook:
# 1. valida el backup
# 2. cuenta los datos existentes
# 3. elimina prueba_ha
# 4. confirma la eliminacion
# 5. realiza una pausa para verla desaparecer en Compass
# 6. restaura prueba_ha desde el backup
# 7. compara colecciones y documentos
# 8. valida el Replica Set

ansible-playbook playbooks/backup/restore_disaster_test.yml --ask-vault-pass


# ============================================================
# 9. VERIFICAR RESULTADO EN MONGODB COMPASS
# ============================================================

# Verificar:
#
# prueba_ha
# └── registros
#     └── 2 documentos
#
# Antes del desastre:
#   prueba_ha existe
#
# Durante la pausa:
#   prueba_ha desaparece
#
# Despues del restore:
#   prueba_ha reaparece con sus datos


# ============================================================
# 10. VERIFICAR ARCHIVOS DE BACKUP
# ============================================================

find backups/mongodb/prueba_ha -type f -ls


# ============================================================
# 11. VERIFICAR BITACORA
# ============================================================

cat logs/mongodb_backup.log


# ============================================================
# 12. LIMPIEZA DE DATOS DE PRUEBA
# ============================================================

# Elimina prueba_ha cuando termine la demostracion.

ansible-playbook playbooks/tests/cleanup_test_data.yml --ask-vault-pass


# ============================================================
# 13. ELIMINAR TODO EL ENTORNO LOCAL - SOLO SI SE REQUIERE
# ============================================================

ansible-playbook playbooks/tests/reset_local_environment.yml

# ============================================================
# 14. BORRAR SOLO LOS ARCHIVOS DE BACKUP
# ============================================================

ansible-playbook playbooks/backup/cleanup_backup_files.yml
