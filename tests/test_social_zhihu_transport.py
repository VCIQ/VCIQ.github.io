"""Zhihu request boundary tested with in-memory HTTP streams only."""
import json
import unittest
from datetime import UTC, datetime
from urllib.parse import urlencode

from tests.test_social_weibo_transport import Client, Stream
from workers.mediacrawler import observer
from workers.mediacrawler.zhihu_transport import MAX_RESPONSE, ZhihuGate, response_payload, retry_after

AUTH = "https://www.zhihu.com/api/v4/me"


def search_url(keyword="机器人", page=1, **changes):
    offset = (page - 1) * 20
    params = {"gk_version": "gz-gaokao", "t": "general", "q": keyword, "correction": 1,
        "offset": offset, "limit": 20, "filter_fields": "", "lc_idx": offset,
        "show_all_topics": 0, "search_source": "Filter", "time_interval": "", "sort": "", "vertical": ""}
    params.update(changes)
    return "https://www.zhihu.com/api/v4/search_v3?" + urlencode(params)


class ZhihuTransportTests(unittest.IsolatedAsyncioTestCase):
    def gate(self, streams, pages=2):
        self.calls, self.delays = [], []
        async def sleep(delay): self.delays.append(delay)
        return ZhihuGate(observer, "机器人", pages, client_factory=lambda: Client(streams, self.calls), sleep=sleep, monotonic=lambda: 100.0)

    def test_exact_host_method_and_query(self):
        gate = self.gate([])
        self.assertEqual(gate.check_url("GET", AUTH), "auth")
        self.assertEqual(gate.check_url("GET", search_url(page=2)), 20)
        for url in (search_url("other"), search_url(page=3), search_url(limit=50), search_url(lc_idx=1), search_url() + "&offset=0", AUTH + "?include=email,is_bind_phone", AUTH.replace("www.zhihu.com", "www.zhihu.com.evil.invalid"), AUTH.replace("https:", "http:"), AUTH.replace(".com/", ".com:443/"), AUTH.replace("//www", "//u@www"), AUTH + "#x", "https://www.zhihu.com/api/v4/answers/1"):
            with self.subTest(url=url), self.assertRaises(observer.CollectorError): gate.check_url("GET", url)
        with self.assertRaises(observer.CollectorError): gate.check_url("POST", search_url())

    async def test_shared_budget_and_request_spacing(self):
        gate = self.gate([Stream(body=b'{}') for _ in range(3)])
        for url in (AUTH, search_url(), search_url(page=2)):
            async with gate.factory() as client:
                self.assertEqual((await client.get(url, headers={"cookie": "PRIVATE"})).json(), {})
        self.assertEqual(gate.requests, 3)
        self.assertEqual(self.delays, [0, 2, 2])
        self.assertEqual(len(self.calls), 3)

    async def test_repeated_request_or_search_before_auth_rejected(self):
        gate = self.gate([Stream(body=b'{}')])
        with self.assertRaisesRegex(observer.CollectorError, "REQUEST_ORDER"):
            async with gate.factory() as client: await client.get(search_url())
        async with gate.factory() as client: await client.get(AUTH)
        with self.assertRaisesRegex(observer.CollectorError, "REQUEST_ORDER"):
            async with gate.factory() as client: await client.get(AUTH)
        self.assertEqual(len(self.calls), 1)

    def test_negative_json_html_duplicates_nonfinite_rejected(self):
        for body in (b'<html>login</html>', b'[]', b'{"error":{}}', b'{"error":{"message":"no data"}}', b'{"code":true}', b'{"data":[],"data":[]}', b'{"data":[NaN]}'):
            with self.subTest(body=body), self.assertRaises(observer.CollectorError): response_payload(200, {}, body, observer)

    def test_restriction_messages_classified_without_echo(self):
        for message, status in (("请登录 PRIVATE", "auth_required"), ("请安全验证 PRIVATE", "verification_required"), ("请求频繁 PRIVATE", "rate_limited")):
            with self.assertRaises(observer.CollectorError) as caught:
                response_payload(200, {}, json.dumps({"error": {"message": message}}).encode(), observer)
            self.assertEqual(caught.exception.status, status)
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_status_restrictions_and_redirect_not_zero(self):
        for code, status in ((401, "auth_required"), (403, "verification_required"), (471, "verification_required"), (302, "auth_required"), (404, "network_error"), (500, "network_error")):
            with self.assertRaises(observer.CollectorError) as caught: response_payload(code, {}, b"PRIVATE", observer)
            self.assertEqual(caught.exception.status, status)
            self.assertNotIn("PRIVATE", str(caught.exception))

    async def test_response_size_bounded(self):
        gate = self.gate([Stream(body=b"x" * (MAX_RESPONSE + 1))])
        with self.assertRaisesRegex(observer.CollectorError, "TOO_LARGE"):
            async with gate.factory() as client: await client.get(AUTH)

    async def test_rate_limit_retry_after_preserved_no_retry(self):
        gate = self.gate([Stream(status=429, headers={"Retry-After": "90000"})])
        with self.assertRaises(observer.CollectorError) as caught:
            async with gate.factory() as client: await client.get(AUTH)
        self.assertEqual(caught.exception.retry_after, 90000)
        self.assertEqual(caught.exception.status, "rate_limited")
        self.assertEqual(len(self.calls), 1)

    def test_retry_http_date_and_invalid_value(self):
        now = datetime(2026, 11, 3, 8, tzinfo=UTC)
        self.assertEqual(retry_after("Tue, 03 Nov 2026 08:02:00 GMT", now), 120)
        self.assertIsNone(retry_after("-5", now))
        self.assertIsNone(retry_after("not-a-date", now))

    async def test_options_proxy_and_tls_override_denied(self):
        gate = self.gate([])
        for args in ({"proxy": "PRIVATE"}, {"verify": False}):
            with self.assertRaises(observer.CollectorError): gate.factory(**args)
        with self.assertRaises(observer.CollectorError):
            async with gate.factory() as client: await client.get(AUTH, follow_redirects=True)
        self.assertEqual(self.calls, [])

    async def test_network_and_timeout_errors_have_no_raw_values(self):
        for exc, status in ((OSError("PRIVATE"), "network_error"), (TimeoutError("PRIVATE"), "timeout")):
            gate = self.gate([exc])
            with self.assertRaises(observer.CollectorError) as caught:
                async with gate.factory() as client: await client.get(AUTH)
            self.assertEqual(caught.exception.status, status)
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_empty_success_envelope_survives_for_paging_validation(self):
        payload = {"data": [], "paging": {"is_end": True}}
        self.assertEqual(response_payload(200, {}, json.dumps(payload).encode(), observer), payload)


if __name__ == "__main__": unittest.main()
