#!/usr/bin/env python3
"""
Regression and Static Validation Test for reset_local_environment.yml.
Verifies:
1. reset_local_environment.yml includes tasks to remove mongo1_tls_control, mongo2_tls_control, mongo3_tls_control.
2. reset_local_environment.yml cleans up operational TLS rollout state artifacts in logs/.
3. reset_local_environment.yml synchronizes vars/local.yml to:
   - mongo_tls_enabled: false
   - mongo_tls_clients_enabled: false
   - mongo_tls_target_mode: requireTLS
   - mongo_tls_deployment_mode: disabled
4. reset_local_environment.yml preserves Docker Secrets TLS (mongo_tls_ca_v1, node pems).
5. reset_local_environment.yml validates all clean bootstrap conditions upon completion.
"""

import os, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

class TestResetLocalEnvironment(unittest.TestCase):

    def setUp(self):
        self.reset_path = os.path.join(REPO, 'playbooks/tests/reset_local_environment.yml')
        with open(self.reset_path) as f:
            self.reset_text = f.read()

    def test_1_removes_tls_control_volumes(self):
        """Verifies reset_local_environment.yml targets mongo1/2/3_tls_control volumes for deletion"""
        self.assertIn('mongo1_tls_control', self.reset_text)
        self.assertIn('mongo2_tls_control', self.reset_text)
        self.assertIn('mongo3_tls_control', self.reset_text)
        self.assertIn('final_tls_volumes', self.reset_text)

    def test_2_removes_operational_rollout_state_files(self):
        """Verifies reset_local_environment.yml deletes tls_rollout_state.json and update specs"""
        self.assertIn('logs/tls_rollout_state.json', self.reset_text)
        self.assertIn('logs/tls_update_spec_mongo1.json', self.reset_text)

    def test_3_synchronizes_vars_local_to_bootstrap_state(self):
        """Verifies reset_local_environment.yml updates vars/local.yml to clean bootstrap values"""
        self.assertIn('line: \'mongo_tls_enabled: false\'', self.reset_text)
        self.assertIn('line: \'mongo_tls_clients_enabled: false\'', self.reset_text)
        self.assertIn('line: \'mongo_tls_target_mode: "requireTLS"\'', self.reset_text)
        self.assertIn('line: \'mongo_tls_deployment_mode: "disabled"\'', self.reset_text)

    def test_4_preserves_tls_pki_secrets(self):
        """Verifies reset_local_environment.yml does NOT delete TLS PKI secrets (only mongo_keyfile)"""
        self.assertIn('docker secret rm {{ mongo_secret }}', self.reset_text)
        self.assertNotIn('mongo_tls_ca_v1', self.reset_text)
        self.assertNotIn('mongo1_tls_pem_v1', self.reset_text)

    def test_5_validates_clean_bootstrap_assertions(self):
        """Verifies final assertion checks all services, data volumes, tls control volumes, and vars"""
        self.assertIn('final_services.stdout | trim == ""', self.reset_text)
        self.assertIn('final_data_volumes.stdout | trim == ""', self.reset_text)
        self.assertIn('final_tls_volumes.stdout | trim == ""', self.reset_text)
        self.assertIn('final_secret.stdout | trim == ""', self.reset_text)
        self.assertIn('not (local_vars.mongo_tls_enabled | bool)', self.reset_text)
        self.assertIn('not (local_vars.mongo_tls_clients_enabled | bool)', self.reset_text)
        self.assertIn('local_vars.mongo_tls_target_mode == \'requireTLS\'', self.reset_text)
        self.assertIn('local_vars.mongo_tls_deployment_mode == \'disabled\'', self.reset_text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
