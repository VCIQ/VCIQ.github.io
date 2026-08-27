import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "internal-company-candidate-review.yml"


class CompanyCandidateReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_is_manual_dispatch_only_and_allowlisted(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("config/tracking_admins.json", self.text)
        self.assertIn('test "$ACTUAL_REF" = "refs/heads/main"', self.text)
        self.assertIn('test "$ACTUAL_EVENT" = "workflow_dispatch"', self.text)

    def test_supports_only_governed_final_actions_and_batch_input(self):
        self.assertIn("options: [accepted, rejected, merged]", self.text)
        self.assertIn("decisions_json:", self.text)
        self.assertIn("tools/company_candidate_review_decision.py", self.text)
        self.assertIn("tools/company_candidate_review_batch.py", self.text)
        self.assertIn("--mode validate", self.text)
        self.assertIn("--mode apply", self.text)

    def test_candidate_fingerprint_replaces_repository_snapshot_lock(self):
        self.assertIn("candidate_fingerprint:", self.text)
        self.assertIn("CANDIDATE_FINGERPRINT", self.text)
        self.assertIn("candidateFingerprint", self.text)
        self.assertNotIn("EXPECTED_REVISION", self.text)
        self.assertNotIn("expected_revision", self.text)
        self.assertIn('test "$(git rev-parse origin/main)" = "$BASE_SHA"', self.text)
        self.assertIn("main advanced during the short writer section", self.text)

    def test_shared_writer_queue_and_narrow_commit_allowlist(self):
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", self.text)
        self.assertIn("config/company_candidate_decisions.json", self.text)
        self.assertIn("config/company_candidate_review_queue.json", self.text)
        self.assertNotIn("git push --force", self.text)
        self.assertNotIn("git pull --rebase", self.text)

    def test_only_accept_or_merge_hands_off_to_onboarding(self):
        self.assertIn("requires_onboarding", self.text)
        self.assertIn("company-candidate-onboarding.yml", self.text)
        self.assertIn("needs.apply.outputs.requires_onboarding == 'true'", self.text)

    def test_public_audit_note_warning_is_explicit(self):
        self.assertIn("PUBLIC audit note", self.text)
        self.assertIn("not confidential", self.text)


if __name__ == "__main__":
    unittest.main()
