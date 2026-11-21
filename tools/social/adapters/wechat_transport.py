"""Bounded HTTPS-only public reads, explicit redirect checks, DNS-pinned TLS."""
from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class FetchError(RuntimeError):
    def __init__(self, status: str, code: str, *, retry_after: int = 0):
        self.status, self.code, self.retry_after = status, code, retry_after
        super().__init__(code)


@dataclass(frozen=True)
class Response:
    url: str
    body: str


def decode_url(value: str) -> str:
    # html.unescape('&timestamp=...') corrupts a legitimate signed URL as '&times'.
    return re.sub(r"&(?:amp|#0*38|#x0*26);", "&", value.strip(), flags=re.I).replace("\\/", "/").replace("\\x26", "&")


def checked_url(value: str) -> str:
    value = decode_url(value)
    try:
        parts = urlsplit(value)
        if parts.scheme != "https" or parts.username is not None or parts.port is not None or parts.fragment or re.search(r"[\s\\\x00-\x1f]", value):
            raise ValueError
        rules = {"mp.weixin.qq.com": r"/s(?:/[A-Za-z0-9_-]+)?",
                 "weixin.sogou.com": r"/(?:weixin|link)?",
                 "www.bing.com": r"/search"}
        if parts.hostname not in rules or not re.fullmatch(rules[parts.hostname], parts.path):
            raise ValueError
        return value
    except ValueError:
        raise FetchError("schema_error", "UNSAFE_DESTINATION") from None


class _PinnedConnection(http.client.HTTPSConnection):
    def connect(self):
        # No ambient proxy, no second DNS lookup by the connection implementation.
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise FetchError("schema_error", "NON_PUBLIC_DESTINATION")
        address = addresses[0][4][0]
        raw = socket.create_connection((address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class PublicTransport:
    def __init__(self, *, before_request, deadline: float, monotonic=time.monotonic,
                 sleep=time.sleep, connection_factory=_PinnedConnection):
        self.before_request = before_request
        self.deadline = deadline
        self.monotonic, self.sleep = monotonic, sleep
        self.connection_factory = connection_factory
        self.requests = 0
        self._last = None

    def get(self, url: str) -> Response:
        url = checked_url(url)
        for redirect in range(4):
            if self._last is not None:
                wait = max(0.0, 1.25 - (self.monotonic() - self._last))
                if self.monotonic() + wait >= self.deadline:
                    raise FetchError("timeout", "JOB_DEADLINE")
                self.sleep(wait)
            remaining = self.deadline - self.monotonic()
            if remaining <= 0:
                raise FetchError("timeout", "JOB_DEADLINE")
            self.before_request()  # durable quota debit before every request/redirect
            self.requests += 1
            self._last = self.monotonic()
            parts = urlsplit(url)
            connection = self.connection_factory(parts.hostname, timeout=min(16.0, remaining), context=ssl.create_default_context())
            try:
                connection.request("GET", urlunsplit(("", "", parts.path, parts.query, "")), headers={
                    "User-Agent": "VCIQ-SocialShadow/1.0 (+https://github.com/VCIQ/VCIQ.github.io)",
                    "Accept": "text/html,application/rss+xml,application/xml", "Accept-Encoding": "identity"})
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location", "")
                    if not location or redirect == 3:
                        raise FetchError("schema_error", "REDIRECT_LIMIT")
                    target = checked_url(urljoin(url, decode_url(location)))
                    target_host = urlsplit(target).hostname
                    allowed_hosts = {parts.hostname}
                    if parts.hostname == "weixin.sogou.com" and parts.path == "/link":
                        allowed_hosts.add("mp.weixin.qq.com")
                    if target_host not in allowed_hosts:
                        raise FetchError("schema_error", "CROSS_PROVIDER_REDIRECT")
                    url = target
                    continue
                if response.status == 429:
                    raw = response.getheader("Retry-After", "")
                    try:
                        retry = max(0, int(raw))
                    except ValueError:
                        try:
                            retry = max(0, int(parsedate_to_datetime(raw).timestamp() - time.time()))
                        except (TypeError, ValueError, OverflowError):
                            retry = 300
                    raise FetchError("rate_limited", "HTTP_RATE_LIMIT", retry_after=retry)
                if response.status == 401:
                    raise FetchError("auth_required", "HTTP_AUTH_REQUIRED")
                if response.status == 403:
                    raise FetchError("verification_required", "HTTP_ACCESS_RESTRICTED")
                if response.status != 200:
                    raise FetchError("network_error", "HTTP_ERROR")
                if response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}:
                    raise FetchError("schema_error", "UNSUPPORTED_CONTENT_ENCODING")
                body = bytearray()
                while len(body) <= MAX_RESPONSE_BYTES:
                    remaining = self.deadline - self.monotonic()
                    if remaining <= 0:
                        raise FetchError("timeout", "JOB_DEADLINE")
                    if connection.sock is not None:
                        connection.sock.settimeout(min(16.0, remaining))
                    chunk = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise FetchError("schema_error", "RESPONSE_TOO_LARGE")
                return Response(url, bytes(body).decode("utf-8", errors="replace"))
            except (TimeoutError, socket.timeout):
                raise FetchError("timeout", "REQUEST_TIMEOUT") from None
            except (OSError, http.client.HTTPException):
                raise FetchError("network_error", "NETWORK_ERROR") from None
            finally:
                connection.close()
        raise FetchError("schema_error", "REDIRECT_LIMIT")
