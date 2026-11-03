"""Video metadata only. An aid/BVID alias requires the same detail response."""
from __future__ import annotations

import re
from ..contracts import ContractError
from .common import epoch, native_id, observation


def normalize_record(raw, job, *, observed_at, title_origin="upstream", terms=None):
    if job["platform"] != "bili" or not isinstance(raw, dict) or raw.get("video_type") != "video" or not isinstance(raw.get("title"), str) or not isinstance(raw.get("desc"), str):
        raise ContractError("bilibili_record_shape")
    identifier = native_id(raw.get("video_id"))
    if not identifier.isdigit():
        raise ContractError("bilibili_aid_required")
    aliases = []
    mapping = raw.get("observed_video_identity")
    if mapping is not None:
        if not isinstance(mapping, dict) or set(mapping) != {"aid", "bvid"} or str(mapping["aid"]) != identifier or not isinstance(mapping["bvid"], str) or not re.fullmatch(r"BV[A-Za-z0-9]{10}", mapping["bvid"]):
            raise ContractError("bilibili_identity_mapping")
        aliases = ["bili:bvid:" + mapping["bvid"]]
    return observation(job, raw, observed_at=observed_at, identifier=identifier,
        content_type="video", url=f"https://www.bilibili.com/video/av{identifier}",
        title=raw["title"], excerpt=raw["desc"], title_origin=title_origin,
        text_scope="video_description", published=epoch(raw.get("create_time")), aliases=aliases, terms=terms,
        metrics={"likes": raw.get("liked_count"), "comments": raw.get("video_comment"),
                 "shares": raw.get("video_share_count"), "views": raw.get("video_play_count")})
