"""Standalone subprocess bridge. VCIQ's root never enters the import path."""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit


def load_local(name):
    if name not in {"observer", "capabilities", "runtime_xhs", "runtime_weibo", "runtime_bilibili", "runtime_zhihu"}:
        raise RuntimeError("BRIDGE_MODULE_DENIED")
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("vciq_shadow_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_observer():
    return load_local("observer")


def import_isolated(upstream):
    upstream = Path(upstream).resolve(strict=True)
    for name in ("config", "tools"):
        if name in sys.modules:
            raise RuntimeError("UPSTREAM_NAMESPACE_ALREADY_LOADED")
    sys.path.insert(0, str(upstream))
    config, tools = importlib.import_module("config"), importlib.import_module("tools")
    for module in (config, tools):
        if not module.__file__ or not Path(module.__file__).resolve().is_relative_to(upstream):
            raise RuntimeError("UPSTREAM_IMPORT_ORIGIN")
    return config


def private_write(path, document):
    raw = (json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode()
    if len(raw) > 4 * 1024 * 1024:
        raise RuntimeError("WORKER_OUTPUT_LIMIT")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def classify_exception(exc):
    name = type(exc).__name__
    if name in {"TimeoutError", "ReadTimeout", "ConnectTimeout", "PoolTimeout"}:
        return "timeout", "UPSTREAM_TIMEOUT"
    if name == "IPBlockError":
        return "rate_limited", "UPSTREAM_RATE_LIMIT"
    if name == "PlatformAccessError":
        return "verification_required", "UPSTREAM_ACCESS_RESTRICTED"
    if name in {"ModuleNotFoundError", "ImportError"}:
        return "unsupported", "UPSTREAM_DEPENDENCY_MISSING"
    if name in {"ConnectError", "NetworkError", "RemoteProtocolError", "DataFetchError", "RetryError"}:
        return "network_error", "UPSTREAM_REQUEST_FAILED"
    return "schema_error", "UPSTREAM_INCOMPATIBLE"


def allowed_host(host, platform):
    return bool(host) and any(host == domain or host.endswith("." + domain) for domain in load_local("capabilities").HOSTS.get(platform, ()))


async def run(envelope, observer_module):
    job = envelope["job"]
    observer = observer_module.Observer(job)
    Halt, interactive, context = observer_module.Halt, envelope["interactive"], None
    try:
        config = import_isolated(envelope["upstream"])
        from cmd_arg import parse_cmd
        await parse_cmd(["--platform", job["platform"], "--type", "search", "--keywords", job["query"]["text"],
                         "--get_comment", "false", "--get_sub_comment", "false", "--get_media", "false",
                         "--enable_ip_proxy", "false", "--max_concurrency_num", "1", "--save_data_option", "jsonl",
                         "--crawler_max_notes_count", str(job["limits"]["maxRecords"]),
                         "--save_data_path", str(Path(envelope["output"]).parent)])
        observer_module.apply_safe_config(config, platform=job["platform"], profile=envelope["profile"], output=Path(envelope["output"]).parent)
        logging.disable(logging.CRITICAL)
        import httpx
        from playwright.async_api import async_playwright
        from var import crawler_type_var, source_keyword_var
        crawler_type_var.set("search")
        source_keyword_var.set(job["query"]["text"])
        original_send = httpx.AsyncClient.send
        last_request = 0.0
        max_requests = 5 + job["limits"]["maxSearchPages"] * 25

        async def checked_send(client, request, *args, **kwargs):
            nonlocal last_request
            if observer.error and observer.error["status"] in {"auth_required", "verification_required", "rate_limited"}:
                raise Halt(observer.error["status"], observer.error["code"])
            parts = urlsplit(str(request.url))
            if parts.scheme != "https" or parts.port not in (None, 443) or parts.username or not allowed_host(parts.hostname, job["platform"]):
                raise Halt("unsupported", "HTTP_ENDPOINT_DENIED")
            if observer.request_count >= max_requests:
                raise Halt("cancelled", "HTTP_REQUEST_BUDGET")
            await asyncio.sleep(max(0, 2 - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            observer.request_count += 1
            kwargs["follow_redirects"] = False
            response = await original_send(client, request, *args, **kwargs)
            if response.is_redirect:
                raise Halt("unsupported", "HTTP_REDIRECT_DENIED")
            mapping = {401: ("auth_required", "HTTP_AUTH"), 403: ("verification_required", "HTTP_ACCESS_DENIED"),
                       429: ("rate_limited", "HTTP_RATE_LIMIT"), 461: ("verification_required", "HTTP_VERIFICATION"),
                       471: ("verification_required", "HTTP_VERIFICATION")}
            if response.status_code in mapping and not (interactive and response.status_code in {401, 403, 461, 471}):
                status, code = mapping[response.status_code]
                value = response.headers.get("retry-after", "")
                observer.retry_after = int(value) if value.isdigit() else 0
                observer.fail(status, code)
                raise Halt(status, code)
            if len(response.content) > 2 * 1024 * 1024:
                raise Halt("schema_error", "HTTP_RESPONSE_LIMIT")
            return response

        httpx.AsyncClient.send = checked_send
        names = load_local("capabilities").CANDIDATES
        if job["platform"] not in names:
            raise Halt("unsupported", "PLATFORM_NOT_IMPLEMENTED")
        platform_runtime = load_local("runtime_" + names[job["platform"]])
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(user_data_dir=envelope["profile"],
                headless=not interactive, accept_downloads=False, service_workers="block", viewport={"width": 1365, "height": 900})
            async def route_request(route):
                parts = urlsplit(route.request.url)
                observer.browser_requests += 1
                if observer.browser_requests > 250 or parts.scheme != "https" or parts.port not in (None, 443) or parts.username or not allowed_host(parts.hostname, job["platform"]):
                    await route.abort()
                elif not interactive and route.request.resource_type in {"image", "media", "font"}:
                    await route.abort()
                else:
                    await route.continue_()
            await context.route("**/*", route_request)
            context.set_default_timeout(15000)
            page = await context.new_page()
            client, cookie_urls = await platform_runtime.setup(context, page)
            if hasattr(type(client).request, "__wrapped__"):
                import types
                client.request = types.MethodType(type(client).request.__wrapped__, client)
            if interactive:
                ready = False
                deadline = time.monotonic() + max(1, job["limits"]["maxWallSeconds"] - 20)
                while time.monotonic() < deadline:
                    if hasattr(platform_runtime, "refresh"):
                        await platform_runtime.refresh(client, context, cookie_urls)
                    else:
                        await client.update_cookies(context, urls=cookie_urls)
                    ready = await client.pong()
                    if ready:
                        break
                    await asyncio.sleep(5)
                return {"sessionStatus": "ready" if ready else "auth_required", "platform": job["platform"]}
            if not await client.pong():
                if observer.error:
                    raise Halt(observer.error["status"], observer.error["code"])
                raise Halt("auth_required", "SESSION_NOT_READY")
            await platform_runtime.collect(client, observer_module, observer)
    except Halt as exc:
        observer.fail(exc.status, exc.code)
    except Exception as exc:
        status, code = classify_exception(exc)
        observer.fail(status, code)
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
    if interactive:
        state = observer.error["status"] if observer.error else "error"
        return {"sessionStatus": state if state in {"auth_required", "verification_required", "rate_limited", "timeout"} else "error", "platform": job["platform"]}
    return observer.payload()


def main():
    if len(sys.argv) != 2:
        return 2
    input_path = Path(sys.argv[1])
    if not input_path.is_absolute() or input_path.is_symlink() or input_path.stat().st_size > 1_000_000:
        return 2
    envelope = json.loads(input_path.read_text(encoding="utf-8"))
    if set(envelope) != {"job", "profile", "interactive", "upstream", "output"} or type(envelope["interactive"]) is not bool:
        return 2
    if Path(envelope["output"]) != input_path.parent / "worker.json" or Path.cwd().resolve() != Path(envelope["upstream"]).resolve():
        return 2
    logging.disable(logging.CRITICAL)
    result = asyncio.run(run(envelope, load_observer()))
    private_write(envelope["output"], result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(2) from None
