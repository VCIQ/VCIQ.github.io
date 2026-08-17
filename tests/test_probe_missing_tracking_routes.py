from __future__ import annotations

import copy
import unittest

from tools import probe_missing_tracking_routes as probe


class ProbeMissingTrackingRoutesTest(unittest.TestCase):
    def test_selects_four_generated_routes_for_new_track(self) -> None:
        config = {
            "tracks": [
                {
                    "slug": "example-track",
                    "name": "示例精确赛道",
                    "enabled": True,
                    "custom": True,
                    "keywords": ["示例精确技术"],
                    "people": [],
                    "sampleCompanies": ["示例公司"],
                }
            ]
        }
        snapshot = {"sourceStatus": []}
        specs, missing = probe.missing_source_specs(config, snapshot)
        self.assertEqual(
            missing,
            [
                "user-track-example-track-bing",
                "user-track-example-track-google-cn",
                "user-track-example-track-google-us",
                "user-track-example-track-toutiao",
            ],
        )
        self.assertEqual({row["id"] for row in specs}, set(missing))

    def test_existing_source_status_avoids_network_work(self) -> None:
        config = {
            "tracks": [
                {
                    "slug": "example-track",
                    "name": "示例精确赛道",
                    "enabled": True,
                    "custom": True,
                    "keywords": ["示例精确技术"],
                    "people": [],
                    "sampleCompanies": [],
                }
            ]
        }
        status = [
            {"id": f"user-track-example-track-{suffix}", "status": "empty"}
            for suffix in ("bing", "google-cn", "google-us", "toutiao")
        ]
        specs, missing = probe.missing_source_specs(config, {"sourceStatus": status})
        self.assertEqual(specs, [])
        self.assertEqual(missing, [])

    def test_merge_preserves_failures_and_adds_real_articles(self) -> None:
        original = {
            "articles": [
                {
                    "id": "existing",
                    "source": {"url": "https://example.com/existing"},
                }
            ],
            "sourceStatus": [{"id": "old-source", "status": "ok", "accepted": 1}],
        }
        incoming = [
            {
                "id": "new-one",
                "source": {"url": "https://example.com/new"},
            },
            {
                "id": "existing",
                "source": {"url": "https://example.com/duplicate"},
            },
        ]
        statuses = [
            {
                "id": "user-track-new-bing",
                "status": "ok",
                "accepted": 1,
                "scanned": 2,
            },
            {
                "id": "user-track-new-toutiao",
                "status": "error",
                "accepted": 0,
                "scanned": 10,
                "failed": 1,
                "error": "No matching original Toutiao feed articles",
            },
        ]
        merged = probe.merge_probe_results(
            copy.deepcopy(original),
            incoming,
            statuses,
            ["user-track-new-bing", "user-track-new-toutiao"],
        )
        self.assertEqual(merged["articleCount"], 2)
        self.assertEqual(
            {row["id"] for row in merged["sourceStatus"]},
            {"old-source", "user-track-new-bing", "user-track-new-toutiao"},
        )
        report = merged["candidateTrackingRouteProbe"]
        self.assertEqual(report["completedRoutes"], 2)
        self.assertEqual(report["productiveRoutes"], 1)
        self.assertEqual(report["failedRoutes"], 1)
        self.assertEqual(report["addedArticles"], 1)


if __name__ == "__main__":
    unittest.main()
