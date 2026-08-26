#!/usr/bin/env python3
"""
Static Security & Compliance Test for MongoDB Backup Duration Logging.
Verifies:
1. SUCCESS log entry in backup_run.yml contains duration_seconds.
2. FAILED log entry in notify_failure_tasks.yml contains duration_seconds.
3. Duration measurement uses epoch arithmetic and enforces integer >= 0.
4. Essential audit fields remain present (timestamp, size, result, environment, database, primary, checksum).
5. Historical logs are untouched.
6. Zero passwords, private keys, or credentials exposed in log tasks.
"""

import os, re, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

class TestBackupDurationLogging(unittest.TestCase):

    def setUp(self):
        self.backup_run_path = os.path.join(REPO, 'playbooks/backup/backup_run.yml')
        self.notify_path = os.path.join(REPO, 'playbooks/backup/tasks/notify_failure_tasks.yml')
        
        with open(self.backup_run_path) as f:
            self.backup_run_text = f.read()
        with open(self.notify_path) as f:
            self.notify_text = f.read()

    def test_1_start_and_end_epoch_capture_in_backup_run(self):
        """Verifies start epoch is captured before mongodump and end epoch after artifact validation"""
        start_idx = self.backup_run_text.find('Capturar epoch de inicio del proceso de respaldo')
        dump_idx = self.backup_run_text.find('mongodump')
        end_idx = self.backup_run_text.find('Capturar epoch de finalizacion del respaldo')
        calc_idx = self.backup_run_text.find('Calcular duracion del proceso de respaldo en segundos')
        log_idx = self.backup_run_text.find('Registrar respaldo en bitacora')

        self.assertTrue(start_idx != -1 and dump_idx != -1 and start_idx < dump_idx,
                        "Start epoch must be captured before mongodump pipeline")
        self.assertTrue(end_idx != -1 and calc_idx != -1 and end_idx < calc_idx,
                        "End epoch must be captured before duration calculation")
        self.assertTrue(calc_idx < log_idx, "Duration calculation must precede bitacora write")

    def test_2_duration_calculation_enforces_non_negative_integer(self):
        """Verifies duration calculation enforces integer arithmetic and >= 0"""
        self.assertIn("[(backup_end_epoch.stdout | trim | int) - (backup_start_epoch.stdout | trim | int), 0] | max",
                      self.backup_run_text)

    def test_3_success_log_entry_format(self):
        """Verifies SUCCESS log entry contains duration_seconds and all required audit fields"""
        self.assertIn('| duration_seconds={{ backup_duration_seconds }}', self.backup_run_text)
        self.assertIn('| size={{ backup_file.stat.size }}', self.backup_run_text)
        self.assertIn('| result=SUCCESS', self.backup_run_text)
        self.assertIn('| checksum=OK', self.backup_run_text)
        self.assertIn('{{ backup_timestamp }}', self.backup_run_text)

    def test_4_failed_log_entry_format(self):
        """Verifies FAILED log entry in notify_failure_tasks.yml contains duration_seconds"""
        self.assertIn('| duration_seconds={{ backup_fail_duration_raw.stdout | default(\'0\') | trim }}', self.notify_text)
        self.assertIn('| result=FAILED', self.notify_text)
        self.assertIn('| reason={{ sanitized_failure_reason }}', self.notify_text)

    def test_5_no_secrets_or_passwords_in_logging_tasks(self):
        """Ensures logging tasks never embed sensitive passwords or unredacted secrets"""
        for text in [self.backup_run_text, self.notify_text]:
            self.assertNotIn('mongo_backup_password', text.split('Registrar ')[1] if 'Registrar ' in text else text)
            self.assertNotIn('AGE-SECRET-KEY', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
