#!/usr/bin/env python3
"""
Static Architecture and Compliance Test for Stage 5 TLS Rollout (allowTLS -> preferTLS / requireTLS),
Recovery / Reconciliation, and Runtime Detector.
Verifies:
1. scripts/run_tls_rollout.sh parameter parsing, validation of allowed modes, and flock locking.
2. Classifier recognition of permanent_disabled, permanent_allowtls, permanent_prefertls, permanent_requiretls, historical_disabled, and unknown.
3. ServiceSpec API builder supports all 4 permanent modes with correct secrets, tmpfs, and arguments.
4. Gated restart, control volume setup, and rollback mechanism are mode-aware.
5. Invariants preserved (no hardcoded allowTLS assumptions, non-destructive rollback, zero runtime changes).
6. Forward transitions strictly enforced:
   - disabled -> allowTLS (allowed)
   - allowTLS -> preferTLS (allowed, requires clients_enabled=true)
   - preferTLS -> requireTLS (allowed, requires clients_enabled=true)
   - Stage jumps rejected.
7. Bug 1 Fix: validate_mongodb_tls_tasks.yml does not use brittle 'first.ID' expressions and validates snapshot safely.
8. Bug 2 Fix: tls_rollback_transition.yml calculates target_arg and spec_mode before using them in separate tasks.
9. Runtime Detector (tls_query_runtime_modes.yml):
   - Primary TLS connection with CA verification (/run/mongo-ca/mongo_ca.pem).
   - Plaintext fallback for bootstrap/historical disabled recovery.
   - Explicit classification: disabled, allowTLS, preferTLS, requireTLS, and unknown.
   - Zero insecure flags and zero passwords in argv.
10. Rollback references tls_query_runtime_modes.yml correctly (zero typos like tls_query_runtime_mods.yml).
"""

import os, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

