"""Weibo store normalizer. No inferred retweet-parent or author identity."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from ..contracts import ContractError
from .common import epoch, native_id, observation, text


def normalize_record(raw, job, *, observed_at, title_origin="derived", terms=None):
    if job["platform"] != "wb" or not isinstance(raw, dict) or not isinstance(raw.get("content"), str):
        raise ContractError("weibo_record_shape")
    identifier = native_id(raw.get("note_id"))
    if not identifier.isdigit():
        raise ContractError("weibo_native_id")
    published = epoch(raw.get("create_time"))
    local = raw.get("create_date_time")
    if local not in (None, ""):
        if not isinstance(local, str):
            raise ContractError("weibo_time_shape")
        try:
            value = datetime.fromisoformat(local.replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone(timedelta(hours=8)))
            local_utc = value.astimezone(UTC).isoformat(timespec="seconds")
        except ValueError:
            raise ContractError("weibo_time_shape") from None
        if published and published != local_utc:
            raise ContractError("weibo_time_conflict")
        published = published or local_utc
    body = text(raw["content"], 500)
    return observation(job, raw, observed_at=observed_at, identifier=identifier,
        content_type="post", url=f"https://m.weibo.cn/detail/{identifier}", title=body[:120],
        excerpt=body, title_origin="derived", published=published, terms=terms,
        metrics={"likes": raw.get("liked_count"), "comments": raw.get("comments_count"), "shares": raw.get("shared_count")})
