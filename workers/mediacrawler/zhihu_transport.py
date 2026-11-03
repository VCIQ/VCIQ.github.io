"""Restricted Zhihu JSON transport, independent of the upstream retry policy."""
from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlsplit

MAX_RESPONSE = 2 * 1024 * 1024


def retry_after(value, now):
    try:
        return int(value) if value.isdigit() else max(0, math.ceil((parsedate_to_datetime(value) - now).total_seconds()))
    except (AttributeError, ValueError, TypeError, OverflowError):
        return None


def response_payload(status, headers, body, observer, *, now=None):
    error = observer.CollectorError
    if status == 401: raise error("auth_required", "HTTP_AUTH_REQUIRED")
    if status in {403, 461, 471}: raise error("verification_required", "HTTP_VERIFICATION_REQUIRED")
    if status == 429:
        raise error("rate_limited", "HTTP_RATE_LIMIT", retry_after(headers.get("retry-after", ""), now or datetime.now(timezone.utc)))
    if 300 <= status < 400: raise error("auth_required", "LOGIN_REDIRECT_NOT_FOLLOWED")
    if status != 200: raise error("network_error", "HTTP_REQUEST_FAILED")
    if len(body) > MAX_RESPONSE: raise error("schema_error", "HTTP_RESPONSE_TOO_LARGE")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate")
            result[key] = value
        return result
    def constant(_): raise ValueError("nonfinite")
    try:
        payload = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise error("schema_error", "HTTP_JSON_REQUIRED") from None
    if not isinstance(payload, dict): raise error("schema_error", "HTTP_OBJECT_REQUIRED")
    if ("error" in payload and payload["error"] is not None
        or "code" in payload and (type(payload["code"]) is not int or payload["code"] != 0)
        or payload.get("success") is False):
        detail = payload.get("error")
        message = detail.get("message", "") if isinstance(detail, dict) else payload.get("message", "")
        message = message.casefold() if isinstance(message, str) else ""
        if any(word in message for word in ("登录", "login", "log in")):
            raise error("auth_required", "PLATFORM_AUTH_REQUIRED")
        if any(word in message for word in ("频繁", "rate limit", "too many")):
            raise error("rate_limited", "PLATFORM_RATE_LIMIT")
        if any(word in message for word in ("验证码", "验证", "captcha", "安全")):
            raise error("verification_required", "PLATFORM_VERIFICATION_REQUIRED")
        raise error("schema_error", "PLATFORM_NEGATIVE_RESPONSE")
    return payload


class ZhihuGate:
    def __init__(self, observer, keyword, pages, *, client_factory=None, sleep=asyncio.sleep, monotonic=time.monotonic):
        self.observer, self.keyword, self.pages = observer, keyword, pages
        self.client_factory, self.sleep, self.monotonic = client_factory, sleep, monotonic
        self.requests, self.next_request, self.seen = 0, 0.0, set()

    def check_url(self, method, url):
        try:
            parts = urlsplit(str(url))
            if (method != "GET" or parts.scheme != "https" or parts.hostname != "www.zhihu.com"
                or parts.port is not None or parts.username is not None or parts.fragment or "\\" in str(url)):
                raise ValueError
            if parts.path == "/api/v4/me" and not parts.query:
                return "auth"
            if parts.path != "/api/v4/search_v3": raise ValueError
            pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
            params = dict(pairs)
            offset = params.get("offset", "")
            if not offset.isascii() or not offset.isdigit() or str(int(offset)) != offset:
                raise ValueError
            number = int(offset)
            if number % 20 or not 0 <= number < self.pages * 20: raise ValueError
            expected = {"gk_version": "gz-gaokao", "t": "general", "q": self.keyword,
                "correction": "1", "offset": offset, "limit": "20", "filter_fields": "",
                "lc_idx": offset, "show_all_topics": "0", "search_source": "Filter",
                "time_interval": "", "sort": "", "vertical": ""}
            if len(params) != len(pairs) or params != expected: raise ValueError
            return number
        except (ValueError, TypeError):
            raise self.observer.CollectorError("unsupported", "HTTP_ENDPOINT_NOT_ALLOWED") from None

    def factory(self, proxy=None, **kwargs):
        if proxy is not None or kwargs:
            raise self.observer.CollectorError("unsupported", "PROXY_OR_OPTIONS_FORBIDDEN")
        gate = self
        class Transport:
            async def __aenter__(self):
                if gate.client_factory is None:
                    import httpx
                    self.client = httpx.AsyncClient(verify=True, trust_env=False, follow_redirects=False, timeout=20)
                else:
                    self.client = gate.client_factory()
                return self
            async def __aexit__(self, *args):
                await self.client.aclose()
            async def request(self, method, url, **options):
                key = gate.check_url(method, url)
                options.pop("timeout", None)
                if set(options) - {"headers"}:
                    raise gate.observer.CollectorError("unsupported", "HTTP_OPTIONS_NOT_ALLOWED")
                if key in gate.seen or key != "auth" and "auth" not in gate.seen:
                    raise gate.observer.CollectorError("unsupported", "HTTP_REQUEST_ORDER")
                if gate.requests >= 1 + gate.pages:
                    raise gate.observer.CollectorError("cancelled", "API_REQUEST_BUDGET")
                await gate.sleep(max(0, gate.next_request - gate.monotonic()))
                gate.next_request = gate.monotonic() + 2
                gate.requests += 1
                gate.seen.add(key)
                try:
                    async with self.client.stream(method, url, **options) as response:
                        headers = {key.lower(): value for key, value in response.headers.items()}
                        if response.status_code != 200:
                            response_payload(response.status_code, headers, b"", gate.observer)
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE:
                                raise gate.observer.CollectorError("schema_error", "HTTP_RESPONSE_TOO_LARGE")
                        payload = response_payload(response.status_code, headers, bytes(body), gate.observer)
                        class Response:
                            status_code = response.status_code
                            text = "[validated JSON response]"
                            def json(self): return payload
                        return Response()
                except gate.observer.CollectorError:
                    raise
                except Exception as exc:
                    if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
                        raise gate.observer.CollectorError("timeout", "REQUEST_TIMEOUT") from None
                    raise gate.observer.CollectorError("network_error", "REQUEST_FAILED") from None
            async def get(self, url, **options):
                return await self.request("GET", url, **options)
        return Transport()
