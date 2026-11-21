"""Synthetic URL rejection diagnostics, no real HTTP and no new destinations."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.test_social_wechat import FakeTransport, make_job, NOW
from tools.social.adapters import wechat
from tools.social.adapters.wechat_transport import (
    FetchError, checked_url, destination_failure_class,
)


class WechatDestinationDiagnostics(unittest.TestCase):
    def test_reason_classes_are_fixed_and_never_include_raw_urls(self):
        samples = [
            ("http://mp.weixin.qq.com/s/SYNTHETIC_TOKEN", "SCHEME"),
            ("https://unrelated.example/s/SYNTHETIC_TOKEN", "HOST"),
            ("https://mp.weixin.qq.com/ck/a?secret=SYNTHETIC_TOKEN", "PATH"),
            ("https://weixin.sogou.com/redirect?secret=SYNTHETIC_TOKEN", "PATH"),
            ("https://www.bing.com/ck/a?secret=SYNTHETIC_TOKEN", "PATH"),
            ("https://mp.weixin.qq.com:8443/s/SYNTHETIC_TOKEN", "AUTHORITY"),
            ("https://name@mp.weixin.qq.com/s/SYNTHETIC_TOKEN", "AUTHORITY"),
            ("https://mp.weixin.qq.com/s/SYNTHETIC_TOKEN#fragment", "AUTHORITY"),
            ("https://mp.weixin.qq.com/s/SYNTHETIC_TOKEN\nbad", "FORMAT"),
            ("https://mp.weixin.qq.com/s/SYNTHETIC_TOKEN", "ALLOWED"),
            ("https://weixin.sogou.com/link?url=SYNTHETIC_TOKEN", "ALLOWED"),
            (None, "FORMAT"),
        ]
        for original, expected in samples:
            with self.subTest(expected=expected):
                result = destination_failure_class(original)
                self.assertEqual(result, expected)
                self.assertNotIn("SYNTHETIC_TOKEN", result)
                if expected != "ALLOWED" and original is not None:
                    with self.assertRaisesRegex(FetchError, "UNSAFE_DESTINATION"):
                        checked_url(original)

    def test_search_destination_rejection_keeps_stage_without_raw_url(self):
        job, context = make_job("bing-rss")
        result = wechat.run_job(
            job, context, FakeTransport(search=FetchError("schema_error", "UNSAFE_DESTINATION")),
            now=lambda: NOW,
        )
        self.assertEqual(result["receipt"]["status"], "schema_error")
        self.assertEqual(result["receipt"]["errorCode"], "WECHAT_SEARCH_DESTINATION_UNSAFE")
        self.assertEqual(result["receipt"]["counts"]["searchItems"], 0)
        self.assertEqual(result["observations"], [])

    def test_bad_index_link_reason_is_precise_but_not_exported(self):
        job, context = make_job("sogou-weixin")
        for url, expected in (
            ("https://www.bing.com/ck/a?token=PRIVATE", "WECHAT_RESULT_URL_PATH"),
            ("https://unrelated.example/link?token=PRIVATE", "WECHAT_RESULT_URL_HOST"),
            ("http://weixin.sogou.com/link?token=PRIVATE", "WECHAT_RESULT_URL_SCHEME"),
        ):
            with self.subTest(expected=expected):
                row = {"url": url, "title": "合成搜索结果"}
                with patch.object(wechat, "_search_page", return_value=([row], False)):
                    result = wechat.run_job(job, context, FakeTransport(), now=lambda: NOW)
                self.assertEqual(result["receipt"]["status"], "schema_error")
                self.assertEqual(result["receipt"]["errorCode"], expected)
                self.assertEqual(result["receipt"]["counts"]["rawRows"], 1)
                self.assertEqual(result["receipt"]["counts"]["emittedRows"], 0)
                self.assertNotIn("PRIVATE", repr(result))

    def test_safe_index_with_untrusted_redirect_has_distinct_error(self):
        job, context = make_job()
        row = {"url": "https://weixin.sogou.com/link?url=SYNTHETIC", "title": "合成搜索结果"}
        with patch.object(wechat, "_search_page", return_value=([row], False)):
            with patch.object(wechat, "_resolve", side_effect=FetchError(
                    "schema_error", "UNSAFE_DESTINATION")):
                result = wechat.run_job(job, context, FakeTransport(), now=lambda: NOW)
        self.assertEqual(result["receipt"]["errorCode"], "WECHAT_RESULT_REDIRECT_UNSAFE")
        self.assertEqual(result["receipt"]["counts"]["emittedRows"], 0)
        self.assertEqual(result["observations"], [])


if __name__ == "__main__":
    unittest.main()
