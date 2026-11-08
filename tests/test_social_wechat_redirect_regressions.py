"""Synthetic reproductions of observed redirects; never fetch a challenge page."""
import ssl
import tempfile
import unittest
from pathlib import Path

from tests.test_social_execution_guards import Connection, HttpResponse, transport
from tests.test_social_wechat import NOW, make_job
from tools.social.adapters.wechat import run_job
from tools.social.adapters.wechat_transport import FetchError, PublicTransport, checked_url
from tools.social.batch import ROOT, build_batch
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.scheduler_state import SchedulerStore, read_state


class WechatRedirectRegressionTests(unittest.TestCase):
    def test_cn_search_is_allowed_but_other_paths_and_hosts_are_not(self):
        self.assertEqual(checked_url("https://cn.bing.com/search?q=synthetic"),
            "https://cn.bing.com/search?q=synthetic")
        for url in ("https://cn.bing.com/", "https://cn.bing.com/account",
                "https://other.bing.com/search", "https://cn.bing.com.evil.invalid/search"):
            with self.subTest(url=url), self.assertRaisesRegex(FetchError, "UNSAFE_DESTINATION"):
                checked_url(url)

    def test_regional_handoff_preserves_query_and_both_quota_debits(self):
        target = "https://cn.bing.com/search?q=synthetic%20term&format=rss"
        debits = []
        client = transport([HttpResponse(302, {"Location": target}), HttpResponse()], debits)
        self.assertEqual(client.get("https://www.bing.com/search?q=synthetic%20term&format=rss").url, target)
        self.assertEqual(len(debits), 2)
        self.assertEqual(client.requests, 2)

    def test_reverse_regional_handoff_is_bounded(self):
        debits = []
        client = transport([HttpResponse(302, {"Location": "https://www.bing.com/search?q=synthetic"}), HttpResponse()], debits)
        self.assertEqual(client.get("https://cn.bing.com/search?q=synthetic").url,
            "https://www.bing.com/search?q=synthetic")
        self.assertEqual(len(debits), 2)

    def test_regional_requests_retain_tls_hostname_verification(self):
        hosts, contexts = [], []
        responses = iter([HttpResponse(302, {"Location": "https://cn.bing.com/search?q=synthetic"}), HttpResponse()])
        def factory(host, *, timeout, context):
            hosts.append(host); contexts.append(context)
            return Connection(next(responses))
        client = PublicTransport(before_request=lambda: None, deadline=100, monotonic=lambda: 0,
            sleep=lambda _: None, connection_factory=factory)
        client.get("https://www.bing.com/search?q=synthetic")
        self.assertEqual(hosts, ["www.bing.com", "cn.bing.com"])
        self.assertTrue(all(c.check_hostname and c.verify_mode == ssl.CERT_REQUIRED for c in contexts))

    def test_regional_http_downgrade_stays_forbidden(self):
        debits = []
        client = transport([HttpResponse(302, {"Location": "http://cn.bing.com/search?q=synthetic"})], debits)
        with self.assertRaisesRegex(FetchError, "UNSAFE_DESTINATION"):
            client.get("https://www.bing.com/search?q=synthetic")
        self.assertEqual(len(debits), 1)

    def test_port_userinfo_and_fragment_stay_forbidden(self):
        for target in ("https://cn.bing.com:443/search", "https://user@cn.bing.com/search",
                "https://cn.bing.com/search#fragment"):
            with self.subTest(target=target), self.assertRaisesRegex(FetchError, "UNSAFE_DESTINATION"):
                checked_url(target)

    def test_bing_cannot_redirect_into_wechat(self):
        client = transport([HttpResponse(302, {"Location": "https://mp.weixin.qq.com/s/SYNTHETIC"})], [])
        with self.assertRaisesRegex(FetchError, "CROSS_PROVIDER_REDIRECT"):
            client.get("https://cn.bing.com/search?q=synthetic")

    def test_sogou_cannot_redirect_into_regional_bing(self):
        client = transport([HttpResponse(302, {"Location": "https://cn.bing.com/search?q=synthetic"})], [])
        with self.assertRaisesRegex(FetchError, "CROSS_PROVIDER_REDIRECT"):
            client.get("https://weixin.sogou.com/link?url=synthetic")

    def test_http_and_https_challenges_are_classified_but_never_followed(self):
        for scheme in ("http", "https"):
            debits = []
            client = transport([HttpResponse(302, {"Location": scheme + "://weixin.sogou.com/antispider/?from=synthetic"})], debits)
            with self.subTest(scheme=scheme), self.assertRaises(FetchError) as caught:
                client.get("https://weixin.sogou.com/link?url=synthetic")
            self.assertEqual(caught.exception.status, "verification_required")
            self.assertEqual(caught.exception.code, "SEARCH_VERIFICATION_REDIRECT")
            self.assertEqual(client.requests, 1); self.assertEqual(len(debits), 1)

    def test_relative_challenge_is_not_a_normal_empty_result(self):
        job, context = make_job()
        client = transport([HttpResponse(302, {"Location": "/antispider/?from=synthetic"})], [])
        result = run_job(job, context, client, now=lambda: NOW)
        self.assertEqual(result["receipt"]["status"], "verification_required")
        self.assertEqual(result["receipt"]["stopReason"], "verification")
        self.assertEqual(result["observations"], [])
        build_batch([job], [result["receipt"]], [], created_at=NOW.isoformat())

    def test_challenge_lookalikes_do_not_get_special_treatment(self):
        for target in ("http://weixin.sogou.com.evil.invalid/antispider/",
                "http://weixin.sogou.com/antispider/extra", "http://user@weixin.sogou.com/antispider/",
                "http://weixin.sogou.com:80/antispider/", "http://weixin.sogou.com/antispider/#x"):
            client = transport([HttpResponse(302, {"Location": target})], [])
            with self.subTest(target=target), self.assertRaisesRegex(FetchError, "UNSAFE_DESTINATION"):
                client.get("https://weixin.sogou.com/link?url=synthetic")

    def test_other_provider_cannot_trigger_sogou_challenge_classification(self):
        client = transport([HttpResponse(302, {"Location": "http://weixin.sogou.com/antispider/"})], [])
        with self.assertRaisesRegex(FetchError, "UNSAFE_DESTINATION"):
            client.get("https://www.bing.com/search?q=synthetic")

    def test_verification_receipt_pauses_scheduler(self):
        job, context = make_job()
        client = transport([HttpResponse(302, {"Location": "http://weixin.sogou.com/antispider/"})], [])
        result = run_job(job, context, client, now=lambda: NOW)
        registry = build_query_registry({"tracks": [{"name": "机器人", "slug": "robot", "keywords": ["人形机器人"]}]}, load_policy())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with SchedulerStore(root, repo_roots=(ROOT,)) as store:
                store.sync(registry); self.assertTrue(store.claim(job, NOW))
                store.finish(job, result, NOW, cadence_hours=24)
            state = read_state(root, repo_roots=(ROOT,))
            self.assertEqual(state["platforms"]["wechat"]["pauseReason"], "verification")
            self.assertIsNone(state["queries"][job["queryId"]]["lastCoveredAt"])

    def test_redirect_loop_does_not_expand_request_limit(self):
        responses = [HttpResponse(302, {"Location": "https://cn.bing.com/search?q=synthetic"}) for _ in range(4)]
        debits = []; client = transport(responses, debits)
        with self.assertRaisesRegex(FetchError, "REDIRECT_LIMIT"):
            client.get("https://www.bing.com/search?q=synthetic")
        self.assertEqual(len(debits), 4)

    def test_second_hop_requires_a_fresh_budget_debit(self):
        debits = []
        def debit():
            if debits: raise FetchError("cancelled", "REQUEST_BUDGET_EXHAUSTED")
            debits.append(True)
        client = transport([HttpResponse(302, {"Location": "https://cn.bing.com/search?q=synthetic"})], [])
        client.before_request = debit
        with self.assertRaisesRegex(FetchError, "REQUEST_BUDGET_EXHAUSTED"):
            client.get("https://www.bing.com/search?q=synthetic")
        self.assertEqual(client.requests, 1)


if __name__ == "__main__": unittest.main()
