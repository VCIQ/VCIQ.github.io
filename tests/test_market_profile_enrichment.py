import json
import unittest

from tools import crawl_market_profiles as market
from tools import market_profile_enrichment as enrichment
from tools import refresh_market_profiles_enriched as enriched_runner


class MarketProfileEnrichmentTests(unittest.TestCase):
    def test_quote_payload_adds_market_cap_and_trading_metrics(self):
        payload = json.dumps(
            {
                "data": {
                    "f116": 1_234_500_000_000,
                    "f117": 987_600_000_000,
                    "f84": 1_000_000_000,
                    "f85": 800_000_000,
                    "f162": 2534,
                    "f167": 481,
                    "f168": 267,
                    "f48": 3_250_000_000,
                }
            }
        )
        result = enrichment.parse_quote_payload(payload, "A股")
        metrics = {item["id"]: item["value"] for item in result["metrics"]}
        self.assertEqual(metrics["marketCap"], "¥1.23万亿")
        self.assertEqual(metrics["floatMarketCap"], "¥9876.00亿")
        self.assertEqual(metrics["totalShares"], "10.00亿股")
        self.assertEqual(metrics["pe"], "25.34")
        self.assertEqual(metrics["pb"], "4.81")
        self.assertEqual(metrics["turnover"], "2.67%")

    def test_region_is_inferred_from_address_and_market(self):
        a_identity = market.company_identity("A股", "600519")
        hk_identity = market.company_identity("港股", "0700")
        us_identity = market.company_identity("美股", "AAPL")
        self.assertIsNotNone(a_identity)
        self.assertEqual(
            enrichment.infer_region(
                {"company": {"address": "贵州省遵义市仁怀市茅台镇"}},
                a_identity,
            ),
            "贵州",
        )
        self.assertEqual(enrichment.infer_region({"company": {}}, hk_identity), "中国香港")
        self.assertEqual(enrichment.infer_region({"company": {}}, us_identity), "美国")

    def test_explicit_region_is_read_from_merged_company_page(self):
        identity = market.company_identity("A股", "688256")
        parsed = enriched_runner.parse_tonghuashun_html(
            "<html><head><title>寒武纪(688256)</title></head>"
            "<body><table><tr><td>公司名称</td><td>中科寒武纪科技股份有限公司</td></tr>"
            "<tr><td>所属地域</td><td>北京</td></tr></table></body></html>",
            identity,
            "寒武纪",
        )
        self.assertEqual(parsed["company"]["region"], "北京")

    def test_navigation_noise_is_rejected_and_previous_copy_is_preserved(self):
        current = {
            "company": {
                "name": "宁德时代",
                "industry": "总市值： -- 亿",
                "description": "所属地域。 经营分析。",
                "mainBusiness": "经营分析。",
            }
        }
        previous = {
            "company": {
                "name": "宁德时代",
                "industry": "电力设备 — 电池",
                "description": "公司主营动力电池、储能电池和电池回收业务。",
                "mainBusiness": "动力电池与储能系统研发、生产和销售。",
            }
        }
        cleaned = enriched_runner.preserve_company_copy(current, previous)
        self.assertEqual(cleaned["company"]["industry"], "电力设备 — 电池")
        self.assertIn("动力电池", cleaned["company"]["description"])
        self.assertIn("储能系统", cleaned["company"]["mainBusiness"])

    def test_inconsistent_provider_ohlc_is_dropped_without_price_rewrite(self):
        profile = {
            "status": "ok",
            "priceHistory": [
                {
                    "date": "2026-09-01",
                    "open": 37.86,
                    "close": 37.78,
                    "high": 39.25,
                    "low": 37.59,
                    "volume": 14_071_700,
                },
                {
                    "date": "2026-09-02",
                    "open": 38.0,
                    "close": 38.5,
                    "high": 38.4,
                    "low": 37.8,
                    "volume": 100,
                },
                {
                    "date": "2026-09-03",
                    "open": 39.0,
                    "close": 39.2,
                    "high": 39.5,
                    "low": 39.1,
                    "volume": 200,
                },
            ],
            "warnings": [],
        }

        cleaned = enriched_runner.filter_inconsistent_price_history(profile)

        self.assertEqual(
            cleaned["priceHistory"],
            [
                {
                    "date": "2026-09-01",
                    "open": 37.86,
                    "close": 37.78,
                    "high": 39.25,
                    "low": 37.59,
                    "volume": 14_071_700,
                }
            ],
        )
        self.assertEqual(cleaned["status"], "partial")
        self.assertTrue(
            any(
                "已过滤2条 OHLC 不一致或非数值日线" in warning
                and "未改写任何价格字段" in warning
                for warning in cleaned["warnings"]
            )
        )

    def test_valid_ohlc_contract_matches_strict_snapshot_validator(self):
        self.assertTrue(
            enriched_runner.valid_ohlc_point(
                {"open": 10, "close": 11, "high": 11, "low": 10}
            )
        )
        self.assertFalse(
            enriched_runner.valid_ohlc_point(
                {"open": 10, "close": 11, "high": 10.99, "low": 10}
            )
        )
        self.assertFalse(
            enriched_runner.valid_ohlc_point(
                {"open": 10, "close": 11, "high": 12, "low": "not-a-number"}
            )
        )

    def test_description_removes_award_tail_and_closes_sentence(self):
        raw = (
            "公司主营人工智能芯片研发、设计与销售，产品覆盖云端、边缘和终端设备。"
            "公司成立至今共获得多项荣誉：2018年获得某奖项，2019年入选某榜单。"
        )
        normalized = enrichment.normalize_company_text(raw, 180)
        self.assertIn("人工智能芯片", normalized)
        self.assertNotIn("多项荣誉", normalized)
        self.assertTrue(normalized.endswith("。"))

    def test_market_cap_can_be_derived_from_shares_and_close(self):
        identity = market.company_identity("港股", "0700")
        profile = {
            "company": {"name": "腾讯控股"},
            "metrics": [{"id": "totalShares", "label": "总股本", "value": "95.00亿股"}],
            "priceHistory": [{"date": "2026-07-24", "close": 500.0}],
        }
        metric = enrichment.infer_market_cap(profile, identity)
        self.assertEqual(metric["id"], "marketCap")
        self.assertEqual(metric["value"], "HK$4.75万亿")

    def test_enrichment_replaces_unit_only_market_cap(self):
        identity = market.company_identity("美股", "AAPL")
        profile = {
            "company": {"name": "Apple", "description": "消费电子与软件服务。"},
            "metrics": [{"id": "marketCap", "label": "总市值", "value": "亿"}],
            "priceHistory": [],
            "sources": {},
        }
        body = json.dumps({"data": {"f116": 3_200_000_000_000}})
        enriched = enrichment.enrich_profile(identity, profile, lambda _: body)
        metrics = {item["id"]: item["value"] for item in enriched["metrics"]}
        self.assertEqual(metrics["marketCap"], "US$3.20万亿")
        self.assertEqual(enriched["company"]["region"], "美国")


if __name__ == "__main__":
    unittest.main()
