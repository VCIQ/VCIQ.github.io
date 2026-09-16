import tempfile
import unittest
from pathlib import Path

from tools import crawl_with_star_vc_watchlist as bridge


class StarVcWatchlistBridgeTests(unittest.TestCase):
    def test_missing_watchlist_is_safe_empty_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = bridge.load_watchlist(Path(tmp) / "missing.json")
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["queryShards"], [])

    def test_query_shards_become_bilingual_google_news_sources(self) -> None:
        payload = {
            "schemaVersion": 1,
            "queryShards": [
                {
                    "id": "star-vc-001",
                    "institutionNames": ["Intel Capital", "深创投集团", "启明创投"],
                },
                {
                    "id": "star-vc-002",
                    "institutionNames": ["高瓴投资"],
                },
            ],
        }
        sources = bridge.generated_star_vc_sources(payload)
        self.assertEqual(len(sources), 4)

        cn_source, us_source, second_cn, second_us = sources
        self.assertEqual(cn_source["sector"], "风险投资")
        self.assertEqual(cn_source["platform"], "Google News")
        self.assertEqual(cn_source["region"], "中国")
        self.assertEqual(us_source["region"], "美国")
        self.assertTrue(cn_source["id"].endswith("-google-cn"))
        self.assertTrue(us_source["id"].endswith("-google-us"))
        self.assertTrue(cn_source["id"].startswith(bridge.SOURCE_PREFIX))
        self.assertIn("news.google.com/rss/search", cn_source["url"])
        self.assertIn("hl=zh-CN", cn_source["url"])
        self.assertIn("hl=en-US", us_source["url"])
        self.assertIn("Intel+Capital", cn_source["url"])
        self.assertIn("%E6%B7%B1%E5%88%9B%E6%8A%95%E9%9B%86%E5%9B%A2", cn_source["url"])
        self.assertIn("investment", cn_source["url"])
        self.assertNotIn("bing.com", cn_source["url"])
        self.assertEqual(second_cn["keywords"], ["高瓴投资"])
        self.assertEqual(second_us["keywords"], ["高瓴投资"])

    def test_source_builder_honors_eight_name_shard_bound(self) -> None:
        payload = {
            "schemaVersion": 1,
            "queryShards": [
                {
                    "id": "oversized",
                    "institutionNames": [f"机构{i}" for i in range(12)],
                }
            ],
        }
        sources = bridge.generated_star_vc_sources(payload)
        self.assertEqual(len(sources), 2)
        for source in sources:
            self.assertEqual(len(source["keywords"]), 8)
            self.assertIn("机构7", source["keywords"])
            self.assertNotIn("机构8", source["keywords"])


if __name__ == "__main__":
    unittest.main()
