from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import patch

from tools import refresh_wechat_snapshot as refresh


class RefreshWeChatSnapshotTest(unittest.TestCase):
    def test_pipeline_installs_title_fallback_after_redirect_compat(self) -> None:
        events: list[str] = []

        def record(name: str):
            return lambda *_args, **_kwargs: events.append(name)

        installers = (
            (refresh.wechat_fetch_compat, "fetch"),
            (refresh.wechat_registry_bridge, "registry"),
            (refresh.wechat_original_redirect_bridge, "original_redirect"),
            (refresh.wechat_index_context_guard, "context"),
            (refresh.wechat_index_record_fallback, "record_fallback"),
            (refresh.wechat_sogou_redirect_compat, "sogou_redirect"),
            (refresh.wechat_sogou_link_compat, "sogou_link"),
            (refresh.wechat_public_index_title_fallback, "title_fallback"),
            (refresh.wechat_public_aggregator, "public_aggregator"),
            (refresh.wechat_sogou_bridge, "sogou_bridge"),
        )
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(
                    patch.object(module, "install", side_effect=record(name))
                )
                for module, name in installers
            }
            refresh.install_wechat_pipeline()

        self.assertEqual(
            events,
            [
                "fetch",
                "registry",
                "original_redirect",
                "context",
                "record_fallback",
                "sogou_redirect",
                "sogou_link",
                "title_fallback",
                "public_aggregator",
                "sogou_bridge",
            ],
        )
        mocks["original_redirect"].assert_called_once_with(
            refresh.wechat_public_sources,
            refresh.wechat_registry_bridge,
        )
        mocks["sogou_redirect"].assert_called_once_with(
            refresh.wechat_sogou_index
        )
        mocks["title_fallback"].assert_called_once_with(
            refresh.wechat_registry_bridge,
            refresh.wechat_sogou_index,
        )
        mocks["public_aggregator"].assert_called_once_with(
            refresh.wechat_sogou_index
        )

    def _article(self, article_id: str, source_id: str, url: str) -> dict:
        return {
            "id": article_id,
            "sourceId": source_id,
            "title": f"文章 {article_id}",
            "summary": "用于测试微信公众号批次替换与历史保留。",
            "type": "公司动态",
            "region": "中国",
            "sector": "AI / AGI",
            "company": "科技产业",
            "publishedAt": "2026-07-25",
            "importance": 75,
            "source": {
                "name": "测试来源",
                "url": url,
                "level": "媒体报道",
                "platform": "微信" if source_id.startswith("user-track-wechat-") else "新闻",
            },
        }

    def test_successful_source_replaces_only_its_previous_batch(self) -> None:
        old_wechat = self._article(
            "old-wechat",
            "user-track-wechat-qbitai-ai",
            "https://mp.weixin.qq.com/s/old",
        )
        unrelated = self._article(
            "news",
            "sina-finance",
            "https://example.com/news",
        )
        incoming = self._article(
            "new-wechat",
            "user-track-wechat-qbitai-ai",
            "https://mp.weixin.qq.com/s/new",
        )
        incoming["mentionedCompanies"] = ["OpenAI"]
        incoming["mentionedPeople"] = ["Sam Altman"]
        payload = {
            "schemaVersion": 3,
            "generatedAt": "2026-07-24T00:00:00+00:00",
            "articleCount": 2,
            "articles": [old_wechat, unrelated],
            "sourceStatus": [],
            "qualityGate": {"passed": True},
        }
        next_payload = refresh.merge_wechat_snapshot(
            payload,
            [incoming],
            [
                {
                    "id": "user-track-wechat-qbitai-ai",
                    "name": "量子位",
                    "status": "ok",
                    "scanned": 3,
                    "accepted": 1,
                    "failed": 0,
                    "platform": "微信",
                }
            ],
        )
        ids = {item["id"] for item in next_payload["articles"]}
        self.assertEqual(ids, {"new-wechat", "news"})
        self.assertEqual(next_payload["qualityGate"], {"passed": True})
        self.assertEqual(next_payload["wechatIngestion"]["acceptedArticles"], 1)
        self.assertEqual(next_payload["wechatIngestion"]["mentionedCompanyLinks"], 1)
        self.assertEqual(next_payload["wechatIngestion"]["mentionedPeopleLinks"], 1)
        self.assertEqual(next_payload["wechatIngestion"]["indexOnlyArticles"], 0)

    def test_failed_source_retains_previous_original_batch(self) -> None:
        old_wechat = self._article(
            "old-wechat",
            "user-track-wechat-qbitai-ai",
            "https://mp.weixin.qq.com/s/old",
        )
        payload = {
            "schemaVersion": 3,
            "articles": [old_wechat],
            "sourceStatus": [],
        }
        next_payload = refresh.merge_wechat_snapshot(
            payload,
            [],
            [
                {
                    "id": "user-track-wechat-qbitai-ai",
                    "name": "量子位",
                    "status": "error",
                    "scanned": 0,
                    "accepted": 0,
                    "failed": 1,
                    "retainedPrevious": True,
                    "platform": "微信",
                }
            ],
        )
        self.assertEqual(next_payload["articleCount"], 1)
        self.assertEqual(next_payload["articles"][0]["id"], "old-wechat")
        self.assertEqual(next_payload["wechatIngestion"]["retainedSources"], 1)

    def test_failed_source_removes_legacy_index_proxy_record(self) -> None:
        original = self._article(
            "original",
            "user-track-wechat-icbank-semiconductor",
            "https://mp.weixin.qq.com/s/original",
        )
        proxy = self._article(
            "proxy",
            "user-track-wechat-icbank-semiconductor",
            "https://www.jintiankansha.com/t/proxy-id",
        )
        proxy["source"]["platform"] = "微信公开索引"
        proxy["source"]["level"] = "数据库记录"
        proxy["wechatContentMode"] = "index-only"
        payload = {
            "schemaVersion": 3,
            "articles": [original, proxy],
            "sourceStatus": [],
        }
        next_payload = refresh.merge_wechat_snapshot(
            payload,
            [],
            [
                {
                    "id": "user-track-wechat-icbank-semiconductor",
                    "name": "半导体行业观察",
                    "status": "error",
                    "scanned": 0,
                    "accepted": 0,
                    "failed": 1,
                    "retainedPrevious": True,
                    "platform": "微信",
                }
            ],
        )
        self.assertEqual(
            [article["id"] for article in next_payload["articles"]],
            ["original"],
        )
        self.assertEqual(next_payload["wechatIngestion"]["removedProxyRecords"], 1)


if __name__ == "__main__":
    unittest.main()
