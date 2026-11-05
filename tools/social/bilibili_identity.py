"""Read-only identity reconciliation against discover_person_video_materials output.

An aid/BVID pair must be supplied by a normalized detail observation. No numeric
conversion algorithm, title-based merge, remote redirect resolution or writes.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from .contracts import ContractError, validate


def link_identity(value):
    if not isinstance(value, str) or len(value) > 2000: return None
    try:
        p = urlsplit(value)
        if p.scheme not in {"http", "https"} or p.hostname not in {"www.bilibili.com", "bilibili.com"} or p.username is not None or p.port is not None or "\\" in value:
            return None
        match = re.fullmatch(r"/video/(av[1-9][0-9]{0,29}|BV[0-9A-Za-z]{10})/?", p.path)
        if not match: return None
        native = match[1]
        return "aid:" + native[2:] if native.startswith("av") else "bvid:" + native
    except ValueError:
        return None


def reconcile_materials(observations, materials):
    if not isinstance(materials, list) or len(materials) > 20000: raise ContractError("video_material_list_required")
    if not isinstance(observations, list) or len(observations) > 10000: raise ContractError("video_observation_list_required")
    aliases, normalized, aid_pairs = {}, [], {}
    for doc in observations:
        validate(doc, expected_kind="signal_observation")
        if doc["platform"] != "bili": raise ContractError("bili_observations_required")
        native = doc["nativeId"]
        if not re.fullmatch(r"[1-9][0-9]{0,29}", native): raise ContractError("bili_aid")
        keys = ["aid:" + native]
        if len(doc["nativeAliases"]) > 1: raise ContractError("bili_alias_count")
        for alias in doc["nativeAliases"]:
            if not re.fullmatch(r"bvid:BV[0-9A-Za-z]{10}", alias): raise ContractError("bili_alias")
            previous = aid_pairs.get(native)
            if previous and previous != alias: raise ContractError("bili_alias_conflict")
            aid_pairs[native] = alias
            keys.append(alias)
        for key in keys:
            if key in aliases and aliases[key] != doc["signalId"]: raise ContractError("bili_alias_conflict")
            aliases[key] = doc["signalId"]
        normalized.append(doc)
    matches, possible, unmatched = [], [], []
    def title_key(value):
        return " ".join(unicodedata.normalize("NFKC", value).casefold().split()) if isinstance(value, str) else ""
    for index, material in enumerate(materials):
        if not isinstance(material, dict): raise ContractError("video_material_object_required")
        key = link_identity(material.get("url"))
        if key and key in aliases:
            matches.append({"materialIndex": index, "signalId": aliases[key], "basis": "exact_aid" if key.startswith("aid:") else "detail_verified_bvid"})
            continue
        # Titles may suggest a manual check only when the existing identifier is
        # of a different kind and no aid/BVID relationship has been established.
        title = title_key(material.get("title"))
        candidates = sorted({d["signalId"] for d in normalized if key and key.startswith("bvid:") and not d["nativeAliases"] and title and title == title_key(d["title"])})
        if candidates:
            possible.append({"materialIndex": index, "candidateSignals": candidates, "basis": "title_only_not_merged"})
        else:
            unmatched.append(index)
    return {"matches": matches, "possibleDuplicates": possible, "unmatchedMaterialIndices": unmatched,
            "productionWrites": False, "observationsRemoved": 0, "personIdentityInferred": False}