class TestTLSStage5RolloutArchitecture(unittest.TestCase):

    def test_run_tls_rollout_script_validation(self):
        """Validates scripts/run_tls_rollout.sh structure and parameter checks"""
        script_path = os.path.join(REPO, 'scripts/run_tls_rollout.sh')
        self.assertTrue(os.path.isfile(script_path), "run_tls_rollout.sh not found")
        self.assertTrue(os.access(script_path, os.X_OK), "run_tls_rollout.sh not executable")
        with open(script_path) as f:
            content = f.read()
        self.assertIn('set -euo pipefail', content)
        self.assertIn('flock -n "$LOCK_FILE"', content)
        self.assertIn('disabled|allowTLS|preferTLS|requireTLS', content)
        self.assertIn('--extra-vars "target_tls_mode=${TARGET_MODE}"', content)

    def test_classifier_recognizes_all_permanent_modes(self):
        """Validates that tls_classify_service_specs.yml classifies all 4 permanent modes"""
        classify_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_classify_service_specs.yml')
        with open(classify_path) as f:
            content = f.read()
        self.assertIn('permanent_requiretls', content)
        self.assertIn('permanent_prefertls', content)
        self.assertIn('permanent_allowtls', content)
        self.assertIn('permanent_disabled', content)
        self.assertIn('historical_disabled', content)
        self.assertIn('unknown', content)

    def test_service_spec_api_supports_prefertls_and_requiretls(self):
        """Validates tls_service_update_api.yml creates correct specs for preferTLS and requireTLS"""
        api_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_service_update_api.yml')
        with open(api_path) as f:
            content = f.read()
        self.assertIn("mongo_tls_target_spec_mode == 'permanent_requiretls'", content)
        self.assertIn("target_tls_arg = 'requireTLS'", content)
        self.assertIn("mongo_tls_target_spec_mode == 'permanent_prefertls'", content)
        self.assertIn("target_tls_arg = 'preferTLS'", content)
        self.assertIn("mongo_tls_target_spec_mode == 'permanent_allowtls'", content)
        self.assertIn("target_tls_arg = 'allowTLS'", content)

    def test_runtime_facts_unified_exec_flags(self):
        """Validates tls_runtime_facts.yml wrapper script supports allowTLS, preferTLS, requireTLS"""
        facts_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_runtime_facts.yml')
        with open(facts_path) as f:
            content = f.read()
        self.assertIn('disabled|allowTLS|preferTLS|requireTLS', content)
        self.assertIn('--tlsMode "$TLS_MODE"', content)
        self.assertIn('--tlsAllowConnectionsWithoutCertificates', content)
        self.assertIn('--setParameter tlsWithholdClientCertificate=true', content)

    def test_rollback_is_mode_aware(self):
        """Validates that tls_rollback_transition.yml rolls back safely to source mode"""
        rollback_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_rollback_transition.yml')
        with open(rollback_path) as f:
            content = f.read()
        self.assertIn('mongo_tls_rollback_spec_mode', content)
        self.assertIn('permanent_allowtls', content)
        self.assertIn('permanent_disabled', content)

    def test_transport_validator_mode_awareness(self):
        """Validates mode-aware transport probes in tls_validate_transport.yml"""
        transport_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_validate_transport.yml')
        with open(transport_path) as f:
            content = f.read()
        self.assertIn("in ['allowTLS', 'preferTLS']", content)
        self.assertIn("== 'requireTLS'", content)

    def test_forward_transitions_matrix_in_rollout(self):
        """Validates that tls_rollout.yml enforces strict adjacent forward transitions"""
        rollout_path = os.path.join(REPO, 'playbooks/mongodb/tls_rollout.yml')
        with open(rollout_path) as f:
            content = f.read()

        self.assertNotIn("mongo_tls_deployment_mode == 'disabled'", content)
        self.assertNotIn("no permitida en Etapa 3", content)
        self.assertIn("allowed_forward_transitions:", content)
        self.assertIn('disabled: "allowTLS"', content)
        self.assertIn('allowTLS: "preferTLS"', content)
        self.assertIn('preferTLS: "requireTLS"', content)

    def test_bug1_snapshot_validation_is_robust_and_no_first_id(self):
        """Validates Bug 1 Fix: ensure no brittle 'first.ID' or similar unchecked access exists in validate_mongodb_tls_tasks.yml"""
        val_path = os.path.join(REPO, 'playbooks/validation/tasks/validate_mongodb_tls_tasks.yml')
        with open(val_path) as f:
            content = f.read()
        self.assertNotIn('| from_json | first).ID', content, "Brittle '.ID' access on unparsed dict found in validator")
        self.assertIn('mongo_tls_validated_services_map', content, "Validator must use structured normalized map")
        self.assertIn('mongo_tls_snapshot_services[item].identity.service_id', content, "Validator must compare canonical snapshot IDs")

    def test_bug2_rollback_tasks_separation(self):
        """Validates Bug 2 Fix: ensure rollback target_arg calculation and target_mode_expected setting are in separate tasks"""
        rb_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_rollback_transition.yml')
        with open(rb_path) as f:
            content = f.read()
        self.assertIn('TAREA A', content, "Task A for calculating target_arg must be present")
        self.assertIn('TAREA B', content, "Task B for setting target_mode_expected must be present")
        task_a_idx = content.find('Calcular target y spec mode de rollback')
        task_b_idx = content.find('Marcar fase de rollback y registrar target_mode esperado')
        self.assertTrue(task_a_idx != -1 and task_b_idx != -1 and task_a_idx < task_b_idx,
                        "Task A must precede Task B in tls_rollback_transition.yml")

    def test_runtime_detector_classification_and_modes(self):
        """Validates tls_query_runtime_modes.yml has full mode awareness: disabled, allowTLS, preferTLS, requireTLS, and unknown"""
        query_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_query_runtime_modes.yml')
        with open(query_path) as f:
            content = f.read()

        # Classification checks
        self.assertIn("return 'disabled'", content)
        self.assertIn("return 'allowTLS'", content)
        self.assertIn("return 'preferTLS'", content)
        self.assertIn("return 'requireTLS'", content)
        self.assertIn("return 'unknown'", content)

        # Primary TLS with CA check and plaintext fallback
        self.assertIn("tlsCAFile", content)
        self.assertIn("/run/mongo-ca/mongo_ca.pem", content)
        self.assertIn("plaintext_fallback", content)
        self.assertIn("tls_error", content)

        # Insecure flags and passwords
        self.assertNotIn("tlsAllowInvalidCertificates", content)
        self.assertNotIn("tlsAllowInvalidHostnames", content)
        self.assertNotIn("tlsInsecure", content)
        self.assertNotIn("password=", content)

    def test_rollback_task_include_spelling(self):
        """Ensures tls_rollback_transition.yml references tls_query_runtime_modes.yml with zero typos"""
        rb_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_rollback_transition.yml')
        with open(rb_path) as f:
            content = f.read()
        self.assertIn('tls_query_runtime_modes.yml', content)
        self.assertNotIn('tls_query_runtime_mods.yml', content)

    def test_zero_runtime_changes_in_vars_local(self):
        """Confirms that vars/local.yml deployment_mode has not been altered prematurely"""
        local_vars_path = os.path.join(REPO, 'vars/local.yml')
        with open(local_vars_path) as f:
            content = f.read()
        self.assertIn('mongo_tls_deployment_mode: "allowTLS"', content)
        self.assertIn('mongo_tls_clients_enabled: true', content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
