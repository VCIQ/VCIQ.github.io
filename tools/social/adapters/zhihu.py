"""Typed Zhihu content; question ID is context, never the answer identity."""
from __future__ import annotations

from ..contracts import ContractError
from .common import epoch, native_id, observation, text


def normalize_record(raw, job, *, observed_at, title_origin="upstream", terms=None):
    if job["platform"] != "zhihu" or not isinstance(raw, dict) or raw.get("content_type") not in {"answer", "article", "zvideo"}:
        raise ContractError("zhihu_record_type")
    identifier = native_id(raw.get("content_id"))
    if not identifier.isdigit():
        raise ContractError("zhihu_native_id")
    kind = raw["content_type"]
    body = text(raw.get("content_text") or raw.get("desc"), 500)
    url = None
    if kind == "answer":
        question = raw.get("question_id")
        if question not in (None, ""):
            question = native_id(question)
            if not question.isdigit():
                raise ContractError("zhihu_question_id")
            url = f"https://www.zhihu.com/question/{question}/answer/{identifier}"
        scope = "answer_excerpt"
    elif kind == "article":
        url, scope = f"https://zhuanlan.zhihu.com/p/{identifier}", "article_excerpt"
    else:
        url = f"https://www.zhihu.com/zvideo/{identifier}"
        scope = "video_description" if body else "title_only"
    published, updated = epoch(raw.get("created_time")), epoch(raw.get("updated_time"))
    if published and updated and updated < published:
        raise ContractError("zhihu_update_before_creation")
    return observation(job, raw, observed_at=observed_at, identifier=identifier,
        content_type=kind, url=url, title=raw.get("title"), excerpt=body, title_origin=title_origin,
        text_scope=scope, published=published, updated=updated, terms=terms,
        metrics={"likes": raw.get("voteup_count"), "comments": raw.get("comment_count")})
