"""Restricted Bilibili HTTP checks with memory responses only."""
import json
import unittest
from datetime import UTC, datetime
from urllib.parse import urlencode

from workers.mediacrawler import observer
from workers.mediacrawler.bilibili_transport import BilibiliGate, response_payload, retry_after, MAX_RESPONSE

NAV = "https://api.bilibili.com/x/web-interface/nav"


def search_url(keyword="robot", page=1, **changes):
    args = {"search_type": "video", "keyword": keyword, "page": page, "page_size": 20,
            "order": "", "pubtime_begin_s": 0, "pubtime_end_s": 0, "wts": 1760000000, "w_rid": "a" * 32}
    args.update(changes)
    return "https://api.bilibili.com/x/web-interface/wbi/search/type?" + urlencode(args)


class MemoryResponse:
    def __init__(self, data=None, *, status=200, body=None, headers=None):
        self.status_code, self.headers = status, headers or {}
        self.body = body if body is not None else json.dumps({"code": 0, "data": data or {}}).encode()
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def aiter_bytes(self): yield self.body


class MemoryClient:
    def __init__(self, responses, calls): self.responses, self.calls = responses, calls
    def stream(self, method, url, **options):
        self.calls.append((method, url, options))
        value = self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return value
    async def aclose(self): pass


class BilibiliTransportTests(unittest.IsolatedAsyncioTestCase):
    def gate(self, responses, *, pages=1, records=1):
        calls, sleeps = [], []
        async def sleep(value): sleeps.append(value)
        gate = BilibiliGate(observer, "robot", pages, records,
            client_factory=lambda: MemoryClient(responses, calls), sleep=sleep, monotonic=lambda: 100)
        return gate, calls, sleeps

    async def test_exact_signed_query_and_detail_allowlist(self):
        gate, _, _ = self.gate([])
        gate.check_url("GET", NAV)
        gate.check_url("GET", search_url())
        detail = "https://api.bilibili.com/x/web-interface/view/detail?aid=123"
        with self.assertRaises(observer.CollectorError): gate.check_url("GET", detail)
        gate.allow_detail("123")
        gate.check_url("GET", detail)
        for url in (search_url("other"), search_url(page=2), search_url(order="click"), search_url(page_size=100), search_url() + "&page=1", NAV + "?x=1", "https://api.bilibili.com.evil/x/web-interface/nav", "https://api.bilibili.com/x/player/wbi/playurl?avid=123", detail + "&bvid=BV1d54y1g7db"):
            with self.subTest(url=url), self.assertRaises(observer.CollectorError): gate.check_url("GET", url)
        with self.assertRaises(observer.CollectorError): gate.check_url("POST", NAV)

    async def test_status_restrictions_and_redirect(self):
        for status, expected in ((401, "auth_required"), (403, "verification_required"), (412, "verification_required"), (429, "rate_limited"), (302, "auth_required"), (503, "network_error")):
            with self.subTest(status=status), self.assertRaises(observer.CollectorError) as error:
                response_payload(status, {}, b"private response", observer)
            self.assertEqual(error.exception.status, expected)
            self.assertNotIn("private response", str(error.exception))

    async def test_retry_after_preserved_no_retry(self):
        gate, calls, _ = self.gate([MemoryResponse(status=429, headers={"Retry-After": "600"})])
        with self.assertRaises(observer.CollectorError) as error:
            async with gate.factory() as client: await client.get(NAV)
        self.assertEqual(error.exception.retry_after, 600)
        self.assertEqual(len(calls), 1)

    async def test_error_json_and_login_html_not_empty(self):
        for body in (b'<html>login</html>', b'{"code":false,"data":{}}', b'{"code":-1,"message":"no results","data":{}}', b'{"code":0,"data":[]}', b'{"code":0,"code":0,"data":{}}', b'{"code":0,"data":{"v":NaN}}'):
            with self.subTest(body=body), self.assertRaises(observer.CollectorError): response_payload(200, {}, body, observer)

    async def test_platform_messages_restricted_without_echo(self):
        for message, status in (("请登录", "auth_required"), ("请求频繁", "rate_limited"), ("请进行验证", "verification_required")):
            with self.assertRaises(observer.CollectorError) as caught:
                response_payload(200, {}, json.dumps({"code": -1, "message": message}).encode(), observer)
            self.assertEqual(caught.exception.status, status)
            self.assertNotIn(message, str(caught.exception))

    async def test_budget_shared_across_contexts(self):
        gate, calls, sleeps = self.gate([MemoryResponse() for _ in range(4)])
        for _ in range(3):
            async with gate.factory() as client: await client.get(NAV)
        with self.assertRaises(observer.CollectorError):
            async with gate.factory() as client: await client.get(NAV)
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [0, 2, 2])

    async def test_detail_budget_and_scalar_identity(self):
        gate, _, _ = self.gate([])
        gate.allow_detail("123")
        with self.assertRaises(observer.CollectorError): gate.allow_detail("124")
        with self.assertRaises(observer.CollectorError): gate.allow_detail(123.0)

    async def test_response_size_and_options(self):
        gate, calls, _ = self.gate([MemoryResponse(body=b"x" * (MAX_RESPONSE + 1))])
        with self.assertRaises(observer.CollectorError):
            async with gate.factory() as client: await client.get(NAV)
        with self.assertRaises(observer.CollectorError): gate.factory(proxy="http://private")
        with self.assertRaises(observer.CollectorError):
            async with gate.factory() as client: await client.request("GET", NAV, data="private")
        self.assertEqual(len(calls), 1)

    async def test_network_error_not_echoed(self):
        gate, _, _ = self.gate([TimeoutError("Cookie: PRIVATE")])
        with self.assertRaises(observer.CollectorError) as error:
            async with gate.factory() as client: await client.get(NAV)
        self.assertEqual(error.exception.status, "timeout")
        self.assertNotIn("PRIVATE", str(error.exception))

    async def test_retry_after_date_rounding(self):
        now = datetime(2026, 11, 3, 0, 0, 0, 500000, tzinfo=UTC)
        self.assertEqual(retry_after("Tue, 03 Nov 2026 00:00:02 GMT", now), 2)
        self.assertIsNone(retry_after("invalid", now))


if __name__ == "__main__": unittest.main()
