import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "internal-innovation-listing-candidate-review.yml"


class InnovationListingCandidateReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_is_manual_dispatch_only_and_allowlisted(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("config/tracking_admins.json", self.text)
        self.assertIn('test "$ACTUAL_REF" = "refs/heads/main"', self.text)
        self.assertIn('test "$ACTUAL_EVENT" = "workflow_dispatch"', self.text)

    def test_only_accept_and_reject_are_human_decisions(self):
        self.assertIn("options: [accepted, rejected]", self.text)
        self.assertNotIn("options: [accepted, rejected, merged]", self.text)
        self.assertIn("candidate_fingerprint:", self.text)
        self.assertIn("CANDIDATE_FINGERPRINT", self.text)

    def test_shared_writer_queue_and_narrow_file_allowlist(self):
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", self.text)
        self.assertIn("config/innovation_listing_candidate_decisions.json", self.text)
        self.assertIn("config/innovation_listing_candidate_review_queue.json", self.text)
        self.assertNotIn("config/innovation_listing_watchlist.json \\", self.text)
        self.assertNotIn("git push --force", self.text)
        self.assertNotIn("git pull --rebase", self.text)

    def test_acceptance_is_final_human_review_but_not_fact_bypass(self):
        self.assertIn("This human decision is final", self.text)
        self.assertIn("mechanical evidence gates", self.text)
        self.assertIn("no second human approval is required", self.text)
        self.assertIn("tools/innovation_listing_candidate_review.py", self.text)
        self.assertIn("tools/build_innovation_listing_candidates.py", self.text)

    def test_public_audit_warning_is_explicit(self):
        self.assertIn("not confidential", self.text)


if __name__ == "__main__":
    unittest.main()
