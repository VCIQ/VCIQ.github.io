from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tools import crawl_articles as crawler
from tools import crawl_with_source_categories as categories
from tools import generic_web_sources as generic


class LanguageAwareSourceTests(unittest.TestCase):
    def test_language_detection_and_keyword_expansion(self) -> None:
        self.assertEqual(generic.detect_language("https://tw.yahoo.com/?p=us"), "zh-Hant")
        self.assertEqual(generic.detect_language("https://www.youtube.com/"), "en")
        traditional = generic.localize_keywords(["人工智能", "半导体", "融资"], "zh-Hant")
        english = generic.localize_keywords(["人工智能", "半导体", "融资"], "en")
        self.assertIn("人工智慧", traditional)
        self.assertIn("半導體", traditional)
        self.assertIn("融資", traditional)
        self.assertIn("artificial intelligence", english)
        self.assertIn("semiconductor", english)
        self.assertIn("funding", english)

    def test_media_website_routes_to_bounded_discovery_without_company_entity(self) -> None:
        tracks = [
            {
                "slug": "ai",
                "name": "AI / AGI",
                "keywords": ["推理模型"],
                "people": [],
                "sampleCompanies": ["OpenAI"],
            }
        ]
        runtime, sec = categories._custom_sources(
            {
                "sources": [
                    {
                        "id": "yahoo-tw",
                        "name": "Yahoo奇摩",
                        "url": "https://tw.yahoo.com/?p=us",
                        "sourceType": "listing-search",
                        "sourceCategory": "media",
                        "region": "全球",
                        "sector": "AI / AGI",
                        "company": "Yahoo",
                        "ticker": "",
                        "keywords": [],
                        "enabled": True,
                    }
                ]
            },
            tracks,
        )
        self.assertEqual(sec, {})
        spec = runtime[0]
        query = parse_qs(urlsplit(spec["url"]).query)["q"][0]
        self.assertEqual(spec["adapter"], "rss")
        self.assertEqual(spec["platform"], "用户媒体来源")
        self.assertEqual(spec["sourceLevel"], "待交叉验证")
        self.assertEqual(spec["sourceUrl"], "https://tw.yahoo.com/")
        self.assertEqual(spec["allowedHosts"], ["tw.yahoo.com"])
        self.assertTrue(query.startswith("site:tw.yahoo.com "))
        self.assertIn('"推理模型"', query)
        self.assertIn("技术 OR technology", query)
        self.assertIn("政策 OR policy", query)
        self.assertNotIn("company", spec)
        self.assertNotIn("companySlug", spec)

    def test_yahoo_subdomain_article_is_discovered_with_traditional_terms(self) -> None:
        source_url = "https://tw.yahoo.com/?p=us"
        article_url = "https://tw.news.yahoo.com/ai-startup-funding-20260725.html"
        index = (
            f'<html lang="zh-Hant-TW"><body><a href="{article_url}">'
            "人工智慧新創完成融資</a></body></html>"
        )
        article = """
        <html lang="zh-Hant-TW"><head>
          <meta property="og:title" content="人工智慧新創完成新一輪融資">
          <meta property="og:description" content="公司將資金投入推理模型與多模態產品。">
          <meta property="article:published_time" content="2026-07-25T08:00:00+08:00">
        </head><body><h1>人工智慧新創完成新一轮融資</h1></body></html>
        """
        spec = {
            "id": "user-source-yahoo",
            "name": "Yahoo奇摩",
            "url": source_url,
            "sourceUrl": source_url,
            "adapter": "generic_web",
            "sourceCategory": "media",
            "sourceLevel": "媒体报道",
            "region": "全球",
            "sector": "AI / AGI",
            "keywords": ["人工智能", "融资", "推理模型"],
            "maxItems": 1,
        }

        def fetch(url: str, *_args, **_kwargs) -> str:
            if url == source_url:
                return index
            if url == article_url:
                return article
            raise AssertionError(f"unexpected URL: {url}")

        with patch.object(crawler, "fetch_text", side_effect=fetch):
            items, status = generic.crawl_generic_source(spec, "test-agent", crawler)

        self.assertEqual(status["status"], "ok")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["publishedAt"], "2026-07-25")
        self.assertEqual(items[0]["source"]["url"], article_url)

    def test_youtube_video_page_is_discovered_with_english_terms(self) -> None:
        source_url = "https://www.youtube.com/"
        video_url = "https://www.youtube.com/watch?v=abc123"
        index = (
            '<html lang="en"><body><a href="/watch?v=abc123">'
            "New semiconductor AI chip architecture</a></body></html>"
        )
        video = """
        <html lang="en"><head>
          <meta property="og:title" content="New semiconductor AI chip architecture">
          <meta property="og:description" content="A technical discussion of inference accelerators.">
          <script type="application/ld+json">
            {"datePublished":"2026-07-24","uploadDate":"2026-07-24"}
          </script>
        </head><body><h1>New semiconductor AI chip architecture</h1></body></html>
        """
        spec = {
            "id": "user-source-youtube",
            "name": "YouTube",
            "url": source_url,
            "sourceUrl": source_url,
            "adapter": "generic_web",
            "sourceCategory": "media",
            "sourceLevel": "媒体报道",
            "region": "全球",
            "sector": "半导体",
            "keywords": ["半导体", "AI 芯片", "推理芯片"],
            "maxItems": 1,
        }

        def fetch(url: str, *_args, **_kwargs) -> str:
            if url == source_url:
                return index
            if url == video_url:
                return video
            raise AssertionError(f"unexpected URL: {url}")

        with patch.object(crawler, "fetch_text", side_effect=fetch):
            items, status = generic.crawl_generic_source(spec, "test-agent", crawler)

        self.assertEqual(status["status"], "ok")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["publishedAt"], "2026-07-24")
        self.assertEqual(items[0]["source"]["url"], video_url)


if __name__ == "__main__":
    unittest.main()
