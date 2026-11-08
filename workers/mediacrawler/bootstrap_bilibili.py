"""Isolated Bilibili child, pinned client only; no original crawler main/start."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent


def sibling(name):
    spec = importlib.util.spec_from_file_location("_vciq_mc_bili_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wbi_keys(auth):
    images = auth.get("wbi_img")
    if not isinstance(images, dict): raise ValueError("BILI_NAV_KEYS_MISSING")
    result = []
    for key in ("img_url", "sub_url"):
        value = images.get(key)
        if not isinstance(value, str) or len(value) > 2000: raise ValueError("BILI_NAV_KEY_INVALID")
        parts = urlsplit(value)
        match = re.fullmatch(r".*/([0-9a-f]{32})\.png", parts.path)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.port is not None or parts.query or parts.fragment or not match:
            raise ValueError("BILI_NAV_KEY_INVALID")
        result.append(match[1])
    # These URLs are never fetched; only key strings are passed to the pinned signer.
    return tuple(result)


def project_video(raw, anonymize, mask):
    view = raw["View"]
    owner, stats = view.get("owner") or {}, view.get("stat") or {}
    if not isinstance(owner, dict) or not isinstance(stats, dict): raise ValueError("BILI_DETAIL_SHAPE")
    identity, nickname = owner.get("mid"), owner.get("name")
    if identity is not None and (isinstance(identity, bool) or not isinstance(identity, (str, int))): raise ValueError("BILI_OWNER_SHAPE")
    if nickname is not None and not isinstance(nickname, str): raise ValueError("BILI_OWNER_SHAPE")
    return {"video_id": str(view["aid"]), "bvid": view.get("bvid") or None,
        "title": view.get("title"), "desc": view.get("desc"), "create_time": view.get("pubdate"),
        "creator_hash": anonymize(str(identity)) if identity is not None else None,
        "nickname": mask(nickname) if nickname else None,
        "liked_count": stats.get("like"), "video_comment": stats.get("reply"),
        "video_share_count": stats.get("share"), "video_play_count": stats.get("view")}


async def bind_and_collect(request, context, observer, *, client_module=None, utils=None,
                           anonymize=None, mask=None, collector=None, gate_class=None):
    if client_module is None:
        from media_platform.bilibili import client as client_module
        from tools import utils
        from tools.user_hash import anonymize_user_id as anonymize, mask_nickname as mask
    collector = collector or sibling("bilibili_observer").collect_bilibili
    gate_class = gate_class or sibling("bilibili_transport").BilibiliGate
    job = request["job"]
    if job["platform"] != "bili" or any(c in job["query"]["text"] for c in ",!'()*"):
        raise observer.CollectorError("unsupported", "BILI_QUERY_FILTER_UNSUPPORTED")
    gate = gate_class(observer, job["query"]["text"], job["limits"]["maxSearchPages"], job["limits"]["maxRecords"])
    gate.before_request = lambda: sibling("request_control").check(observer, platform="bili")
    client_module.make_async_client = gate.factory
    cookie_string, cookie_dict = await utils.convert_browser_context_cookies(context, urls=["https://www.bilibili.com"])
    page = await context.new_page()
    user_agent = await page.evaluate("() => navigator.userAgent")
    client = client_module.BilibiliClient(headers={"User-Agent": user_agent,
        "Accept": "application/json", "Referer": "https://www.bilibili.com/", "Cookie": cookie_string},
        playwright_page=page, cookie_dict=cookie_dict, proxy=None)
    # Do not call pong(): it suppresses exceptions. Cache nav signing keys to
    # avoid unbudgeted requests or reliance on a navigated page's localStorage.
    auth = await client.get("/x/web-interface/nav", enable_params_sign=False)
    if not isinstance(auth, dict) or auth.get("isLogin") is not True:
        raise observer.CollectorError("auth_required", "SESSION_NOT_AUTHENTICATED")
    keys = wbi_keys(auth)
    async def cached_keys(): return keys
    client.get_wbi_keys = cached_keys
    async def search(keyword, page):
        return await client.search_video_by_keyword(keyword=keyword, page=page, page_size=20, pubtime_begin_s=0, pubtime_end_s=0)
    async def detail(native):
        gate.allow_detail(native)
        return await client.get_video_info(aid=native)
    async def project(value): return project_video(value, anonymize, mask)
    return await collector(job, search, detail, project, observer=observer)


async def execute(request, observer):
    if request["action"] == "run": sibling("request_control").check(observer, platform="bili")
    upstream = Path(request["upstream"])
    sys.path.insert(0, str(upstream))
    import config
    import tools
    for module in (config, tools):
        paths = [module.__file__] if module.__file__ else list(module.__path__)
        if not paths or not all(Path(p).resolve().is_relative_to(upstream) for p in paths):
            raise observer.CollectorError("schema_error", "IMPORT_ORIGIN_MISMATCH")
    sibling("bootstrap").safe_settings(config)
    config.PLATFORM = "bili"
    config.CREATOR_MODE = False
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(request["profile"],
            headless=request["action"] != "session", accept_downloads=False,
            channel="chromium", service_workers="block", timeout=30000)
        try:
            if request["action"] == "session":
                page = await context.new_page()
                await page.goto("https://www.bilibili.com", timeout=30000)
                await page.wait_for_event("close", timeout=180000)
                return {"sessionPrepared": True, "authenticationVerified": False, "liveQueryExecuted": False}
            return await bind_and_collect(request, context, observer)
        finally:
            await context.close()


def main():
    logging.disable(logging.CRITICAL)
    os.umask(0o077)
    observer = sibling("observer")
    try:
        if len(sys.argv) != 2: return 2
        path = Path(sys.argv[1])
        if not path.is_absolute() or path.is_symlink() or path.stat().st_size > 1024 * 1024: return 2
        request = json.loads(path.read_text(encoding="utf-8"))
        if set(request) != {"action", "upstream", "profile", "output", "job", "lock"} or request["action"] not in {"run", "session"}: return 2
        if request["action"] == "run" and (not isinstance(request["job"], dict) or request["job"].get("platform") != "bili"): return 2
        if request["action"] == "session" and request["job"] is not None: return 2
        target = Path(request["output"])
        if target.parent != path.parent or target.name != "captured.json" or target.exists() or target.is_symlink(): return 2
        sibling("upstream").verify_checkout(Path(request["upstream"]), request["lock"])
        started = observer.stamp()
        try:
            result = asyncio.run(execute(request, observer))
        except Exception as exc:
            if request["action"] == "session": result = {"sessionPrepared": False, "authenticationVerified": False, "liveQueryExecuted": False}
            else:
                result = observer.envelope(request["job"], lambda: started)
                observer.fail(result, observer.classify(exc))
                result["completedAt"] = observer.stamp()
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(payload) > 4 * 1024 * 1024: return 2
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        return 0
    except Exception:
        return 2


if __name__ == "__main__": raise SystemExit(main())
