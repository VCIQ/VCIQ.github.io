"""Normalize the pinned MediaCrawler XHS store payload, not arbitrary HTTP JSON."""
from __future__ import annotations

from ..contracts import ContractError
from .common import epoch, native_id, observation


def normalize_record(raw, job, *, observed_at, title_origin="upstream", terms=None):
    if job["platform"] != "xhs" or not isinstance(raw, dict):
        raise ContractError("xhs_record_shape")
    if "desc" not in raw or "title" not in raw:
        raise ContractError("xhs_record_shape")
    identifier = native_id(raw.get("note_id"))
    # The pinned note-card/store time fields are milliseconds; last_modify_ts is
    # a collection timestamp and must never supply a missing publication time.
    return observation(job, raw, observed_at=observed_at, identifier=identifier,
        content_type="note", url=f"https://www.xiaohongshu.com/explore/{identifier}",
        title=raw["title"], excerpt=raw["desc"], title_origin=title_origin,
        published=epoch(raw.get("time"), unit="milliseconds"),
        updated=epoch(raw.get("last_update_time"), unit="milliseconds"), terms=terms,
        metrics={"likes": raw.get("liked_count"), "comments": raw.get("comment_count"),
                 "shares": raw.get("share_count")})
