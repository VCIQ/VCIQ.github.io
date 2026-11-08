"""Bounded Weibo search projection; no network, imports, or browser at load time."""
from __future__ import annotations

import re

FIELDS = frozenset({"note_id", "content", "create_time", "create_date_time", "raw_created_at",
    "creator_hash", "nickname", "liked_count", "comments_count", "shared_count"})


class ShapeError(ValueError):
    """Only fixed codes; never include platform response values."""


def native_id(value):
    if type(value) is int and value > 0:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,39}", value):
        raise ShapeError("WEIBO_ID_INVALID")
    return value


def extract_posts(response):
    """Recognize type-9 cards, including groups; do not infer repost parents.

    A successful *empty cards array* ends the accessible query. A nonempty array
    with only recommendations is not proof of zero results. Search totals are
    not trusted as pagination cursors or evidence of exhaustive coverage.
    """
    if not isinstance(response, dict) or not isinstance(response.get("cards"), list):
        raise ShapeError("WEIBO_SEARCH_SCHEMA")
    if "cardlistInfo" in response and not isinstance(response["cardlistInfo"], dict):
        raise ShapeError("WEIBO_SEARCH_SCHEMA")
    posts, visited = [], 0
    def visit(cards, depth):
        nonlocal visited
        if not isinstance(cards, list) or depth > 3 or len(cards) > 200:
            raise ShapeError("WEIBO_CARD_GROUP_INVALID")
        for card in cards:
            visited += 1
            if visited > 300 or not isinstance(card, dict):
                raise ShapeError("WEIBO_CARD_GROUP_INVALID")
            if card.get("card_type") == 9 and type(card.get("card_type")) is int:
                post = card.get("mblog")
                if not isinstance(post, dict):
                    raise ShapeError("WEIBO_POST_INVALID")
                identity = native_id(post.get("id"))
                for key in ("idstr", "mid"):
                    if post.get(key) is not None and native_id(post[key]) != identity:
                        raise ShapeError("WEIBO_ID_CONFLICT")
                posts.append({**card, "mblog": {**post, "id": identity}})
            if "card_group" in card:
                visit(card["card_group"], depth + 1)
    visit(response["cards"], 0)
    return posts, False if response["cards"] == [] else None


def select_record(raw, expected_id, observed_at):
    if not isinstance(raw, dict) or native_id(raw.get("note_id")) != expected_id:
        raise ShapeError("WEIBO_PROJECTION_ID")
    selected = {key: raw.get(key) for key in FIELDS}
    selected["note_id"] = expected_id
    for value in selected.values():
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float))):
            raise ShapeError("WEIBO_PROJECTION_TYPE")
        if isinstance(value, str) and len(value) > 100_000:
            raise ShapeError("WEIBO_PROJECTION_SIZE")
    return {"record": selected, "originalTitle": False, "observedAt": observed_at}


async def collect_weibo(job, search, project, *, observer=None, clock=None):
    if observer is None:
        from . import observer
    clock = clock or observer.stamp
    result = observer.envelope(job, clock)
    seen, attempts = set(), 0
    try:
        if job["platform"] != "wb" or job["operation"] != "search":
            raise observer.CollectorError("unsupported", "WEIBO_SEARCH_ONLY")
        query = job["query"]
        if query["scope"] != "track" or query["targetId"] is not None:
            raise observer.CollectorError("unsupported", "WEIBO_TRACK_ONLY")
        if any(ch in query["text"] for ch in ",&=#?") or job["window"]["filterMode"] == "native":
            raise observer.CollectorError("unsupported", "WEIBO_QUERY_UNSUPPORTED")
        limits = job["limits"]
        if any(type(limits[key]) is not int or limits[key] <= 0 for key in ("maxSearchPages", "maxRecords", "maxWallSeconds")):
            raise ShapeError("WEIBO_LIMIT_INVALID")
        for number in range(1, limits["maxSearchPages"] + 1):
            posts, more = extract_posts(await search(query["text"], number))
            page = {"pageIndex": number, "schemaValid": True, "contentItems": len(posts),
                    "processed": False, "hasMore": more}
            result["pages"].append(page)
            for index, post in enumerate(posts):
                identity = post["mblog"]["id"]
                if identity in seen:
                    result["searchDuplicates"] += 1
                    continue
                if attempts >= limits["maxRecords"]:
                    result["detailsNotRequested"] += len(posts) - index
                    break
                seen.add(identity)
                attempts += 1
                projected = await project(post)
                result["records"].append(select_record(projected, identity, clock()))
            page["processed"] = True
            if result["detailsNotRequested"] or attempts >= limits["maxRecords"]:
                result["stopReason"] = "item_limit"
                break
            if more is False:
                result["stopReason"] = "exhausted"
                break
        result["stopReason"] = result["stopReason"] or "page_limit"
        if sum(page["contentItems"] for page in result["pages"]):
            result["status"] = "ok"
        elif result["stopReason"] == "exhausted":
            result["status"] = "empty"
        else:
            raise observer.CollectorError("schema_error", "EMPTY_COVERAGE_UNPROVEN")
    except ShapeError as exc:
        observer.fail(result, observer.CollectorError("schema_error", str(exc)))
    except Exception as exc:
        observer.fail(result, observer.classify(exc))
    result["completedAt"] = clock()
    return result
