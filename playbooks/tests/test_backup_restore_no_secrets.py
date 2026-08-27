#!/usr/bin/env python3
"""
Static Security Test for MongoDB Backup & Restore Runners
Verifies:
1. No --password="$MONGO_ in runner mongodump/mongorestore commands
2. No --password={{ in runner mongodump/mongorestore commands
3. No --password flag in mongodump / mongorestore runner argv
4. No URI containing credentials (user:password@) in runner invocations
5. --config is used with temporary config file for sensitive parameters
6. Sensitive tasks have no_log: true
7. Proper umask 077, chmod 0600, and trap cleanup are in place
"""

import os, re, sys, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

class TestRunnerSecurity(unittest.TestCase):

    def setUp(self):
        self.backup_run_path = os.path.join(REPO, 'playbooks/backup/backup_run.yml')
        self.restore_tasks_path = os.path.join(REPO, 'playbooks/backup/tasks/restore_test_tasks.yml')
        
        with open(self.backup_run_path) as f:
            self.backup_run_text = f.read()
            
        with open(self.restore_tasks_path) as f:
            self.restore_tasks_text = f.read()

    def _extract_mongodump_cmd(self):
        # Extract lines starting with mongodump up to register or next YAML key
        m = re.search(r'mongodump\s*\\?\s*\n.*?(?=\n\s*(?:environment|register|rescue|always|\- name):)', self.backup_run_text, re.DOTALL)
        return m.group(0) if m else ""

    def _extract_mongorestore_cmd(self):
        # Extract lines starting with mongorestore up to register or next YAML key
        m = re.search(r'mongorestore\s*\\?\s*\n.*?(?=\n\s*(?:environment|register|rescue|always|\- name):)', self.restore_tasks_text, re.DOTALL)
        return m.group(0) if m else ""

    def test_no_password_env_expansion_in_runners(self):
        """Fails if --password=\"$MONGO_ is found in mongodump or mongorestore"""
        self.assertNotIn('--password="$MONGO_BACKUP_PASSWORD"', self.backup_run_text,
            "Found --password=\"$MONGO_BACKUP_PASSWORD in backup_run.yml!")
        self.assertNotIn('--password="$MONGO_RESTORE_PASSWORD"', self.restore_tasks_text,
            "Found --password=\"$MONGO_RESTORE_PASSWORD in restore_test_tasks.yml!")

    def test_no_password_template_in_runners(self):
        """Fails if --password={{ is found in backup_run.yml or restore_test_tasks.yml"""
        self.assertNotIn('--password={{ mongo_backup_password }}', self.backup_run_text)
        self.assertNotIn('--password={{ mongo_restore_password }}', self.restore_tasks_text)
        self.assertNotIn('--password "{{ mongo_backup_password }}"', self.backup_run_text)
        self.assertNotIn('--password "{{ mongo_restore_password }}"', self.restore_tasks_text)

    def test_no_password_flag_in_mongodump_and_mongorestore_argv(self):
        """Ensures mongodump and mongorestore invocations do not include any --password flag"""
        dump_cmd = self._extract_mongodump_cmd()
        restore_cmd = self._extract_mongorestore_cmd()
        
        self.assertTrue(len(dump_cmd) > 0, "Could not locate mongodump command block")
        self.assertTrue(len(restore_cmd) > 0, "Could not locate mongorestore command block")
        
        self.assertNotIn('--password', dump_cmd, "mongodump command contains --password flag in argv!")
        self.assertNotIn('-p ', dump_cmd, "mongodump command contains -p flag in argv!")
        self.assertNotIn('--password', restore_cmd, "mongorestore command contains --password flag in argv!")
        self.assertNotIn('-p ', restore_cmd, "mongorestore command contains -p flag in argv!")

    def test_no_embedded_credentials_in_uri(self):
        """Fails if mongodb://.*:.*@ is found in runner invocations"""
        pattern = re.compile(r'mongodb://(?!\[REDACTED\])[^/\s]+:[^@\s]+@', re.IGNORECASE)
        self.assertFalse(pattern.search(self.backup_run_text),
            "Found embedded user:password credentials in URI in backup_run.yml!")
        self.assertFalse(pattern.search(self.restore_tasks_text),
            "Found embedded user:password credentials in URI in restore_test_tasks.yml!")

    def test_config_flag_used_in_backup_and_restore(self):
        """Ensures --config is present in mongodump and mongorestore calls"""
        self.assertIn('--config="$CFG_FILE"', self.backup_run_text,
            "backup_run.yml must use --config=\"$CFG_FILE\" for mongodump")
        self.assertIn('--config="$CFG_FILE"', self.restore_tasks_text,
            "restore_test_tasks.yml must use --config=\"$CFG_FILE\" for mongorestore")

    def test_umask_and_chmod_on_temp_config(self):
        """Ensures umask 077 and chmod 0600 are used to protect temp config file"""
        self.assertIn('umask 077', self.backup_run_text)
        self.assertIn('chmod 0600 "$CFG_FILE"', self.backup_run_text)
        self.assertIn('umask 077', self.restore_tasks_text)
        self.assertIn('chmod 0600 "$CFG_FILE"', self.restore_tasks_text)

    def test_trap_cleanup_present(self):
        """Ensures trap cleanup is present to delete temp config file on exit"""
        self.assertIn('trap \'rm -f "$CFG_FILE"\' EXIT INT TERM', self.backup_run_text)
        self.assertIn('trap \'rm -f "$CFG_FILE"\' EXIT INT TERM', self.restore_tasks_text)

    def test_no_log_is_true(self):
        """Ensures sensitive tasks have no_log: true"""
        self.assertIn('no_log: true', self.backup_run_text)
        self.assertIn('no_log: true', self.restore_tasks_text)



    def test_ssl_ca_file_in_database_tools(self):
        """Ensures mongodump and mongorestore use --sslCAFile flag for Database Tools 100.18.0"""
        self.assertIn('--sslCAFile', self.backup_run_text, "backup_run.yml must use --sslCAFile")
        self.assertIn('--sslCAFile', self.restore_tasks_text, "restore_test_tasks.yml must use --sslCAFile")


    def test_auth_database_coherence_between_users_and_runners(self):
        """Ensures mongo_backup_auth_database is used consistently in backup_run.yml"""
        self.assertIn('mongo_backup_auth_database', self.backup_run_text,
            "backup_run.yml must reference mongo_backup_auth_database")
        self.assertIn('mongo_restore_auth_database', self.restore_tasks_text,
            "restore_test_tasks.yml must reference mongo_restore_auth_database")

    def test_preflight_authentication_check_in_backup_run(self):
        """Ensures preflight authentication check exists in backup_run.yml"""
        self.assertIn('Preflight — Validar autenticacion', self.backup_run_text,
            "backup_run.yml must contain a preflight authentication check task")
        self.assertIn('BACKUP_AUTHENTICATION_FAILED', self.backup_run_text,
            "backup_run.yml preflight must fail with BACKUP_AUTHENTICATION_FAILED")

if __name__ == '__main__':
    unittest.main(verbosity=2)
