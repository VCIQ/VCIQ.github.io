from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from tools import cninfo_structured_disclosures as cninfo
from tools import crawl_listed_company_disclosures as disclosures
from tools import regulatory_source_health as regulatory
from tools import source_performance as performance


CONFIG = {
    "officialSources": {
        "cninfo": {"name": "巨潮资讯", "homepage": "https://www.cninfo.com.cn/"},
        "hkex": {"name": "香港交易所披露易", "homepage": "https://www.hkexnews.hk/"},
    }
}


class QualifiedYieldPerformanceTest(unittest.TestCase):
    def _sample(self, *, scanned: int, accepted: int, qualified: int | None = None):
        status = {
            "id": "regulatory:test",
            "status": "ok",
            "scanned": scanned,
            "accepted": accepted,
        }
        if qualified is not None:
            status["qualified"] = qualified
        sample = performance._run_sample(status, None, timestamp="2026-09-04T00:00:00+00:00")
        self.assertIsNotNone(sample)
        return sample

    def test_explicit_qualified_drives_valid_yield_instead_of_retention_cap(self):
        result = performance._aggregate([
            self._sample(scanned=100, qualified=80, accepted=18)
        ])
        self.assertEqual(result["scanned"], 100)
        self.assertEqual(result["accepted"], 18)
        self.assertEqual(result["qualified"], 80)
        self.assertEqual(result["validYieldRate"], 0.8)

    def test_low_qualified_yield_remains_low(self):
        result = performance._aggregate([
            self._sample(scanned=100, qualified=10, accepted=10)
        ])
        self.assertEqual(result["validYieldRate"], 0.1)

    def test_legacy_sample_without_qualified_keeps_accepted_over_scanned(self):
        result = performance._aggregate([
            self._sample(scanned=100, accepted=18)
        ])
        self.assertEqual(result["validYieldRate"], 0.18)
        self.assertIsNone(result.get("qualified"))

    def test_mixed_window_uses_qualified_per_explicit_run_and_accepted_for_legacy(self):
        result = performance._aggregate([
            self._sample(scanned=100, qualified=80, accepted=18),
            self._sample(scanned=100, accepted=20),
        ])
        self.assertEqual(result["validYieldRate"], 0.5)


class CollectorQualifiedCountTest(unittest.TestCase):
    def setUp(self):
        self.hk_listing = disclosures.Listing(
            "demo-hk",
            "Demo Holdings",
            "港股",
            "01234",
            "人工智能",
        )
        self.a_listing = disclosures.Listing(
            "demo-a",
            "示例科技",
            "A股",
            "300001",
            "人工智能",
        )

    def test_hkex_reports_pre_limit_qualified_separately_from_retained(self):
        today = date.today().isoformat()
        candidates = [
            disclosures.Candidate(
                f"Demo Holdings Annual Report {index}",
                f"https://www1.hkexnews.hk/listedco/listconews/sehk/{today.replace('-', '')}/demo-{index}.pdf",
                f"Demo Holdings 01234 Annual Report {index}",
                today,
                "official-direct-index",
            )
            for index in range(25)
        ]
        settings = {
            "requestTimeout": 1,
            "requestAttempts": 1,
            "maxAgeDays": 1095,
            "maxItemsPerListing": 18,
        }
        with (
            patch.object(disclosures, "direct_index_url", return_value="https://www.hkexnews.hk/"),
            patch.object(disclosures, "fetch_text", return_value="ok"),
            patch.object(disclosures, "parse_direct_page", return_value=candidates),
            patch.object(disclosures, "parse_rss", return_value=[]),
        ):
            rows, status = disclosures.discover(
                self.hk_listing,
                settings,
                {},
                fallback=False,
            )
        self.assertEqual(len(rows), 18)
        self.assertEqual(status["accepted"], 18)
        self.assertEqual(status["qualified"], 25)
        self.assertLessEqual(status["accepted"], status["qualified"])
        self.assertLessEqual(status["qualified"], status["scanned"])

    def test_cninfo_reports_pre_limit_qualified_separately_from_retained(self):
        today = date.today().isoformat()
        candidates = [
            disclosures.Candidate(
                f"示例科技年度报告 {index}",
                f"https://static.cninfo.com.cn/finalpage/2026-09-04/demo-{index}.pdf",
                f"示例科技 300001 年度报告 {index}",
                today,
                cninfo.PROVIDER,
            )
            for index in range(25)
        ]
        payload = {"announcements": [{} for _ in candidates], "hasMore": False}
        settings = {
            "requestTimeout": 1,
            "requestAttempts": 1,
            "maxAgeDays": 1095,
            "maxItemsPerListing": 18,
            "cninfoMaxPages": 1,
        }
        with (
            patch.object(cninfo, "fetch_json", return_value=payload),
            patch.object(cninfo, "parse_announcements", return_value=candidates),
        ):
            rows, status = cninfo.query_listing(
                self.a_listing,
                "org-demo",
                settings,
            )
        self.assertEqual(len(rows), 18)
        self.assertEqual(status["accepted"], 18)
        self.assertEqual(status["qualified"], 25)
        self.assertEqual(status["scanned"], 25)


class RegulatoryBridgeQualifiedCountTest(unittest.TestCase):
    def test_bridge_preserves_cninfo_and_hkex_qualified_counts(self):
        payload = {
            "sourceStatus": [
                {
                    "id": "exchange-disclosure-demo-a-a-300001",
                    "market": "A股",
                    "structuredAttempted": True,
                    "structuredScanned": 100,
                    "structuredQualified": 80,
                    "structuredAccepted": 18,
                    "structuredErrors": [],
                },
                {
                    "id": "exchange-disclosure-demo-hk-hk-01234",
                    "market": "港股",
                    "status": "ok",
                    "scanned": 100,
                    "qualified": 75,
                    "accepted": 18,
                    "fallback": False,
                    "errors": [],
                },
            ]
        }
        by_id = {
            row["id"]: row
            for row in regulatory.regulatory_source_statuses(payload, config=CONFIG)
        }
        self.assertEqual(by_id["regulatory:cninfo"]["qualified"], 80)
        self.assertEqual(by_id["regulatory:cninfo"]["accepted"], 18)
        self.assertEqual(by_id["regulatory:hkex"]["qualified"], 75)
        self.assertEqual(by_id["regulatory:hkex"]["accepted"], 18)

    def test_eastmoney_fallback_never_inflates_hkex_regulatory_counts(self):
        payload = {
            "sourceStatus": [
                {
                    "id": "exchange-disclosure-demo-hk-hk-01234",
                    "market": "港股",
                    "status": "partial",
                    "scanned": 12,
                    "qualified": 0,
                    "accepted": 18,
                    "fallbackUsed": True,
                    "fallbackScanned": 100,
                    "fallbackQualified": 80,
                    "fallbackAccepted": 18,
                    "errors": ["direct:blocked"],
                }
            ]
        }
        rows = regulatory.regulatory_source_statuses(payload, config=CONFIG)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "regulatory:hkex")
        self.assertEqual(row["scanned"], 12)
        self.assertEqual(row["qualified"], 0)
        self.assertEqual(row["accepted"], 0)

    def test_lifecycle_thresholds_remain_unchanged(self):
        policy_path = Path(__file__).resolve().parents[1] / "config" / "source_lifecycle_policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy["coreMinValidYieldRate"], 0.5)
        self.assertEqual(policy["coreMinObservedDays"], 7)
        self.assertTrue(policy["requiresManualApproval"])


if __name__ == "__main__":
    unittest.main()
