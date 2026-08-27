import unittest
from datetime import UTC, datetime

from tools.company_candidate_review_decision import (
    ReviewDecisionError,
    apply_review_decisions,
    candidate_review_fingerprint,
    validate_review_request,
    validate_review_requests,
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
                    "articleCount": 2,
                    "sourceCount": 2,
                    "sourceArticleIds": ["article-b", "article-a"],
                    "sourceUrls": ["https://example.com/b", "https://example.com/a"],
                },
                {
                    "id": "candidate-beta",
                    "decisionKey": "beta",
                    "name": "Beta Robotics",
                    "status": "pending",
                    "score": 76,
                    "articleCount": 1,
                    "sourceCount": 1,
                    "sourceArticleIds": ["article-c"],
                    "sourceUrls": ["https://example.com/c"],
                },
            ],
        }
        self.decisions = {"schemaVersion": 1, "decisions": {}}
        self.registry = {
            "schemaVersion": 1,
            "companies": [{"slug": "existing-co", "name": "Existing Co"}],
        }
        self.now = datetime(2026, 8, 24, 7, 0, tzinfo=UTC)

    def request(self, key="acme", **overrides):
        candidate = next(row for row in self.candidates["candidates"] if row["decisionKey"] == key)
        values = {
            "candidate_key": key,
            "action": "accepted",
            "note": "",
            "merged_slug": "",
            "reviewed_by": "VCIQ/tracking-console",
            "candidate_fingerprint": candidate_review_fingerprint(candidate),
            "homepage_hint": "",
        }
        values.update(overrides)
        return validate_review_request(**values)

    def apply(self, *requests):
        return apply_review_decisions(
            self.candidates,
            self.decisions,
            self.registry,
            list(requests),
            now=self.now,
        )

    def test_accept_pending_candidate_uses_default_audit_note(self):
        updated, report = self.apply(self.request())
        decision = updated["decisions"]["acme"]
        self.assertTrue(report["changed"])
        self.assertTrue(report["requiresOnboarding"])
        self.assertEqual(report["changedCount"], 1)
        self.assertEqual(decision["status"], "accepted")
        self.assertIn("人工确认", decision["note"])
        self.assertEqual(decision["reviewedBy"], "VCIQ/tracking-console")
        self.assertEqual(decision["decidedAt"], "2026-08-24T07:00:00+00:00")

    def test_candidate_fingerprint_is_evidence_specific_not_repository_specific(self):
        candidate = self.candidates["candidates"][0]
        first = candidate_review_fingerprint(candidate)
        reordered = dict(candidate)
        reordered["sourceUrls"] = list(reversed(candidate["sourceUrls"]))
        reordered["sourceArticleIds"] = list(reversed(candidate["sourceArticleIds"]))
        self.assertEqual(first, candidate_review_fingerprint(reordered))
        changed = dict(candidate)
        changed["articleCount"] = 3
        self.assertNotEqual(first, candidate_review_fingerprint(changed))

    def test_stale_candidate_fingerprint_rejects_only_that_review(self):
        with self.assertRaisesRegex(ReviewDecisionError, "evidence changed"):
            self.apply(self.request(candidate_fingerprint="0" * 64))

    def test_batch_accept_and_reject_are_atomic(self):
        updated, report = self.apply(
            self.request(),
            self.request("beta", action="rejected"),
        )
        self.assertEqual(report["decisionCount"], 2)
        self.assertEqual(report["changedCount"], 2)
        self.assertEqual(updated["decisions"]["acme"]["status"], "accepted")
        self.assertEqual(updated["decisions"]["beta"]["status"], "rejected")

    def test_batch_preflight_prevents_partial_write(self):
        with self.assertRaisesRegex(ReviewDecisionError, "evidence changed"):
            self.apply(
                self.request(),
                self.request("beta", candidate_fingerprint="0" * 64),
            )
        self.assertEqual(self.decisions, {"schemaVersion": 1, "decisions": {}})

    def test_merge_requires_existing_registry_slug(self):
        with self.assertRaisesRegex(ReviewDecisionError, "merge target"):
            self.apply(self.request(action="merged", merged_slug="missing-co"))

        updated, report = self.apply(
            self.request(action="merged", merged_slug="existing-co")
        )
        self.assertEqual(updated["decisions"]["acme"]["mergedSlug"], "existing-co")
        self.assertTrue(report["requiresOnboarding"])

    def test_optional_homepage_hint_is_stored_for_verification_not_publication(self):
        updated, _ = self.apply(
            self.request(homepage_hint="https://acme.example/about")
        )
        self.assertEqual(
            updated["decisions"]["acme"]["homepageHint"],
            "https://acme.example/about",
        )
        with self.assertRaisesRegex(ReviewDecisionError, "only valid for accepted"):
            self.request(action="rejected", homepage_hint="https://acme.example")

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
            apply_review_decisions(
                self.candidates,
                existing,
                self.registry,
                [self.request(action="accepted")],
                now=self.now,
            )

    def test_non_pending_candidate_is_rejected(self):
        candidates = {
            "schemaVersion": 1,
            "candidates": [
                {
                    "decisionKey": "acme",
                    "name": "Acme AI",
                    "status": "accepted",
                    "score": 82,
                    "articleCount": 2,
                    "sourceCount": 2,
                    "sourceArticleIds": ["article-a"],
                    "sourceUrls": ["https://example.com/a"],
                }
            ],
        }
        with self.assertRaisesRegex(ReviewDecisionError, "no longer pending"):
            apply_review_decisions(
                candidates,
                self.decisions,
                self.registry,
                [self.request()],
                now=self.now,
            )

    def test_public_actor_must_not_be_email(self):
        with self.assertRaisesRegex(ReviewDecisionError, "not an email"):
            self.request(reviewed_by="operator@example.com")

    def test_batch_limit_and_duplicates_are_rejected(self):
        raw = [
            {
                "candidateKey": "acme",
                "decision": "accepted",
                "candidateFingerprint": "a" * 64,
            },
            {
                "candidateKey": "acme",
                "decision": "rejected",
                "candidateFingerprint": "a" * 64,
            },
        ]
        with self.assertRaisesRegex(ReviewDecisionError, "twice"):
            validate_review_requests(raw, reviewed_by="VCIQ/tracking-console")
        with self.assertRaisesRegex(ReviewDecisionError, "at most 20"):
            validate_review_requests(
                [
                    {
                        "candidateKey": f"candidate-{index}",
                        "decision": "accepted",
                        "candidateFingerprint": "a" * 64,
                    }
                    for index in range(21)
                ],
                reviewed_by="VCIQ/tracking-console",
            )


if __name__ == "__main__":
    unittest.main()
