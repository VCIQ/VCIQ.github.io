"""Restricted Bilibili metadata API transport; no retries, proxies or media routes."""
from __future__ import annotations

import asyncio
import json
import math
import re
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
    if len(body) > MAX_RESPONSE: raise error("schema_error", "HTTP_RESPONSE_TOO_LARGE")
    if status == 401: raise error("auth_required", "HTTP_AUTH_REQUIRED")
    if status in {403, 412, 461, 471}: raise error("verification_required", "HTTP_VERIFICATION_REQUIRED")
    if status == 429:
        raise error("rate_limited", "HTTP_RATE_LIMIT", retry_after(headers.get("retry-after", ""), now or datetime.now(timezone.utc)))
    if 300 <= status < 400: raise error("auth_required", "LOGIN_REDIRECT_NOT_FOLLOWED")
    if status != 200: raise error("network_error", "HTTP_REQUEST_FAILED")
    def pairs(items):
        value = {}
        for key, child in items:
            if key in value: raise ValueError("duplicate")
            value[key] = child
        return value
    def constant(_): raise ValueError("nonfinite")
    try:
        payload = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise error("schema_error", "HTTP_JSON_REQUIRED") from None
    if not isinstance(payload, dict): raise error("schema_error", "HTTP_OBJECT_REQUIRED")
    if type(payload.get("code")) is not int or payload["code"] != 0:
        message = payload.get("message", "")
        message = message.casefold() if isinstance(message, str) else ""
        if any(word in message for word in ("登录", "login", "log in")):
            raise error("auth_required", "PLATFORM_AUTH_REQUIRED")
        if any(word in message for word in ("频繁", "rate limit", "too many")):
            raise error("rate_limited", "PLATFORM_RATE_LIMIT")
        if any(word in message for word in ("验证码", "验证", "风控", "captcha", "risk")):
            raise error("verification_required", "PLATFORM_VERIFICATION_REQUIRED")
        raise error("schema_error", "PLATFORM_NEGATIVE_RESPONSE")
    if not isinstance(payload.get("data"), dict): raise error("schema_error", "HTTP_DATA_OBJECT_REQUIRED")
    return payload


class BilibiliGate:
    def __init__(self, observer, keyword, pages, records, *, client_factory=None, sleep=asyncio.sleep, monotonic=time.monotonic):
        self.observer, self.keyword, self.pages, self.records = observer, keyword, pages, records
        self.client_factory, self.sleep, self.monotonic = client_factory, sleep, monotonic
        self.requests, self.next_request, self.detail_ids = 0, 0.0, set()

    def allow_detail(self, native):
        if not isinstance(native, str) or not re.fullmatch(r"[1-9][0-9]{0,29}", native):
            raise self.observer.CollectorError("schema_error", "DETAIL_ID_INVALID")
        if native not in self.detail_ids and len(self.detail_ids) >= self.records:
            raise self.observer.CollectorError("cancelled", "DETAIL_REQUEST_BUDGET")
        self.detail_ids.add(native)

    def check_url(self, method, url):
        try:
            parts = urlsplit(str(url))
            if method != "GET" or parts.scheme != "https" or parts.hostname != "api.bilibili.com" or parts.port is not None or parts.username is not None or parts.fragment or "\\" in str(url): raise ValueError
            if parts.path == "/x/web-interface/nav" and not parts.query: return
            pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
            args = dict(pairs)
            if len(pairs) != len(args): raise ValueError
            if parts.path == "/x/web-interface/view/detail":
                if set(args) != {"aid"} or args["aid"] not in self.detail_ids: raise ValueError
                return
            if parts.path != "/x/web-interface/wbi/search/type": raise ValueError
            fixed = {"search_type": "video", "keyword": self.keyword, "page_size": "20", "order": "", "pubtime_begin_s": "0", "pubtime_end_s": "0"}
            if set(args) != {*fixed, "page", "wts", "w_rid"} or any(args[k] != v for k, v in fixed.items()): raise ValueError
            if not re.fullmatch(r"[1-9][0-9]*", args["page"]) or not 1 <= int(args["page"]) <= self.pages: raise ValueError
            if not re.fullmatch(r"[0-9]{1,12}", args["wts"]) or not re.fullmatch(r"[0-9a-f]{32}", args["w_rid"]): raise ValueError
        except (ValueError, TypeError):
            raise self.observer.CollectorError("unsupported", "HTTP_ENDPOINT_NOT_ALLOWED") from None

    def factory(self, proxy=None, **kwargs):
        if proxy is not None or kwargs: raise self.observer.CollectorError("unsupported", "PROXY_OR_OPTIONS_FORBIDDEN")
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
                gate.check_url(method, url)
                options.pop("timeout", None)
                if set(options) - {"headers"}: raise gate.observer.CollectorError("unsupported", "HTTP_OPTIONS_NOT_ALLOWED")
                if gate.requests >= 1 + gate.pages + gate.records: raise gate.observer.CollectorError("cancelled", "API_REQUEST_BUDGET")
                await gate.sleep(max(0, gate.next_request - gate.monotonic()))
                if hasattr(gate, "before_request"): gate.before_request()
                gate.next_request = gate.monotonic() + 2
                gate.requests += 1
                try:
                    async with self.client.stream(method, url, **options) as response:
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE: raise gate.observer.CollectorError("schema_error", "HTTP_RESPONSE_TOO_LARGE")
                        payload = response_payload(response.status_code, {k.lower(): v for k, v in response.headers.items()}, bytes(body), gate.observer)
                        class Response:
                            status_code = response.status_code
                            text = "[validated metadata JSON]"
                            def json(self): return payload
                        return Response()
                except gate.observer.CollectorError:
                    raise
                except Exception as exc:
                    if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
                        raise gate.observer.CollectorError("timeout", "REQUEST_TIMEOUT") from None
                    raise gate.observer.CollectorError("network_error", "REQUEST_FAILED") from None
            async def get(self, url, **options): return await self.request("GET", url, **options)
        return Transport()
