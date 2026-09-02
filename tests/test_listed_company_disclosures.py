from __future__ import annotations

import json
import unittest

from tools import crawl_listed_company_disclosures as disclosures


class ListedCompanyDisclosureTest(unittest.TestCase):
    def test_enabled_a_share_and_hk_listings_are_registered(self) -> None:
        listings = disclosures.load_listings()
        identities = {(row.catalog_slug, row.market, row.ticker) for row in listings}

        tracking = json.loads(disclosures.TRACKING_PATH.read_text(encoding="utf-8"))
        disclosure_config = disclosures.load_config()
        configured_rows = [
            row
            for row in tracking.get("listedCompanies", [])
            if isinstance(row, dict)
            and row.get("enabled", True) is not False
            and row.get("market") in disclosures.SUPPORTED_MARKETS
        ]
        configured_rows.extend(
            row
            for row in disclosure_config.get("extraListings", [])
            if isinstance(row, dict)
            and row.get("enabled", True) is not False
            and row.get("market") in disclosures.SUPPORTED_MARKETS
        )
        expected = {
            (
                str(row.get("catalogSlug") or "").strip(),
                str(row.get("market") or "").strip(),
                disclosures.normalize_ticker(row.get("market"), row.get("ticker")),
            )
            for row in configured_rows
        }

        self.assertEqual(identities, expected)
        self.assertIn(("cambricon", "A股", "688256"), identities)
        self.assertIn(("catl", "A股", "300750"), identities)
        self.assertIn(("catl", "港股", "03750"), identities)
        self.assertIn(("horizon-robotics", "港股", "09660"), identities)
        self.assertIn(("xtalpi", "港股", "02228"), identities)

    def test_exchange_routing_uses_official_hosts(self) -> None:
        sse = disclosures.Listing("cambricon", "寒武纪", "A股", "688256", "半导体")
        szse = disclosures.Listing("catl", "宁德时代", "A股", "300750", "新能源")
        hkex = disclosures.Listing("horizon-robotics", "地平线机器人", "港股", "09660", "半导体")
        self.assertIn("site:sse.com.cn/disclosure", disclosures.official_query(sse))
        self.assertIn("site:szse.cn/disclosure", disclosures.official_query(szse))
        self.assertIn("site:hkexnews.hk/listedco/listconews/sehk", disclosures.official_query(hkex))
        self.assertTrue(
            disclosures.allowed_url(
                sse,
                "https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/example.shtml",
            )
        )
        self.assertTrue(
            disclosures.allowed_url(
                szse,
                "https://www.cninfo.com.cn/new/disclosure/detail?announcementId=1",
            )
        )
        self.assertTrue(
            disclosures.allowed_url(
                hkex,
                "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0723/example.pdf",
            )
        )
        self.assertFalse(
            disclosures.allowed_url(
                hkex,
                "https://example.com/fake-prospectus.pdf",
            )
        )

    def test_classifies_capital_market_documents(self) -> None:
        cases = {
            "首次公开发行股票并在科创板上市招股说明书": "招股与上市",
            "2025年年度报告": "定期报告与业绩",
            "关于向特定对象发行股票募集资金的公告": "证券发行与融资",
            "重大资产重组及收购公告": "并购与资产交易",
            "GRANT OF SHARE OPTIONS AND RESTRICTED SHARE UNITS": "股权激励",
            "VOLUNTARY ANNOUNCEMENT ON-MARKET SHARE REPURCHASE": "股份回购",
            "INSIDE INFORMATION BUSINESS UPDATE": "重大经营与风险",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(disclosures.classify_document(title), expected)
        self.assertEqual(disclosures.classify_document("Monthly Return for June 2026"), "")

    def test_event_requires_date_classification_and_original_host(self) -> None:
        listing = disclosures.Listing(
            "horizon-robotics",
            "地平线机器人",
            "港股",
            "09660",
            "半导体",
        )
        candidate = disclosures.Candidate(
            "PRICING OF US$450,000,000 ZERO COUPON CONVERTIBLE BONDS DUE 2027",
            "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0723/example.pdf",
            "Stock Code 09660 issue of convertible securities",
            "2026-07-23",
            "official-domain-search",
        )
        event = disclosures.to_event(listing, candidate, fallback=False)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["documentType"], "证券发行与融资")
        self.assertEqual(event["source"]["name"], "香港交易所披露易")
        self.assertEqual(event["source"]["level"], "监管文件")
        self.assertFalse(event["fallback"])


if __name__ == "__main__":
    unittest.main()
