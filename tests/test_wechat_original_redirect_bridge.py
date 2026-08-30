from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tools import wechat_original_redirect_bridge as bridge


class WeChatOriginalRedirectBridgeTest(unittest.TestCase):
    def test_recognizes_only_original_public_article_urls(self) -> None:
        self.assertTrue(
            bridge.is_direct_wechat_url(
                "https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=abc"
            )
        )
        self.assertFalse(
            bridge.is_direct_wechat_url(
                "https://www.jintiankansha.com/t/article-id"
            )
        )
        self.assertFalse(
            bridge.is_direct_wechat_url("http://mp.weixin.qq.com/s/insecure")
        )
        self.assertFalse(
            bridge.is_direct_wechat_url("ftp://mp.weixin.qq.com/s/wrong-scheme")
        )
        self.assertTrue(
            bridge.is_public_index_proxy_url(
                "https://www.jintiankansha.com/t_original/article-id"
            )
        )

    def test_follows_original_endpoint_from_detail_page(self) -> None:
        body = '<a class="original" href="/t_original/abc123">原文地址</a>'
        expected = "https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=abc"
        with patch.object(bridge, "_follow_original_endpoint", return_value=expected) as follow:
            resolved = bridge.resolve_detail_url(
                "https://www.jintiankansha.com/t/detail123",
                body,
                "test-agent",
            )
        self.assertEqual(resolved, expected)
        follow.assert_called_once_with(
            "https://www.jintiankansha.com/t_original/abc123",
            "test-agent",
        )

    def test_extracts_direct_original_embedded_in_page(self) -> None:
        body = (
            '<script>window.location.href="https://mp.weixin.qq.com/s?'
            '__biz=test&amp;mid=1&amp;idx=1&amp;sn=abc";</script>'
        )
        resolved = bridge.resolve_detail_url(
            "https://www.jintiankansha.com/t/detail123",
            body,
            "test-agent",
        )
        self.assertEqual(
            resolved,
            "https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=abc",
        )

    def test_preserves_signed_timestamp_from_detail_page(self) -> None:
        values = (
            "&timestamp=1788018564",
            "&amp;timestamp=1788018564",
            "×tamp=1788018564",
            "%C3%97tamp%3D1788018564",
        )
        for timestamp in values:
            with self.subTest(timestamp=timestamp):
                body = (
                    '<script>window.location.href="https://mp.weixin.qq.com/s?'
                    f'src=11{timestamp}&amp;ver=6934&amp;signature=a%2Ab";</script>'
                )
                resolved = bridge.resolve_detail_url(
                    "https://www.jintiankansha.com/t/detail123",
                    body,
                    "test-agent",
                )
                query = parse_qs(
                    urlsplit(resolved).query,
                    keep_blank_values=True,
                )
                self.assertEqual(query["src"], ["11"])
                self.assertEqual(query["timestamp"], ["1788018564"])
                self.assertEqual(query["ver"], ["6934"])
                self.assertEqual(query["signature"], ["a*b"])


if __name__ == "__main__":
    unittest.main()
