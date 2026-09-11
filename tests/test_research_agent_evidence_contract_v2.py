from __future__ import annotations

import unittest

from tools import research_agent_evidence_contract_v2 as contract


class ResearchAgentEvidenceContractV2Tests(unittest.TestCase):
    def test_verified_change_is_auto_verified_but_not_human_reviewed(self) -> None:
        report = {
            "generatedAt": "2026-09-11T08:00:00Z",
            "evidence": [
                {
                    "id": "E001",
                    "publishedAt": "2020-01-01",
                    "publicationTier": "verified_change",
                    "reviewStatus": "automated_unreviewed",
                    "qualityStatus": "passed",
                    "supportStatus": "supports",
                }
            ],
        }

        contract.annotate_report(report)
        row = report["evidence"][0]
        self.assertEqual(report["evidenceContractVersion"], 2)
        self.assertEqual(row["verificationStatus"], "auto_verified")
        self.assertEqual(row["observedAt"], "2026-09-11T08:00:00Z")
        self.assertEqual(row["dateSource"], "legacy_published_at")
        self.assertEqual(row["dateConfidence"], "unknown")
        self.assertNotIn("eventDate", row)

    def test_review_and_rejection_override_automatic_state(self) -> None:
        report = {
            "generatedAt": "2026-09-11T08:00:00Z",
            "evidence": [
                {
                    "id": "E001",
                    "reviewStatus": "approved",
                    "publicationTier": "verified_change",
                    "qualityStatus": "passed",
                    "supportStatus": "supports",
                },
                {
                    "id": "E002",
                    "reviewStatus": "rejected",
                    "verificationStatus": "cross_verified",
                    "publicationTier": "verified_change",
                    "qualityStatus": "passed",
                    "supportStatus": "supports",
                },
            ],
        }

        contract.annotate_report(report)
        self.assertEqual(report["evidence"][0]["verificationStatus"], "reviewed")
        self.assertEqual(report["evidence"][1]["verificationStatus"], "rejected")

    def test_explicit_event_and_page_times_keep_distinct_semantics(self) -> None:
        report = {
            "generatedAt": "2026-09-11T08:00:00Z",
            "evidence": [
                {
                    "id": "E001",
                    "eventDate": "2026-09-10",
                    "pageCreatedAt": "2020-01-01",
                    "pageUpdatedAt": "2026-09-10T10:00:00Z",
                    "publishedAt": "2020-01-01",
                    "publicationTier": "candidate",
                }
            ],
        }

        contract.annotate_report(report)
        row = report["evidence"][0]
        self.assertEqual(row["dateSource"], "event_date")
        self.assertEqual(row["dateConfidence"], "high")
        self.assertEqual(row["eventDate"], "2026-09-10")
        self.assertEqual(row["pageCreatedAt"], "2020-01-01")
        self.assertEqual(row["pageUpdatedAt"], "2026-09-10T10:00:00Z")
        self.assertEqual(row["publishedAt"], "2020-01-01")

    def test_observation_time_is_fallback_without_inventing_event_time(self) -> None:
        report = {
            "generatedAt": "2026-09-11T08:00:00Z",
            "evidence": [{"id": "E001", "publicationTier": "candidate"}],
        }

        contract.annotate_report(report)
        row = report["evidence"][0]
        self.assertEqual(row["observedAt"], "2026-09-11T08:00:00Z")
        self.assertEqual(row["dateSource"], "observed_at")
        self.assertEqual(row["dateConfidence"], "high")
        self.assertNotIn("eventDate", row)


if __name__ == "__main__":
    unittest.main()
