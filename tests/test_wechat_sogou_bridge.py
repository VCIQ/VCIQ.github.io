from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools import wechat_sogou_bridge as bridge


class WeChatSogouBridgeRoutingTest(unittest.TestCase):
    def _crawler(self) -> SimpleNamespace:
        return SimpleNamespace(
            DEFAULT_USER_AGENT="crawler-default-agent",
            normalize_date=lambda value: str(value or "") or None,
        )

    def _spec(self, *, public_indexes: bool) -> dict:
        return {
            "id": "user-track-wechat-example-sector",
            "name": "示例公众号",
            "maxItems": 6,
            "maxArticleAgeDays": 45,
            "expectedAccounts": ["示例公众号"],
            "publicIndexUrls": (
                ["https://index.example/account"] if public_indexes else []
            ),
        }

    def test_public_index_source_uses_only_wrapped_crawl_on_success(self) -> None:
        spec = self._spec(public_indexes=True)
        crawler = self._crawler()
        expected_articles = [{"id": "verified-original"}]
        original_status = {
            "id": spec["id"],
            "name": spec["name"],
            "status": "partial",
            "scanned": 2,
            "accepted": 1,
            "failed": 1,
            "discoveryProvider": "bing-or-public-index",
            "error": "one public-index detail remained unresolved",
            "sentinel": "preserve-original-status",
            "diagnostics": {"publicIndex": {"discovered": 3, "resolved": 2}},
        }

        def original_crawl(source, _user_agent, _crawler):
            source["_publicIndexTitleSearchQueries"] = 2
            source["_publicIndexTitleRedirectAttempts"] = 1
            return expected_articles, original_status

        original = Mock(side_effect=original_crawl)
        original._wechat_sogou_primary = False
        wechat = SimpleNamespace(crawl_wechat_source=original)
        bridge.install(wechat)

        with patch.object(bridge.wechat_sogou_index, "discover") as discover:
            articles, status = wechat.crawl_wechat_source(
                spec, "caller-agent", crawler
            )

        discover.assert_not_called()
        original.assert_called_once()
        self.assertEqual(articles, expected_articles)
        self.assertEqual(status["status"], "partial")
        self.assertEqual(status["discoveryProvider"], "bing-or-public-index")
        self.assertEqual(status["error"], original_status["error"])
        self.assertEqual(status["sentinel"], "preserve-original-status")
        self.assertEqual(status["diagnostics"], original_status["diagnostics"])
        self.assertIs(status["sogouPrimarySkipped"], True)
        self.assertEqual(status["publicIndexTitleQueries"], 2)
        self.assertEqual(status["publicIndexTitleRedirects"], 1)

    def test_public_index_source_failure_retains_original_diagnostics(self) -> None:
        spec = self._spec(public_indexes=True)
        crawler = self._crawler()
        original_status = {
            "id": spec["id"],
            "name": spec["name"],
            "status": "error",
            "scanned": 0,
            "accepted": 0,
            "failed": 3,
            "discoveryProvider": "bing-or-public-index",
            "error": "title lookup redirects did not resolve",
            "sentinel": "keep-failure-branch",
            "diagnostics": {
                "publicIndex": {
                    "discovered": 4,
                    "detailUnresolved": 4,
                }
            },
        }

        def original_crawl(source, _user_agent, _crawler):
            source["_publicIndexTitleSearchQueries"] = 2
            source["_publicIndexTitleRedirectAttempts"] = 2
            return [], original_status

        original = Mock(side_effect=original_crawl)
        original._wechat_sogou_primary = False
        wechat = SimpleNamespace(crawl_wechat_source=original)
        bridge.install(wechat)

        with patch.object(bridge.wechat_sogou_index, "discover") as discover:
            articles, status = wechat.crawl_wechat_source(
                spec, "caller-agent", crawler
            )

        discover.assert_not_called()
        original.assert_called_once()
        self.assertEqual(articles, [])
        self.assertEqual(status["status"], "error")
        self.assertIs(status["retainedPrevious"], True)
        self.assertEqual(status["discoveryProvider"], "bing-or-public-index")
        self.assertEqual(status["error"], original_status["error"])
        self.assertEqual(status["sentinel"], "keep-failure-branch")
        self.assertEqual(status["diagnostics"], original_status["diagnostics"])
        self.assertIs(status["sogouPrimarySkipped"], True)
        self.assertEqual(status["publicIndexTitleQueries"], 2)
        self.assertEqual(status["publicIndexTitleRedirects"], 2)

    def test_public_index_empty_result_normalizes_stale_success_status(self) -> None:
        spec = self._spec(public_indexes=True)
        crawler = self._crawler()
        original_status = {
            "id": spec["id"],
            "name": spec["name"],
            "status": "ok",
            "scanned": 7,
            "accepted": 7,
            "failed": 0,
            "discoveryProvider": "bing-or-public-index",
        }
        original = Mock(return_value=([], original_status))
        original._wechat_sogou_primary = False
        wechat = SimpleNamespace(crawl_wechat_source=original)
        bridge.install(wechat)

        articles, status = wechat.crawl_wechat_source(
            spec, "caller-agent", crawler
        )

        self.assertEqual(articles, [])
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["accepted"], 0)
        self.assertEqual(status["failed"], 1)
        self.assertIs(status["retainedPrevious"], True)
        self.assertIn("No current-run", status["error"])

    def test_source_without_public_index_keeps_sogou_primary(self) -> None:
        spec = self._spec(public_indexes=False)
        crawler = self._crawler()
        today = datetime.now(UTC).date().isoformat()
        expected_article = {
            "id": "sogou-original",
            "publishedAt": today,
        }
        original = Mock(side_effect=AssertionError("fallback must not run"))
        original._wechat_sogou_primary = False
        fetch_page = Mock(return_value="original page")
        parse_article = Mock(return_value=expected_article)
        wechat = SimpleNamespace(
            crawl_wechat_source=original,
            fetch_public_wechat_page=fetch_page,
            parse_wechat_article=parse_article,
        )
        bridge.install(wechat)
        row = {
            "directUrl": "https://mp.weixin.qq.com/s/example",
            "title": "示例公众号发布新产品",
            "summary": "示例摘要",
            "publishedAt": today,
            "account": "",
        }

        with patch.object(
            bridge.wechat_sogou_index,
            "discover",
            return_value=(
                [row],
                {
                    "provider": "sogou-weixin",
                    "scanned": 1,
                    "resolved": 1,
                    "failed": 0,
                },
            ),
        ) as discover:
            articles, status = wechat.crawl_wechat_source(
                spec, "caller-agent", crawler
            )

        discover.assert_called_once_with(spec)
        original.assert_not_called()
        fetch_page.assert_called_once_with(row["directUrl"])
        parse_article.assert_called_once()
        self.assertEqual(articles, [expected_article])
        self.assertEqual(status["accepted"], 1)
        self.assertEqual(status["discoveryProvider"], "sogou-weixin")

    def test_source_without_public_index_calls_original_after_sogou_failure(self) -> None:
        spec = self._spec(public_indexes=False)
        crawler = self._crawler()
        events: list[str] = []
        fallback_articles = [{"id": "fallback-original"}]
        fallback_status = {
            "id": spec["id"],
            "name": spec["name"],
            "status": "partial",
            "scanned": 1,
            "accepted": 1,
            "failed": 0,
            "discoveryProvider": "bing",
        }

        def discover(_source):
            events.append("sogou")
            return [], {
                "provider": "sogou-weixin",
                "scanned": 0,
                "resolved": 0,
                "failed": 0,
            }

        def original_crawl(_source, _user_agent, _crawler):
            events.append("original")
            return fallback_articles, fallback_status

        original = Mock(side_effect=original_crawl)
        original._wechat_sogou_primary = False
        wechat = SimpleNamespace(crawl_wechat_source=original)
        bridge.install(wechat)

        with patch.object(
            bridge.wechat_sogou_index, "discover", side_effect=discover
        ) as sogou_discover:
            articles, status = wechat.crawl_wechat_source(
                spec, "caller-agent", crawler
            )

        sogou_discover.assert_called_once_with(spec)
        original.assert_called_once()
        self.assertEqual(events, ["sogou", "original"])
        self.assertEqual(articles, fallback_articles)
        self.assertEqual(status["status"], "partial")
        self.assertEqual(status["accepted"], 1)


if __name__ == "__main__":
    unittest.main()
