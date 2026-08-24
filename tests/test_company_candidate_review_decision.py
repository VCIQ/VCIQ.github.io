import unittest
from datetime import UTC, datetime

from tools.company_candidate_review_decision import (
    ReviewDecisionError,
    apply_review_decision,
    validate_review_request,
)


class CompanyCandidateReviewDecisionTests(unittest.TestCase):
    def setUp(self):
        self.candidates = {
            "schemaVersion": 1,
            "candidates": [
                {
                    "id": "candidate-acme",
                    "decisionKey": "acme",
                    "name": "Acme AI",
                    "status": "pending",
                    "score": 82,
                }
            ],
        }
        self.decisions = {"schemaVersion": 1, "decisions": {}}
        self.registry = {
            "schemaVersion": 1,
            "companies": [{"slug": "existing-co", "name": "Existing Co"}],
        }
        self.now = datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
        self.revision = "a" * 40

    def request(self, **overrides):
        values = {
            "candidate_key": "acme",
            "action": "accepted",
            "note": "证据充分，进入受控建档流程",
            "merged_slug": "",
            "reviewed_by": "VCIQ/tracking-console",
            "expected_revision": self.revision,
        }
        values.update(overrides)
        return validate_review_request(**values)

    def test_accept_pending_candidate(self):
        updated, report = apply_review_decision(
            self.candidates,
            self.decisions,
            self.registry,
            self.request(),
            now=self.now,
        )
        decision = updated["decisions"]["acme"]
        self.assertTrue(report["changed"])
        self.assertTrue(report["requiresOnboarding"])
        self.assertEqual(decision["status"], "accepted")
        self.assertEqual(decision["reviewedBy"], "VCIQ/tracking-console")
        self.assertEqual(decision["decidedAt"], "2026-08-24T07:00:00+00:00")

    def test_reject_does_not_require_onboarding(self):
        updated, report = apply_review_decision(
            self.candidates,
            self.decisions,
            self.registry,
            self.request(action="rejected", note="名称为抽取粘连，不是单一公司"),
            now=self.now,
        )
        self.assertEqual(updated["decisions"]["acme"]["status"], "rejected")
        self.assertFalse(report["requiresOnboarding"])

    def test_merge_requires_existing_registry_slug(self):
        with self.assertRaisesRegex(ReviewDecisionError, "merge target does not exist"):
            apply_review_decision(
                self.candidates,
                self.decisions,
                self.registry,
                self.request(action="merged", merged_slug="missing-co", note="与现有公司重复"),
                now=self.now,
            )

        updated, report = apply_review_decision(
            self.candidates,
            self.decisions,
            self.registry,
            self.request(action="merged", merged_slug="existing-co", note="与现有公司为同一主体"),
            now=self.now,
        )
        self.assertEqual(updated["decisions"]["acme"]["mergedSlug"], "existing-co")
        self.assertTrue(report["requiresOnboarding"])

    def test_final_decision_is_immutable(self):
        existing = {
            "schemaVersion": 1,
            "decisions": {
                "acme": {
                    "status": "rejected",
                    "note": "已审核",
                    "mergedSlug": "",
                    "decidedAt": "2026-08-20T00:00:00Z",
                    "reviewedBy": "VCIQ",
                }
            },
        }
        with self.assertRaisesRegex(ReviewDecisionError, "final decision rejected"):
            apply_review_decision(
                self.candidates,
                existing,
                self.registry,
                self.request(action="accepted"),
                now=self.now,
            )

    def test_same_final_decision_is_idempotent(self):
        existing = {
            "schemaVersion": 1,
            "decisions": {
                "acme": {
                    "status": "accepted",
                    "note": "已审核",
                    "mergedSlug": "",
                    "decidedAt": "2026-08-20T00:00:00Z",
                    "reviewedBy": "VCIQ",
                }
            },
        }
        updated, report = apply_review_decision(
            self.candidates,
            existing,
            self.registry,
            self.request(action="accepted"),
            now=self.now,
        )
        self.assertFalse(report["changed"])
        self.assertEqual(updated, existing)

    def test_non_pending_candidate_is_rejected(self):
        candidates = {
            "schemaVersion": 1,
            "candidates": [{"decisionKey": "acme", "name": "Acme AI", "status": "accepted"}],
        }
        with self.assertRaisesRegex(ReviewDecisionError, "no longer pending"):
            apply_review_decision(candidates, self.decisions, self.registry, self.request(), now=self.now)

    def test_public_actor_must_not_be_email(self):
        with self.assertRaisesRegex(ReviewDecisionError, "not an email"):
            self.request(reviewed_by="operator@example.com")

    def test_expected_revision_must_be_full_sha(self):
        with self.assertRaisesRegex(ReviewDecisionError, "full git SHA"):
            self.request(expected_revision="abc123")

    def test_note_is_required(self):
        with self.assertRaisesRegex(ReviewDecisionError, "public review note"):
            self.request(note="")


if __name__ == "__main__":
    unittest.main()
