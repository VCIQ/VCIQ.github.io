from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "manual-tracking-ignore.yml"


class ManualTrackingIgnoreWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_is_manual_dispatch_only_and_has_validate_apply_split(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertIn("options: [validate, apply]", self.text)
        self.assertIn("if: inputs.operation == 'validate'", self.text)
        self.assertIn("if: inputs.operation == 'apply'", self.text)

    def test_apply_alone_has_repository_write_permission(self):
        apply_job = self.text.split("  apply:\n", 1)[1]
        validate_job = self.text.split("  validate:\n", 1)[1].split("  apply:\n", 1)[0]
        self.assertIn("permissions:\n      contents: write", apply_job)
        self.assertIn("permissions:\n      contents: read", validate_job)
        self.assertIn("environment: tracking-admin", apply_job)
        self.assertIn("environment: tracking-admin", validate_job)

    def test_rejection_commits_only_the_three_approved_governance_files(self):
        self.assertIn("tools/manual_tracking_ignore.py", self.text)
        self.assertIn("config/tracking_intents.json", self.text)
        self.assertIn("config/user_tracking.json", self.text)
        self.assertIn("config/tracking_auto_discovery.json", self.text)
        self.assertNotIn("git add .", self.text)
        self.assertNotIn("git add -A", self.text)
        self.assertIn("refusing to rebase, force, or overwrite", self.text)

    def test_changed_configuration_reuses_existing_governance_gates(self):
        self.assertIn("tests.test_manual_tracking_ignore", self.text)
        self.assertIn("tests.test_tracking_manual_feedback", self.text)
        self.assertIn("tests.test_expand_tracking_entities", self.text)
        self.assertIn("npm run validate:tracking", self.text)
        self.assertIn("npm run validate:taxonomy", self.text)
        self.assertIn("tracking_source_governance.py --check", self.text)

    def test_writer_lock_is_fifo_and_never_coalesced(self):
        apply_job = self.text.split("  apply:\n", 1)[1]
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", apply_job)
        self.assertIn("queue: max", apply_job)
        self.assertNotIn("queue: single", apply_job)


if __name__ == "__main__":
    unittest.main()
