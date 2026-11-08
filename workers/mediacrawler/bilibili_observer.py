"""Bounded video search/detail orchestration; no network or VCIQ imports."""
from __future__ import annotations

import re

FIELDS = frozenset({"video_id", "bvid", "title", "desc", "create_time", "creator_hash",
    "nickname", "liked_count", "video_comment", "video_share_count", "video_play_count"})
KNOWN_VALIDATION_ERRORS = frozenset({
    "BILI_AID_INVALID", "BILI_BVID_INVALID", "BILI_SEARCH_SCHEMA",
    "BILI_SEARCH_PAGE_TOO_LARGE", "BILI_SEARCH_PAGE_MISMATCH",
    "BILI_SEARCH_PAGE_COUNT", "BILI_SEARCH_PAGE_CONTRADICTION",
    "BILI_EMPTY_PAGE_CONTRADICTION", "BILI_VIDEO_ITEM_REQUIRED",
    "BILI_SEARCH_ID_CONFLICT", "BILI_DETAIL_ID_MISMATCH",
    "BILI_DETAIL_ALIAS_MISMATCH", "BILI_ALIAS_CONFLICT",
    "BILI_PROJECTED_ID_MISMATCH", "BILI_STORE_RECORD",
    "BILI_STORE_FIELD_TYPE", "BILI_STORE_FIELD_LENGTH", "BILI_LIMITS",
})
STAGES = frozenset({"PRECHECK", "SEARCH_CALL", "SEARCH_RESPONSE",
    "DETAIL_CALL", "DETAIL_RESPONSE", "PROJECT"})


def classify_bilibili(exc, observer, stage):
    """Fixed error code + stage only. Never export raw platform text or URLs."""
    if isinstance(exc, ValueError) and str(exc) in KNOWN_VALIDATION_ERRORS:
        return observer.CollectorError("schema_error", str(exc))
    classified = observer.classify(exc)
    if classified.code == "UNEXPECTED_WORKER_ERROR":
        return observer.CollectorError("schema_error",
            "BILI_" + stage + "_UNEXPECTED" if stage in STAGES else "BILI_UNKNOWN_UNEXPECTED")
    return classified


def aid(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,29}", value):
        raise ValueError("BILI_AID_INVALID")
    return value


def bvid(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not re.fullmatch(r"BV[0-9A-Za-z]{10}", value):
        raise ValueError("BILI_BVID_INVALID")
    return value


def search_items(response, page_no):
    if not isinstance(response, dict) or not isinstance(response.get("result"), list):
        raise ValueError("BILI_SEARCH_SCHEMA")
    items = response["result"]
    if len(items) > 100:
        raise ValueError("BILI_SEARCH_PAGE_TOO_LARGE")
    if "page" in response and (type(response["page"]) is not int or response["page"] != page_no):
        raise ValueError("BILI_SEARCH_PAGE_MISMATCH")
    pages = response.get("numPages")
    if pages is not None and (type(pages) is not int or not 0 <= pages <= 1000000):
        raise ValueError("BILI_SEARCH_PAGE_COUNT")
    if items and pages is not None and pages < page_no:
        raise ValueError("BILI_SEARCH_PAGE_CONTRADICTION")
    if not items and pages is not None and pages > page_no:
        raise ValueError("BILI_EMPTY_PAGE_CONTRADICTION")
    for item in items:
        if not isinstance(item, dict) or item.get("type", "video") != "video":
            raise ValueError("BILI_VIDEO_ITEM_REQUIRED")
        aid(item.get("aid"))
        bvid(item.get("bvid"))
    more = False if not items else page_no < pages if pages is not None else None
    return items, more


def select_record(raw):
    if not isinstance(raw, dict):
        raise ValueError("BILI_STORE_RECORD")
    selected = {key: raw.get(key) for key in FIELDS}
    if any(value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float))) for value in selected.values()):
        raise ValueError("BILI_STORE_FIELD_TYPE")
    if any(isinstance(value, str) and len(value) > 100000 for value in selected.values()):
        raise ValueError("BILI_STORE_FIELD_LENGTH")
    selected["video_id"] = aid(selected["video_id"])
    selected["bvid"] = bvid(selected["bvid"])
    return selected


