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

class ShadowAuditRegressionTests(unittest.TestCase):
    def test_first_seen_survives_a_failed_daily_run(self):
        from datetime import timedelta
        body = rss(("可追踪的论文发布", URL_1.replace("&amp;", "&"), PUB))
        first = observe([SPEC], {SPEC["id"]: body}, {"articles": []}, None, TIME)
        second = observe([SPEC], {}, {"articles": []}, first, TIME + timedelta(days=1))
        third = observe([SPEC], {SPEC["id"]: body}, {"articles": []},
                        second, TIME + timedelta(days=2))
        self.assertEqual(second["sources"][0]["status"], "fetch-error")
        self.assertEqual(second["summary"]["observed"], 0)
        self.assertEqual(len(second["seenHistory"]), 1)
        self.assertEqual(first["rows"][0]["firstSeenAt"], third["rows"][0]["firstSeenAt"])
        self.assertIs(third["rows"][0]["newSincePrevious"], False)
        self.assertEqual(third["summary"]["newSincePrevious"], 0)

    def test_repeated_title_and_near_title_inside_feed_are_only_review_leads(self):
        from datetime import timedelta
        t = "MEET2027含金量再加码：AI4S/量子计算/AI Infra…第二批嘉宾强势来袭！"
        alt = "MEET2027含金量加码：第二批嘉宾强势来袭！"
        u1 = URL_1.replace("&amp;", "&")
        u2 = URL_2.replace("&amp;", "&")
        u3 = u1.replace("idx=1", "idx=3")
        body = rss((t, u1, PUB), (t, u2, PUB), (alt, u3, PUB))
        report = observe([SPEC], {SPEC["id"]: body}, {"articles": []}, None, TIME)
        self.assertEqual(report["summary"]["observed"], 3)
        self.assertEqual(report["summary"]["sameFeedExactTitlePairs"], 1)
        self.assertGreaterEqual(report["summary"]["sameFeedNearTitlePairs"], 2)
        self.assertEqual(report["summary"]["feedReviewRows"], 3)
        self.assertTrue(all(r["status"] == "manual-review" and not r["published"]
                            for r in report["rows"]))
        self.assertTrue(all(r["feedReviewCandidates"] for r in report["rows"]))

    def test_cross_feed_title_pairs_have_separate_counters(self):
        specs = [SPEC, {"id": "wechat-rss-deepseek", "name": "DeepSeek"}]
        q = rss(("同一场技术活动通稿", URL_1.replace("&amp;", "&"), PUB))
        d = rss(("同一场技术活动通稿", URL_2.replace("&amp;", "&"), PUB))
        d = d.replace(b"<title>" + "量子位".encode() + b"</title>",
                      b"<title>DeepSeek</title>", 1)
        report = observe(specs, {specs[0]["id"]: q, specs[1]["id"]: d},
                         {"articles": []}, None, TIME)
        self.assertEqual(report["summary"]["sameFeedExactTitlePairs"], 0)
        self.assertEqual(report["summary"]["crossFeedExactTitlePairs"], 1)
        self.assertEqual(report["summary"]["sameWeChatKeyPairs"], 0)
        self.assertTrue(all(row["status"] == "manual-review" for row in report["rows"]))

    def test_same_wechat_key_cross_feed_caught_beyond_three_days(self):
        specs = [SPEC, {"id": "wechat-rss-deepseek", "name": "DeepSeek"}]
        url = URL_1.replace("&amp;", "&")
        first = rss(("历史文章", url, "Tue, 17 Nov 2026 15:00:00 +0800"))
        later = rss(("历史文章重发", url, "Sat, 21 Nov 2026 15:00:00 +0800"))
        later = later.replace(b"<title>" + "量子位".encode() + b"</title>",
                              b"<title>DeepSeek</title>", 1)
        observed = datetime(2026, 11, 22, 2, tzinfo=timezone.utc)
        report = observe(specs, {specs[0]["id"]: first, specs[1]["id"]: later},
                         {"articles": []}, None, observed)
        self.assertEqual(report["summary"]["sameWeChatKeyPairs"], 1)
        self.assertEqual(report["summary"]["sameFeedExactTitlePairs"], 0)
        self.assertEqual(report["summary"]["crossFeedExactTitlePairs"], 0)
        self.assertEqual(report["summary"]["feedReviewRows"], 2)

    def test_raw_valid_duplicate_invalid_and_truncated_counts_are_separate(self):
        from tools.wechat_rss_shadow_audit import feed_entries_with_stats
        good = URL_1.replace("&amp;", "&")
        raw = rss(("原创", good, PUB), ("重复键", good, PUB),
                  ("外部链接", "https://evil.example/article", PUB),
                  ("被截断", URL_2.replace("&amp;", "&"), PUB))
        _, rows, stats = feed_entries_with_stats(raw, max_items=3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats, {"rawFeedItems": 4, "processedFeedItems": 3,
                                 "validParsedItems": 1, "invalidItems": 1,
                                 "sameWeChatKeyItems": 1, "truncatedItems": 1})

    def test_source_snapshot_unavailable_is_not_miscounted_as_zero_matches(self):
        body = rss(("测试", URL_1.replace("&amp;", "&"), PUB))
        report = observe([SPEC], {SPEC["id"]: body}, {}, None, TIME,
                         snapshot_status="fetch-error")
        self.assertEqual(report["summary"]["observed"], 1)
        self.assertIsNone(report["summary"]["exactTitle"])
        self.assertIsNone(report["summary"]["possibleSameEvent"])
        self.assertIsNone(report["rows"][0]["exactTitleSources"])

    def test_redirects_fail_closed_and_unapproved_hosts_are_rejected(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        from tools.wechat_rss_shadow_audit import fetch_public
        with patch("tools.wechat_rss_shadow_audit.subprocess.run") as run:
            with self.assertRaises(ValueError):
                fetch_public("https://not-allowed.example/feed.xml", 5000)
            run.assert_not_called()
            run.return_value = CompletedProcess([], 47, b"", b"Maximum (0) redirects followed")
            with self.assertRaises(RuntimeError):
                fetch_public("https://wechat2rss.xlab.app/feed/test.xml", 5000)
            args = run.call_args.args[0]
            self.assertIn("--max-redirs", args)
            self.assertEqual(args[args.index("--max-redirs") + 1], "0")

    def test_legacy_report_rows_migrate_into_accumulated_history(self):
        from datetime import timedelta
        body = rss(("可追踪的论文发布", URL_1.replace("&amp;", "&"), PUB))
        original = observe([SPEC], {SPEC["id"]: body}, {"articles": []}, None, TIME)
        legacy = {"rows": original["rows"], "asOf": original["asOf"]}
        next_day = observe([SPEC], {SPEC["id"]: body}, {"articles": []},
                           legacy, TIME + timedelta(days=1))
        self.assertEqual(next_day["rows"][0]["firstSeenAt"], original["rows"][0]["firstSeenAt"])
        self.assertEqual(next_day["historyEntries"], 1)

    def test_cli_writes_failure_evidence_when_site_snapshot_times_out(self):
        import contextlib
        import io
        import json
        import sys
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from tools.wechat_rss_shadow_audit import main
        specs = [
            {"id": "wechat-rss-qbitai", "name": "量子位", "url": "https://wechat2rss.xlab.app/q.xml",
             "enabled": False, "allowedHosts": ["mp.weixin.qq.com"]},
            {"id": "wechat-rss-deepseek", "name": "DeepSeek", "url": "https://wechat2rss.bestblogs.dev/d.xml",
             "enabled": False, "allowedHosts": ["mp.weixin.qq.com"]},
            {"id": "wechat-rss-kimi", "name": "月之暗面 Kimi", "url": "https://wechat2rss.bestblogs.dev/k.xml",
             "enabled": False, "allowedHosts": ["mp.weixin.qq.com"]},
        ]
        def fake_fetch(url, max_bytes):
            if url.endswith('articles.json'):
                raise RuntimeError('snapshot connection timed out')
            match = next(s for s in specs if s['url'] == url)
            inner = '<item><title>人工复核</title><link>' + URL_1 + '</link><pubDate>' + PUB + '</pubDate></item>'
            if match['id'] != 'wechat-rss-qbitai':
                inner = ''
            return ('<rss><channel><title>' + match['name'] + '</title>' + inner + '</channel></rss>').encode()
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / 'config.json'
            config.write_text(json.dumps({'feeds': specs}), encoding='utf8')
            out = io.StringIO()
            with patch('tools.wechat_rss_shadow_audit.fetch_public', side_effect=fake_fetch), \
                 patch.object(sys, 'argv', ['audit', '--config', str(config), '--as-of', TIME.isoformat()]), \
                 contextlib.redirect_stdout(out):
                return_code = main()
            report = json.loads(out.getvalue())
        self.assertEqual(return_code, 2)
        self.assertEqual(report['snapshotStatus'], 'fetch-error')
        self.assertEqual(report['summary']['observed'], 1)
        self.assertIsNone(report['summary']['exactTitle'])
        self.assertEqual([s['status'] for s in report['sources']], ['ok', 'ok', 'ok'])


if __name__ == "__main__":
    unittest.main()
