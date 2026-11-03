"""Isolated Weibo child. Reuses the pinned client, not its auto-login crawler main."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sibling(name):
    spec = importlib.util.spec_from_file_location("_vciq_mc_wb_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_post(card, anonymize, mask):
    """Preserve source time text and missing metrics; no raw identity/media export."""
    post = card["mblog"]
    user = post.get("user") or {}
    if not isinstance(user, dict): raise ValueError("WEIBO_USER_SHAPE")
    identity = user.get("id")
    if identity is not None and (isinstance(identity, bool) or not isinstance(identity, (str, int))):
        raise ValueError("WEIBO_USER_SHAPE")
    nickname = user.get("screen_name")
    if nickname is not None and not isinstance(nickname, str):
        raise ValueError("WEIBO_USER_SHAPE")
    return {"note_id": post["id"], "content": post.get("text"),
        "create_time": None, "create_date_time": None, "raw_created_at": post.get("created_at"),
        "liked_count": post.get("attitudes_count"), "comments_count": post.get("comments_count"),
        "shared_count": post.get("reposts_count"),
        "creator_hash": anonymize(str(identity)) if identity is not None else None,
        "nickname": mask(nickname) if nickname else None}


async def bind_and_collect(request, context, observer, *, client_module=None, utils=None,
                           anonymize=None, mask=None, collector=None, gate_class=None):
    """Injection seam exercises the real runtime wiring without platform traffic."""
    if client_module is None:
        from media_platform.weibo import client as client_module
        from tools import utils
        from tools.user_hash import anonymize_user_id as anonymize, mask_nickname as mask
    collector = collector or sibling("weibo_observer").collect_weibo
    gate_class = gate_class or sibling("weibo_transport").WeiboGate
    job = request["job"]
    gate = gate_class(observer, job["query"]["text"], job["limits"]["maxSearchPages"])
    client_module.make_async_client = gate.factory
    cookie_string, cookie_dict = await utils.convert_browser_context_cookies(context, urls=["https://m.weibo.cn"])
    page = await context.new_page()
    client = client_module.WeiboClient(headers={"User-Agent": utils.get_mobile_user_agent(),
        "Accept": "application/json, text/plain, */*", "Referer": "https://m.weibo.cn/",
        "Cookie": cookie_string}, playwright_page=page, cookie_dict=cookie_dict, proxy=None)
    underlying = getattr(client_module.WeiboClient.request, "__wrapped__", None)
    if underlying is None:
        raise observer.CollectorError("schema_error", "REQUEST_WRAPPER_CHANGED")
    client.request = types.MethodType(underlying, client)
    # Do not call pong(): upstream catches all errors and loses restriction state.
    auth = await client.get("/api/config")
    if not isinstance(auth, dict) or not (auth.get("login") is True or type(auth.get("login")) is int and auth["login"] == 1):
        raise observer.CollectorError("auth_required", "SESSION_NOT_AUTHENTICATED")
    async def search(keyword, page):
        return await client.get_note_by_keyword(keyword=keyword, page=page)
    async def project(card):
        return project_post(card, anonymize, mask)
    return await collector(job, search, project, observer=observer)


async def execute(request, observer):
    upstream = Path(request["upstream"])
    sys.path.insert(0, str(upstream))
    import config
    import tools
    for module in (config, tools):
        paths = [module.__file__] if module.__file__ else list(module.__path__)
        if not paths or not all(Path(path).resolve().is_relative_to(upstream) for path in paths):
            raise observer.CollectorError("schema_error", "IMPORT_ORIGIN_MISMATCH")
    sibling("bootstrap").safe_settings(config)
    config.PLATFORM = "wb"
    config.WEIBO_SEARCH_TYPE = "default"
    from playwright.async_api import async_playwright
    from tools import utils
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            request["profile"], headless=request["action"] != "session", accept_downloads=False,
            service_workers="block", user_agent=utils.get_mobile_user_agent(), timeout=30000)
        try:
            if request["action"] == "session":
                page = await context.new_page()
                await page.goto("https://m.weibo.cn", timeout=30000)
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
        if request["action"] == "run" and (not isinstance(request["job"], dict) or request["job"].get("platform") != "wb"): return 2
        if request["action"] == "session" and request["job"] is not None: return 2
        target = Path(request["output"])
        if target.parent != path.parent or target.name != "captured.json" or target.exists() or target.is_symlink(): return 2
        sibling("upstream").verify_checkout(Path(request["upstream"]), request["lock"])
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
