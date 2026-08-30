from __future__ import annotations

import unittest
from urllib.parse import unquote_plus

from tools import wechat_source_registry as registry


class WeChatSourceRegistryTest(unittest.TestCase):
    def test_configured_accounts_are_additive_to_generic_sector_source(self) -> None:
        tracks = [
            {
                "slug": "semiconductor",
                "name": "半导体",
                "keywords": ["HBM", "先进封装"],
                "people": ["黄仁勋"],
                "sampleCompanies": ["英伟达", "中芯国际"],
            }
        ]
        sources = registry.generated_wechat_sources(tracks, object())
        names = {source["name"] for source in sources}
        self.assertIn("微信公众号 · 半导体", names)
        self.assertIn("半导体行业观察", names)
        self.assertIn("集微网", names)

        generic = next(source for source in sources if source.get("genericDiscovery"))
        self.assertEqual(generic["sector"], "半导体")
        self.assertEqual(generic["discoveryScope"], "track")
        self.assertNotIn("expectedAccounts", generic)
        self.assertEqual(generic["queryIdentity"], "半导体")
        self.assertIn("中芯国际", generic["trackedCompanies"])

        account_sources = [
            source for source in sources if source.get("discoveryScope") == "account"
        ]
        self.assertGreaterEqual(len(account_sources), 2)
        for source in account_sources:
            self.assertEqual(source["sector"], "半导体")
            self.assertEqual(source["adapter"], "wechat_search")
            self.assertTrue(source.get("expectedAccounts"))
            self.assertIn("mp.weixin.qq.com", source["url"])
            self.assertIn("中芯国际", source["trackedCompanies"])

    def test_unconfigured_track_keeps_generic_discovery(self) -> None:
        tracks = [
            {
                "slug": "space",
                "name": "商业航天",
                "keywords": ["可复用火箭"],
                "people": ["埃隆·马斯克 @elonmusk"],
                "sampleCompanies": ["SpaceX"],
            }
        ]
        sources = registry.generated_wechat_sources(tracks, object())
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["name"], "微信公众号 · 商业航天")
        self.assertTrue(sources[0]["genericDiscovery"])
        self.assertNotIn("expectedAccounts", sources[0])
        self.assertIn("SpaceX", sources[0]["trackedCompanies"])

    def test_new_empty_custom_track_is_still_crawlable_by_name(self) -> None:
        tracks = [
            {
                "slug": "custom-neurotech",
                "name": "脑机接口",
                "keywords": [],
                "people": [],
                "sampleCompanies": [],
                "custom": True,
            }
        ]
        sources = registry.generated_wechat_sources(tracks, object())
        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source["sector"], "脑机接口")
        self.assertIn("脑机接口", source["keywords"])
        self.assertIn("脑机接口", unquote_plus(source["url"]))
        self.assertTrue(source["genericDiscovery"])

    def test_all_tracks_receive_a_generic_source_without_global_truncation(self) -> None:
        tracks = [
            {
                "slug": f"custom-{index}",
                "name": f"自定义赛道{index}",
                "keywords": [f"关键词{index}"],
                "people": [],
                "sampleCompanies": [],
            }
            for index in range(100)
        ]
        sources = registry.generated_wechat_sources(tracks, object())
        generic_sectors = {
            source["sector"] for source in sources if source.get("genericDiscovery")
        }
        self.assertEqual(len(generic_sectors), 100)
        self.assertIn("自定义赛道99", generic_sectors)

    def test_account_name_must_match_whitelist(self) -> None:
        spec = {"expectedAccounts": ["量子位", "qbitai"]}
        self.assertTrue(registry.account_matches(spec, "量子位"))
        self.assertTrue(registry.account_matches(spec, "量子位Pro"))
        self.assertFalse(registry.account_matches(spec, "量子"))
        self.assertFalse(
            registry.account_matches(
                {"expectedAccounts": ["芯潮IC"]},
                "IC",
            )
        )
        self.assertFalse(registry.account_matches(spec, "无关科技媒体"))
        self.assertFalse(registry.account_matches(spec, ""))


if __name__ == "__main__":
    unittest.main()