async def collect_bilibili(job, search, detail, project, *, observer, clock=None):
    clock = clock or observer.stamp
    result = observer.envelope(job, clock)
    seen, search_pairs, verified_pairs = set(), {}, {}
    attempts = 0
    stage = "PRECHECK"
    try:
        if job["platform"] != "bili" or job["operation"] != "search":
            raise observer.CollectorError("unsupported", "BILI_SEARCH_ONLY")
        query = job["query"]
        if query["scope"] != "track" or query["targetId"] is not None or query["providerFilters"]:
            raise observer.CollectorError("unsupported", "BILI_TRACK_SCOPE_ONLY")
        if any(c in query["text"] for c in ",!'()*") or job["window"]["filterMode"] == "native":
            raise observer.CollectorError("unsupported", "BILI_QUERY_FILTER_UNSUPPORTED")
        limits = job["limits"]
        if not all(type(limits[k]) is int and limits[k] > 0 for k in ("maxSearchPages", "maxRecords", "maxWallSeconds")):
            raise ValueError("BILI_LIMITS")
        for number in range(1, limits["maxSearchPages"] + 1):
            stage = "SEARCH_CALL"
            response = await search(query["text"], number)
            stage = "SEARCH_RESPONSE"
            items, more = search_items(response, number)
            page = {"pageIndex": number, "schemaValid": True, "contentItems": len(items), "processed": False, "hasMore": more}
            result["pages"].append(page)
            for index, item in enumerate(items):
                native, bv = aid(item["aid"]), bvid(item.get("bvid"))
                previous = search_pairs.get(native)
                if previous and bv and previous != bv:
                    raise ValueError("BILI_SEARCH_ID_CONFLICT")
                search_pairs[native] = bv or previous
                if native in seen:
                    result["searchDuplicates"] += 1
                    continue
                if attempts >= limits["maxRecords"]:
                    result["detailsNotRequested"] += len(items) - index
                    break
                seen.add(native)
                attempts += 1
                try:
                    stage = "DETAIL_CALL"
                    raw = await detail(native)
                    stage = "DETAIL_RESPONSE"
                    view = raw.get("View") if isinstance(raw, dict) else None
                    if not isinstance(view, dict) or aid(view.get("aid")) != native:
                        raise ValueError("BILI_DETAIL_ID_MISMATCH")
                    detail_bv = bvid(view.get("bvid"))
                    if bv and detail_bv and bv != detail_bv:
                        raise ValueError("BILI_DETAIL_ALIAS_MISMATCH")
                    if detail_bv and detail_bv in verified_pairs and verified_pairs[detail_bv] != native:
                        raise ValueError("BILI_ALIAS_CONFLICT")
                    observed = clock()
                    stage = "PROJECT"
                    projected = select_record(await project(raw))
                    if projected["video_id"] != native or projected["bvid"] != detail_bv:
                        raise ValueError("BILI_PROJECTED_ID_MISMATCH")
                    if detail_bv:
                        verified_pairs[detail_bv] = native
                    result["records"].append({"record": projected, "originalTitle": bool(view.get("title")), "observedAt": observed})
                except Exception as exc:
                    error = classify_bilibili(exc, observer, stage)
                    result["detailFailures"] += 1
                    observer.fail(result, error)
                    if error.status != "network_error":
                        raise error
            page["processed"] = True
            if result["detailsNotRequested"]:
                result["stopReason"] = result["stopReason"] or "item_limit"
                break
            if more is False:
                result["stopReason"] = result["stopReason"] or "exhausted"
                break
            if attempts >= limits["maxRecords"]:
                result["stopReason"] = result["stopReason"] or "item_limit"
                break
        if result["status"] is None:
            result["stopReason"] = result["stopReason"] or "page_limit"
            total = sum(p["contentItems"] for p in result["pages"])
            if total:
                result["status"] = "ok"
            elif result["stopReason"] == "exhausted":
                result["status"] = "empty"
            else:
                raise observer.CollectorError("schema_error", "EMPTY_COVERAGE_UNPROVEN")
    except Exception as exc:
        observer.fail(result, classify_bilibili(exc, observer, stage))
    result["completedAt"] = clock()
    return result
