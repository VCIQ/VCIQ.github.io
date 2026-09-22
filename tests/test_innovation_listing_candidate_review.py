import unittest
from datetime import UTC, datetime

from tools.innovation_listing_candidate_review import (
    InnovationListingReviewError,
    apply_decision,
    validate_request,
)


class InnovationListingCandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "id": "innovation-listing-test",
            "decisionKey": "新锐量子科技股份有限公司|中信证券",
            "candidateFingerprint": "a" * 64,
            "company": "新锐量子科技股份有限公司",
            "broker": "中信证券",
            "status": "pending",
            "evidenceClass": "discovery-only",
        }
        self.queue = {"schemaVersion": 1, "candidates": [self.candidate]}
        self.decisions = {"schemaVersion": 1, "decisions": {}}
        self.now = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)

    def request(self, **overrides):
        values = {
            "candidate_key": self.candidate["decisionKey"],
            "candidate_fingerprint": self.candidate["candidateFingerprint"],
            "decision": "accepted",
            "note": "人工核对公司与辅导券商关系成立。",
            "reviewed_by": "VCIQ/tracking-console",
        }
        values.update(overrides)
        return validate_request(**values)

    def test_accept_is_final_human_decision_and_waits_only_for_mechanical_evidence(self):
        updated, report = apply_decision(
            self.queue,
            self.decisions,
            self.request(),
            now=self.now,
        )
        row = updated["decisions"][self.candidate["decisionKey"]]
        self.assertTrue(report["changed"])
        self.assertEqual(row["status"], "accepted")
        self.assertEqual(row["promotionStatus"], "awaiting-primary-evidence")
        self.assertEqual(row["candidateFingerprint"], "a" * 64)
        self.assertEqual(row["decidedAt"], "2026-09-22T11:00:00+00:00")
        self.assertIn("only mechanical evidence gates remain", report["message"])

    def test_primary_backed_accept_is_ready_for_mechanical_promotion(self):
        queue = {
            "candidates": [
                {**self.candidate, "evidenceClass": "primary-backed"}
            ]
        }
        updated, report = apply_decision(
            queue,
            self.decisions,
            self.request(),
            now=self.now,
        )
        self.assertEqual(
            updated["decisions"][self.candidate["decisionKey"]]["promotionStatus"],
            "ready-for-mechanical-promotion",
        )
        self.assertEqual(report["promotionStatus"], "ready-for-mechanical-promotion")

    def test_reject_is_sticky(self):
        request = self.request(decision="rejected", note="人工确认误匹配。")
        updated, report = apply_decision(
            self.queue,
            self.decisions,
            request,
            now=self.now,
        )
        self.assertEqual(report["promotionStatus"], "rejected")
        self.assertEqual(
            updated["decisions"][self.candidate["decisionKey"]]["status"],
            "rejected",
        )

    def test_stale_fingerprint_fails_closed(self):
        with self.assertRaisesRegex(InnovationListingReviewError, "evidence changed"):
            apply_decision(
                self.queue,
                self.decisions,
                self.request(candidate_fingerprint="b" * 64),
                now=self.now,
            )

    def test_final_decision_cannot_be_changed(self):
        accepted = {
            "schemaVersion": 1,
            "decisions": {
                self.candidate["decisionKey"]: {
                    "status": "accepted",
                    "candidateFingerprint": "a" * 64,
                    "promotionStatus": "awaiting-primary-evidence",
                }
            },
        }
        reviewed_queue = {
            "candidates": [{**self.candidate, "status": "accepted"}]
        }
        with self.assertRaisesRegex(InnovationListingReviewError, "no longer pending"):
            apply_decision(
                reviewed_queue,
                accepted,
                self.request(decision="rejected"),
                now=self.now,
            )

    def test_exact_retry_is_idempotent(self):
        accepted = {
            "schemaVersion": 1,
            "decisions": {
                self.candidate["decisionKey"]: {
                    "status": "accepted",
                    "candidateFingerprint": "a" * 64,
                    "promotionStatus": "awaiting-primary-evidence",
                }
            },
        }
        reviewed_queue = {
            "candidates": [{**self.candidate, "status": "accepted"}]
        }
        _updated, report = apply_decision(
            reviewed_queue,
            accepted,
            self.request(),
            now=self.now,
        )
        self.assertFalse(report["changed"])
        self.assertIn("already has", report["message"])

    def test_public_actor_must_not_be_email(self):
        with self.assertRaisesRegex(InnovationListingReviewError, "not an email"):
            self.request(reviewed_by="private@example.com")


if __name__ == "__main__":
    unittest.main()
