"""Weibo bounded search using pinned client and anonymizing store mapping."""
from __future__ import annotations

import asyncio
import copy
from html.parser import HTMLParser


class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "template"}:
            self.hidden += 1
        elif not self.hidden and tag in {"p", "div", "br"}:
            self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "template"} and self.hidden:
            self.hidden -= 1
    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


async def setup(context, page):
    from media_platform.weibo.core import WeiboCrawler
    crawler = WeiboCrawler()
    crawler.browser_context, crawler.context_page = context, page
    await page.goto(crawler.mobile_index_url, wait_until="domcontentloaded", timeout=30000)
    return await crawler.create_weibo_client(None), crawler.cookie_urls


async def search(client, store, observer_module, observer, *, sleep=asyncio.sleep):
    Halt = observer_module.Halt
    job, seen = observer.job, set()
    for index in range(1, job["limits"]["maxSearchPages"] + 1):
        response = await client.get_note_by_keyword(keyword=job["query"]["text"], page=index)
        if not isinstance(response, dict) or not isinstance(response.get("cards"), list):
            raise Halt("schema_error", "WEIBO_SEARCH_SHAPE")
        cards, notes = response["cards"], []
        for card in cards:
            if not isinstance(card, dict) or not isinstance(card.get("card_group", []), list):
                raise Halt("schema_error", "WEIBO_CARD_SHAPE")
            for candidate in [card, *card.get("card_group", [])]:
                if not isinstance(candidate, dict):
                    raise Halt("schema_error", "WEIBO_CARD_SHAPE")
                if candidate.get("card_type") == 9:
                    item = candidate.get("mblog")
                    if not isinstance(item, dict) or isinstance(item.get("id"), bool) or not isinstance(item.get("id"), (str, int)) or not isinstance(item.get("text"), str):
                        raise Halt("schema_error", "WEIBO_POST_SHAPE")
                    notes.append(candidate)
        page = {"pageIndex": index, "schemaValid": True, "contentItems": len(notes), "processed": False, "hasMore": False if not cards else None}
        observer.pages.append(page)
        for note in notes:
            identifier = str(note["mblog"]["id"])
            if identifier in seen:
                continue
            seen.add(identifier)
            safe_input = copy.deepcopy(note)
            parser = _Plain()
            parser.feed(safe_input["mblog"]["text"])
            safe_input["mblog"]["text"] = " ".join("".join(parser.parts).split())
            observer.current_origin = "derived"
            await store.update_weibo_note(safe_input)
        page["processed"] = True
        if not cards:
            observer.stop_reason = "exhausted"
            return
        # A nonempty card list is not proof of another page or total exhaustion.
        await sleep(2)
    observer.stop_reason = "page_limit"


async def collect(client, observer_module, observer):
    from store import weibo as store
    capture = observer_module.CaptureStore(observer)
    store.WeibostoreFactory.create_store = staticmethod(lambda: capture)
    await search(client, store, observer_module, observer)
