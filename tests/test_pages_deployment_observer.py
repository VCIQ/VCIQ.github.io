from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "observe-pages-deployment.yml"


class PagesDeploymentObserverWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_observer_is_diagnostic_only(self):
        self.assertIn("actions: read", self.source)
        self.assertNotIn("actions: write", self.source)
        self.assertNotIn("gh workflow run scheduled-sync.yml", self.source)
        self.assertNotIn("gh workflow run frequent-intelligence-refresh.yml", self.source)
        self.assertNotIn("gh workflow run company-candidate-discovery.yml", self.source)

    def test_observer_distinguishes_workflow_success_from_real_deployment(self):
        self.assertIn("workflowName,jobs", self.source)
        self.assertIn('select(.name == "deploy")', self.source)
        self.assertIn('deployment_status="deferred"', self.source)
        self.assertIn("deploymentStatus", self.source)
        self.assertIn("deployConclusion", self.source)

    def test_observer_records_stale_tracking_and_entity_defer_reasons(self):
        self.assertIn(
            "tracking configuration is newer than the article snapshot",
            self.source,
        )
        self.assertIn('deferred_reason="tracking_snapshot_refresh"', self.source)
        self.assertIn(
            "entity resolution reconciliation is not at a fixed point",
            self.source,
        )
        self.assertIn('deferred_reason="entity_reconciliation"', self.source)


if __name__ == "__main__":
    unittest.main()
