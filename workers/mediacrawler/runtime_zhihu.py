"""Observe raw Zhihu search before the pinned extractor discards pagination."""
from __future__ import annotations

import asyncio
import copy
from html.parser import HTMLParser
from urllib.parse import urlencode


class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "template"}:
            self.hidden += 1
        elif not self.hidden and tag in {"br", "p", "div", "section"}:
            self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object", "template"} and self.hidden:
            self.hidden -= 1
    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


async def setup(context, page):
    from media_platform.zhihu.core import ZhihuCrawler
    crawler = ZhihuCrawler()
    crawler.browser_context, crawler.context_page = context, page
    await page.goto(crawler.index_url, wait_until="domcontentloaded", timeout=30000)
    client = await crawler.create_zhihu_client(None)
    # The pinned ZhiHuClient receives but does not retain playwright_page.
    client._vciq_page = page
    return client, crawler.cookie_urls


async def search(client, store, observer_module, observer, *, sleep=asyncio.sleep):
    Halt = observer_module.Halt
    original_get = client.get
    raw_page = None
    supported = {"answer", "article", "zvideo"}

    async def observed_get(uri, params=None, **kwargs):
        nonlocal raw_page
        response = await original_get(uri, params, **kwargs)
        if uri != "/api/v4/search_v3":
            return response
        if not isinstance(response, dict) or not isinstance(response.get("data"), list) or len(response["data"]) > 100:
            raise Halt("schema_error", "ZHIHU_SEARCH_SHAPE")
        paging = response.get("paging")
        if paging is not None and (not isinstance(paging, dict) or ("is_end" in paging and type(paging["is_end"]) is not bool)):
            raise Halt("schema_error", "ZHIHU_PAGING_SHAPE")
        cleaned = copy.deepcopy(response)
        expected = []
        for row in cleaned["data"]:
            if not isinstance(row, dict):
                raise Halt("schema_error", "ZHIHU_RESULT_SHAPE")
            if row.get("type") not in {"search_result", "zvideo"}:
                continue
            obj = row.get("object")
            if not isinstance(obj, dict):
                raise Halt("schema_error", "ZHIHU_OBJECT_MISSING")
            if obj.get("type") not in supported:
                raise Halt("schema_error", "ZHIHU_CONTENT_TYPE")
            if not isinstance(obj.get("id"), (str, int)) or isinstance(obj["id"], bool):
                raise Halt("schema_error", "ZHIHU_CONTENT_ID")
            expected.append((obj["type"], str(obj["id"])))
            for field in ("content", "title", "description", "excerpt"):
                value = obj.get(field)
                if value is not None:
                    if not isinstance(value, str):
                        raise Halt("schema_error", "ZHIHU_TEXT_SHAPE")
                    parser = _Plain()
                    parser.feed(value)
                    obj[field] = " ".join("".join(parser.parts).split())
        raw_page = {"expected": expected, "hasMore": not paging["is_end"] if isinstance(paging, dict) and "is_end" in paging else None}
        return cleaned

    client.get = observed_get
    seen = set()
    try:
        for index in range(1, observer.job["limits"]["maxSearchPages"] + 1):
            raw_page = None
            contents = await client.get_note_by_keyword(keyword=observer.job["query"]["text"], page=index)
            if raw_page is None or not isinstance(contents, list):
                raise Halt("schema_error", "ZHIHU_RESPONSE_NOT_OBSERVED")
            identities = [(getattr(row, "content_type", None), str(getattr(row, "content_id", ""))) for row in contents]
            if identities != raw_page["expected"]:
                raise Halt("schema_error", "ZHIHU_EXTRACTOR_DROPPED_CONTENT")
            page = {"pageIndex": index, "schemaValid": True, "contentItems": len(contents), "processed": False, "hasMore": raw_page["hasMore"]}
            observer.pages.append(page)
            for content, identity in zip(contents, identities):
                if identity in seen:
                    continue
                seen.add(identity)
                observer.current_origin = "upstream" if getattr(content, "title", "") else "missing"
                await store.update_zhihu_content(content)
            page["processed"] = True
            if raw_page["hasMore"] is False:
                observer.stop_reason = "exhausted"
                return
            await sleep(2)
        observer.stop_reason = "page_limit"
    finally:
        client.get = original_get


async def collect(client, observer_module, observer):
    from store import zhihu as store
    page = getattr(client, "_vciq_page", None)
    if page is None:
        raise observer_module.Halt("schema_error", "ZHIHU_PAGE_CONTEXT_MISSING")
    await page.goto("https://www.zhihu.com/search?" + urlencode({"q": observer.job["query"]["text"], "type": "content"}), wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)
    await client.update_cookies(page.context, urls=["https://www.zhihu.com"])
    capture = observer_module.CaptureStore(observer)
    store.ZhihuStoreFactory.create_store = staticmethod(lambda: capture)
    await search(client, store, observer_module, observer)
