"""Isolated Zhihu entrypoint: pinned client/signing, explicit user session only."""
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
    spec = importlib.util.spec_from_file_location("_vciq_mc_zh_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_signer(upstream, *, helper=None, compiler=None):
    """Load the pinned JS by absolute path, never cwd/libs or an arbitrary script."""
    root = Path(upstream).resolve(strict=True)
    path = root / "libs/zhihu.js"
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.resolve().parent != root / "libs" or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("ZHIHU_SIGNING_RESOURCE_INVALID")
    if helper is None:
        from media_platform.zhihu import help as helper
    if compiler is None:
        import execjs
        compiler = execjs.compile
    helper.ZHIHU_SGIN_JS = compiler(path.read_text(encoding="utf-8-sig"))


def project_content(obj, anonymize, mask, observer):
    kind, native, parent = sibling("zhihu_observer").content_identity(obj, observer)
    author = obj.get("author") or {}
    if not isinstance(author, dict): raise ValueError("ZHIHU_AUTHOR_SHAPE")
    if not author.get("id") and isinstance(author.get("member"), dict): author = author["member"]
    identity, nickname = author.get("id"), author.get("name")
    if identity is not None and (isinstance(identity, bool) or not isinstance(identity, (str, int))):
        raise ValueError("ZHIHU_AUTHOR_SHAPE")
    if nickname is not None and not isinstance(nickname, str): raise ValueError("ZHIHU_AUTHOR_SHAPE")
    row = {key: obj.get(key) for key in ("title", "description", "excerpt", "created_time", "updated_time", "created", "updated", "created_at", "published_at", "updated_at", "voteup_count", "comment_count")}
    row.update(content_id=native, content_type=kind, question_id=parent,
        question_title=(obj.get("question") or {}).get("title") if kind == "answer" else None,
        content=obj.get("content") if kind != "zvideo" else None,
        creator_hash=anonymize(str(identity)) if identity not in (None, "") else None,
        nickname=mask(nickname) if nickname else None)
    return row


async def bind_and_collect(request, context, observer, *, client_module=None, utils=None,
                           anonymize=None, mask=None, collector=None, gate_class=None):
    if client_module is None:
        from media_platform.zhihu import client as client_module
        from tools import utils
        from tools.user_hash import anonymize_user_id as anonymize, mask_nickname as mask
        prepare_signer(request["upstream"])
    collector = collector or sibling("zhihu_observer").collect_zhihu
    gate_class = gate_class or sibling("zhihu_transport").ZhihuGate
    job = request["job"]
    gate = gate_class(observer, job["query"]["text"], job["limits"]["maxSearchPages"])
    gate.before_request = lambda: sibling("request_control").check(observer, platform="zhihu")
    client_module.make_async_client = gate.factory
    cookie_string, cookie_dict = await utils.convert_browser_context_cookies(context, urls=["https://www.zhihu.com"])
    if not isinstance(cookie_dict.get("d_c0"), str) or not cookie_dict["d_c0"]:
        raise observer.CollectorError("auth_required", "SESSION_SIGNING_COOKIE_MISSING")
    client = client_module.ZhiHuClient(proxy=None, headers={
        "accept": "application/json", "accept-language": "zh-CN,zh;q=0.9", "cookie": cookie_string,
        "referer": "https://www.zhihu.com/", "user-agent": utils.get_user_agent(),
        "x-api-version": "3.0.91", "x-app-za": "OS=Web", "x-requested-with": "fetch", "x-zse-93": "101_3_3.0"},
        playwright_page=await context.new_page(), cookie_dict=cookie_dict)
    raw_request = getattr(client_module.ZhiHuClient.request, "__wrapped__", None)
    if raw_request is None:
        raise observer.CollectorError("schema_error", "REQUEST_WRAPPER_CHANGED")
    client.request = types.MethodType(raw_request, client)
    # The original extractor loses paging and supplies defaults for missing data.
    # Replace only this in-memory projection; native URL and signature code stay.
    class RawSearch:
        def extract_contents_from_search(self, payload): return payload
    client._extractor = RawSearch()
    # Do not request the upstream helper's email/phone include fields, or call
    # pong(), which catches restrictions and turns them into a boolean.
    auth = await client.get("/api/v4/me")
    identity = (auth.get("uid") or auth.get("id")) if isinstance(auth, dict) else None
    valid_id = isinstance(identity, str) and bool(identity.strip()) or type(identity) is int and identity > 0
    if not valid_id or not isinstance(auth.get("name"), str) or not auth["name"].strip():
        raise observer.CollectorError("auth_required", "SESSION_NOT_AUTHENTICATED")
    async def search(keyword, number):
        return await client.get_note_by_keyword(keyword=keyword, page=number, page_size=20)
    async def project(obj):
        return project_content(obj, anonymize, mask, observer)
    return await collector(job, search, project, observer=observer)


async def execute(request, observer):
    if request["action"] == "run": sibling("request_control").check(observer, platform="zhihu")
    upstream = Path(request["upstream"])
    sys.path.insert(0, str(upstream))
    import config
    import tools
    for module in (config, tools):
        paths = [module.__file__] if module.__file__ else list(module.__path__)
        if not paths or not all(Path(path).resolve().is_relative_to(upstream) for path in paths):
            raise observer.CollectorError("schema_error", "IMPORT_ORIGIN_MISMATCH")
    sibling("bootstrap").safe_settings(config)
    config.PLATFORM = "zhihu"
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            request["profile"], headless=request["action"] != "session", accept_downloads=False,
            channel="chromium", service_workers="block", timeout=30000)
        try:
            if request["action"] == "session":
                page = await context.new_page()
                await page.goto("https://www.zhihu.com", timeout=30000)
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
        if request["action"] == "run" and (not isinstance(request["job"], dict) or request["job"].get("platform") != "zhihu"): return 2
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
            stream.write(payload + b"\n"); stream.flush(); os.fsync(stream.fileno())
        return 0
    except Exception:
        return 2


if __name__ == "__main__": raise SystemExit(main())
