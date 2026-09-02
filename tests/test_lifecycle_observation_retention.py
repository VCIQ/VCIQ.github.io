from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from tools.source_performance import update_source_performance


class LifecycleObservationRetentionTest(unittest.TestCase):
    def test_observed_dates_outlive_rolling_performance_samples(self) -> None:
        performance: dict = {}
        base = datetime(2026, 8, 1, tzinfo=UTC)
        policy = {"performanceWindowRuns": 30}
        status = {
            "id": "high-frequency-source",
            "status": "ok",
            "scanned": 10,
            "accepted": 5,
            "candidateCount": 5,
            "publishedCount": 5,
            "duplicateCount": 0,
            "droppedCount": 0,
        }

        for day in range(8):
            for run in range(12):
                performance = update_source_performance(
                    performance,
                    status,
                    None,
                    evidence_grade="A",
                    collection_state="active",
                    priority="normal",
                    manual_quality=None,
                    policy=policy,
                    now=base + timedelta(days=day, hours=run * 2),
                )

        self.assertEqual(len(performance["samples"]), 30)
        self.assertEqual(performance["runs"], 30)
        self.assertEqual(
            performance["observedDates"],
            [(base + timedelta(days=day)).date().isoformat() for day in range(8)],
        )

    def test_legacy_samples_bootstrap_observed_dates_before_window_rolls(self) -> None:
        base = datetime(2026, 8, 1, tzinfo=UTC)
        previous = {
            "samples": [
                {
                    "at": (base + timedelta(days=day)).isoformat(),
                    "status": "ok",
                    "successful": True,
                    "productive": True,
                    "scanned": 10,
                    "accepted": 5,
                    "failed": 0,
                    "candidates": 5,
                    "published": 5,
                    "duplicates": 0,
                    "withheld": 0,
                    "dropped": 0,
                    "newArticles": 0,
                    "lagDayTotal": 0,
                    "lagSamples": 0,
                }
                for day in range(3)
            ]
        }

        performance = update_source_performance(
            previous,
            {"id": "legacy-source", "status": "ok", "scanned": 10, "accepted": 5},
            None,
            evidence_grade="A",
            collection_state="active",
            priority="normal",
            manual_quality=None,
            policy={"performanceWindowRuns": 2},
            now=base + timedelta(days=3),
        )

        self.assertEqual(len(performance["samples"]), 2)
        self.assertEqual(
            performance["observedDates"],
            [(base + timedelta(days=day)).date().isoformat() for day in range(4)],
        )

    def test_non_attempted_run_does_not_create_observation_date(self) -> None:
        base = datetime(2026, 8, 1, tzinfo=UTC)
        performance = update_source_performance(
            {},
            {"id": "skipped-source", "status": "skipped"},
            None,
            evidence_grade="A",
            collection_state="active",
            priority="normal",
            manual_quality=None,
            policy={"performanceWindowRuns": 30},
            now=base,
        )

        self.assertEqual(performance["samples"], [])
        self.assertEqual(performance["observedDates"], [])


if __name__ == "__main__":
    unittest.main()
