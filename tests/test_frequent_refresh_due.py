from __future__ import annotations

import unittest
from datetime import UTC, datetime

from tools.frequent_refresh_due import evaluate_due


def payload(*, last_news: str, last_full: str = "", mode: str = "frequent") -> dict:
    audit = {
        "mode": mode,
        "pipelineCompleted": True,
        "completedAt": last_news,
        "lastNewsCrawlAt": last_news,
    }
    if last_full:
        audit["lastFullRefreshAt"] = last_full
    return {"refreshAudit": audit}


class FrequentRefreshDueTests(unittest.TestCase):
    def test_delayed_scheduled_run_is_blocked_in_full_refresh_window(self) -> None:
        result = evaluate_due(
            payload(last_news="2026-08-13T20:07:35+00:00"),
            event_name="schedule",
            now=datetime(2026, 8, 13, 22, 25, tzinfo=UTC),
        )
        self.assertFalse(result["due"])
        self.assertEqual(result["reason"], "awaiting-daily-full-refresh")

    def test_current_day_full_refresh_releases_scheduled_refreshes(self) -> None:
        result = evaluate_due(
            payload(
                last_news="2026-08-13T23:30:00+00:00",
                last_full="2026-08-13T23:30:00+00:00",
            ),
            event_name="schedule",
            now=datetime(2026, 8, 14, 0, 30, tzinfo=UTC),
            min_age_minutes=30,
        )
        self.assertTrue(result["due"])
        self.assertEqual(result["reason"], "age-threshold")

    def test_previous_day_full_refresh_keeps_later_scheduled_run_blocked(self) -> None:
        result = evaluate_due(
            payload(
                last_news="2026-08-14T00:00:00+00:00",
                last_full="2026-08-12T23:30:00+00:00",
            ),
            event_name="schedule",
            now=datetime(2026, 8, 14, 2, 17, tzinfo=UTC),
        )
        self.assertFalse(result["due"])
        self.assertEqual(result["reason"], "awaiting-daily-full-refresh")

    def test_manual_dispatch_bypasses_full_refresh_reservation(self) -> None:
        result = evaluate_due(
            payload(last_news="2026-08-13T20:07:35+00:00"),
            event_name="workflow_dispatch",
            now=datetime(2026, 8, 13, 22, 25, tzinfo=UTC),
        )
        self.assertTrue(result["due"])
        self.assertEqual(result["reason"], "manual-dispatch")

    def test_scheduled_refresh_before_reservation_uses_age_threshold(self) -> None:
        result = evaluate_due(
            payload(last_news="2026-08-13T18:00:00+00:00"),
            event_name="schedule",
            now=datetime(2026, 8, 13, 20, 17, tzinfo=UTC),
        )
        self.assertTrue(result["due"])
        self.assertEqual(result["reason"], "age-threshold")

    def test_rollout_without_full_marker_fails_open_after_bootstrap_window(self) -> None:
        result = evaluate_due(
            payload(last_news="2026-08-13T23:00:00+00:00"),
            event_name="schedule",
            now=datetime(2026, 8, 14, 2, 17, tzinfo=UTC),
        )
        self.assertTrue(result["due"])
        self.assertEqual(result["reason"], "age-threshold")

    def test_legacy_full_audit_counts_as_full_refresh_marker(self) -> None:
        legacy = payload(last_news="2026-08-13T23:20:00+00:00", mode="full")
        result = evaluate_due(
            legacy,
            event_name="schedule",
            now=datetime(2026, 8, 14, 0, 50, tzinfo=UTC),
        )
        self.assertTrue(result["due"])
        self.assertEqual(result["reason"], "age-threshold")


if __name__ == "__main__":
    unittest.main()
