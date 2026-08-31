from __future__ import annotations

import unittest
from types import SimpleNamespace

from tools import crawl_articles
from tools import wechat_official_index_bridge as target
from tools import wechat_public_sources as wechat
from tools import wechat_registry_bridge as bridge


class WeChatOfficialIndexBridgeTests(unittest.TestCase):
    def test_extracts_only_relevant_links_from_explicitly_allowed_host(self) -> None:
        original_wechat = bridge._WECHAT
        bridge._WECHAT = wechat
        try:
            spec = {
                "name": "量子位",
                "publisherEntity": "量子位",
                "officialCrosspostHosts": ["qbitai.com"],
                "acceptedSourceKinds": ["wechat-original", "official-website"],
                "keywords": ["大模型", "AI4S"],
                "trackedCompanies": ["OpenAI", "紫东太初"],
                "trackedPeople": [],
                "maxItems": 6,
            }
            body = """
            <html><body>
              <a href="https://www.qbitai.com/">量子位首页</a>
              <a href="https://www.qbitai.com/about">关于我们</a>
              <a href="https://www.qbitai.com/2026/08/479096.html">
                AI4S开始进入项目时代：紫东太初发布新进展
              </a>
              <a href="https://example.com/2026/08/wrong.html">
                OpenAI发布新大模型
              </a>
            </body></html>
            """

            rows = target.extract_official_index_rows(
                body,
                "https://www.qbitai.com/2026/",
                spec,
                crawl_articles,
                bridge,
            )

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["kind"], "official")
            self.assertEqual(
                rows[0]["url"],
                "https://www.qbitai.com/2026/08/479096.html",
            )
        finally:
            bridge._WECHAT = original_wechat

    def test_non_whitelisted_index_is_not_promoted(self) -> None:
        spec = {
            "officialCrosspostHosts": ["qbitai.com"],
            "keywords": ["大模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": [],
        }
        body = """
        <a href="https://random.example/article">OpenAI发布大模型进展</a>
        """

        rows = target.extract_official_index_rows(
            body,
            "https://random.example/",
            spec,
            crawl_articles,
            bridge,
        )

        self.assertEqual(rows, [])

    def test_source_kind_allowlist_remains_mandatory(self) -> None:
        spec = {"acceptedSourceKinds": ["wechat-original", "official-crosspost"]}
        self.assertTrue(target.source_kind_allowed(spec, "wechat-original"))
        self.assertTrue(target.source_kind_allowed(spec, "official-crosspost"))
        self.assertFalse(target.source_kind_allowed(spec, "official-website"))

    def test_platform_labels_are_loaded_from_registry(self) -> None:
        labels = target._platform_labels()
        # This assertion becomes active when the cross-platform registry patch is
        # applied; Sohu remains handled by the legacy bridge itself.
        self.assertEqual(labels.get("leiphone.com"), "雷峰网认证作者页")
        self.assertEqual(labels.get("m.leiphone.com"), "雷峰网认证作者页")


if __name__ == "__main__":
    unittest.main()
