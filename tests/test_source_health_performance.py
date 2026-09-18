from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from tools.update_source_health import DEFAULT_POLICY, update_health


class SourceHealthPerformanceIntegrationTest(unittest.TestCase):
    def test_health_state_persists_rolling_performance_metrics(self) -> None:
        state: dict = {}
        base = datetime(2026, 8, 1, tzinfo=UTC)
        for offset in range(5):
            status = {
                "id": "source-a",
                "name": "Source A",
                "platform": "专业媒体",
                "status": "ok",
                "scanned": 10,
                "accepted": 5,
                "candidateCount": 5,
                "publishedCount": 4,
                "duplicateCount": 1,
                "droppedCount": 0,
                "withheldCount": 0,
            }
            state, _ = update_health(
                state,
                {
                    "sourceStatus": [status],
                    "articles": [
                        {
                            "id": f"article-{offset}",
                            "sourceId": "source-a",
                            "publishedAt": (base + timedelta(days=offset - 1)).date().isoformat(),
                            "firstSeenAt": (base + timedelta(days=offset)).isoformat(),
                            "firstSeenEstimated": False,
                            "source": {"evidenceGrade": "C"},
                        }
                    ],
                },
                DEFAULT_POLICY,
                now=base + timedelta(days=offset, hours=1),
            )

        entry = state["sources"]["source-a"]
        performance = entry["performance"]
        self.assertEqual(state["schemaVersion"], 3)
        self.assertEqual(performance["runs"], 5)
        self.assertEqual(performance["availabilityRate"], 1.0)
        self.assertEqual(performance["productiveRate"], 1.0)
        self.assertEqual(performance["validYieldRate"], 0.5)
        self.assertEqual(performance["duplicateRate"], 0.2)
        self.assertEqual(performance["dropRate"], 0.0)
        self.assertEqual(performance["newArticles"], 4)
        self.assertEqual(performance["averageDiscoveryLagDays"], 1.0)
        self.assertEqual(performance["reviewState"], "retain")

    def test_manual_review_metrics_flow_into_health_state(self) -> None:
        state: dict = {}
        base = datetime(2026, 8, 1, tzinfo=UTC)
        manual = {
            "source-a": {
                "reviewedRecords": 20,
                "misattributedRecords": 2,
                "confirmedDuplicateRecords": 1,
                "misattributionRate": 0.1,
                "lastReviewedAt": "2026-08-01T00:00:00Z",
            }
        }
        for offset in range(5):
            state, _ = update_health(
                state,
                {
                    "sourceStatus": [
                        {
                            "id": "source-a",
                            "name": "Source A",
                            "platform": "专业媒体",
                            "status": "ok",
                            "scanned": 10,
                            "accepted": 5,
                            "candidateCount": 5,
                            "publishedCount": 5,
                            "duplicateCount": 0,
                            "droppedCount": 0,
                        }
                    ],
                    "articles": [
                        {
                            "sourceId": "source-a",
                            "source": {"evidenceGrade": "C"},
                        }
                    ],
                },
                DEFAULT_POLICY,
                now=base + timedelta(days=offset),
                manual_reviews=manual,
            )
        performance = state["sources"]["source-a"]["performance"]
        self.assertEqual(performance["manualQuality"]["reviewedRecords"], 20)
        self.assertIn("manual-misattribution", performance["reviewReasons"])
        self.assertEqual(performance["reviewState"], "monitor")

    def test_retained_previous_batch_is_not_counted_as_productive(self) -> None:
        previous = {
            "generatedAt": "2026-08-01T00:00:00+00:00",
            "sources": {
                "source-a": {
                    "id": "source-a",
                    "name": "Source A",
                    "platform": "专业媒体",
                    "evidenceGrade": "C",
                    "collectionState": "active",
                    "priority": "normal",
                    "alertActive": False,
                    "consecutiveFailures": 0,
                    "firstObservedAt": "2026-07-01T00:00:00+00:00",
                    "lastProductiveAt": "2026-07-31T00:00:00+00:00",
                }
            },
        }
        state, _ = update_health(
            previous,
            {
                "sourceStatus": [
                    {
                        "id": "source-a",
                        "name": "Source A",
                        "platform": "专业媒体",
                        "status": "partial",
                        "accepted": 3,
                        "retainedPrevious": True,
                    }
                ],
                "articles": [
                    {
                        "sourceId": "source-a",
                        "source": {"evidenceGrade": "C"},
                    }
                ],
            },
            DEFAULT_POLICY,
            now=datetime(2026, 8, 2, tzinfo=UTC),
        )
        entry = state["sources"]["source-a"]
        self.assertEqual(entry["lastProductiveAt"], "2026-07-31T00:00:00+00:00")
        self.assertEqual(entry["performance"]["productiveRuns"], 0)

    def test_adaptive_new_accepted_count_drives_productivity(self) -> None:
        state, _ = update_health(
            {},
            {
                "sourceStatus": [
                    {
                        "id": "adaptive",
                        "name": "Adaptive",
                        "platform": "专业媒体",
                        "status": "partial",
                        "accepted": 12,
                        "newAccepted": 0,
                        "retainedPrevious": True,
                    }
                ],
                "articles": [
                    {
                        "sourceId": "adaptive",
                        "source": {"evidenceGrade": "C"},
                    }
                ],
            },
            DEFAULT_POLICY,
            now=datetime(2026, 8, 2, tzinfo=UTC),
        )
        entry = state["sources"]["adaptive"]
        self.assertEqual(entry["accepted"], 0)
        self.assertIsNone(entry["lastProductiveAt"])
        self.assertEqual(entry["performance"]["productiveRuns"], 0)

    def test_official_retention_uses_pre_retention_acceptance_for_current_run(self) -> None:
        state, _ = update_health(
            {},
            {
                "sourceStatus": [
                    {
                        "id": "official-form-energy",
                        "name": "Form Energy 官方动态",
                        "platform": "官方网站",
                        "status": "ok",
                        "scanned": 0,
                        "accepted": 1,
                        "acceptedBeforeRetention": 0,
                    }
                ],
                "articles": [
                    {
                        "sourceId": "official-form-energy",
                        "source": {"evidenceGrade": "B"},
                    }
                ],
            },
            DEFAULT_POLICY,
            now=datetime(2026, 9, 18, tzinfo=UTC),
        )

        entry = state["sources"]["official-form-energy"]
        self.assertEqual(entry["scanned"], 0)
        self.assertEqual(entry["accepted"], 0)
        self.assertIsNone(entry["lastProductiveAt"])
        self.assertEqual(entry["performance"]["productiveRuns"], 0)


if __name__ == "__main__":
    unittest.main()
