import json
import unittest
from unittest.mock import patch
from urllib.robotparser import RobotFileParser

from tools import wechat_collection_preview as preview


class WechatCollectionPreviewTest(unittest.TestCase):
    def test_publisher_links_are_deduplicated_and_bound_to_the_official_host(self):
        parser = preview.PublisherPage()
        parser.feed('''
          <a href="/p/123.html">article</a><a href="https://www.zhidx.com/p/123.html">again</a>
          <a href="https://another.example/p/124.html">external</a>
          <a href="/p/125.html?utm_source=tracking">query</a>
        ''')
        self.assertEqual(list(parser.links), ["https://www.zhidx.com/p/123.html"])

    def test_candidate_uses_only_the_matching_structured_news_record(self):
        url = "https://www.zhidx.com/p/123.html"
        record = {"@type": "NewsArticle", "url": url, "headline": "智东西的  公开报道",
                  "datePublished": "2026-11-10T23:00:00+08:00", "articleBody": "excluded"}
        data = '<script type="application/ld+json">' + json.dumps(record) + '</script>'
        self.assertEqual(preview.publisher_candidate(url, data), {
            "sourceKind": "publisher-website", "publisher": "智东西", "title": "智东西的 公开报道",
            "publishedAt": "2026-11-10", "url": url,
        })
        with self.assertRaisesRegex(preview.SourceUnavailable, "article_metadata_missing"):
            preview.publisher_candidate("https://www.zhidx.com/p/124.html", data)

    def test_disallowed_robot_path_never_reaches_the_fetcher(self):
        robots = RobotFileParser()
        robots.parse(["User-agent: *", "Disallow: /p/"])
        with patch.object(preview, "read_page") as read:
            with self.assertRaisesRegex(preview.SourceUnavailable, "robots_disallowed"):
                preview.read_html(preview.PUBLISHER_INDEX, robots)
            read.assert_not_called()
