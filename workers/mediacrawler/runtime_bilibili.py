"""Bounded Bilibili video search; no media/comment/creator methods are called."""
from __future__ import annotations

import asyncio


async def setup(context, page):
    from media_platform.bilibili.core import BilibiliCrawler
    crawler = BilibiliCrawler()
    crawler.browser_context, crawler.context_page = context, page
    await page.goto(crawler.index_url, wait_until="domcontentloaded", timeout=30000)
    return await crawler.create_bilibili_client(None), crawler.cookie_urls


async def search(client, store, observer_module, observer, *, sleep=asyncio.sleep):
    Halt = observer_module.Halt
    job, seen = observer.job, set()
    for index in range(1, job["limits"]["maxSearchPages"] + 1):
        response = await client.search_video_by_keyword(keyword=job["query"]["text"], page=index,
            page_size=20, pubtime_begin_s=0, pubtime_end_s=0)
        if not isinstance(response, dict) or not isinstance(response.get("result"), list):
            raise Halt("schema_error", "BILI_SEARCH_SHAPE")
        items = response["result"]
        if len(items) > 100:
            raise Halt("schema_error", "BILI_PAGE_LIMIT")
        for item in items:
            if not isinstance(item, dict) or isinstance(item.get("aid"), bool) or not isinstance(item.get("aid"), (str, int)) or not str(item["aid"]).isdigit():
                raise Halt("schema_error", "BILI_SEARCH_ID")
        # An explicit empty result is a query end. Otherwise numPages is optional
        # and trusted only when it is a consistent nonnegative integer.
        total = response.get("numPages")
        more = None
        if not items:
            more = False
        elif type(total) is int and total >= index:
            more = index < total
        page = {"pageIndex": index, "schemaValid": True, "contentItems": len(items), "processed": False, "hasMore": more}
        observer.pages.append(page)
        for item in items:
            aid = str(item["aid"])
            if aid in seen:
                continue
            seen.add(aid)
            detail = await client.get_video_info(aid=int(aid))
            view = detail.get("View") if isinstance(detail, dict) else None
            if not isinstance(view, dict) or str(view.get("aid")) != aid or not isinstance(view.get("title"), str) or not isinstance(view.get("desc"), str) or not isinstance(view.get("owner"), dict) or not isinstance(view.get("stat"), dict):
                raise Halt("schema_error", "BILI_DETAIL_SHAPE")
            observer.current_origin = "upstream"
            before = len(observer.rows)
            await store.update_bilibili_video(detail)
            if len(observer.rows) != before + 1:
                raise Halt("schema_error", "BILI_STORE_BOUNDARY")
            if view.get("bvid"):
                observer.rows[-1]["record"]["observed_video_identity"] = {"aid": aid, "bvid": view["bvid"]}
            await sleep(2)
        page["processed"] = True
        if more is False:
            observer.stop_reason = "exhausted"
            return
        await sleep(2)
    observer.stop_reason = "page_limit"


async def collect(client, observer_module, observer):
    from store import bilibili as store
    capture = observer_module.CaptureStore(observer)
    store.BiliStoreFactory.create_store = staticmethod(lambda: capture)
    await search(client, store, observer_module, observer)
