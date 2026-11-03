"""Bounded search loops and factual receipts for an isolated MediaCrawler process.

Only explicit response structure establishes empty/exhausted. These loops replace
upstream convenience loops at runtime; no upstream source file is rewritten.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4


class Halt(RuntimeError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


class Observer:
    def __init__(self, job, *, clock=now):
        self.job, self.clock = job, clock
        self.started = clock()
        self.pages, self.rows = [], []
        self.detail_failures = 0
        self.error = None
        self.stop_reason = "page_limit"
        self.current_origin = "upstream"
        self.request_count = 0
        self.browser_requests = 0
        self.retry_after = 0

    def fail(self, status, code):
        if self.error is None:
            self.error = {"status": status, "code": code}

    def capture(self, record):
        if not isinstance(record, dict):
            raise Halt("schema_error", "STORE_RECORD_SHAPE")
        self.rows.append({"record": record, "observedAt": self.clock(), "titleOrigin": self.current_origin})

    def payload(self):
        return {"schemaVersion": 1, "jobId": self.job["jobId"], "attemptId": self.job["attemptId"],
            "startedAt": self.started, "completedAt": self.clock(), "pages": self.pages,
            "rows": self.rows, "detailFailures": self.detail_failures, "error": self.error,
            "stopReason": self.stop_reason, "httpRequests": self.request_count,
            "browserRequests": self.browser_requests, "retryAfterSeconds": self.retry_after}


class CaptureStore:
    def __init__(self, observer):
        self.observer = observer

    async def store_content(self, content_item):
        self.observer.capture(content_item)

    async def store_comment(self, *args, **kwargs):
        raise Halt("unsupported", "COMMENTS_DISABLED")

    async def store_creator(self, *args, **kwargs):
        raise Halt("unsupported", "CREATORS_DISABLED")


async def xhs_search(client, store, observer, *, sleep=asyncio.sleep):
    """Process a nonempty final page BEFORE looking at has_more=false.

Uses the pinned client's search/detail methods and upstream content mapping.
No HTML fallback, comments, creators, or media download paths are invoked.
"""
    job = observer.job
    seen = set()
    search_id = uuid4().hex
    for page_index in range(1, job["limits"]["maxSearchPages"] + 1):
        response = await client.get_note_by_keyword(keyword=job["query"]["text"], search_id=search_id, page=page_index)
        if not isinstance(response, dict) or not isinstance(response.get("items"), list) or type(response.get("has_more")) is not bool:
            raise Halt("schema_error", "XHS_SEARCH_SHAPE")
        items = []
        for item in response["items"]:
            if not isinstance(item, dict):
                raise Halt("schema_error", "XHS_SEARCH_ITEM_SHAPE")
            if item.get("model_type") in {"rec_query", "hot_query"}:
                continue
            if not isinstance(item.get("id"), str) or not item["id"]:
                raise Halt("schema_error", "XHS_SEARCH_ITEM_ID")
            items.append(item)
        page = {"pageIndex": page_index, "schemaValid": True, "contentItems": len(items),
                "processed": False, "hasMore": response["has_more"]}
        observer.pages.append(page)
        for item in items:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            if not isinstance(item.get("xsec_token"), str) or not item["xsec_token"]:
                raise Halt("schema_error", "XHS_ACCESS_LOCATOR_MISSING")
            try:
                detail = await client.get_note_by_id(item["id"], item.get("xsec_source") or "pc_search", item["xsec_token"])
                if not isinstance(detail, dict) or detail.get("note_id") != item["id"] or "desc" not in detail:
                    raise Halt("schema_error", "XHS_DETAIL_SHAPE")
                observer.current_origin = "upstream" if detail.get("title") else "derived" if detail.get("desc") else "missing"
                await store.update_xhs_note(detail)
            except Halt:
                raise
            except Exception as exc:
                name = type(exc).__name__
                if name == "NoteNotFoundError":
                    observer.detail_failures += 1
                    observer.fail("network_error", "CONTENT_UNAVAILABLE")
                else:
                    raise
            await sleep(2)
        page["processed"] = True
        if not response["has_more"]:
            observer.stop_reason = "exhausted"
            return
        await sleep(2)
    observer.stop_reason = "page_limit"


def apply_safe_config(config, *, platform, profile, output):
    """Apply AFTER parse_cmd; never let CLI defaults re-enable unsafe modes."""
    values = {
        "PLATFORM": platform, "CRAWLER_TYPE": "search", "START_PAGE": 1,
        "ENABLE_CDP_MODE": False, "CDP_CONNECT_EXISTING": False,
        "ENABLE_IP_PROXY": False, "STATIC_PROXY_URL": "", "DISABLE_SSL_VERIFY": False,
        "ENABLE_GET_COMMENTS": False, "ENABLE_GET_SUB_COMMENTS": False,
        "ENABLE_GET_MEDIA": False, "ENABLE_GET_WORDCLOUD": False,
        "MAX_CONCURRENCY_NUM": 1, "SAVE_DATA_OPTION": "jsonl", "SAVE_DATA_PATH": str(output),
        "SAVE_LOGIN_STATE": True, "USER_DATA_DIR": str(profile), "COOKIES": "",
        "BILI_SEARCH_MODE": "normal", "CREATOR_MODE": False, "XHS_INTERNATIONAL": False,
    }
    for key, value in values.items():
        setattr(config, key, value)
    return values
