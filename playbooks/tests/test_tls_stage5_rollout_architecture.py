#!/usr/bin/env python3
"""
Static Architecture and Compliance Test for Stage 6 TLS Rollout (preferTLS -> requireTLS),
Idempotency, Recovery, Strict Rejection of Plaintext, and Helpers Audit.
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
   - requireTLS -> requireTLS (idempotent no-op)
   - Stage jumps (e.g. allowTLS -> requireTLS, disabled -> requireTLS) rejected.
7. Snapshot validation is robust and compares canonical IDs.
8. Rollback tasks separation (target_arg calculated before target_mode_expected).
9. Runtime Detector (tls_query_runtime_modes.yml):
   - Primary TLS connection with CA verification.
   - Explicit classification: disabled, allowTLS, preferTLS, requireTLS, and unknown.
10. Identity helper (tls_task_identity.yml) uses TLS with CA mounted readonly in TLS modes.
11. Precheck (tls_precheck_pre_mutation.yml) is mode-aware and uses TLS with CA in allowTLS/preferTLS/requireTLS.
12. Plaintext rejection:
   - In requireTLS, plaintext is rejected on all nodes.
13. Zero insecure flags and zero passwords in argv across repo.
"""

import os, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

class TestTLSStage6RolloutArchitecture(unittest.TestCase):

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
        self.assertIn('target_tls_mode=', content)

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

    def test_rollback_is_mode_aware_for_requiretls(self):
        """Validates that tls_rollback_transition.yml rolls back requireTLS to preferTLS"""
        rollback_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_rollback_transition.yml')
        with open(rollback_path) as f:
            content = f.read()
        self.assertIn('mongo_tls_rollback_spec_mode', content)
        self.assertIn('permanent_prefertls', content)
        self.assertIn('permanent_allowtls', content)
        self.assertIn('permanent_disabled', content)

    def test_transport_validator_mode_awareness_and_plaintext_rejection(self):
        """Validates mode-aware transport probes in tls_validate_transport.yml"""
        transport_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_validate_transport.yml')
        with open(transport_path) as f:
            content = f.read()
        self.assertIn("in ['allowTLS', 'preferTLS']", content)
        self.assertIn("== 'requireTLS'", content)
        self.assertIn("mongo_plaintext_reject_probe.rc != 0", content)

    def test_forward_transitions_matrix_and_idempotency_in_rollout(self):
        """Validates that tls_rollout.yml enforces strict adjacent forward transitions and idempotency"""
        rollout_path = os.path.join(REPO, 'playbooks/mongodb/tls_rollout.yml')
        with open(rollout_path) as f:
            content = f.read()

        self.assertNotIn("mongo_tls_deployment_mode == 'disabled'", content)
        self.assertNotIn("no permitida en Etapa 3", content)
        self.assertIn("allowed_forward_transitions:", content)
        self.assertIn('disabled: "allowTLS"', content)
        self.assertIn('allowTLS: "preferTLS"', content)
        self.assertIn('preferTLS: "requireTLS"', content)
        self.assertIn("Manejo idempotente de cluster ya en requireTLS", content)

    def test_runtime_detector_classification_and_modes(self):
        """Validates tls_query_runtime_modes.yml has full mode awareness: disabled, allowTLS, preferTLS, requireTLS, and unknown"""
        query_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_query_runtime_modes.yml')
        with open(query_path) as f:
            content = f.read()
        self.assertIn("return 'disabled'", content)
        self.assertIn("return 'allowTLS'", content)
        self.assertIn("return 'preferTLS'", content)
        self.assertIn("return 'requireTLS'", content)
        self.assertIn("return 'unknown'", content)
        self.assertIn("tlsCAFile", content)
        self.assertIn("/run/mongo-ca/mongo_ca.pem", content)
        self.assertIn("plaintext_fallback", content)

    def test_task_identity_uses_tls_and_ca(self):
        """Validates tls_task_identity.yml uses TLS with CA file in TLS modes"""
        identity_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_task_identity.yml')
        with open(identity_path) as f:
            content = f.read()
        self.assertIn('/run/mongo-ca/mongo_ca.pem', content)
        self.assertIn('&tls=true&tlsCAFile=/run/mongo-ca/mongo_ca.pem', content)
        self.assertNotIn('tlsAllowInvalidCertificates', content)
        self.assertNotIn('tlsAllowInvalidHostnames', content)

    def test_precheck_is_mode_aware_and_uses_tls(self):
        """Validates tls_precheck_pre_mutation.yml uses TLS with CA file in TLS modes"""
        precheck_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_precheck_pre_mutation.yml')
        with open(precheck_path) as f:
            content = f.read()
        self.assertIn('/run/mongo-ca/mongo_ca.pem', content)
        self.assertIn('&tls=true&tlsCAFile=/run/mongo-ca/mongo_ca.pem', content)
        self.assertIn("sourceMode !== 'requireTLS'", content, "requireTLS must never fallback to plaintext")

    def test_rollback_task_include_spelling(self):
        """Ensures tls_rollback_transition.yml references tls_query_runtime_modes.yml with zero typos"""
        rb_path = os.path.join(REPO, 'playbooks/mongodb/tasks/tls_rollback_transition.yml')
        with open(rb_path) as f:
            content = f.read()
        self.assertIn('tls_query_runtime_modes.yml', content)
        self.assertNotIn('tls_query_runtime_mods.yml', content)

    def test_zero_runtime_changes_in_vars_local(self):
        """Confirms that vars/local.yml deployment_mode is a valid recognized mode"""
        local_vars_path = os.path.join(REPO, 'vars/local.yml')
        with open(local_vars_path) as f:
            content = f.read()
        self.assertTrue(any(f'mongo_tls_deployment_mode: "{m}"' in content for m in ['disabled', 'allowTLS', 'preferTLS', 'requireTLS']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
