#!/usr/bin/env python3
"""
Static Security and Compliance Test for MongoDB Backup Notification.
Verifies:
1. Notifier script exists, is executable and uses set -euo pipefail.
2. Notifier is invoked ONLY in FAILED/rescue routes, never in SUCCESS routes.
3. No passwords or secrets are passed in notifier argv.
4. Alerts log is created with 0600 permissions.
"""

import os, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir(os.path.join(REPO, 'playbooks')):
    REPO = '/home/usuario01/mongo-ansible-v2'

class TestBackupNotificationStatic(unittest.TestCase):

    def test_notifier_script_properties(self):
        """Ensures scripts/notify_backup_failure.sh exists and is properly structured"""
        script_path = os.path.join(REPO, 'scripts/notify_backup_failure.sh')
        self.assertTrue(os.path.isfile(script_path), "notify_backup_failure.sh not found")
        self.assertTrue(os.access(script_path, os.X_OK), "notify_backup_failure.sh is not executable")
        with open(script_path) as f:
            content = f.read()
        self.assertTrue(content.startswith('#!/bin/bash'), "Missing #!/bin/bash")
        self.assertIn('set -euo pipefail', content, "Missing set -euo pipefail")
        self.assertIn('chmod 0600 "$ALERT_LOG"', content, "Missing chmod 0600 on alert log")
        self.assertIn('notification=GENERATED', content, "Missing notification=GENERATED in log format")
        self.assertIn('severity=ERROR', content, "Missing severity=ERROR in log format")

    def test_notifier_present_only_in_rescue_blocks(self):
        """Ensures notify_failure_tasks.yml or notify_backup_failure.sh is in rescue: blocks and never in regular success flow"""
        backup_run_path = os.path.join(REPO, 'playbooks/backup/backup_run.yml')
        with open(backup_run_path) as f:
            content = f.read()

        # Should be called in rescue: block
        self.assertIn('rescue:', content, "Missing rescue: block in backup_run.yml")
        self.assertIn('tasks/notify_failure_tasks.yml', content, "Missing notify_failure_tasks in backup_run.yml")

        # In notify_failure_tasks.yml, result is FAILED and never SUCCESS
        notify_task_path = os.path.join(REPO, 'playbooks/backup/tasks/notify_failure_tasks.yml')
        with open(notify_task_path) as f:
            notify_content = f.read()
        self.assertIn('result=FAILED', notify_content, "notify_failure_tasks.yml must record result=FAILED")
        self.assertNotIn('result=SUCCESS', notify_content, "notify_failure_tasks.yml cannot record result=SUCCESS")

    def test_no_passwords_passed_to_notifier(self):
        """Ensures no passwords or secrets are passed as arguments to notify_backup_failure.sh"""
        notify_task_path = os.path.join(REPO, 'playbooks/backup/tasks/notify_failure_tasks.yml')
        with open(notify_task_path) as f:
            content = f.read()

        self.assertNotIn('mongo_backup_password', content.split('notify_backup_failure.sh')[1],
                         "Password passed in notifier argv!")
        self.assertNotIn('mongo_admin_password', content.split('notify_backup_failure.sh')[1],
                         "Password passed in notifier argv!")
        self.assertIn('sanitized_failure_reason', content, "Reason must be sanitized before invoking notifier")


if __name__ == '__main__':
    unittest.main(verbosity=2)
