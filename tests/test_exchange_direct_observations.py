from __future__ import annotations

import unittest

from tools import crawl_listed_company_disclosures as base
from tools import exchange_direct_observations as exchange
from tools import regulatory_source_health as regulatory


class ExchangeDirectObservationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sse = base.Listing("cambricon", "寒武纪", "A股", "688256", "半导体")
        self.szse = base.Listing("catl", "宁德时代", "A股", "300750", "新能源")

    def test_sse_jsonp_payload_is_decoded_and_classified(self) -> None:
        payload = exchange._decode_json(
            'jsonpCallback123({"pageHelp":{"data":['
            '{"TITLE":"2026年半年度报告"},'
            '{"TITLE":"关于董事会会议通知的公告"}'
            ']}})'
        )
        rows = exchange._sse_rows(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(exchange._classify_rows(rows), (2, 1))

    def test_szse_payload_is_classified(self) -> None:
        rows = exchange._szse_rows(
            {
                "data": [
                    {"title": "2026年半年度报告摘要"},
                    {"title": "关于可转换公司债券发行结果的公告"},
                    {"title": "投资者关系活动记录表"},
                ]
            }
        )
        self.assertEqual(exchange._classify_rows(rows), (3, 2))

    def test_enrichment_adds_strict_exchange_fields_without_mutating_aggregate_status(self) -> None:
        snapshot = {
            "schemaVersion": 1,
            "sourceStatus": [
                {
                    "id": self.sse.source_id,
                    "companySlug": "cambricon",
                    "name": "寒武纪",
                    "market": "A股",
                    "ticker": "688256",
                    "exchange": "上海证券交易所",
                    "provider": "official+cninfo-structured",
                    "status": "ok",
                    "scanned": 12,
                    "accepted": 18,
                    "structuredAccepted": 18,
                },
                {
                    "id": self.szse.source_id,
                    "companySlug": "catl",
                    "name": "宁德时代",
                    "market": "A股",
                    "ticker": "300750",
                    "exchange": "深圳证券交易所",
                    "provider": "official+cninfo-structured",
                    "status": "ok",
                    "scanned": 8,
                    "accepted": 18,
                    "structuredAccepted": 18,
                },
            ],
        }

        def observer(listing, settings):
            if listing.ticker == "688256":
                return {
                    "institution": "sse",
                    "provider": "sse-company-bulletin-api",
                    "status": "ok",
                    "scanned": 30,
                    "accepted": 7,
                    "errors": [],
                }
            return {
                "institution": "szse",
                "provider": "szse-announcement-api",
                "status": "error",
                "scanned": 0,
                "accepted": 0,
                "errors": ["timeout"],
            }

        enriched = exchange.enrich_snapshot(
            snapshot,
            [self.sse, self.szse],
            {},
            observer=observer,
        )
        by_id = {row["id"]: row for row in enriched["sourceStatus"]}

        sse = by_id[self.sse.source_id]
        self.assertEqual(sse["provider"], "official+cninfo-structured")
        self.assertEqual(sse["accepted"], 18)
        self.assertTrue(sse["exchangeDirectAttempted"])
        self.assertEqual(sse["exchangeDirectInstitution"], "sse")
        self.assertEqual(sse["exchangeDirectScanned"], 30)
        self.assertEqual(sse["exchangeDirectAccepted"], 7)

        szse = by_id[self.szse.source_id]
        self.assertEqual(szse["provider"], "official+cninfo-structured")
        self.assertEqual(szse["accepted"], 18)
        self.assertEqual(szse["exchangeDirectInstitution"], "szse")
        self.assertEqual(szse["exchangeDirectStatus"], "error")
        self.assertEqual(szse["exchangeDirectErrors"], ["timeout"])

        self.assertEqual(
            exchange.validate_snapshot(
                enriched,
                [self.sse, self.szse],
                require_attempts=True,
            ),
            [],
        )

    def test_regulatory_bridge_uses_only_exchange_direct_counters(self) -> None:
        payload = {
            "sourceStatus": [
                {
                    "id": self.sse.source_id,
                    "market": "A股",
                    "exchange": "上海证券交易所",
                    "provider": "official+cninfo-structured",
                    "status": "ok",
                    "scanned": 12,
                    "accepted": 18,
                    "structuredAttempted": True,
                    "structuredScanned": 120,
                    "structuredAccepted": 18,
                    "structuredErrors": [],
                    "exchangeDirectAttempted": True,
                    "exchangeDirectInstitution": "sse",
                    "exchangeDirectProvider": "sse-company-bulletin-api",
                    "exchangeDirectStatus": "ok",
                    "exchangeDirectScanned": 30,
                    "exchangeDirectAccepted": 7,
                    "exchangeDirectErrors": [],
                }
            ]
        }
        rows = regulatory.regulatory_source_statuses(payload)
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id["regulatory:sse"]["scanned"], 30)
        self.assertEqual(by_id["regulatory:sse"]["accepted"], 7)
        self.assertEqual(by_id["regulatory:cninfo"]["scanned"], 120)
        self.assertEqual(by_id["regulatory:cninfo"]["accepted"], 18)

    def test_legacy_mixed_a_share_status_is_not_inferred_as_exchange_evidence(self) -> None:
        payload = {
            "sourceStatus": [
                {
                    "id": self.sse.source_id,
                    "market": "A股",
                    "exchange": "上海证券交易所",
                    "provider": "official+cninfo-structured",
                    "status": "ok",
                    "scanned": 12,
                    "accepted": 18,
                }
            ]
        }
        rows = regulatory.regulatory_source_statuses(payload)
        self.assertNotIn("regulatory:sse", {row["id"] for row in rows})

    def test_mismatched_institution_fails_closed(self) -> None:
        snapshot = {
            "schemaVersion": 1,
            "sourceStatus": [
                {
                    "id": self.sse.source_id,
                    "market": "A股",
                    "ticker": "688256",
                    "exchange": "上海证券交易所",
                }
            ],
        }

        def observer(listing, settings):
            return {
                "institution": "szse",
                "provider": "wrong",
                "status": "ok",
                "scanned": 1,
                "accepted": 1,
                "errors": [],
            }

        with self.assertRaisesRegex(ValueError, "exchange observation mismatch"):
            exchange.enrich_snapshot(snapshot, [self.sse], {}, observer=observer)


if __name__ == "__main__":
    unittest.main()
