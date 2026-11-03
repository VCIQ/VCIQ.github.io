"""Isolated child entrypoint. Never import the VCIQ tools/config packages here."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
import time
import types
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent


def sibling(name):
    spec = importlib.util.spec_from_file_location("_vciq_mc_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_settings(config):
    for key, value in {"PLATFORM": "xhs", "CRAWLER_TYPE": "search", "XHS_INTERNATIONAL": False,
        "ENABLE_CDP_MODE": False, "CDP_CONNECT_EXISTING": False, "ENABLE_IP_PROXY": False,
        "STATIC_PROXY_URL": "", "COOKIES": "", "ENABLE_GET_COMMENTS": False,
        "ENABLE_GET_SUB_COMMENTS": False, "ENABLE_GET_MEDIA": False,
        "ENABLE_GET_WORDCLOUD": False, "DISABLE_SSL_VERIFY": False,
        "MAX_CONCURRENCY_NUM": 1, "SAVE_DATA_OPTION": "jsonl", "HEADLESS": True}.items():
        setattr(config, key, value)


async def execute(request, observer):
    upstream = Path(request["upstream"])
    # -I ignores PYTHONPATH; only the pinned upstream is added. VCIQ itself is
    # not added, so its same-named tools/config cannot shadow MediaCrawler.
    sys.path.insert(0, str(upstream))
    import config
    import tools
    if not all(all(Path(path).resolve().is_relative_to(upstream) for path in ([module.__file__] if module.__file__ else list(module.__path__))) for module in (config, tools)):
        raise observer.CollectorError("schema_error", "IMPORT_ORIGIN_MISMATCH")
    safe_settings(config)
    from playwright.async_api import async_playwright
    profile = Path(request["profile"])
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(profile), headless=request["action"] != "session", accept_downloads=False,
            service_workers="block", timeout=30000)
        try:
            if request["action"] == "session":
                page = await context.new_page()
                await page.goto("https://www.xiaohongshu.com", timeout=30000)
                # Manual website login only. Closing this tab ends setup; the next
                # search independently verifies authentication with query_self.
                await page.wait_for_event("close", timeout=180000)
                return {"sessionPrepared": True, "authenticationVerified": False,
                        "liveQueryExecuted": False}
            import httpx
            from media_platform.xhs import client as client_module
            from media_platform.xhs.core import XiaoHongShuCrawler
            from store import xhs as store_module
            from var import source_keyword_var
            next_request = 0.0
            requests = 0
            max_requests = 1 + request["job"]["limits"]["maxSearchPages"] + request["job"]["limits"]["maxRecords"]

            class Transport:
                async def __aenter__(self):
                    self.client = httpx.AsyncClient(verify=True, trust_env=False, follow_redirects=False, timeout=20)
                    return self
                async def __aexit__(self, *args):
                    await self.client.aclose()
                async def get(self, url, **kwargs):
                    return await self.request("GET", url, **kwargs)
                async def request(self, method, url, **kwargs):
                    nonlocal next_request, requests
                    parts = urlsplit(str(url))
                    allowed = {("GET", "/api/sns/web/v1/user/selfinfo"),
                               ("POST", "/api/sns/web/v1/search/notes"), ("POST", "/api/sns/web/v1/feed")}
                    if parts.scheme != "https" or parts.hostname != "edith.xiaohongshu.com" or parts.port is not None or parts.username or parts.fragment or (method.upper(), parts.path) not in allowed:
                        raise observer.CollectorError("unsupported", "HTTP_ENDPOINT_NOT_ALLOWED")
                    if requests >= max_requests:
                        raise observer.CollectorError("cancelled", "API_REQUEST_BUDGET")
                    await asyncio.sleep(max(0, next_request - time.monotonic()))
                    next_request = time.monotonic() + 2
                    requests += 1
                    kwargs.pop("timeout", None)
                    if set(kwargs) - {"headers", "data", "params"}:
                        raise observer.CollectorError("unsupported", "HTTP_OPTIONS_NOT_ALLOWED")
                    async with self.client.stream(method, url, **kwargs) as response:
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 2 * 1024 * 1024:
                                raise observer.CollectorError("schema_error", "HTTP_RESPONSE_TOO_LARGE")
                        status = response.status_code
                        if status == 401:
                            raise observer.CollectorError("auth_required", "HTTP_AUTH_REQUIRED")
                        if status in {403, 461, 471}:
                            raise observer.CollectorError("verification_required", "HTTP_VERIFICATION_REQUIRED")
                        if status == 429:
                            retry = response.headers.get("Retry-After", "")
                            try:
                                delay = int(retry) if retry.isdigit() else max(0, int((parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()))
                            except (ValueError, TypeError, OverflowError):
                                delay = None
                            raise observer.CollectorError("rate_limited", "HTTP_RATE_LIMIT", delay)
                        if 300 <= status < 400:
                            raise observer.CollectorError("unsupported", "HTTP_REDIRECT_REJECTED")
                        if status >= 400:
                            raise observer.CollectorError("network_error", "HTTP_REQUEST_FAILED")
                        try:
                            payload = json.loads(body)
                        except (ValueError, UnicodeError):
                            raise observer.CollectorError("schema_error", "HTTP_JSON_REQUIRED") from None
                        if not isinstance(payload, dict):
                            raise observer.CollectorError("schema_error", "HTTP_OBJECT_REQUIRED")
                        if str(payload.get("code")) == "300011":
                            raise observer.CollectorError("verification_required", "ACCOUNT_SECURITY_RESTRICTION")
                        if str(payload.get("code")) == "300012":
                            raise observer.CollectorError("rate_limited", "PLATFORM_RATE_LIMIT")
                        headers = {key: value for key, value in response.headers.items() if key.lower() not in {"content-encoding", "content-length"}}
                        return httpx.Response(status, headers=headers, content=bytes(body), request=response.request)

            def transport_factory(proxy=None, **kwargs):
                if proxy is not None or kwargs:
                    raise observer.CollectorError("unsupported", "PROXY_OR_OPTIONS_FORBIDDEN")
                return Transport()
            client_module.make_async_client = transport_factory
            crawler = XiaoHongShuCrawler()
            crawler.browser_context, crawler.context_page = context, await context.new_page()
            client = await crawler.create_xhs_client(None)
            # Bypass only the upstream automatic retry decorator. Restricted
            # responses must terminate immediately, not trigger retries/login.
            underlying = getattr(client_module.XiaoHongShuClient.request, "__wrapped__", None)
            if underlying is None:
                raise observer.CollectorError("schema_error", "REQUEST_WRAPPER_CHANGED")
            client.request = types.MethodType(underlying, client)
            selfinfo = await client.query_self()
            if not isinstance(selfinfo, dict) or selfinfo.get("data", {}).get("result", {}).get("success") is not True:
                raise observer.CollectorError("auth_required", "SESSION_NOT_AUTHENTICATED")
            source_keyword_var.set(request["job"]["query"]["text"])
            captured = []
            class CaptureStore:
                async def store_content(self, content_item):
                    captured.append(content_item)
            store_module.XhsStoreFactory.create_store = staticmethod(lambda: CaptureStore())
            async def project(note):
                captured.clear()
                await store_module.update_xhs_note(note)
                if len(captured) != 1:
                    raise observer.CollectorError("schema_error", "STORE_CALLBACK_CHANGED")
                return captured.pop()
            search_id = client_module.get_search_id()
            async def search(keyword, page):
                return await client.get_note_by_keyword(keyword=keyword, search_id=search_id, page=page)
            async def detail(item):
                return await client.get_note_by_id(item["id"], item.get("xsec_source") or "pc_search", item.get("xsec_token") or "")
            return await observer.collect_xhs(request["job"], search, detail, project)
        finally:
            await context.close()


def main() -> int:
    logging.disable(logging.CRITICAL)
    os.umask(0o077)
    observer = sibling("observer")
    request = None
    try:
        if len(sys.argv) != 2:
            return 2
        request_file = Path(sys.argv[1])
        if not request_file.is_absolute() or request_file.is_symlink() or request_file.stat().st_size > 1024 * 1024:
            return 2
        request = json.loads(request_file.read_text(encoding="utf-8"))
        if set(request) != {"action", "upstream", "profile", "output", "job", "lock"} or request["action"] not in {"run", "session"}:
            return 2
        output = Path(request["output"])
        if output.parent != request_file.parent or output.name != "captured.json" or output.exists() or output.is_symlink():
            return 2
        verifier = sibling("upstream")
        verifier.verify_checkout(Path(request["upstream"]), request["lock"])
        started = observer.stamp()
        try:
            result = asyncio.run(execute(request, observer))
        except Exception as exc:
            if request["action"] == "session":
                result = {"sessionPrepared": False, "authenticationVerified": False, "liveQueryExecuted": False}
            else:
                result = observer.envelope(request["job"], lambda: started)
                observer.fail(result, observer.classify(exc))
                result["completedAt"] = observer.stamp()
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(payload) > 4 * 1024 * 1024:
            return 2
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        return 0
    except Exception:
        # stdout/stderr are discarded by the parent; no raw exceptions or cookies.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
