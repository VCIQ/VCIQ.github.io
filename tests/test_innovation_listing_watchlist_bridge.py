import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote_plus

from tools import crawl_with_innovation_listing_watchlist as bridge


class InnovationListingWatchlistBridgeTests(unittest.TestCase):
    def test_load_watchlist_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            self.assertEqual(bridge.load_watchlist(missing), {"brokers": [], "projects": []})

    def test_generates_broker_and_project_discovery_sources(self) -> None:
        payload = {
            "brokers": ["中信证券", "中金公司"],
            "projects": [
                {"company": "甲科技股份有限公司"},
                {"company": "乙航天股份有限公司"},
            ],
        }
        sources = bridge.generated_innovation_sources(payload)
        ids = {item["id"] for item in sources}
        self.assertIn("innovation-listing-broker-01", ids)
        self.assertIn("innovation-listing-broker-02", ids)
        self.assertIn("innovation-listing-projects-01", ids)
        self.assertTrue(all(item["sourceLevel"] == "待交叉验证" for item in sources))
        self.assertTrue(all(item["sourceCategory"] == "company" for item in sources))

    def test_project_progress_source_contains_listing_lifecycle_terms(self) -> None:
        payload = {
            "brokers": [],
            "projects": [{"company": "测试量子科技股份有限公司"}],
        }
        source = bridge.generated_innovation_sources(payload)[0]
        decoded = unquote_plus(source["url"])
        self.assertIn("受理", decoded)
        self.assertIn("撤回", decoded)
        self.assertIn("A+H", decoded)


if __name__ == "__main__":
    unittest.main()
