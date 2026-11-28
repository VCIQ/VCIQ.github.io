import unittest

from tools.prelisting_article_evidence import (
    extract_article_evidence,
    is_safe_public_http_url,
)


class PrelistingArticleEvidenceTests(unittest.TestCase):
    def test_extracts_article_metadata_and_jsonld_body(self):
        html = """<!doctype html><html><head>
        <title>杉数科技完成D轮融资</title>
        <link rel="canonical" href="https://news.example.com/article/1">
        <meta property="og:site_name" content="示例财经">
        <meta property="og:description" content="杉数科技宣布完成D轮融资">
        <meta property="article:published_time" content="2026-11-22T08:00:00+08:00">
        <script type="application/ld+json">
        {"@type":"NewsArticle","articleBody":"杉数科技完成D轮融资，红杉中国领投。","datePublished":"2026-11-22T08:00:00+08:00","author":{"name":"记者甲"},"publisher":{"name":"示例财经"}}
        </script></head><body><p>正文摘要</p></body></html>"""
        result = extract_article_evidence(html)
        self.assertEqual(result["htmlTitle"], "杉数科技完成D轮融资")
        self.assertEqual(result["publishedTime"], "2026-11-22T08:00:00+08:00")
        self.assertEqual(result["canonicalUrl"], "https://news.example.com/article/1")
        self.assertEqual(result["publisherName"], "示例财经")
        self.assertEqual(result["authorNames"], ["记者甲"])
        self.assertIn("红杉中国领投", result["articleBody"])
        self.assertEqual(result["bodyExtractionMethod"], "jsonld_articleBody")

    def test_falls_back_to_visible_text_without_scripts(self):
        result = extract_article_evidence("<html><body><p>公开新闻正文内容</p></body></html>")
        self.assertIn("公开新闻正文内容", result["articleBody"])
        self.assertEqual(result["bodyExtractionMethod"], "visible_text_fallback")

    def test_rejects_non_http_and_private_urls(self):
        self.assertFalse(is_safe_public_http_url("file:///etc/passwd"))
        self.assertFalse(is_safe_public_http_url("http://127.0.0.1/admin"))
        self.assertFalse(is_safe_public_http_url("http://localhost/"))
        self.assertTrue(is_safe_public_http_url("https://news.example.com/article"))


if __name__ == "__main__":
    unittest.main()
