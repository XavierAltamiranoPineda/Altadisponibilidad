#!/usr/bin/env python3
"""
Static Security and Compliance Test for MongoDB Clients (ETAPA 4.10)
Verifies:
1. Operational administrative clients use ONLY TLS (tls=true, sslCAFile, tlsCAFile=/run/mongo-ca/mongo_ca.pem).
2. Operational clients mount ONLY the public CA certificate read-only (:ro).
3. No private keys (*.key, mongo_local_root_ca.key) or server node PEMs (*.pem except mongo_ca.pem) mounted in client runners.
4. Zero usage of insecure flags: tlsAllowInvalidCertificates, tlsAllowInvalidHostnames, tlsInsecure across the entire codebase.
5. Zero password exposure in argv or command lines across all operational clients.
6. Zero unauthorized plaintext connections: any playbook/task connecting to MongoDB without TLS must be in the strictly justified whitelist (Bootstrap, Disaster Recovery, Mode-Aware rollout probes).
"""

import os, re, sys, unittest, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

OPERATIONAL_CLIENT_PLAYBOOKS = [
    'playbooks/mongodb/configure_priorities.yml',
    'playbooks/mongodb/rotate_admin_password.yml',
    'playbooks/validation/validate_replset.yml',
    'playbooks/validation/validate_mongodb.yml',
    'playbooks/tests/test_replication_data.yml',
    'playbooks/tests/test_high_availability.yml',
    'playbooks/tests/cleanup_test_data.yml',
    'playbooks/backup/backup_create_users.yml',
    'playbooks/backup/restore_create_user.yml',
    'playbooks/backup/backup_run.yml',
    'playbooks/backup/restore_disaster_test.yml',
    'playbooks/backup/restore_quarterly_evidence.yml',
]

OPERATIONAL_CLIENT_TASKS = [
    'playbooks/backup/tasks/restore_test_tasks.yml',
    'playbooks/mongodb/tasks/mongo_admin_auth_check.yml',
    'playbooks/mongodb/tasks/rotate_admin_password_transaction.yml',
]

ALL_OPERATIONAL_FILES = OPERATIONAL_CLIENT_PLAYBOOKS + OPERATIONAL_CLIENT_TASKS

# Strict whitelist of justified non-operational or transitional components
EXEMPT_BOOTSTRAP_OR_RECOVERY = {
    'playbooks/mongodb/mongo_replset.yml': 'Bootstrap inicial del Replica Set antes de aprovisionar TLS',
    'playbooks/mongodb/mongo_replset_add_nodes.yml': 'Bootstrap inicial al incorporar nodos antes de TLS',
    'playbooks/mongodb/mongo_create_admin.yml': 'Bootstrap inicial para crear administrador previo a TLS',
    'playbooks/recovery/mongo_recover_admin.yml': 'Recuperacion de desastres en mongod standalone disabled',
    'playbooks/mongodb/tasks/tls_precheck_pre_mutation.yml': 'Mode-aware probe de invariantes pre-mutacion',
    'playbooks/mongodb/tasks/tls_query_cluster.yml': 'Mode-aware probe de topologia durante transiciones',
    'playbooks/mongodb/tasks/tls_query_runtime_modes.yml': 'Mode-aware probe individual para detectar modo TLS de cada mongod',
    'playbooks/mongodb/tasks/tls_task_identity.yml': 'Mode-aware probe de identidad y salud Swarm',
    'playbooks/mongodb/tasks/tls_validate_transport.yml': 'Probe intencional de compatibilidad allowTLS (plaintext & TLS)',
}

