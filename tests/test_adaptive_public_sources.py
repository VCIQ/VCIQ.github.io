from __future__ import annotations

import unittest
from urllib.parse import urlsplit

from tools import adaptive_public_sources as adaptive


class FakeCrawler:
    @staticmethod
    def normalize_url(url: str) -> str:
        return url.rstrip("/")

    @staticmethod
    def _status(
        source_id: str,
        name: str,
        status: str,
        scanned: int,
        accepted: int,
        *,
        failed: int = 0,
        platform: str = "",
        error: str | None = None,
    ) -> dict:
        result = {
            "id": source_id,
            "name": name,
            "status": status,
            "scanned": scanned,
            "accepted": accepted,
            "failed": failed,
            "platform": platform,
        }
        if error:
            result["error"] = error
        return result


class FakeGeneric:
    @staticmethod
    def platform_name(spec: dict) -> str:
        return str(spec.get("name") or urlsplit(str(spec.get("sourceUrl"))).hostname)

    @staticmethod
    def localize_keywords(terms, _language):
        return list(terms)


class FakeRobust:
    @staticmethod
    def crawl_with_second_stage(spec, _agent, _crawler, _generic):
        source_url = spec["sourceUrl"]
        if source_url == "https://tw.news.yahoo.com/search?p=AI":
            articles = [
                {
                    "id": f"yahoo-article-{index}",
                    "sourceId": spec["id"],
                    "title": f"人工智慧產業新聞 {index}",
                    "publishedAt": "2026-07-25",
                    "importance": 80 - index,
                    "source": {
                        "url": f"https://tw.news.yahoo.com/ai-news-{index}-20260725.html",
                        "name": "Yahoo奇摩",
                    },
                }
                for index in range(1, 4)
            ]
            return articles, {
                "status": "ok",
                "scanned": 4,
                "accepted": 3,
                "failed": 0,
                "strategies": ["primary", "structured-data"],
            }
        if source_url == "https://finance.eastmoney.com/":
            article = {
                "id": "eastmoney-discovered",
                "sourceId": spec["id"],
                "title": "AI芯片公司签署合作协议",
                "publishedAt": "2026-07-25",
                "importance": 80,
                "source": {
                    "url": "https://finance.eastmoney.com/a/202607253821110827.html",
                    "name": "东方财富",
                },
            }
            return [article], {
                "status": "ok",
                "scanned": 2,
                "accepted": 1,
                "failed": 0,
                "strategies": ["primary", "structured-data"],
            }
        return [], {
            "status": "empty",
            "scanned": 1,
            "accepted": 0,
            "failed": 0,
            "strategies": ["primary"],
        }


def article(article_id: str, url: str, day: str) -> dict:
    return {
        "id": article_id,
        "sourceId": "user-source-example",
        "title": article_id,
        "publishedAt": day,
        "importance": 70,
        "source": {"url": url, "name": "Example"},
    }


