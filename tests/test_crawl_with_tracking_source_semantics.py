from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from tools import crawl_with_tracking as tracking_crawl


class TrackingSourceSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracks = tracking_crawl._enabled_tracks(
            {
                "tracks": [
                    {
                        "slug": "ai",
                        "name": "AI / AGI",
                        "keywords": ["大模型", "AI 芯片"],
                        "people": [],
                        "sampleCompanies": ["OpenAI"],
                        "enabled": True,
                    }
                ]
            }
        )

    @staticmethod
    def _query(spec: dict) -> str:
        return parse_qs(urlsplit(spec["url"]).query)["q"][0]

    def test_media_listing_source_uses_broad_intelligence_discovery(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "media-example",
                    "name": "Example Tech Media",
                    "url": "https://news.example.com/",
                    "sourceType": "listing-search",
                    "sourceCategory": "media",
                    "sector": "AI / AGI",
                    "keywords": ["推理芯片"],
                    "region": "全球",
                    "enabled": True,
                }
            ]
        }

        specs, sec_specs = tracking_crawl._custom_sources(tracking, self.tracks)

        self.assertEqual(sec_specs, {})
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        query = self._query(spec)
        self.assertEqual(spec["platform"], "用户媒体来源")
        self.assertEqual(spec["sourceLevel"], "待交叉验证")
        self.assertEqual(spec["sourceCategory"], "media")
        self.assertEqual(spec["allowedHosts"], ["news.example.com"])
        self.assertNotIn("company", spec)
        self.assertNotIn("companySlug", spec)
        self.assertTrue(query.startswith("site:news.example.com "))
        self.assertIn('"推理芯片"', query)
        self.assertIn('"大模型"', query)
        self.assertIn("技术 OR technology", query)
        self.assertIn("政策 OR policy", query)
        self.assertIn("产品 OR product", query)
        self.assertIn("科研 OR research", query)
        self.assertIn("投资 OR investment", query)
        self.assertNotIn('"Example Tech Media"', query)

    def test_company_listing_source_retains_company_event_filter(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "company-example",
                    "name": "OpenAI Newsroom",
                    "company": "OpenAI",
                    "ticker": "",
                    "url": "https://openai.com/news/",
                    "sourceType": "listing-search",
                    "sourceCategory": "company",
                    "sector": "AI / AGI",
                    "keywords": ["GPT"],
                    "region": "美国",
                    "enabled": True,
                }
            ]
        }

        specs, _ = tracking_crawl._custom_sources(tracking, self.tracks)

        spec = specs[0]
        query = self._query(spec)
        self.assertEqual(spec["platform"], "用户公司来源")
        self.assertEqual(spec["allowedHosts"], ["openai.com"])
        self.assertEqual(spec["company"], "OpenAI")
        self.assertEqual(spec["companySlug"], "openai")
        self.assertIn('"OpenAI"', query)
        self.assertIn("IPO OR listing OR filing OR earnings", query)
        self.assertIn("上市 OR 公告 OR 财报 OR 融资", query)
        self.assertNotIn("政策 OR policy", query)

    def test_media_rss_keeps_feed_but_drops_company_attribution(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "media-rss",
                    "name": "Technology Review",
                    "url": "https://www.technologyreview.com/feed/",
                    "sourceType": "rss",
                    "sourceCategory": "media",
                    "sector": "AI / AGI",
                    "keywords": ["人工智能"],
                    "region": "美国",
                    "enabled": True,
                }
            ]
        }

        specs, _ = tracking_crawl._custom_sources(tracking, self.tracks)

        spec = specs[0]
        self.assertEqual(spec["url"], "https://www.technologyreview.com/feed/")
        self.assertEqual(spec["platform"], "用户媒体来源")
        self.assertNotIn("allowedHosts", spec)
        self.assertNotIn("company", spec)
        self.assertNotIn("companySlug", spec)

    def test_missing_category_preserves_legacy_company_semantics(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "legacy-source",
                    "name": "Legacy Company Source",
                    "company": "Legacy Labs",
                    "url": "https://legacy.example.com/",
                    "sourceType": "listing-search",
                    "sector": "AI / AGI",
                    "enabled": True,
                }
            ]
        }

        specs, _ = tracking_crawl._custom_sources(tracking, self.tracks)

        spec = specs[0]
        self.assertEqual(spec["sourceCategory"], "company")
        self.assertEqual(spec["platform"], "用户公司来源")
        self.assertEqual(spec["company"], "Legacy Labs")
        self.assertIn("filing", self._query(spec))


if __name__ == "__main__":
    unittest.main()
