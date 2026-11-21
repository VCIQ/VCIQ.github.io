"""Content identity checks for the shadow store, never person/entity inference."""
import re
from urllib.parse import urlsplit

from .contracts import ContractError


def identity_facts(doc):
    platform, native = doc["platform"], doc["nativeId"]
    aliases = doc["nativeAliases"]
    parent = None
    if platform == "bili":
        if not re.fullmatch(r"[1-9][0-9]{0,39}", native):
            raise ContractError("store_bilibili_aid")
        if len(aliases) > 1 or any(not re.fullmatch(r"bvid:BV[A-Za-z0-9]{10}", a) for a in aliases):
            raise ContractError("store_bilibili_alias")
    elif aliases:
        # The current adapters emit no other alias kind. Future alias families
        # require explicit semantics, not automatic cross-platform merging.
        raise ContractError("store_alias_not_supported")
    url = doc["canonicalUrl"]
    if url:
        path = urlsplit(url).path.rstrip("/")
        if platform == "bili":
            allowed = {"/video/av" + native} | {"/video/" + a[5:] for a in aliases}
            if path not in allowed: raise ContractError("store_url_identity")
        elif platform in {"xhs", "wb"}:
            if path.split("/")[-1] != native: raise ContractError("store_url_identity")
        elif platform == "zhihu":
            if path.split("/")[-1] != native: raise ContractError("store_url_identity")
            if doc["contentType"] == "answer":
                match = re.fullmatch(r"/question/([1-9][0-9]*)/answer/([1-9][0-9]*)", path)
                if not match: raise ContractError("store_answer_parent")
                parent = match[1]
            elif path != ("/p/" if doc["contentType"] == "article" else "/zvideo/") + native:
                raise ContractError("store_url_identity")
    return {"questionId": parent}


def merge_facts(old, new):
    if old.get("questionId") and new.get("questionId") and old["questionId"] != new["questionId"]:
        raise ContractError("store_answer_parent_conflict")
    return {"questionId": old.get("questionId") or new.get("questionId")}
