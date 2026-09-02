from __future__ import annotations

import unittest

from tools.regulatory_source_health import (
    merge_regulatory_statuses,
    regulatory_source_statuses,
)


CONFIG = {
    "officialSources": {
        "sse": {"name": "上海证券交易所", "homepage": "https://www.sse.com.cn/"},
        "szse": {"name": "深圳证券交易所", "homepage": "https://www.szse.cn/"},
        "cninfo": {"name": "巨潮资讯", "homepage": "https://www.cninfo.com.cn/"},
        "hkex": {"name": "香港交易所披露易", "homepage": "https://www.hkexnews.hk/"},
        "sec": {"name": "美国证券交易委员会 SEC", "homepage": "https://www.sec.gov/"},
        "eastmoney": {"name": "东方财富公告", "homepage": "https://data.eastmoney.com/notices/"},
    }
}


class RegulatorySourceHealthTest(unittest.TestCase):
    def test_cninfo_structured_metrics_do_not_leak_into_exchange_evidence(self) -> None:
        payload = {
            "sourceStatus": [
                {
                    "id": "exchange-disclosure-cambricon-a-688256",
                    "market": "A股",
                    "exchange": "上海证券交易所",
                    "provider": "official+cninfo-structured",
                    "status": "ok",
                    "scanned": 72,
                    "accepted": 17,
                    "structuredAttempted": True,
                    "structuredScanned": 120,
                    "structuredAccepted": 17,
                    "structuredErrors": [],
                }
            ]
        }

        rows = regulatory_source_statuses(payload, config=CONFIG)
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(set(by_id), {"regulatory:cninfo"})
        self.assertEqual(by_id["regulatory:cninfo"]["scanned"], 120)
        self.assertEqual(by_id["regulatory:cninfo"]["accepted"], 17)
        self.assertNotIn("regulatory:sse", by_id)
        self.assertNotIn("regulatory:szse", by_id)

    def test_hkex_direct_rows_are_aggregated_at_institution_level(self) -> None:
        payload = {
            "sourceStatus": [
                {
                    "id": "exchange-disclosure-one-hk-00001",
                    "market": "港股",
                    "provider": "official",
                    "status": "ok",
                    "scanned": 40,
                    "accepted": 5,
                    "errors": [],
                },
                {
                    "id": "exchange-disclosure-two-hk-00002",
                    "market": "港股",
                    "provider": "official",
                    "status": "error",
                    "scanned": 0,
                    "accepted": 0,
                    "errors": ["timeout"],
                },
            ]
        }

        rows = regulatory_source_statuses(payload, config=CONFIG)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "regulatory:hkex")
        self.assertEqual(row["status"], "partial")
        self.assertEqual(row["scanned"], 40)
        self.assertEqual(row["accepted"], 5)
        self.assertEqual(row["failed"], 1)
        self.assertEqual(row["observationCount"], 2)

    def test_hkex_fallback_rows_are_not_misattributed_to_hkex(self) -> None:
        payload = {
            "sourceStatus": [
                {
                    "id": "exchange-disclosure-one-hk-00001",
                    "market": "港股",
                    "provider": "official",
                    "status": "partial",
                    "scanned": 11,
                    "accepted": 3,
                    "errors": [],
                    "fallbackUsed": True,
                    "fallbackScanned": 20,
                    "fallbackAccepted": 3,
                    "fallbackErrors": [],
                }
            ]
        }

        rows = regulatory_source_statuses(payload, config=CONFIG)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "regulatory:hkex")
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["accepted"], 0)
        self.assertNotIn("regulatory:eastmoney", {item["id"] for item in rows})

    def test_company_ir_mirror_is_not_sec_performance_evidence(self) -> None:
        payload = {
            "sourceStatus": [
                {
                    "id": "us-ir-disclosure-ionq-ionq",
                    "market": "美股",
                    "provider": "official-company-ir-sec-filings",
                    "status": "ok",
                    "scanned": 24,
                    "accepted": 1,
                    "errors": [],
                }
            ],
            "usIrStructured": {
                "directSecAccess": "blocked-by-sec-for-shared-ci-ip",
            },
        }

        rows = regulatory_source_statuses(payload, config=CONFIG)
        self.assertNotIn("regulatory:sec", {row["id"] for row in rows})

    def test_direct_sec_rows_are_valid_sec_performance_evidence(self) -> None:
        payload = {
            "sourceStatus": [
                {
                    "id": "sec-disclosure-ionq-ionq",
                    "provider": "sec-edgar-submissions",
                    "status": "ok",
                    "scanned": 80,
                    "accepted": 12,
                    "errors": [],
                },
                {
                    "id": "sec-disclosure-joby-joby",
                    "provider": "sec-edgar-submissions",
                    "status": "error",
                    "scanned": 0,
                    "accepted": 0,
                    "errors": ["SEC request failed"],
                },
            ]
        }

        rows = regulatory_source_statuses(payload, config=CONFIG)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "regulatory:sec")
        self.assertEqual(row["status"], "partial")
        self.assertEqual(row["scanned"], 80)
        self.assertEqual(row["accepted"], 12)
        self.assertEqual(row["failed"], 1)

    def test_merge_preserves_unrelated_statuses_and_replaces_regulatory_rows(self) -> None:
        articles = {
            "sourceStatus": [
                {"id": "feed-a", "status": "ok"},
                {"id": "regulatory:cninfo", "status": "error"},
            ]
        }
        disclosures = {
            "sourceStatus": [
                {
                    "id": "exchange-disclosure-a-a-000001",
                    "market": "A股",
                    "structuredAttempted": True,
                    "structuredScanned": 20,
                    "structuredAccepted": 4,
                    "structuredErrors": [],
                }
            ]
        }

        merged = merge_regulatory_statuses(articles, disclosures, config=CONFIG)
        by_id = {row["id"]: row for row in merged["sourceStatus"]}
        self.assertEqual(set(by_id), {"feed-a", "regulatory:cninfo"})
        self.assertEqual(by_id["feed-a"]["status"], "ok")
        self.assertEqual(by_id["regulatory:cninfo"]["status"], "ok")
        self.assertEqual(by_id["regulatory:cninfo"]["accepted"], 4)


if __name__ == "__main__":
    unittest.main()
