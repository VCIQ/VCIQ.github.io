from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/innovation-investor-reviewed-release.yml"
SCOUT = ROOT / ".github/workflows/innovation-investor-source-scout.yml"


class InvestorReleaseWorkflowTests(unittest.TestCase):
    def test_human_gate_and_original_artifact_bound(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn('environment: tracking-admin', text)
        self.assertIn('config/tracking_admins.json', text)
        self.assertIn('github.triggering_actor', text)
        self.assertIn('innovation-investor-source-scout.yml', text)
        self.assertIn('run.get("conclusion") != "success"', text)
        self.assertIn('run.get("head_branch") != "main"', text)
        self.assertIn('run.get("event") == "pull_request"', text)
        self.assertIn('--review-queue /tmp/investor-source-review/innovation-investor-review-queue.json', text)
        self.assertIn('--mode validate', text)

    def test_propose_is_a_draft_pr_not_a_second_news_writer(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('--mode apply', text)
        self.assertIn('npm run build:pages', text)
        self.assertIn('tests/homepage-investor-publication.test.ts', text)
        self.assertIn('git add -- config/innovation_investor_evidence.json', text)
        self.assertIn('config/innovation_investor_project_identities.json', text)
        self.assertIn('gh pr create', text)
        self.assertIn('--draft', text)
        self.assertNotIn('git push origin HEAD:main', text)
        self.assertNotIn('gh pr merge', text)
        self.assertNotIn('schedule:', text)
        # The isolated local development checkout predates the production scout;
        # the current main-branch PR additionally checks its read-only contract.
        if SCOUT.exists():
            scout = SCOUT.read_text(encoding="utf-8")
            self.assertIn('contents: read', scout)
            self.assertIn('permissions:', scout)


if __name__ == "__main__":
    unittest.main()
