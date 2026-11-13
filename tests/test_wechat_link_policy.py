from __future__ import annotations

import unittest

from tools import wechat_link_policy as policy

SHORT = "https://mp.weixin.qq.com/s/hNvk76l8FzVEhglIQqebJg"
LONG = "https://mp.weixin.qq.com/s?__biz=Mzk0&mid=2247496030&idx=1&sn=abcd&chksm=xyz"
SIGNED = (
    "https://mp.weixin.qq.com/s?new=1&signature=abc%2Adef"
    "&src=11&timestamp=1794138303&ver=7076"
)


class WeChatLinkPolicyTests(unittest.TestCase):
    def test_shareable_short_and_complete_long_forms(self) -> None:
        for url in (SHORT, LONG, SHORT + "?scene=2",
                    "https://mp.weixin.qq.com/s?__biz=Mzk0&mid=2247496030&idx=1"):
            with self.subTest(url=url):
                self.assertEqual(policy.classify_wechat_article_url(url), "durable")
                self.assertTrue(policy.is_durable_wechat_article_url(url))

    def test_search_index_signatures_are_not_durable(self) -> None:
        for url in (
            SIGNED,
            "https://mp.weixin.qq.com/s?src=11&timestamp=1794138303&signature=x",
            LONG + "&signature=x",
            SHORT + "?timestamp=1794138303",
        ):
            with self.subTest(url=url):
                self.assertEqual(policy.classify_wechat_article_url(url), "temporary")
                self.assertTrue(policy.is_non_durable_wechat_article_url(url))

    def test_incomplete_and_invalid_identity_is_not_durable(self) -> None:
        for url in (
            "https://mp.weixin.qq.com/s?src=11&ver=7076",
            "https://mp.weixin.qq.com/s?__biz=xyz&mid=1",
            "https://mp.weixin.qq.com/s?__biz=xyz&mid=1&idx=1&sn=",
            "https://mp.weixin.qq.com/s?__biz=xyz&mid=abc&idx=1&sn=123",
            "http://mp.weixin.qq.com/s/shortcode",
            "https://mp.weixin.qq.com/s/",
        ):
            with self.subTest(url=url):
                self.assertEqual(policy.classify_wechat_article_url(url), "unverified")

    def test_external_media_urls_are_out_of_scope(self) -> None:
        for url in (
            "https://www.yunfu.gov.cn/news/example",
            "https://mp.weixin.qq.com.evil.example/s/abc",
            "https://www.zhidx.com/p/608449.html",
        ):
            self.assertEqual(policy.classify_wechat_article_url(url), "other")
            self.assertFalse(policy.is_non_durable_wechat_article_url(url))


if __name__ == "__main__":
    unittest.main()
