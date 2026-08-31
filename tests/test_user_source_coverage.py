from __future__ import annotations

import unittest

from tools.validate_user_source_coverage import evaluate_coverage


def source(
    source_id: str,
    url: str,
    *,
    source_type: str = "listing-search",
    category: str = "media",
    name: str | None = None,
) -> dict:
    return {
        "id": source_id,
        "name": name or source_id,
        "url": url,
        "sourceType": source_type,
        "sourceCategory": category,
        "region": "全球",
        "sector": "AI / AGI",
        "company": "",
        "ticker": "",
        "keywords": [],
        "enabled": True,
    }


class UserSourceCoverageTests(unittest.TestCase):
    def test_adaptive_public_source_with_status_passes(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [
                source(
                    "researcher",
                    "https://researcher.example.com/",
                    category="person",
                )
            ],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-researcher",
                    "status": "ok",
                    "accepted": 3,
                    "adapter": "adaptive-public-v1",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertTrue(report["passed"])
        self.assertEqual(report["attemptedRuntimeStatuses"], 1)
        self.assertEqual(report["productiveRuntimeStatuses"], 1)
        self.assertEqual(report["runtimeContractViolations"], [])
        self.assertEqual(report["missingStatuses"], [])
        self.assertEqual(report["adapterMismatches"], [])
        self.assertEqual(report["missingHandoffs"], [])

    def test_bounded_media_source_with_status_passes(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("media", "https://media.example.com/news")],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-media",
                    "status": "ok",
                    "accepted": 2,
                    "platform": "用户媒体来源",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertTrue(report["passed"])
        self.assertEqual(report["runtimeContractViolations"], [])
        self.assertEqual(report["attemptedRuntimeStatuses"], 1)
        self.assertEqual(report["productiveRuntimeStatuses"], 1)

    def test_missing_status_fails(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("example", "https://example.com/news")],
        }

        report = evaluate_coverage(config, {"sourceStatus": []})

        self.assertFalse(report["passed"])
        self.assertEqual(report["missingStatuses"], ["user-source-example"])

    def test_generic_website_cannot_bypass_adaptive_adapter(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [
                source(
                    "example",
                    "https://example.com/news",
                    category="person",
                )
            ],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-example",
                    "status": "ok",
                    "accepted": 1,
                    "adapter": "generic-web-v2",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertFalse(report["passed"])
        self.assertEqual(report["runtimeContractViolations"], [])
        self.assertEqual(report["adapterMismatches"][0]["actual"], "generic-web-v2")

    def test_handoff_without_strict_publisher_status_fails(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [
                source(
                    "eastmoney",
                    "https://www.eastmoney.com/default.html",
                    name="东方财富",
                )
            ],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-eastmoney",
                    "status": "partial",
                    "accepted": 0,
                    "adapter": "adaptive-public-v1",
                    "publisherHandoff": "eastmoney-strict-detail",
                    "handoffStatusId": "official-user-东方财富",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertFalse(report["passed"])
        self.assertEqual(report["runtimeContractViolations"], [])
        self.assertEqual(
            report["missingHandoffs"][0]["expectedStatusId"],
            "official-user-东方财富",
        )

    def test_handoff_counts_strict_publisher_as_source_output(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [
                source(
                    "eastmoney",
                    "https://www.eastmoney.com/default.html",
                    name="东方财富",
                )
            ],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-eastmoney",
                    "status": "partial",
                    "accepted": 0,
                    "adapter": "adaptive-public-v1",
                    "publisherHandoff": "eastmoney-strict-detail",
                    "handoffStatusId": "official-user-东方财富",
                },
                {
                    "id": "official-user-东方财富",
                    "status": "ok",
                    "accepted": 7,
                },
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertTrue(report["passed"])
        self.assertEqual(report["runtimeContractViolations"], [])
        self.assertEqual(report["productiveRuntimeStatuses"], 1)
        self.assertEqual(report["missingHandoffs"], [])

    def test_x_direct_source_only_requires_diagnostic_status(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("washington-post", "https://x.com/washingtonpost")],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-washington-post",
                    "status": "error",
                    "accepted": 0,
                    "failed": 1,
                    "platform": "X",
                    "error": "HTTP 429",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertTrue(report["passed"])
        self.assertEqual(report["runtimeContractViolations"], [])
        self.assertEqual(report["attemptedRuntimeStatuses"], 1)
        self.assertEqual(report["productiveRuntimeStatuses"], 0)

    def test_google_alerts_settings_page_only_requires_explicit_error(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("alerts", "https://www.google.com/alerts")],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-alerts",
                    "status": "error",
                    "accepted": 0,
                    "failed": 1,
                    "platform": "Google Alerts",
                    "error": "not a public content feed",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)
        self.assertTrue(report["passed"])
        self.assertEqual(report["runtimeContractViolations"], [])

    def test_invalid_enabled_url_is_unroutable(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("bad", "not-a-url")],
        }

        report = evaluate_coverage(config, {"sourceStatus": []})

        self.assertFalse(report["passed"])
        self.assertEqual(report["unroutableSources"][0]["id"], "bad")


if __name__ == "__main__":
    unittest.main()
