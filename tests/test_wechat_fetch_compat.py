from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import wechat_fetch_compat as fetcher


class _Headers:
    def get_content_charset(self):
        return "utf-8"


class _Response:
    def __init__(self, url: str, body: str):
        self.url = url
        self.body = body.encode("utf-8")
        self.headers = _Headers()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def geturl(self):
        return self.url

    def read(self, _size=-1):
        return self.body


class WeChatFetchCompatTest(unittest.TestCase):
    def test_uses_micromessenger_user_agent_for_original_page(self) -> None:
        url = "https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=abc"
        body = '<h1 id="activity-name">测试文章</h1><div id="js_content">正文内容</div>'
        captured = {}

        def fake_open(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response(url, body)

        with patch.object(fetcher, "urlopen", side_effect=fake_open), patch.object(
            fetcher, "_wait_for_rate_limit"
        ):
            result = fetcher.fetch_public_wechat_page(url, attempts=1)

        self.assertEqual(result, body)
        user_agent = captured["request"].get_header("User-agent")
        self.assertIn("MicroMessenger/", user_agent)
        self.assertEqual(captured["timeout"], 18)

    def test_rejects_proxy_page_before_request(self) -> None:
        rejected = (
            "https://www.jintiankansha.com/t/example",
            "http://mp.weixin.qq.com/s/insecure",
            "ftp://mp.weixin.qq.com/s/wrong-scheme",
        )
        for url in rejected:
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetcher.fetch_public_wechat_page(url, attempts=1)

    def test_verification_page_is_terminal(self) -> None:
        url = "https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=abc"
        with patch.object(
            fetcher,
            "urlopen",
            return_value=_Response(url, "当前环境存在异常，请输入验证码"),
        ), patch.object(fetcher, "_wait_for_rate_limit"):
            with self.assertRaises(fetcher.WeChatOriginalUnavailable):
                fetcher.fetch_public_wechat_page(url, attempts=1)


if __name__ == "__main__":
    unittest.main()