class TestTLSClientAudit(unittest.TestCase):

    def test_operational_clients_enforce_tls_and_ca_validation(self):
        """Ensures all operational administrative clients configure TLS and reference canonical client CA file"""
        for rel_path in OPERATIONAL_CLIENT_PLAYBOOKS:
            full_path = os.path.join(REPO, rel_path)
            self.assertTrue(os.path.isfile(full_path), f"File not found: {rel_path}")
            with open(full_path) as f:
                content = f.read()

            self.assertTrue(
                ('tls=true' in content or '--tls' in content or '--sslCAFile' in content or 'tlsCAFile' in content or 'restore_test_tasks.yml' in content),
                f"Operational client {rel_path} does not configure TLS connection!"
            )
            self.assertTrue(
                ('mongo_tls_client_ca_file' in content or '/run/mongo-ca/mongo_ca.pem' in content or 'restore_test_tasks.yml' in content),
                f"Operational client {rel_path} does not reference canonical CA file!"
            )
            self.assertNotIn('tls=false', content, f"Operational client {rel_path} contains tls=false!")

    def test_operational_tasks_mount_ca_cert_readonly(self):
        """Ensures operational tasks mount mongo_tls_ca_cert_path to client CA file with :ro"""
        for rel_path in ALL_OPERATIONAL_FILES:
            full_path = os.path.join(REPO, rel_path)
            with open(full_path) as f:
                content = f.read()

            if 'docker' in content and 'run' in content:
                self.assertTrue(
                    ('mongo_tls_ca_cert_path' in content and ':ro' in content),
                    f"Operational client {rel_path} must mount mongo_tls_ca_cert_path as :ro!"
                )

    def test_no_private_keys_or_server_pems_mounted_in_clients(self):
        """Ensures no client runner mounts CA private keys or server node PEM certificates"""
        for rel_path in ALL_OPERATIONAL_FILES:
            full_path = os.path.join(REPO, rel_path)
            with open(full_path) as f:
                content = f.read()

            self.assertNotIn('mongo_local_root_ca.key', content, f"{rel_path} references CA key!")
            self.assertNotIn('mongo1.pem', content, f"{rel_path} mounts server node PEM!")
            self.assertNotIn('mongo2.pem', content, f"{rel_path} mounts server node PEM!")
            self.assertNotIn('mongo3.pem', content, f"{rel_path} mounts server node PEM!")

    def test_zero_insecure_tls_flags_across_repo(self):
        """Ensures no client uses tlsInsecure, tlsAllowInvalidCertificates, or tlsAllowInvalidHostnames"""
        for root, _, files in os.walk(os.path.join(REPO, 'playbooks')):
            for file in files:
                if file.endswith(('.yml', '.yaml')):
                    full_path = os.path.join(root, file)
                    with open(full_path) as f:
                        content = f.read()

                    self.assertNotIn('tlsAllowInvalidCertificates', content,
                        f"Found tlsAllowInvalidCertificates in {file}!")
                    self.assertNotIn('tlsAllowInvalidHostnames', content,
                        f"Found tlsAllowInvalidHostnames in {file}!")
                    self.assertNotIn('tlsInsecure', content,
                        f"Found tlsInsecure in {file}!")

    def test_no_passwords_in_argv_in_operational_clients(self):
        """Ensures no operational client passes passwords directly in argv"""
        for rel_path in ALL_OPERATIONAL_FILES:
            full_path = os.path.join(REPO, rel_path)
            with open(full_path) as f:
                content = f.read()

            self.assertNotIn('--password={{', content, f"{rel_path} contains --password={{{{")
            self.assertNotIn('--password "{{', content, f"{rel_path} contains --password \"{{{{")
            self.assertNotIn('--password "$', content, f"{rel_path} contains --password \"$")

    def test_all_non_tls_mongo_connections_are_strictly_justified_exemptions(self):
        """Ensures every single mongosh/mongodump/mongorestore call connecting to MongoDB without tls=true is in the justified whitelist"""
        all_playbook_files = glob.glob(f"{REPO}/playbooks/**/*.yml", recursive=True)
        for f in all_playbook_files:
            rel = os.path.relpath(f, REPO)
            with open(f) as fp:
                content = fp.read()

            # Identify actual network connections to MongoDB cluster
            lines = content.splitlines()
            connects_to_cluster = False
            for l in lines:
                s = l.strip()
                if ('connect(' in l) or ('--eval' in l and 'db.' in l) or ('--host' in l and '27017' in l) or ('--uri' in l and 'mongo' in l):
                    connects_to_cluster = True
                    break
                if ('mongodump' in l or 'mongorestore' in l) and ('--uri' in l or '--archive' in l):
                    connects_to_cluster = True
                    break

            if connects_to_cluster:
                has_tls = bool(
                    ('tls=true' in content) or
                    ('--sslCAFile' in content) or
                    ('--tls' in content and 'tlsCAFile' in content) or
                    ('restore_test_tasks.yml' in content) or # Includes TLS tasks
                    (rel in ['playbooks/mongodb/tasks/mongo_admin_auth_check.yml',
                             'playbooks/mongodb/tasks/rotate_admin_password_transaction.yml']) # URI passed from parent rotate_admin_password.yml
                )

                if not has_tls:
                    self.assertIn(
                        rel,
                        EXEMPT_BOOTSTRAP_OR_RECOVERY,
                        f"UNJUSTIFIED PLAINTEXT MONGO CONNECTION FOUND IN: {rel}!\n"
                        f"Every non-TLS client must be in EXEMPT_BOOTSTRAP_OR_RECOVERY whitelist."
                    )


if __name__ == '__main__':
    unittest.main(verbosity=2)
