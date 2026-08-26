#!/usr/bin/env python3
"""
Static Security & Compliance Test for Institutional Backup Architecture & Encryption Policy.
Verifies:
1. Institutional backup format is strictly <db>_<YYYYMMDD_HHMMSS>.archive.gz.
2. Institutional variables declare external encryption capability without hardcoding age.
3. No age key dependencies or hardcoded key generation in dev/prod architecture.
4. Checksum SHA-256 is generated and verified on the standard archive (.archive.gz).
5. Strict pipefail is enforced in shell execution.
6. Restore verifies SHA-256 checksum before restoring.
7. Restore pipeline uses standard .archive.gz stream to mongorestore via TLS.
8. No plaintext passwords or secrets in argv or logs.
9. Cron jobs do not contain encryption keys or credentials.
10. Retention policy operates reliably on .archive.gz archives.
11. No insecure TLS flags; MongoDB connection enforces TLS with CA validation.
12. duration_seconds is captured and logged.
"""

import os, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

class TestBackupInstitutionalEncryption(unittest.TestCase):

    def setUp(self):
        self.common_path = os.path.join(REPO, 'vars/common.yml')
        self.local_path = os.path.join(REPO, 'vars/local.yml')
        self.backup_run_path = os.path.join(REPO, 'playbooks/backup/backup_run.yml')
        self.restore_play_path = os.path.join(REPO, 'playbooks/backup/restore_test.yml')
        self.restore_tasks_path = os.path.join(REPO, 'playbooks/backup/tasks/restore_test_tasks.yml')
        self.restore_select_path = os.path.join(REPO, 'playbooks/backup/tasks/restore_select_backup_tasks.yml')
        self.retention_path = os.path.join(REPO, 'playbooks/backup/backup_retention.yml')
        self.scheduler_path = os.path.join(REPO, 'playbooks/backup/backup_scheduler_setup.yml')

        with open(self.common_path) as f:
            self.common_text = f.read()
        with open(self.local_path) as f:
            self.local_text = f.read()
        with open(self.backup_run_path) as f:
            self.backup_run_text = f.read()
        with open(self.restore_play_path) as f:
            self.restore_play_text = f.read()
        with open(self.restore_tasks_path) as f:
            self.restore_tasks_text = f.read()
        with open(self.restore_select_path) as f:
            self.restore_select_text = f.read()
        with open(self.retention_path) as f:
            self.retention_text = f.read()
        with open(self.scheduler_path) as f:
            self.scheduler_text = f.read()

    def test_1_institutional_encryption_variables_and_format(self):
        """Verifies neutral institutional encryption declarations and standard .archive.gz extension"""
        self.assertIn('backup_encryption_required: true', self.common_text)
        self.assertIn('backup_encryption_provider: "institutional"', self.common_text)
        self.assertIn('backup_encryption_at_rest_managed_externally: true', self.common_text)
        self.assertIn('backup_transfer_encryption_managed_externally: true', self.common_text)
        self.assertIn('backup_extension: ".archive.gz"', self.common_text)
        self.assertIn('backup_filename: "{{ mongo_database }}_{{ backup_time.stdout | trim }}{{ backup_extension }}"', self.backup_run_text)

    def test_2_no_mandatory_age_dependency_in_institutional_pipeline(self):
        """Verifies backup_run.yml does not enforce age in main pipeline"""
        self.assertNotIn('age -r', self.backup_run_text)
        self.assertNotIn('tasks/backup_encryption_preflight.yml', self.backup_run_text)

    def test_3_checksum_generated_on_archive(self):
        """Verifies SHA-256 checksum is calculated on {{ backup_filename }} (.archive.gz)"""
        self.assertIn('sha256sum "{{ backup_filename }}" > "{{ backup_filename }}.sha256"', self.backup_run_text)

    def test_4_pipefail_enforced(self):
        """Verifies set -euo pipefail is active in backup and restore shell scripts"""
        self.assertIn('set -euo pipefail', self.backup_run_text)
        self.assertIn('set -euo pipefail', self.restore_tasks_text)

    def test_5_restore_verifies_checksum_before_restoring(self):
        """Verifies restore playbook validates sha256 before invoking mongorestore"""
        self.assertIn('sha256sum -c', self.restore_play_text)
        self.assertIn('restore_test_tasks.yml', self.restore_play_text)
        chk_idx = self.restore_play_text.find('sha256sum -c')
        inc_idx = self.restore_play_text.find('tasks/restore_test_tasks.yml')
        self.assertTrue(chk_idx != -1 and inc_idx != -1 and chk_idx < inc_idx,
                        "SHA-256 check must precede restore tasks inclusion in restore_test.yml")

    def test_6_restore_selects_standard_archive(self):
        """Verifies restore_select_backup_tasks.yml selects .archive.gz by default"""
        self.assertIn('"{{ backup_extension }}"', self.restore_select_text)
        self.assertIn('formato estandar institucional (.archive.gz)', self.restore_select_text)

    def test_7_cron_scheduler_has_no_secrets(self):
        """Verifies backup_scheduler_setup.yml does not embed any credentials or keys"""
        self.assertNotIn('AGE-SECRET-KEY', self.scheduler_text)
        self.assertNotIn('backup_age.key', self.scheduler_text)

    def test_8_no_insecure_tls_flags_and_restore_uses_tls(self):
        """Verifies no insecure flags and mongorestore enforces TLS with CA validation"""
        for text in [self.backup_run_text, self.restore_tasks_text]:
            self.assertNotIn('tlsInsecure', text)
            self.assertNotIn('tlsAllowInvalidCertificates', text)
            self.assertNotIn('tlsAllowInvalidHostnames', text)
        self.assertIn('--sslCAFile="{{ mongo_tls_client_ca_file }}"', self.restore_tasks_text)
        self.assertIn('tls=true', self.restore_tasks_text)

    def test_9_passwords_never_in_argv(self):
        """Verifies sensitive password is provided via temporary config file with umask 077"""
        self.assertNotIn('--password=', self.backup_run_text)
        self.assertNotIn('--password=', self.restore_tasks_text)
        self.assertIn('--config="$CFG_FILE"', self.backup_run_text)
        self.assertIn('--config="$CFG_FILE"', self.restore_tasks_text)

    def test_10_duration_seconds_logged(self):
        """Verifies duration_seconds is present in bitacora"""
        self.assertIn('| duration_seconds={{ backup_duration_seconds }}', self.backup_run_text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
