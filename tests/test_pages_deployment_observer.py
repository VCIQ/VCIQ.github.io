from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "observe-pages-deployment.yml"


class PagesDeploymentObserverWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_observer_has_permission_to_recover_deferred_publication(self):
        self.assertIn("actions: write", self.source)

    def test_observer_distinguishes_workflow_success_from_real_deployment(self):
        self.assertIn("workflowName,jobs", self.source)
        self.assertIn('select(.name == \\"deploy\\")', self.source)
        self.assertIn('deployment_status=\"deferred\"', self.source)
        self.assertIn("deploymentStatus", self.source)
        self.assertIn("deployConclusion", self.source)

    def test_observer_recovers_stale_tracking_snapshot(self):
        self.assertIn(
            "tracking configuration is newer than the article snapshot",
            self.source,
        )
        self.assertIn('deferred_reason=\"tracking_snapshot_refresh\"', self.source)
        self.assertIn("gh workflow run scheduled-sync.yml", self.source)
        self.assertIn('--ref main', self.source)


if __name__ == "__main__":
    unittest.main()
