from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tools import wechat_public_aggregator as aggregator


class WeChatPublicAggregatorTests(unittest.TestCase):
    def test_account_matched_direct_article_is_extracted(self) -> None:
        body = """
        <article>
          <a href="https://mp.weixin.qq.com/s/AbCdEf123">大模型推理效率取得新突破</a>
          <a href="https://mp.weixin.qq.com/s/AbCdEf123">打开原文</a>
          <div>AI 量子位 2026-07-22 05:00:00 UTC</div>
        </article>
        """
        rows = aggregator.parse_public_index(
            body,
            {
                "name": "量子位",
                "queryIdentity": "量子位",
                "expectedAccounts": ["量子位"],
                "maxItems": 2,
            },
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["account"], "量子位")
        self.assertEqual(rows[0]["publishedAt"], "2026-07-22")
        self.assertEqual(rows[0]["directUrl"], "https://mp.weixin.qq.com/s/AbCdEf123")

    def test_other_accounts_are_not_misattributed(self) -> None:
        body = """
        <a href="https://mp.weixin.qq.com/s/Other123">机器人行业动态</a>
        <div>AI 机器之心 2026-07-22 04:00:00 UTC</div>
        """
        rows = aggregator.parse_public_index(
            body,
            {
                "name": "量子位",
                "queryIdentity": "量子位",
                "expectedAccounts": ["量子位"],
            },
        )
        self.assertEqual(rows, [])

    def test_insecure_direct_article_is_rejected(self) -> None:
        body = """
        <a href="http://mp.weixin.qq.com/s/Insecure123">大模型推理效率取得新突破</a>
        <div>AI 量子位 2026-08-29</div>
        """
        rows = aggregator.parse_public_index(
            body,
            {
                "name": "量子位",
                "expectedAccounts": ["量子位"],
            },
        )
        self.assertEqual(rows, [])

    def test_signed_timestamp_query_survives_index_parsing(self) -> None:
        for separator in ("&timestamp=", "&amp;timestamp=", "×tamp="):
            with self.subTest(separator=separator):
                body = f"""
                <a href="https://mp.weixin.qq.com/s?src=11{separator}1788018564&amp;ver=6934&amp;signature=a%2Ab">
                  半导体芯片产业取得新突破
                </a>
                <div>半导体 半导体行业观察 2026-08-29</div>
                """
                rows = aggregator.parse_public_index(
                    body,
                    {
                        "name": "半导体行业观察",
                        "expectedAccounts": ["半导体行业观察"],
                    },
                )
                self.assertEqual(len(rows), 1)
                query = parse_qs(
                    urlsplit(rows[0]["directUrl"]).query,
                    keep_blank_values=True,
                )
                self.assertEqual(query["src"], ["11"])
                self.assertEqual(query["timestamp"], ["1788018564"])
                self.assertEqual(query["ver"], ["6934"])
                self.assertEqual(query["signature"], ["a*b"])

    def test_primary_direct_results_win_over_fallback(self) -> None:
        class Index:
            @staticmethod
            def discover(_spec):
                return ([{"directUrl": "https://mp.weixin.qq.com/s/primary"}], {"provider": "sogou-weixin"})

        index = Index()
        aggregator.install(index)
        with patch.object(aggregator, "discover") as fallback:
            rows, meta = index.discover({"name": "量子位"})
        self.assertEqual(meta["provider"], "sogou-weixin")
        self.assertEqual(rows[0]["directUrl"], "https://mp.weixin.qq.com/s/primary")
        fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
