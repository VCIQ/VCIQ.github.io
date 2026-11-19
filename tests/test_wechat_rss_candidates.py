"""Guard staged third-party WeChat RSS candidates without running any crawl."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.crawl_articles import parse_feed_items

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "config" / "intelligence_sources.json"
FEED_PREFIX = "wechat-rss-"
APPROVED_FEED_HOSTS = {
    "wechat2rss.xlab.app",
    "wechat2rss.bestblogs.dev",
    "raw.githubusercontent.com",
}
EXPECTED_COUNT = 23


class WechatRssCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        cls.candidates = [
            feed for feed in cls.config["feeds"]
            if feed["id"].startswith(FEED_PREFIX)
        ]

    def test_all_candidates_staged_with_unique_ids_and_urls(self):
        self.assertEqual(len(self.candidates), EXPECTED_COUNT)
        ids = [feed["id"] for feed in self.candidates]
        urls = [feed["url"] for feed in self.candidates]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(len(self.config["feeds"]), EXPECTED_COUNT + 11)

    def test_no_candidate_is_live_without_explicit_owner_approval(self):
        for feed in self.candidates:
            with self.subTest(name=feed["name"]):
                self.assertIs(feed["enabled"], False)
                self.assertEqual(feed["adapter"], "rss")
                self.assertEqual(feed["platform"], "微信公众号线索")
                self.assertEqual(feed["sourceLevel"], "媒体报道")
                self.assertEqual(feed["allowedHosts"], ["mp.weixin.qq.com"])
                self.assertLessEqual(feed["maxItems"], 4)
                self.assertTrue(feed["name"])

    def test_transport_hosts_are_scoped_to_supplied_providers(self):
        from urllib.parse import urlsplit

        for feed in self.candidates:
            with self.subTest(name=feed["name"]):
                self.assertEqual(urlsplit(feed["url"]).scheme, "https")
                self.assertIn(urlsplit(feed["url"]).hostname, APPROVED_FEED_HOSTS)

    def test_parser_accepts_wechat_original_url_and_rejects_offsite_url(self):
        spec = self.candidates[0]
        xml = (
            '<rss version="2.0"><channel><title>样例</title>'
            '<item><title>AI 模型发布</title>'
            '<link>https://mp.weixin.qq.com/s?__biz=abc&amp;mid=123</link>'
            '<description>公众号测试</description>'
            '<pubDate>Wed, 18 Nov 2026 08:00:00 GMT</pubDate></item>'
            '<item><title>错误链接</title><link>https://evil.example/123</link>'
            '<pubDate>Wed, 18 Nov 2026 08:00:00 GMT</pubDate></item>'
            '</channel></rss>'
        )
        items = parse_feed_items(xml, spec)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["sourceId"], spec["id"])
        self.assertEqual(items[0]["source"]["name"], spec["name"])
        self.assertEqual(items[0]["source"]["platform"], "微信公众号线索")
        self.assertTrue(
            items[0]["source"]["url"].startswith("https://mp.weixin.qq.com/")
        )


    def test_same_wechat_broadcast_distinct_idx_are_distinct_articles(self):
        spec = self.candidates[0]
        # One WeChat broadcast (same __biz and mid) can contain many articles.
        xml = (
            '<rss version="2.0"><channel><title>样例</title>'
            '<item><title>技术新闻一</title>'
            '<link>https://mp.weixin.qq.com/s?__biz=abc&amp;mid=123&amp;idx=1</link>'
            '<pubDate>Wed, 18 Nov 2026 08:00:00 GMT</pubDate></item>'
            '<item><title>技术新闻二</title>'
            '<link>https://mp.weixin.qq.com/s?__biz=abc&amp;mid=123&amp;idx=2</link>'
            '<pubDate>Wed, 18 Nov 2026 08:00:00 GMT</pubDate></item>'
            '</channel></rss>'
        )
        rows = parse_feed_items(xml, spec)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])
        self.assertNotEqual(rows[0]["source"]["url"], rows[1]["source"]["url"])


if __name__ == "__main__":
    unittest.main()
