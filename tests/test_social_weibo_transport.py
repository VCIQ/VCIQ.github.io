"""HTTP-layer regression with in-memory streams; no socket or actual upstream import."""
import json
import unittest
from datetime import UTC, datetime
from urllib.parse import urlencode

from workers.mediacrawler import observer
from workers.mediacrawler.weibo_transport import MAX_RESPONSE, WeiboGate, response_payload, retry_after

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def search_url(keyword="机器人", page=1):
    return "https://m.weibo.cn/api/container/getIndex?" + urlencode({"containerid": "100103type=1&q=" + keyword, "page_type": "searchall", "page": page})


class Stream:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self.headers = status, headers or {}
        self.body = json.dumps({"ok": 1, "data": {"cards": []}}).encode() if body is None else body
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def aiter_bytes(self):
        yield self.body


class Client:
    def __init__(self, streams, calls): self.streams, self.calls = streams, calls
    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        value = self.streams.pop(0)
        if isinstance(value, Exception): raise value
        return value
    async def aclose(self): pass


class WeiboTransportTests(unittest.IsolatedAsyncioTestCase):
    def gate(self, streams, pages=1):
        self.calls, self.delays = [], []
        async def sleep(value): self.delays.append(value)
        return WeiboGate(observer, "机器人", pages, client_factory=lambda: Client(streams, self.calls), sleep=sleep, monotonic=lambda: 100.0)

    def test_endpoint_exact_host_query_and_method(self):
        gate = self.gate([])
        gate.check_url("GET", search_url())
        gate.check_url("GET", "https://m.weibo.cn/api/config")
        for url in (search_url("别的词"), search_url(page=2), search_url() + "&page=1", "https://m.weibo.cn/api/config?x=1", "http://m.weibo.cn/api/config", "https://m.weibo.cn:443/api/config", "https://m.weibo.cn.evil.invalid/api/config", "https://u@m.weibo.cn/api/config", "https://m.weibo.cn/comments/hotflow", "https://m.weibo.cn/api/config#fragment"):
            with self.subTest(url=url), self.assertRaises(observer.CollectorError): gate.check_url("GET", url)
        with self.assertRaises(observer.CollectorError): gate.check_url("POST", search_url())

    async def test_budget_spans_client_contexts_and_spaces_requests(self):
        gate = self.gate([Stream(), Stream()])
        for url in ("https://m.weibo.cn/api/config", search_url()):
            async with gate.factory() as client:
                response = await client.request("GET", url, headers={"Cookie": "PRIVATE"}, timeout=60)
                self.assertEqual(response.json()["ok"], 1)
        with self.assertRaisesRegex(observer.CollectorError, "API_REQUEST_BUDGET"):
            async with gate.factory() as client: await client.get(search_url())
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.delays, [0, 2])

    async def test_limit_response_size(self):
        gate = self.gate([Stream(body=b"x" * (MAX_RESPONSE + 1))])
        with self.assertRaisesRegex(observer.CollectorError, "TOO_LARGE"):
            async with gate.factory() as client: await client.get(search_url())

    async def test_rate_limit_preserves_retry_after_without_retry(self):
        gate = self.gate([Stream(status=429, headers={"Retry-After": "90000"})])
        with self.assertRaises(observer.CollectorError) as error:
            async with gate.factory() as client: await client.get(search_url())
        self.assertEqual(error.exception.status, "rate_limited")
        self.assertEqual(error.exception.retry_after, 90000)
        self.assertEqual(len(self.calls), 1)

    def test_status_restrictions_and_redirect_never_empty(self):
        for status, expected in ((401, "auth_required"), (403, "verification_required"), (432, "verification_required"), (302, "auth_required"), (500, "network_error")):
            with self.subTest(status=status), self.assertRaises(observer.CollectorError) as error:
                response_payload(status, {}, b"PRIVATE", observer, now=NOW)
            self.assertEqual(error.exception.status, expected)
            self.assertNotIn("PRIVATE", str(error.exception))

    def test_http200_login_html_negative_json_are_not_zero(self):
        for body in (b"<html>login</html>", b'{"ok":0,"msg":"no data"}', b'{"ok":1,"data":[]}', b'{"ok":true,"data":{}}', b'{"ok":1,"ok":0,"data":{}}', b'{"ok":1,"data":{"x":NaN}}'):
            with self.subTest(body=body), self.assertRaises(observer.CollectorError):
                response_payload(200, {}, body, observer)

    def test_negative_messages_classify_auth_and_verification(self):
        for message, expected in (("请登录 PRIVATE", "auth_required"), ("请进行验证 PRIVATE", "verification_required"), ("操作频繁 PRIVATE", "rate_limited")):
            with self.assertRaises(observer.CollectorError) as error:
                response_payload(200, {}, json.dumps({"ok": 0, "msg": message}).encode(), observer)
            self.assertEqual(error.exception.status, expected)
            self.assertNotIn("PRIVATE", str(error.exception))

    def test_retry_date_and_invalid_value(self):
        self.assertEqual(retry_after("Fri, 23 Oct 2026 12:02:00 GMT", NOW), 120)
        self.assertIsNone(retry_after("invalid", NOW))
        self.assertIsNone(retry_after("-5", NOW))

    async def test_proxy_and_options_rejected_without_network(self):
        gate = self.gate([])
        with self.assertRaises(observer.CollectorError): gate.factory(proxy="PRIVATE")
        with self.assertRaises(observer.CollectorError): gate.factory(verify=False)
        with self.assertRaises(observer.CollectorError):
            async with gate.factory() as client: await client.get(search_url(), follow_redirects=True)
        self.assertEqual(self.calls, [])

    async def test_timeout_or_network_error_never_echo_response(self):
        for exception, status in ((TimeoutError("PRIVATE"), "timeout"), (OSError("PRIVATE"), "network_error")):
            gate = self.gate([exception])
            with self.assertRaises(observer.CollectorError) as error:
                async with gate.factory() as client: await client.get(search_url())
            self.assertEqual(error.exception.status, status)
            self.assertNotIn("PRIVATE", str(error.exception))


if __name__ == "__main__": unittest.main()
