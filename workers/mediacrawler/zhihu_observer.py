"""Bounded Zhihu search with raw paging evidence; no network at import time."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

TYPES = frozenset({"answer", "article", "zvideo"})
NON_TARGETS = frozenset({"question", "topic", "people", "person", "column"})
FIELDS = frozenset({"content_id", "content_type", "question_id", "title", "question_title",
    "content", "description", "excerpt", "created_time", "updated_time", "created", "updated",
    "created_at", "published_at", "updated_at", "voteup_count", "comment_count",
    "creator_hash", "nickname"})


def identifier(value, observer, *, optional=False):
    if optional and value in (None, ""):
        return None
    if type(value) is int and value > 0:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,39}", value):
        raise observer.CollectorError("schema_error", "ZHIHU_ID_INVALID")
    return value


def content_identity(obj, observer):
    if not isinstance(obj, dict) or obj.get("type") not in TYPES:
        raise observer.CollectorError("schema_error", "ZHIHU_CONTENT_TYPE")
    native = identifier(obj.get("id"), observer)
    question = obj.get("question")
    if question is not None and not isinstance(question, dict):
        raise observer.CollectorError("schema_error", "ZHIHU_QUESTION_SHAPE")
    parent = identifier((question or {}).get("id"), observer, optional=True) if obj["type"] == "answer" else None
    return obj["type"], native, parent


def validate_next_cursor(next_url, job, page_number, observer):
    """Diagnose a returned cursor without following or exporting its URL."""
    error = observer.CollectorError
    if not isinstance(next_url, str) or len(next_url) > 4096 or "\\" in next_url:
        raise error("schema_error", "ZHIHU_PAGING_CURSOR_FORMAT")
    try:
        parts = urlsplit(next_url)
        # The server's paging.next is metadata only. We *never follow it*;
        # the pinned, exact-allowlisted client constructs any later request.
        # Accept a path-only cursor or one of two fixed Zhihu API hosts.
        # Never accept arbitrary subdomains, cross-domain or HTTP redirects.
        relative = not parts.scheme and not parts.netloc
        official = (parts.scheme == "https" and
                    parts.hostname in {"www.zhihu.com", "api.zhihu.com"})
        if ((not relative and not official) or parts.port is not None
            or parts.username is not None or parts.fragment):
            raise error("schema_error", "ZHIHU_PAGING_CURSOR_AUTHORITY")
        if parts.path != "/api/v4/search_v3":
            raise error("schema_error", "ZHIHU_PAGING_CURSOR_PATH")
        pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
        params = dict(pairs)
        if len(params) != len(pairs):
            raise error("schema_error", "ZHIHU_PAGING_CURSOR_QUERY")
        if params.get("offset") != str(page_number * 20):
            raise error("schema_error", "ZHIHU_PAGING_CURSOR_OFFSET")
        if "q" in params and params["q"] != job["query"]["text"]:
            raise error("schema_error", "ZHIHU_PAGING_CURSOR_KEYWORD")
    except error:
        raise
    except (ValueError, TypeError):
        raise error("schema_error", "ZHIHU_PAGING_CURSOR_FORMAT") from None


def page_contents(response, job, page_number, observer):
    error = observer.CollectorError
    if not isinstance(response, dict) or "error" in response or not isinstance(response.get("data"), list):
        raise error("schema_error", "ZHIHU_SEARCH_SCHEMA")
    paging = response.get("paging")
    if not isinstance(paging, dict) or len(response["data"]) > 100:
        raise error("schema_error", "ZHIHU_PAGING_SCHEMA")
    end = paging.get("is_end")
    if end is not None and type(end) is not bool:
        raise error("schema_error", "ZHIHU_PAGING_END_TYPE")
    # Never follow a server-supplied URL. Validate a supplied next cursor, then
    # let the pinned client build the next page's offset from its page number.
    next_url = paging.get("next")
    if next_url not in (None, "") and end is not True:
        validate_next_cursor(next_url, job, page_number, observer)
    items, excluded = [], 0
    for wrapper in response["data"]:
        if not isinstance(wrapper, dict) or wrapper.get("type") not in {"search_result", "zvideo"}:
            raise error("schema_error", "ZHIHU_SEARCH_CARD_UNKNOWN")
        obj = wrapper.get("object")
        if not isinstance(obj, dict):
            raise error("schema_error", "ZHIHU_SEARCH_OBJECT_REQUIRED")
        if obj.get("type") in NON_TARGETS and wrapper["type"] == "search_result":
            excluded += 1
            continue
        identity = content_identity(obj, observer)
        if wrapper["type"] == "zvideo" and identity[0] != "zvideo":
            raise error("schema_error", "ZHIHU_WRAPPER_TYPE_CONFLICT")
        items.append((obj, identity))
    return items, (not end if end is not None else None), excluded


def select_record(row, observer):
    if not isinstance(row, dict):
        raise observer.CollectorError("schema_error", "ZHIHU_PROJECTION_REQUIRED")
    selected = {field: row.get(field) for field in FIELDS}
    for value in selected.values():
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float))):
            raise observer.CollectorError("schema_error", "ZHIHU_PROJECTION_TYPE")
        if isinstance(value, str) and len(value) > 100000:
            raise observer.CollectorError("schema_error", "ZHIHU_PROJECTION_SIZE")
    return selected


async def collect_zhihu(job, search, project, *, observer, clock=None):
    """A search-card collector, not a detail/full-text/comment downloader."""
    clock = clock or observer.stamp
    result = observer.envelope(job, clock)
    result["excludedItems"] = 0
    seen = {}
    attempts = 0
    try:
        if job["platform"] != "zhihu" or job["operation"] != "search":
            raise observer.CollectorError("unsupported", "ZHIHU_SEARCH_ONLY")
        query = job["query"]
        if query["scope"] != "track" or query["targetId"] is not None or query["providerFilters"]:
            raise observer.CollectorError("unsupported", "ZHIHU_TRACK_SCOPE_ONLY")
        if not isinstance(query["text"], str) or not query["text"].strip() or "," in query["text"] or job["window"]["filterMode"] == "native":
            raise observer.CollectorError("unsupported", "ZHIHU_QUERY_FILTER_UNSUPPORTED")
        limits = job["limits"]
        if not all(type(limits[key]) is int and limits[key] > 0 for key in ("maxSearchPages", "maxRecords", "maxWallSeconds")):
            raise observer.CollectorError("schema_error", "ZHIHU_LIMITS_INVALID")
        for number in range(1, limits["maxSearchPages"] + 1):
            response = await search(query["text"], number)
            items, more, excluded = page_contents(response, job, number, observer)
            result["excludedItems"] += excluded
            page = {"pageIndex": number, "schemaValid": True, "contentItems": len(items), "processed": False, "hasMore": more}
            result["pages"].append(page)
            for index, (obj, identity) in enumerate(items):
                kind, native, parent = identity
                key = (kind, native)
                if key in seen:
                    if seen[key] != parent:
                        raise observer.CollectorError("schema_error", "ZHIHU_ANSWER_QUESTION_CONFLICT")
                    result["searchDuplicates"] += 1
                    continue
                if attempts >= limits["maxRecords"]:
                    result["detailsNotRequested"] += len(items) - index
                    break
                seen[key] = parent
                attempts += 1
                try:
                    row = select_record(await project(obj), observer)
                    if row["content_id"] != native or row["content_type"] != kind or row["question_id"] != parent:
                        raise observer.CollectorError("schema_error", "ZHIHU_PROJECTION_ID_CONFLICT")
                    result["records"].append({"record": row, "originalTitle": bool(obj.get("title")), "observedAt": clock()})
                except Exception as exc:
                    result["detailFailures"] += 1
                    raise observer.classify(exc)
            page["processed"] = True
            if result["detailsNotRequested"]:
                result["stopReason"] = "item_limit"
                break
            if more is False:
                result["stopReason"] = "exhausted"
                break
            if attempts >= limits["maxRecords"]:
                result["stopReason"] = "item_limit"
                break
        result["stopReason"] = result["stopReason"] or "page_limit"
        if sum(page["contentItems"] for page in result["pages"]):
            result["status"] = "ok"
        elif result["stopReason"] == "exhausted" and not result["excludedItems"]:
            result["status"] = "empty"
        else:
            raise observer.CollectorError("schema_error", "ZHIHU_EMPTY_COVERAGE_UNPROVEN")
    except Exception as exc:
        observer.fail(result, observer.classify(exc))
    result["completedAt"] = clock()
    return result
