"""Bounded XHS search orchestration; standard library only, no import-time I/O.

The pinned upstream search exits before processing a final nonempty page. This
companion owns pagination instead, calling the unmodified upstream client/store.
It never interprets process exit status or an absent file as a successful search.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

STATUSES = frozenset({"auth_required", "verification_required", "rate_limited",
    "network_error", "timeout", "schema_error", "unsupported", "cancelled"})
REASONS = {
    "auth_required": "auth", "verification_required": "verification",
    "rate_limited": "rate_limit", "network_error": "network", "timeout": "timeout",
    "schema_error": "schema", "unsupported": "unsupported", "cancelled": "cancelled"}
FIELDS = frozenset({"note_id", "type", "title", "desc", "time", "last_update_time",
    "creator_hash", "nickname", "liked_count", "comment_count", "share_count"})


class CollectorError(Exception):
    """An allowlisted status/code, never raw server response text."""
    def __init__(self, status: str, code: str, retry_after: int | None = None):
        if status not in STATUSES or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,119}", code):
            status, code = "schema_error", "INVALID_ERROR_CLASSIFICATION"
        self.status, self.code = status, code
        self.retry_after = retry_after if type(retry_after) is int and retry_after >= 0 else None
        super().__init__(code)


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify(exc: Exception) -> CollectorError:
    if isinstance(exc, CollectorError):
        return exc
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return CollectorError("timeout", "REQUEST_TIMEOUT")
    name = type(exc).__name__
    if name == "IPBlockError":
        return CollectorError("rate_limited", "PLATFORM_RATE_LIMIT")
    if name == "PlatformAccessError":
        return CollectorError("verification_required", "PLATFORM_ACCESS_RESTRICTED")
    if name in {"DataFetchError", "RequestError", "ConnectError", "ReadError", "NoteNotFoundError"}:
        return CollectorError("network_error", "DETAIL_OR_NETWORK_FAILURE")
    return CollectorError("schema_error", "UNEXPECTED_WORKER_ERROR")


def envelope(job: dict, clock=stamp) -> dict:
    return {"version": 1, "attemptId": job["attemptId"], "queryId": job["queryId"],
            "startedAt": clock(), "completedAt": None, "pages": [], "records": [],
            "detailFailures": 0, "searchDuplicates": 0, "detailsNotRequested": 0,
            "status": None, "stopReason": None, "errorCode": None, "retryAfter": None}


def fail(result: dict, error: CollectorError) -> None:
    result.update(status=error.status, stopReason=REASONS[error.status],
                  errorCode=error.code, retryAfter=error.retry_after)


def select_record(raw: dict, *, original_title: bool, observed_at: str) -> dict:
    if not isinstance(raw, dict):
        raise CollectorError("schema_error", "STORE_RECORD_INVALID")
    # Upstream note_url, xsec_token, media URLs and original user IDs never cross
    # the child boundary. Unknown upstream fields are not silently re-exported.
    selected = {key: raw.get(key) for key in FIELDS}
    if any(value is not None and not isinstance(value, (str, int, float))
           or isinstance(value, bool) for value in selected.values()):
        raise CollectorError("schema_error", "STORE_FIELD_TYPE")
    if any(isinstance(value, str) and len(value) > 100_000 for value in selected.values()):
        raise CollectorError("schema_error", "STORE_FIELD_TOO_LARGE")
    return {"record": selected, "originalTitle": bool(original_title), "observedAt": observed_at}


async def collect_xhs(job: dict, search, detail, store_projection, *, clock=stamp) -> dict:
    """Run one literal query. Callbacks are injected; this module opens no network.

    maxRecords also bounds detail attempts (not only accepted observations).
    searchItems may exceed rawRows: deliberately unrequested details are counted
    separately and must not be presented as normalizer budgetSkipped rows.
    """
    result = envelope(job, clock)
    seen: set[str] = set()
    attempts = 0
    try:
        if job["platform"] != "xhs" or job["operation"] != "search":
            raise CollectorError("unsupported", "XHS_SEARCH_ONLY")
        if job["query"]["scope"] != "track" or job["query"]["targetId"] is not None:
            raise CollectorError("unsupported", "XHS_TRACK_SCOPE_ONLY")
        if "," in job["query"]["text"] or job["window"]["filterMode"] == "native":
            raise CollectorError("unsupported", "QUERY_FILTER_UNSUPPORTED")
        limits = job["limits"]
        if not all(type(limits[k]) is int and limits[k] > 0 for k in ("maxSearchPages", "maxRecords", "maxWallSeconds")):
            raise CollectorError("schema_error", "INVALID_LIMITS")
        for page_no in range(1, limits["maxSearchPages"] + 1):
            response = await search(job["query"]["text"], page_no)
            if not isinstance(response, dict) or not isinstance(response.get("items"), list):
                raise CollectorError("schema_error", "SEARCH_SCHEMA_CHANGED")
            more = response.get("has_more")
            if more is not None and type(more) is not bool or len(response["items"]) > 100:
                raise CollectorError("schema_error", "SEARCH_SCHEMA_CHANGED")
            items = []
            for item in response["items"]:
                if not isinstance(item, dict):
                    raise CollectorError("schema_error", "SEARCH_ITEM_INVALID")
                if item.get("model_type") in {"rec_query", "hot_query"}:
                    continue
                native = item.get("id")
                if not isinstance(native, str) or not re.fullmatch(r"[0-9a-fA-F]{24}", native):
                    raise CollectorError("schema_error", "SEARCH_ITEM_ID_INVALID")
                items.append(item)
            page = {"pageIndex": page_no, "schemaValid": True,
                    "contentItems": len(items), "processed": False, "hasMore": more}
            result["pages"].append(page)
            for index, item in enumerate(items):
                native = item["id"]
                if native in seen:
                    result["searchDuplicates"] += 1
                    continue
                if attempts >= limits["maxRecords"]:
                    result["detailsNotRequested"] += len(items) - index
                    break
                seen.add(native)
                attempts += 1
                try:
                    note = await detail(item)
                    if not isinstance(note, dict) or note.get("note_id") != native:
                        raise CollectorError("schema_error", "DETAIL_ID_MISMATCH")
                    observed_at = clock()
                    projected = await store_projection(note)
                    if not isinstance(projected, dict) or projected.get("note_id") != native:
                        raise CollectorError("schema_error", "STORE_ID_MISMATCH")
                    result["records"].append(select_record(projected,
                        original_title=bool(note.get("title")), observed_at=observed_at))
                except Exception as exc:
                    error = classify(exc)
                    result["detailFailures"] += 1
                    fail(result, error)
                    # Restrictions and schema drift stop the query, not another
                    # login attempt or an IP switch. Ordinary detail loss may be partial.
                    if error.status != "network_error":
                        raise error
            page["processed"] = True
            # Process items BEFORE testing the final-page marker.
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
            total = sum(page["contentItems"] for page in result["pages"])
            if total:
                result["status"] = "ok"
            elif result["stopReason"] == "exhausted":
                result["status"] = "empty"
            else:
                # Frozen v1 has no 'empty but not proven exhausted' success state.
                fail(result, CollectorError("schema_error", "EMPTY_COVERAGE_UNPROVEN"))
    except Exception as exc:
        fail(result, classify(exc))
    result["completedAt"] = clock()
    return result
