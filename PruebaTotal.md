# ============================================================
# 1. INFRAESTRUCTURA
# ============================================================

ansible-playbook playbooks/infrastructure/swarm_setup.yml

ansible-playbook playbooks/infrastructure/network_setup.yml


# ============================================================
# 2. SEGURIDAD
# ============================================================

ansible-playbook playbooks/security/keyfile_setup.yml

ansible-playbook playbooks/security/keyfile_secret.yml

docker secret ls

docker network ls | grep mongo_swarm_net


# ============================================================
# 3. CREAR MONGODB
# ============================================================

ansible-playbook playbooks/mongodb/mongo_services.yml

ansible-playbook playbooks/mongodb/mongo_replset.yml

ansible-playbook playbooks/mongodb/mongo_replset_nodes.yml


# ============================================================
# 4. AUTENTICACION
# ============================================================

ansible-playbook playbooks/mongodb/mongo_create_admin.yml --ask-vault-pass


# ============================================================
# 5. AGREGAR NODOS AL REPLICA SET
# ============================================================

ansible-playbook playbooks/mongodb/mongo_replset_add_nodes.yml --ask-vault-pass


ansible-playbook playbooks/mongodb/configure_priorities.yml --ask-vault-pass


ansible-playbook playbooks/validation/validate_replset.yml --ask-vault-pass


# ============================================================
# 6. CREAR DATOS DE PRUEBA
# ============================================================

ansible-playbook playbooks/tests/test_replication_data.yml --ask-vault-pass


# ============================================================
# 7. PRUEBA DE ALTA DISPONIBILIDAD
# ============================================================

ansible-playbook playbooks/tests/test_high_availability.yml --ask-vault-pass


# ============================================================
# 8. BORRAR SOLO LA BASE prueba_ha
# ============================================================

ansible-playbook playbooks/tests/cleanup_test_data.yml --ask-vault-pass


# ============================================================
# 9. ELIMINAR EL ENTORNO DOCKER V2
# ============================================================

ansible-playbook playbooks/tests/reset_local_environment.yml

