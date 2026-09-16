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

    def test_query_shards_become_independent_risk_investment_sources(self) -> None:
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
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["sector"], "风险投资")
        self.assertEqual(sources[0]["platform"], "科创板投资机构追踪")
        self.assertTrue(sources[0]["id"].startswith(bridge.SOURCE_PREFIX))
        self.assertIn("Intel+Capital", sources[0]["url"])
        self.assertIn("%E6%B7%B1%E5%88%9B%E6%8A%95%E9%9B%86%E5%9B%A2", sources[0]["url"])
        self.assertIn("investment", sources[0]["url"])
        self.assertEqual(sources[1]["keywords"], ["高瓴投资"])

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
        source = bridge.generated_star_vc_sources(payload)[0]
        self.assertEqual(len(source["keywords"]), 8)
        self.assertIn("机构7", source["keywords"])
        self.assertNotIn("机构8", source["keywords"])


if __name__ == "__main__":
    unittest.main()
