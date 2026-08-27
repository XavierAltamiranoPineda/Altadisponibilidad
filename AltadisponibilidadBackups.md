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

# 11. CREAR DATOS DE PRUEBA

# ============================================================

ansible-playbook \
  playbooks/tests/test_replication_data.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


🍃 VER AHORA EN MONGODB COMPASS

Haz Refresh.

Ahora sí debe aparecer:

prueba_ha
└── datos_failover

Dentro debe existir el documento de prueba.

Este momento demuestra que la base fue creada nuevamente después del rebuild.

# ============================================================

# 12. PRUEBA DE ALTA DISPONIBILIDAD

# ============================================================

ansible-playbook \
  playbooks/tests/test_high_availability.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local



🖥️ MIRAR DOCKER DESKTOP DURANTE EL TEST

Cuando aparezca:

Detener mongo1 mediante scale=0

mira Docker Desktop.

Debes ver temporalmente algo equivalente a:

mongo1   0/0
mongo2   1/1
mongo3   1/1

Luego uno de los secundarios asume como PRIMARY.

Después, cuando Ansible recupere mongo1, debe volver a:

mongo1   1/1
🍃 VER AHORA EN COMPASS

La base debe seguir accesible durante la prueba cuando exista un PRIMARY disponible.

Después del failback, los datos escritos durante la caída deben seguir presentes.

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


🍃 VER AHORA EN COMPASS

No debería cambiar nada visualmente.

La base sigue funcionando normalmente mientras se genera el respaldo.

📁 VER AHORA EN BACKUPS
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


🍃 VER AHORA EN COMPASS

Después del restore debes ver:

prueba_ha
prueba_ha_restore_test

La original debe seguir existiendo.

# ============================================================

# 15. DISASTER RECOVERY VISUAL

# ============================================================

Abre prueba_ha en Compass antes de ejecutar:

ansible-playbook \
  playbooks/backup/restore_disaster_test.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


🍃 MIRAR COMPASS DURANTE LA PAUSA

Cuando el playbook elimine prueba_ha y haga la pausa:

haz Refresh.

Debe desaparecer:

prueba_ha ❌

Ese es el desastre simulado.

🍃 MIRAR COMPASS AL TERMINAR

Haz otro Refresh.

Debe reaparecer:

prueba_ha ✅

con sus colecciones y documentos.

Este es probablemente el mejor momento visual de toda la demostración.

# ============================================================

# 16. PRUEBA DEL CRON

# ============================================================

ansible-playbook \
  playbooks/tests/test_backup_cron_execution.yml \
  --vault-password-file secrets/vault_password \
  -e target_environment=local


📁 VER AHORA EN BACKUPS

Debe aparecer un backup adicional.

🍃 EN COMPASS

La base debe seguir funcionando normalmente.

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
🖥️ ULTIMA VISTA EN DOCKER DESKTOP

Debe terminar exactamente:

mongo1   1/1
mongo2   1/1
mongo3   1/1