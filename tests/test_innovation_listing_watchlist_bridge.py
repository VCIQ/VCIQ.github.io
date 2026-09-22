import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote_plus

from tools import crawl_with_innovation_listing_watchlist as bridge


class InnovationListingWatchlistBridgeTests(unittest.TestCase):
    def test_load_watchlist_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            self.assertEqual(
                bridge.load_watchlist(missing),
                {"brokers": [], "projects": [], "policyThemes": []},
            )

    def test_generates_broker_ah_policy_and_project_discovery_sources(self) -> None:
        payload = {
            "brokers": ["中信证券", "中金公司"],
            "policyThemes": ["人工智能", "量子科技", "低空经济", "新型储能", "具身智能"],
            "projects": [
                {"company": "甲科技股份有限公司"},
                {"company": "乙航天股份有限公司"},
            ],
        }
        sources = bridge.generated_innovation_sources(payload)
        ids = {item["id"] for item in sources}
        self.assertIn("innovation-listing-broker-01", ids)
        self.assertIn("innovation-listing-broker-02", ids)
        self.assertIn("innovation-listing-primary-broker-01-01", ids)
        self.assertIn("innovation-listing-primary-regulatory-01-01", ids)
        self.assertIn("innovation-listing-a-plus-h-01", ids)
        self.assertIn("innovation-listing-a-plus-h-02", ids)
        self.assertIn("innovation-listing-policy-01", ids)
        self.assertIn("innovation-listing-policy-02", ids)
        self.assertIn("innovation-listing-projects-01", ids)
        discovery = [
            item for item in sources
            if "primary-" not in item["id"]
        ]
        self.assertTrue(all(item["sourceLevel"] == "待交叉验证" for item in discovery))
        self.assertTrue(all(item["sourceCategory"] == "company" for item in sources))

    def test_primary_sources_are_host_bounded_and_promoted_as_primary_evidence(self) -> None:
        payload = {
            "brokers": ["中信证券"],
            "policyThemes": [],
            "projects": [],
        }
        sources = {
            item["id"]: item for item in bridge.generated_innovation_sources(payload)
        }
        broker = sources["innovation-listing-primary-broker-01-01"]
        regulator = sources["innovation-listing-primary-regulatory-01-01"]

        self.assertEqual(broker["sourceLevel"], "官方披露")
        self.assertEqual(broker["allowedHosts"], ["citics.com"])
        self.assertIn("site:citics.com", unquote_plus(broker["url"]))
        self.assertIn("中信证券", unquote_plus(broker["url"]))

        self.assertEqual(regulator["sourceLevel"], "监管文件")
        self.assertEqual(regulator["allowedHosts"], ["eid.csrc.gov.cn"])
        self.assertIn("site:eid.csrc.gov.cn", unquote_plus(regulator["url"]))
        self.assertIn("辅导备案", unquote_plus(regulator["url"]))

    def test_policy_discovery_requires_broker_and_hard_tech_context(self) -> None:
        payload = {
            "brokers": ["中信证券", "中金公司"],
            "policyThemes": ["人工智能", "量子科技", "具身智能"],
            "projects": [],
        }
        source = next(
            item
            for item in bridge.generated_innovation_sources(payload)
            if item["id"] == "innovation-listing-policy-01"
        )
        decoded = unquote_plus(source["url"])
        self.assertIn("中信证券", decoded)
        self.assertIn("中金公司", decoded)
        self.assertIn("人工智能", decoded)
        self.assertIn("量子科技", decoded)
        self.assertIn("辅导", decoded)

    def test_a_plus_h_discovery_keeps_broker_identity(self) -> None:
        payload = {
            "brokers": ["华泰联合"],
            "policyThemes": [],
            "projects": [],
        }
        source = next(
            item
            for item in bridge.generated_innovation_sources(payload)
            if item["id"] == "innovation-listing-a-plus-h-01"
        )
        decoded = unquote_plus(source["url"])
        self.assertIn("华泰联合", decoded)
        self.assertIn("A+H", decoded)
        self.assertIn("港交所", decoded)

    def test_project_progress_source_contains_listing_lifecycle_terms(self) -> None:
        payload = {
            "brokers": [],
            "policyThemes": [],
            "projects": [{"company": "测试量子科技股份有限公司"}],
        }
        source = bridge.generated_innovation_sources(payload)[0]
        decoded = unquote_plus(source["url"])
        self.assertIn("受理", decoded)
        self.assertIn("撤回", decoded)
        self.assertIn("A+H", decoded)


if __name__ == "__main__":
    unittest.main()