class AdaptivePublicSourceTests(unittest.TestCase):
    def test_yahoo_consent_parameters_are_removed(self) -> None:
        self.assertEqual(
            adaptive.canonical_source_url(
                "https://tw.yahoo.com/?p=us&guccounter=1&utm_source=test"
            ),
            "https://tw.yahoo.com/",
        )

    def test_yahoo_search_parameter_is_preserved(self) -> None:
        self.assertEqual(
            adaptive.canonical_source_url("https://tw.news.yahoo.com/search?p=AI"),
            "https://tw.news.yahoo.com/search?p=AI",
        )
        self.assertEqual(
            adaptive.native_search_seed_urls(
                "https://tw.yahoo.com/",
                ["AI / AGI", "人工智慧"],
            ),
            ["https://tw.news.yahoo.com/search?p=AI"],
        )

    def test_unknown_site_business_parameters_are_preserved(self) -> None:
        self.assertEqual(
            adaptive.canonical_source_url(
                "https://example.com/list?p=2&from=archive&utm_source=test"
            ),
            "https://example.com/list?from=archive&p=2",
        )

    def test_unknown_deep_url_adds_root_entry(self) -> None:
        self.assertEqual(
            adaptive.source_seed_urls("https://example.com/research/archive?p=2"),
            [
                "https://example.com/research/archive?p=2",
                "https://example.com/",
            ],
        )

    def test_yahoo_profile_adds_regional_public_entries(self) -> None:
        self.assertEqual(adaptive.profile_for("https://tw.news.yahoo.com/").id, "yahoo-tw")
        self.assertEqual(
            adaptive.source_seed_urls("https://tw.yahoo.com/?p=us&guccounter=1"),
            [
                "https://tw.yahoo.com/",
                "https://tw.news.yahoo.com/",
                "https://tw.stock.yahoo.com/",
            ],
        )

    def test_eastmoney_uses_same_profile_kernel(self) -> None:
        seeds = adaptive.source_seed_urls("https://www.eastmoney.com/default.html")
        profile = adaptive.profile_for(seeds[0])
        self.assertEqual(profile.id, "eastmoney")
        self.assertEqual(profile.publisher_handoff, "eastmoney-strict-detail")
        self.assertEqual(profile.handoff_status_id, "official-user-东方财富")
        self.assertIn("https://finance.eastmoney.com/", seeds)
        self.assertIn("https://fund.eastmoney.com/", seeds)

    def test_profile_decoding_supports_big5_and_gbk(self) -> None:
        traditional = "人工智慧與半導體".encode("big5")
        simplified = "人工智能与半导体".encode("gb18030")
        self.assertEqual(
            adaptive.decode_public_bytes(traditional, "https://tw.yahoo.com/"),
            "人工智慧與半導體",
        )
        self.assertEqual(
            adaptive.decode_public_bytes(simplified, "https://finance.eastmoney.com/"),
            "人工智能与半导体",
        )

    def test_adaptive_pipeline_prioritizes_native_search_and_stops(self) -> None:
        spec = {
            "id": "user-source-yahoo-tw",
            "name": "Yahoo奇摩",
            "url": "https://tw.yahoo.com/?p=us&guccounter=1",
            "sourceUrl": "https://tw.yahoo.com/?p=us&guccounter=1",
            "sourceLanguage": "zh-Hant",
            "keywords": ["AI / AGI", "人工智慧"],
            "maxItems": 5,
        }
        items, status = adaptive.crawl_adaptive_source(
            spec,
            "test-agent",
            FakeCrawler(),
            FakeGeneric(),
            FakeRobust(),
        )
        self.assertEqual(
            [item["id"] for item in items],
            ["yahoo-article-1", "yahoo-article-2", "yahoo-article-3"],
        )
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["adapter"], "adaptive-public-v1")
        self.assertEqual(status["profile"], "yahoo-tw")
        self.assertEqual(status["accepted"], 3)
        self.assertGreaterEqual(status["scanned"], status["accepted"])
        self.assertEqual(status["transportRequests"], 4)
        self.assertIn("structured-data", status["strategies"])
        self.assertEqual(status["canonicalSourceUrl"], "https://tw.yahoo.com/")
        self.assertEqual(
            status["nativeSearchSeeds"],
            ["https://tw.news.yahoo.com/search?p=AI"],
        )
        self.assertEqual(
            status["attemptedSeeds"],
            ["https://tw.news.yahoo.com/search?p=AI"],
        )
        self.assertEqual(status["requestBudget"]["stopAfterAccepted"], 3)
        self.assertEqual(status["historyLimit"], adaptive.DEFAULT_HISTORY_LIMIT)

    def test_strict_profile_discovers_but_does_not_publish_generic_batch(self) -> None:
        spec = {
            "id": "user-source-eastmoney",
            "name": "东方财富",
            "url": "https://www.eastmoney.com/default.html",
            "sourceUrl": "https://www.eastmoney.com/default.html",
            "keywords": ["AI"],
            "maxItems": 5,
        }

        items, status = adaptive.crawl_adaptive_source(
            spec,
            "test-agent",
            FakeCrawler(),
            FakeGeneric(),
            FakeRobust(),
        )

        self.assertEqual(items, [])
        self.assertEqual(status["adapter"], "adaptive-public-v1")
        self.assertEqual(status["profile"], "eastmoney")
        self.assertEqual(status["status"], "partial")
        self.assertEqual(status["accepted"], 0)
        self.assertEqual(status["discoveredAccepted"], 1)
        self.assertEqual(status["publisherHandoff"], "eastmoney-strict-detail")
        self.assertEqual(status["handoffStatusId"], "official-user-东方财富")
        self.assertEqual(status["requestBudget"]["seedLimit"], 2)

    def test_successful_adaptive_batch_keeps_bounded_history(self) -> None:
        existing = [
            article("old-1", "https://example.com/news/old-1", "2026-07-23"),
            article("old-2", "https://example.com/news/old-2", "2026-07-24"),
        ]
        incoming = [
            article("new-1", "https://example.com/news/new-1", "2026-07-25"),
            article("new-2", "https://example.com/news/old-2", "2026-07-25"),
        ]
        status = {
            "id": "user-source-example",
            "status": "ok",
            "accepted": 2,
            "adapter": "adaptive-public-v1",
            "historyLimit": 3,
        }

        merged = adaptive.merge_adaptive_history(
            existing,
            incoming,
            [status],
            FakeCrawler(),
        )

        self.assertEqual(
            [item["id"] for item in merged],
            ["new-2", "new-1", "old-1"],
        )
        self.assertEqual(status["newAccepted"], 2)
        self.assertEqual(status["accepted"], 2)
        self.assertEqual(status["retainedCount"], 3)
        self.assertEqual(status["retainedPreviousCount"], 1)
        self.assertTrue(status["retainedPrevious"])

    def test_failed_adaptive_batch_does_not_replace_history(self) -> None:
        incoming = [article("other", "https://other.example/news/1", "2026-07-25")]
        status = {
            "id": "user-source-example",
            "status": "error",
            "accepted": 0,
            "adapter": "adaptive-public-v1",
        }
        self.assertEqual(
            adaptive.merge_adaptive_history([], incoming, [status], FakeCrawler()),
            incoming,
        )


if __name__ == "__main__":
    unittest.main()
