import unittest
from datetime import UTC, datetime

from tools.company_candidate_review_batch import apply_batch
from tools.company_candidate_review_decision import (
    ReviewDecisionError,
    candidate_review_fingerprint,
    validate_review_request,
)


class CompanyCandidateReviewBatchTests(unittest.TestCase):
    def setUp(self):
        self.pending = {
            "decisionKey": "nova",
            "name": "Nova AI",
            "status": "pending",
            "score": 80,
            "articleCount": 2,
            "sourceCount": 2,
            "sourceArticleIds": ["a", "b"],
            "sourceUrls": ["https://news.example/a", "https://news.example/b"],
        }
        self.accepted = {
            "decisionKey": "acme",
            "name": "Acme AI",
            "status": "accepted",
            "score": 75,
            "articleCount": 1,
            "sourceCount": 1,
            "sourceArticleIds": ["c"],
            "sourceUrls": ["https://news.example/c"],
        }
        self.candidates = {"candidates": [self.pending, self.accepted]}
        self.decisions = {
            "schemaVersion": 1,
            "decisions": {
                "acme": {
                    "status": "accepted",
                    "note": "人工确认是公司",
                    "mergedSlug": "",
                    "decidedAt": "2026-08-20T00:00:00Z",
                    "reviewedBy": "VCIQ",
                }
            },
        }
        self.registry = {"companies": []}
        self.now = datetime(2026, 8, 26, 7, 0, tzinfo=UTC)

    def request(self, candidate, **overrides):
        values = {
            "candidate_key": candidate["decisionKey"],
            "action": "accepted",
            "note": "",
            "merged_slug": "",
            "reviewed_by": "VCIQ/tracking-console",
            "candidate_fingerprint": candidate_review_fingerprint(candidate),
            "homepage_hint": "",
        }
        values.update(overrides)
        return validate_review_request(**values)

    def test_pending_review_and_accepted_homepage_hint_can_share_one_batch(self):
        updated, report = apply_batch(
            self.candidates,
            self.decisions,
            self.registry,
            [
                self.request(self.pending),
                self.request(self.accepted, homepage_hint="https://acme.example/"),
            ],
            now=self.now,
        )
        self.assertEqual(report["changedCount"], 2)
        self.assertEqual(updated["decisions"]["nova"]["status"], "accepted")
        self.assertEqual(updated["decisions"]["acme"]["status"], "accepted")
        self.assertEqual(updated["decisions"]["acme"]["homepageHint"], "https://acme.example/")
        self.assertEqual(updated["decisions"]["acme"]["note"], "人工确认是公司")

    def test_repeated_accepted_identity_decision_is_idempotent(self):
        updated, report = apply_batch(
            self.candidates,
            self.decisions,
            self.registry,
            [self.request(self.accepted)],
            now=self.now,
        )
        self.assertFalse(report["changed"])
        self.assertEqual(report["changedCount"], 0)
        self.assertEqual(report["decisionCount"], 1)
        self.assertFalse(report["reports"][0]["changed"])
        self.assertIn("already has", report["reports"][0]["message"])
        self.assertEqual(updated["decisions"]["acme"]["status"], "accepted")
        self.assertEqual(updated["decisions"]["acme"]["decidedAt"], "2026-08-20T00:00:00Z")

    def test_duplicate_retry_does_not_abort_fresh_decision_in_same_batch(self):
        updated, report = apply_batch(
            self.candidates,
            self.decisions,
            self.registry,
            [self.request(self.pending), self.request(self.accepted)],
            now=self.now,
        )
        self.assertTrue(report["changed"])
        self.assertEqual(report["changedCount"], 1)
        self.assertEqual(report["decisionCount"], 2)
        self.assertTrue(report["requiresOnboarding"])
        self.assertEqual(updated["decisions"]["nova"]["status"], "accepted")
        self.assertFalse(report["reports"][1]["changed"])

    def test_homepage_hint_does_not_allow_changing_final_identity_decision(self):
        request = self.request(self.accepted, action="rejected")
        with self.assertRaisesRegex(ReviewDecisionError, "no longer eligible"):
            apply_batch(
                self.candidates,
                self.decisions,
                self.registry,
                [request],
                now=self.now,
            )

    def test_accepted_homepage_hint_remains_fingerprint_bound(self):
        request = self.request(
            self.accepted,
            homepage_hint="https://acme.example/",
            candidate_fingerprint="0" * 64,
        )
        with self.assertRaisesRegex(ReviewDecisionError, "evidence changed"):
            apply_batch(
                self.candidates,
                self.decisions,
                self.registry,
                [request],
                now=self.now,
            )


if __name__ == "__main__":
    unittest.main()
