"""Deterministic, offline checks for read-only WeChat RSS shadow observations."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from tools.wechat_rss_shadow_audit import feed_entries, observe, wechat_key


def rss(*items: tuple[str, str, str]) -> bytes:
    entries = "".join(
        "<item><title>" + title + "</title><link>" + url.replace("&", "&amp;")
        + "</link><pubDate>" + pubdate + "</pubDate></item>"
        for title, url, pubdate in items
    )
    return ("<rss><channel><title>量子位</title>" + entries + "</channel></rss>").encode()


TIME = datetime(2026, 11, 19, 2, 0, tzinfo=timezone.utc)
PUB = "Wed, 18 Nov 2026 15:00:00 +0800"
URL_1 = "https://mp.weixin.qq.com/s?__biz=test&amp;mid=3&amp;idx=1"
URL_2 = "https://mp.weixin.qq.com/s?__biz=test&amp;mid=3&amp;idx=2"
SPEC = {"id": "wechat-rss-qbitai", "name": "量子位"}


class ShadowAuditTests(unittest.TestCase):
    def test_distinct_group_articles_and_offsite_rejection(self):
        body = rss(
            ("AI 测试文章一", URL_1.replace("&amp;", "&"), PUB),
            ("AI 测试文章二", URL_2.replace("&amp;", "&"), PUB),
            ("外部域名", "https://evil.example/s?__biz=test&mid=3&idx=3", PUB),
            ("重复文章一", URL_1.replace("&amp;", "&"), PUB),
        )
        title, rows = feed_entries(body)
        self.assertEqual(title, "量子位")
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["wechatKey"], rows[1]["wechatKey"])
        self.assertIsNone(wechat_key("http://mp.weixin.qq.com/s?__biz=x&mid=1&idx=1"))
        self.assertIsNone(wechat_key("https://mp.weixin.qq.com.evil.example/s?__biz=x&mid=1&idx=1"))

    def test_no_publication_and_stable_first_seen(self):
        body = rss(("DeepSeek 新模型发布", URL_1.replace("&amp;", "&"), PUB))
        snapshot = {"generatedAt": "2026-11-19T00:00:00Z", "articles": [
            {"title": "DeepSeek 新模型发布", "sourceId": "official-deepseek", "publishedAt": "2026-11-18"},
        ]}
        first = observe([SPEC], {SPEC["id"]: body}, snapshot, None, TIME)
        self.assertEqual(first["summary"]["observed"], 1)
        self.assertEqual(first["summary"]["exactTitle"], 1)
        self.assertEqual(first["rows"][0]["status"], "manual-review")
        self.assertIs(first["rows"][0]["published"], False)
        self.assertEqual(first["rows"][0]["exactTitleSources"], ["official-deepseek"])
        later = datetime(2026, 11, 20, 2, tzinfo=timezone.utc)
        second = observe([SPEC], {SPEC["id"]: body}, snapshot, first, later)
        self.assertEqual(second["rows"][0]["firstSeenAt"], first["rows"][0]["firstSeenAt"])
        self.assertNotEqual(second["rows"][0]["lastSeenAt"], first["rows"][0]["lastSeenAt"])

    def test_fetch_failure_and_title_mismatch_fail_closed(self):
        report = observe([SPEC], {}, {"articles": []}, None, TIME)
        self.assertEqual(report["sources"][0]["status"], "fetch-error")
        self.assertEqual(report["rows"], [])
        body = b"<rss><channel><title>Other account</title></channel></rss>"
        report = observe([SPEC], {SPEC["id"]: body}, {"articles": []}, None, TIME)
        self.assertEqual(report["sources"][0]["status"], "title-mismatch")
        self.assertEqual(report["rows"], [])


if __name__ == "__main__":
    unittest.main()
