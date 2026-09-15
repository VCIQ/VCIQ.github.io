from __future__ import annotations

import unittest

from tools import crawl_listed_company_disclosures as base
from tools import exchange_direct_observations as exchange


class ExchangeDirectPublicationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sse = base.Listing("cambricon", "寒武纪", "A股", "688256", "半导体")
        self.szse = base.Listing("catl", "宁德时代", "A股", "300750", "新能源")

    def test_sse_structured_row_publishes_official_document(self) -> None:
        events = exchange.direct_events(
            self.sse,
            "sse",
            [
                {
                    "TITLE": "寒武纪2026年半年度报告",
                    "URL": "/disclosure/listedinfo/announcement/c/new/2026-08-15/example.pdf",
                    "SSEDATE": "2026-08-15",
                    "SECURITY_NAME": "寒武纪",
                    "BULLETIN_TYPE": "定期报告",
                }
            ],
        )
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["source"]["name"], "上海证券交易所")
        self.assertEqual(event["source"]["level"], "监管文件")
        self.assertEqual(
            event["source"]["url"],
            "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-08-15/example.pdf",
        )
        self.assertEqual(event["discoveredVia"], "sse-company-bulletin-api")
        self.assertFalse(event["fallback"])

    def test_szse_structured_row_publishes_official_document(self) -> None:
        events = exchange.direct_events(
            self.szse,
            "szse",
            [
                {
                    "title": "宁德时代2026年半年度报告",
                    "publishTime": "2026-08-15 18:30:00",
                    "attachPath": "/disc/disk03/finalpage/2026-08-15/example.PDF",
                    "attachFormat": "PDF",
                    "secName": ["宁德时代"],
                }
            ],
        )
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["source"]["name"], "深圳证券交易所")
        self.assertEqual(event["source"]["level"], "监管文件")
        self.assertEqual(
            event["source"]["url"],
            "https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-08-15/example.PDF",
        )
        self.assertEqual(event["discoveredVia"], "szse-announcement-api")
        self.assertFalse(event["fallback"])

    def test_enrichment_merges_direct_exchange_events_into_company_channel(self) -> None:
        direct_event = exchange.direct_events(
            self.szse,
            "szse",
            [
                {
                    "title": "宁德时代关于重大合同的公告",
                    "publishTime": "2026-09-15 08:00:00",
                    "attachPath": "/disc/disk03/finalpage/2026-09-15/contract.PDF",
                    "attachFormat": "PDF",
                    "secName": ["宁德时代"],
                }
            ],
        )[0]
        snapshot = {
            "schemaVersion": 1,
            "companies": {
                "catl": {
                    "slug": "catl",
                    "name": "宁德时代",
                    "updatedAt": "2026-09-14T00:00:00+00:00",
                    "status": "ok",
                    "listings": [],
                    "events": [],
                    "officialEventCount": 0,
                    "fallbackEventCount": 0,
                }
            },
            "sourceStatus": [
                {
                    "id": self.szse.source_id,
                    "companySlug": "catl",
                    "name": "宁德时代",
                    "market": "A股",
                    "ticker": "300750",
                    "exchange": "深圳证券交易所",
                    "provider": "official+cninfo-structured",
                    "status": "ok",
                    "scanned": 10,
                    "accepted": 5,
                }
            ],
        }

        def observer(listing, settings):
            return {
                "institution": "szse",
                "provider": "szse-announcement-api",
                "status": "ok",
                "scanned": 30,
                "accepted": 1,
                "published": 1,
                "events": [direct_event],
                "errors": [],
            }

        enriched = exchange.enrich_snapshot(
            snapshot,
            [self.szse],
            {"maxItemsPerListing": 18},
            observer=observer,
        )
        self.assertEqual(len(enriched["companies"]["catl"]["events"]), 1)
        self.assertEqual(enriched["companies"]["catl"]["officialEventCount"], 1)
        status = enriched["sourceStatus"][0]
        self.assertEqual(status["exchangeDirectAccepted"], 1)
        self.assertEqual(status["exchangeDirectPublished"], 1)
        self.assertEqual(enriched["exchangeDirect"]["publishedEventCount"], 1)
        self.assertEqual(
            exchange.validate_snapshot(enriched, [self.szse], require_attempts=True),
            [],
        )


if __name__ == "__main__":
    unittest.main()
