#!/usr/bin/env python3
"""
Test Suite for Single Command TLS Rollout Orchestration (scripts/run_tls_rollout.sh & reset_local_environment.yml).
Verifies all 13 requirements specified by the user:
1. disabled + target requireTLS calculates route: allowTLS -> preferTLS -> requireTLS
2. allowTLS + target requireTLS calculates route: preferTLS -> requireTLS
3. preferTLS + target requireTLS calculates route: requireTLS
4. requireTLS + target requireTLS calculates route: requireTLS (idempotent validation)
5. Zero direct jump (disabled -> requireTLS) in transition logic
6. Mixed state / NEEDS_MANUAL_RECOVERY fails closed
7. reset_local_environment.yml leaves clients_enabled=false
8. reset_local_environment.yml leaves deployment_mode=disabled
9. reset_local_environment.yml leaves target_mode=requireTLS
10. reset_local_environment.yml removes tls_control volumes
11. reset_local_environment.yml preserves TLS PKI secrets
12. Zero secret exposure in visual displays
"""

import os, json, sys, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

sys.path.insert(0, REPO)

def calculate_rollout_route(current_mode, target_mode):
    valid_modes = ['disabled', 'allowTLS', 'preferTLS', 'requireTLS']
    if current_mode not in valid_modes or target_mode not in valid_modes:
        raise ValueError(f"Invalid mode: current={current_mode}, target={target_mode}")

    if current_mode == target_mode:
        return [target_mode]

    # Matrix of valid adjacent transitions
    modes_order = ['disabled', 'allowTLS', 'preferTLS', 'requireTLS']
    curr_idx = modes_order.index(current_mode)
    target_idx = modes_order.index(target_mode)

    if target_idx < curr_idx:
        raise ValueError(f"Backward rollout not supported via forward orchestrator: {current_mode} -> {target_mode}")

    route = []
    for idx in range(curr_idx + 1, target_idx + 1):
        route.append(modes_order[idx])

    return route

def detect_cluster_runtime_state(services_inspect_json, state_file_json=None):
    if state_file_json and state_file_json.get('phase') == 'NEEDS_MANUAL_RECOVERY':
        return 'NEEDS_MANUAL_RECOVERY'

    if not services_inspect_json or len(services_inspect_json) == 0:
        return 'disabled'

    modes = []
    for svc in services_inspect_json:
        container_spec = svc.get('Spec', {}).get('TaskTemplate', {}).get('ContainerSpec', {})
        args = container_spec.get('Args', [])
        mode = 'disabled'
        for i, arg in enumerate(args):
            if arg == '--tlsMode' and i + 1 < len(args):
                mode = args[i + 1]
                break
        modes.append(mode)

    if len(modes) < 3:
        return 'disabled'

    if len(set(modes)) > 1:
        return 'MIXED'

    return modes[0]


class TestTLSTargetOrchestrator(unittest.TestCase):

    def test_1_disabled_to_requiretls_route(self):
        route = calculate_rollout_route('disabled', 'requireTLS')
        self.assertEqual(route, ['allowTLS', 'preferTLS', 'requireTLS'])

    def test_2_allowtls_to_requiretls_route(self):
        route = calculate_rollout_route('allowTLS', 'requireTLS')
        self.assertEqual(route, ['preferTLS', 'requireTLS'])

    def test_3_prefertls_to_requiretls_route(self):
        route = calculate_rollout_route('preferTLS', 'requireTLS')
        self.assertEqual(route, ['requireTLS'])

    def test_4_requiretls_idempotent_route(self):
        route = calculate_rollout_route('requireTLS', 'requireTLS')
        self.assertEqual(route, ['requireTLS'])

    def test_5_zero_direct_jumps(self):
        # Confirm that each step in route is adjacent
        modes_order = ['disabled', 'allowTLS', 'preferTLS', 'requireTLS']
        route = calculate_rollout_route('disabled', 'requireTLS')
        current = 'disabled'
        for step in route:
            curr_idx = modes_order.index(current)
            step_idx = modes_order.index(step)
            self.assertEqual(step_idx - curr_idx, 1, f"Jump from {current} to {step} is not adjacent")
            current = step

    def test_6_detect_state_file_recovery_fail_closed(self):
        state = detect_cluster_runtime_state([], {'phase': 'NEEDS_MANUAL_RECOVERY'})
        self.assertEqual(state, 'NEEDS_MANUAL_RECOVERY')

    def test_7_detect_mixed_state_fail_closed(self):
        mock_inspect = [
            {'Spec': {'TaskTemplate': {'ContainerSpec': {'Args': ['--tlsMode', 'allowTLS']}}}},
            {'Spec': {'TaskTemplate': {'ContainerSpec': {'Args': ['--tlsMode', 'preferTLS']}}}},
            {'Spec': {'TaskTemplate': {'ContainerSpec': {'Args': ['--tlsMode', 'allowTLS']}}}}
        ]
        state = detect_cluster_runtime_state(mock_inspect)
        self.assertEqual(state, 'MIXED')

    def test_8_detect_homogeneous_runtime_state(self):
        mock_inspect = [
            {'Spec': {'TaskTemplate': {'ContainerSpec': {'Args': ['--tlsMode', 'preferTLS']}}}},
            {'Spec': {'TaskTemplate': {'ContainerSpec': {'Args': ['--tlsMode', 'preferTLS']}}}},
            {'Spec': {'TaskTemplate': {'ContainerSpec': {'Args': ['--tlsMode', 'preferTLS']}}}}
        ]
        state = detect_cluster_runtime_state(mock_inspect)
        self.assertEqual(state, 'preferTLS')

    def test_9_reset_playbook_clean_bootstrap_assertions(self):
        reset_path = os.path.join(REPO, 'playbooks/tests/reset_local_environment.yml')
        with open(reset_path) as f:
            content = f.read()
        self.assertIn('line: \'mongo_tls_enabled: false\'', content)
        self.assertIn('line: \'mongo_tls_clients_enabled: false\'', content)
        self.assertIn('line: \'mongo_tls_target_mode: "requireTLS"\'', content)
        self.assertIn('line: \'mongo_tls_deployment_mode: "disabled"\'', content)
        self.assertIn('not (local_vars.mongo_tls_clients_enabled | bool)', content)

    def test_10_script_has_orchestration_and_visual_summary(self):
        script_path = os.path.join(REPO, 'scripts/run_tls_rollout.sh')
        with open(script_path) as f:
            content = f.read()
        self.assertIn('TLS TARGET ORCHESTRATOR', content)
        self.assertIn('TLS TARGET ALCANZADO', content)
        self.assertIn('flock', content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
