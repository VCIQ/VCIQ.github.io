"""PR-02 W05-W09. All responses are synthetic; real platform status stays live_pending."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tools.social.adapters import wechat
from tools.social.adapters.wechat_transport import FetchError, PublicTransport, Response, _PinnedConnection, checked_url, decode_url
from tools.social.contracts import ContractError, validate
from tools.social.guard import protected_snapshot, assert_unchanged
from tools.social.planning_cli import main as planning_main
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.scheduler import plan_jobs

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/social/wechat"
NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)
ORIGINAL = "https://mp.weixin.qq.com/s/SYNTHETIC_ARTICLE"


def fixture(name):
    return (FIX / name).read_text(encoding="utf-8")


def make_job(provider="sogou-weixin", *, account=None, text="人形机器人", pages=1):
    policy = load_policy()
    policy["budget"]["pagesPerJob"] = pages
    accounts = {"accounts": [{"id": "synthetic-account", "name": account,
                              "sectorKeywords": {"机器人": [text]}}]} if account else None
    registry = build_query_registry({"tracks": [{"name": "机器人", "slug": "robot", "keywords": [text]}]},
                                   policy, providers=(provider,), accounts=accounts)
    plan = plan_jobs(registry, {}, NOW, policy, vciq_commit="a" * 40, config_hash="b" * 64, upstream_commit="c" * 40)
    job = next(row for row in plan["jobs"] if row["query"]["scope"] == ("account" if account else "track"))
    return job, registry.by_id()[job["queryId"]]


class FakeTransport:
    def __init__(self, search=None, article=None, second=None):
        self.search = fixture("sogou.html") if search is None else search
        self.article = fixture("article.html") if article is None else article
        self.second = second
        self.urls = []
        self.requests = 0

    def get(self, url):
        self.urls.append(url)
        self.requests += 1
        is_search = urlsplit(url).hostname in {"weixin.sogou.com", "www.bing.com"}
        content = self.search if is_search else self.article
        if is_search and parse_qs(urlsplit(url).query).get("page") == ["2"]:
            content = self.second
        if isinstance(content, Exception):
            raise content
        return Response(url, content)


class WechatTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("socket.create_connection", side_effect=AssertionError("live network forbidden")).start()

    def run_synthetic(self, job, context, transport):
        return wechat.run_job(job, context, transport, now=lambda: NOW)

    def test_W05_actual_sogou_url_changes_with_each_job(self):
        urls = []
        for text in ("人形机器人", "具身智能"):
            job, context = make_job(text=text)
            transport = FakeTransport(search=fixture("empty.html"))
            result = self.run_synthetic(job, context, transport)
            self.assertEqual(result["receipt"]["status"], "empty")
            urls.append(parse_qs(urlsplit(transport.urls[0]).query)["query"][0])
        self.assertEqual(urls, ["人形机器人", "具身智能"])

    def test_W05_bing_literal_query_is_sent_and_no_fake_pagination(self):
        for text in ("人形机器人", "具身智能"):
            job, context = make_job("bing-rss", text=text, pages=3)
            transport = FakeTransport(search=fixture("bing.xml"))
            result = self.run_synthetic(job, context, transport)
            query = parse_qs(urlsplit(transport.urls[0]).query)["q"][0]
            self.assertEqual(query, f'site:mp.weixin.qq.com/s "{text}"')
            self.assertEqual(len(result["receipt"]["pageReceipts"]), 1)
            self.assertEqual(result["receipt"]["completeness"], "bounded")

    def test_W06_track_accepts_unregistered_account_from_original(self):
        job, context = make_job()
        result = self.run_synthetic(job, context, FakeTransport())
        self.assertEqual(result["receipt"]["status"], "ok")
        observation = result["observations"][0]
        self.assertEqual(observation["author"]["displayName"], "合成未登记公众号")
        self.assertEqual(observation["evidence"]["role"], "discovery")
        self.assertEqual(observation["accessStatus"], "verified_public")
        validate(observation)

    def test_W06_account_requires_actual_page_match_not_index_name(self):
        job, context = make_job(account="合成指定公众号")
        misleading_index = fixture("sogou.html").replace("合成未登记公众号", "合成指定公众号")
        result = self.run_synthetic(job, context, FakeTransport(search=misleading_index))
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["hints"][0]["reason"], "ACCOUNT_MISMATCH")
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)

    def test_matching_account_accepted(self):
        job, context = make_job(account="合成指定公众号")
        article = fixture("article.html").replace("合成未登记公众号", "合成指定公众号")
        result = self.run_synthetic(job, context, FakeTransport(article=article))
        self.assertEqual(len(result["observations"]), 1)

    def test_W07_captcha_is_not_empty(self):
        job, context = make_job()
        result = self.run_synthetic(job, context, FakeTransport(search=fixture("verification.html")))
        self.assertEqual(result["receipt"]["status"], "verification_required")
        self.assertFalse(result["receipt"]["pageReceipts"][0]["schemaValid"])

    def test_W07_index_without_original_is_hint_not_verified_content(self):
        job, context = make_job()
        result = self.run_synthetic(job, context, FakeTransport(article=FetchError("network_error", "NETWORK_ERROR")))
        self.assertEqual(result["receipt"]["status"], "network_error")
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["receipt"]["counts"]["detailFailures"], 1)
        self.assertEqual(result["hints"][0]["reason"], "NETWORK_ERROR")

    def test_W07_explicit_empty_vs_unknown_html(self):
        job, context = make_job()
        empty = self.run_synthetic(job, context, FakeTransport(search=fixture("empty.html")))
        broken = self.run_synthetic(job, context, FakeTransport(search="<html>not a search result</html>"))
        self.assertEqual(empty["receipt"]["status"], "empty")
        self.assertEqual(broken["receipt"]["status"], "schema_error")

    def test_rss_html_login_is_never_empty(self):
        job, context = make_job("bing-rss")
        result = self.run_synthetic(job, context, FakeTransport(search='<html><form id="login"></form></html>'))
        self.assertEqual(result["receipt"]["status"], "auth_required")

    def test_second_page_failure_reports_partial_and_keeps_first(self):
        job, context = make_job(pages=2)
        transport = FakeTransport(search=fixture("sogou.html") + '<a id="sogou_next">下一页</a>',
                                  second=FetchError("network_error", "NETWORK_ERROR"))
        result = self.run_synthetic(job, context, transport)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(len(result["observations"]), 1)
        self.assertEqual(len(result["receipt"]["pageReceipts"]), 2)
        validate(result["receipt"])

    def test_second_page_explicit_empty_proves_only_query_exhaustion(self):
        job, context = make_job(pages=2)
        transport = FakeTransport(search=fixture("sogou.html") + '<a id="sogou_next">下一页</a>', second=fixture("empty.html"))
        result = self.run_synthetic(job, context, transport)
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["receipt"]["completeness"], "exhausted")
        self.assertEqual(len(result["observations"]), 1)

    def test_W08_signed_url_preserved_for_fetch_but_not_safe_export(self):
        url = "https://mp.weixin.qq.com/s?__biz=SYNTHETIC&amp;mid=123&amp;idx=1&amp;sn=SYNTHETIC&amp;timestamp=456"
        decoded = decode_url(url)
        self.assertIn("&timestamp=456", decoded)
        self.assertNotIn("×", decoded)
        native, canonical = wechat.identity(url)
        self.assertEqual(parse_qs(urlsplit(canonical).query), {"__biz": ["SYNTHETIC"], "mid": ["123"], "idx": ["1"]})
        self.assertEqual(native, wechat.identity(decoded.replace("sn=SYNTHETIC", "sn=CHANGED"))[0])
        self.assertNotIn("sn=", canonical)
        job, context = make_job()
        transport = FakeTransport(search=fixture("sogou.html").replace(ORIGINAL, url))
        result = self.run_synthetic(job, context, transport)
        self.assertIn("&timestamp=456", transport.urls[1])
        self.assertNotIn("sn=", json.dumps(result))

    def test_opaque_and_different_article_ids_do_not_merge(self):
        first = wechat.identity(ORIGINAL)[0]
        self.assertNotEqual(first, wechat.identity(ORIGINAL + "_OTHER")[0])
        self.assertNotEqual(wechat.identity("https://mp.weixin.qq.com/s?__biz=A&mid=1&idx=1")[0],
                            wechat.identity("https://mp.weixin.qq.com/s?__biz=A&mid=1&idx=2")[0])
        with self.assertRaises(FetchError):
            wechat.identity("https://mp.weixin.qq.com/s?__biz=A&mid=1&mid=2&idx=1")

    def test_future_missing_or_old_dates_not_filled_with_observation_time(self):
        job, context = make_job()
        for substitute in ("2030-01-01", "", "2020-01-01"):
            article = fixture("article.html").replace("2026-10-20", substitute)
            result = self.run_synthetic(job, context, FakeTransport(article=article))
            self.assertEqual(result["observations"], [])
            self.assertNotEqual(result["receipt"]["status"], "empty")

    def test_original_irrelevance_and_index_only_content_rejected(self):
        job, context = make_job()
        for article in (fixture("article.html").replace("人形机器人", "测试文章"), "<html><title>人形机器人</title></html>"):
            result = self.run_synthetic(job, context, FakeTransport(article=article))
            self.assertEqual(result["observations"], [])
            self.assertTrue(result["hints"])

    def test_http200_with_verification_original_pauses_not_success(self):
        job, context = make_job()
        result = self.run_synthetic(job, context, FakeTransport(article=fixture("verification.html")))
        self.assertEqual(result["receipt"]["status"], "verification_required")
        self.assertEqual(result["receipt"]["counts"]["emittedRows"], 0)

    def test_native_window_is_explicitly_unsupported(self):
        job, context = make_job()
        job["window"] = {"from": "2026-10-01", "to": "2026-10-24", "filterMode": "native"}
        transport = FakeTransport()
        self.assertEqual(self.run_synthetic(job, context, transport)["receipt"]["status"], "unsupported")
        self.assertEqual(transport.urls, [])

    def test_request_deadline_and_exception_text_not_exported(self):
        job, context = make_job()
        transport = FakeTransport(search=FetchError("timeout", "REQUEST_TIMEOUT"))
        result = self.run_synthetic(job, context, transport)
        self.assertEqual(result["receipt"]["status"], "timeout")
        self.assertEqual(result["receipt"]["errorCode"], "REQUEST_TIMEOUT")

    def test_ssrf_hosts_userinfo_paths_and_encoded_redirects_denied(self):
        for url in ("http://mp.weixin.qq.com/s/x", "https://127.0.0.1/s/x", "https://mp.weixin.qq.com.evil.invalid/s/x",
                    "https://mp.weixin.qq.com@evil.invalid/s/x", "https://mp.weixin.qq.com:8443/s/x",
                    "file:///etc/passwd", "https://mp.weixin.qq.com/%2e%2e/admin"):
            with self.subTest(url=url), self.assertRaises(FetchError):
                checked_url(url)
        connection = _PinnedConnection("mp.weixin.qq.com", timeout=1)
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaisesRegex(FetchError, "NON_PUBLIC_DESTINATION"):
                connection.connect()

    def test_W09_real_production_wrapper_order_unchanged(self):
        script = r'''
import json, sys
from pathlib import Path
from unittest.mock import patch
from tools import crawl_with_wechat_registry as production
from tools import wechat_source_registry as registry
from tools import wechat_public_sources as parser
from tools.social.adapters.wechat import run_job
from tests.test_social_wechat import make_job, FakeTransport, NOW

def deny(*a, **k): raise AssertionError("network forbidden")
with patch("socket.create_connection", deny), patch.object(production.base, "main", return_value=0):
    production.main()
tracks=[{"name":"机器人", "slug":"robot", "enabled":True,"keywords":["人形机器人"],"sampleCompanies":[],"people":[]}]
before=json.dumps(registry.generated_wechat_sources(tracks, None), sort_keys=True, ensure_ascii=False)
bindings=(parser.parse_wechat_article, parser.crawl_wechat_source, production.base.tracking.crawler.replace_source_batches)
job, context=make_job()
run_job(job, context, FakeTransport(), now=lambda: NOW)
after=json.dumps(registry.generated_wechat_sources(tracks, None), sort_keys=True, ensure_ascii=False)
assert before==after
assert bindings==(parser.parse_wechat_article, parser.crawl_wechat_source, production.base.tracking.crawler.replace_source_batches)
print("PRODUCTION_WRAPPER_REPLAY_OK")
'''
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True,
                                timeout=30, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PRODUCTION_WRAPPER_REPLAY_OK", result.stdout)

    def test_cli_dry_plan_no_directory_no_network_no_production_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, accounts = root / "tracking.json", root / "accounts.json"
            config.write_text(json.dumps({"tracks": [{"name": "机器人", "keywords": ["人形机器人"]}]}))
            accounts.write_text('{"accounts": []}')
            state = root / "absent"
            before = protected_snapshot(ROOT)
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                code = planning_main(["plan", "--config", str(config), "--accounts", str(accounts),
                                      "--state-dir", str(state), "--dry-run", "--vciq-commit", "a" * 40])
            self.assertEqual(code, 0)
            validate(json.loads(captured.getvalue()), expected_kind="job_plan")
            self.assertFalse(state.exists())
            assert_unchanged(before, repo_root=ROOT)


if __name__ == "__main__":
    unittest.main()
