#!/usr/bin/env python3
"""Authenticated manual-tracking command for the repository admin workflow.

The public Pages application is deliberately read-only.  This command is the
single write boundary used by ``workflow_dispatch``: it authenticates the
GitHub actor against a repository allowlist, validates one owner-entered
tracking intent, records durable provenance in ``tracking_intents.json`` and
compiles compatible values into the existing v1 tracking configuration.

No network request is made here.  In particular, an entered URL is evidence or
a future crawl source, never something this command fetches while privileged.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import ipaddress
import json
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from entity_resolution import (
        COMPANY_REGISTRY_PATH,
        PEOPLE_PATH,
        company_index,
        load_json,
        normalize_identity,
        people_index,
        resolve_entity,
    )
    from strict_tracking_config import parse_person_label, parse_tracking_keyword
    from tracking_manual_feedback import (
        build_manual_feedback,
        manual_held_source_hosts,
        signal_identity,
        source_host,
    )
except ImportError:  # pragma: no cover - supports ``python -m tools.manual_tracking``
    from tools.entity_resolution import (
        COMPANY_REGISTRY_PATH,
        PEOPLE_PATH,
        company_index,
        load_json,
        normalize_identity,
        people_index,
        resolve_entity,
    )
    from tools.strict_tracking_config import parse_person_label, parse_tracking_keyword
    from tools.tracking_manual_feedback import (
        build_manual_feedback,
        manual_held_source_hosts,
        signal_identity,
        source_host,
    )


ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"
INTENTS_PATH = ROOT / "config" / "tracking_intents.json"
ADMINS_PATH = ROOT / "config" / "tracking_admins.json"

KINDS = {"technology", "track", "company", "person", "source"}
MODES = {"validate", "apply", "recommend"}
SOURCE_CATEGORIES = {"media", "company", "person"}
REGIONS = {
    "china": "中国",
    "中国": "中国",
    "us": "美国",
    "usa": "美国",
    "美国": "美国",
    "global": "全球",
    "全球": "全球",
}
ALLOWED_REASONS = {
    "个人研究兴趣",
    "融资机会",
    "技术突破",
    "IPO可能",
    "商业模式创新",
    "市场竞争",
    "监管变化",
}
ROLE_BY_KIND = {
    "technology": "keyword",
    "company": "actor",
    "person": "actor",
    "source": "source-anchor",
}
LEGACY_TYPE_BY_KIND = {
    "technology": "topic",
    "company": "company",
    "person": "person",
}
FIELD_BY_KIND = {
    "technology": "keywords",
    "company": "sampleCompanies",
    "person": "people",
}
LEGAL_COMPANY_SUFFIX_RE = re.compile(
    r"^[^,]+,\s*(?:Inc\.?|LLC|Ltd\.?|L\.P\.?|Corp\.?)$", re.IGNORECASE
)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
SPLIT_RE = re.compile(r"[|｜\n\r]+")
TRACK_SPLIT_RE = re.compile(r"[|｜,，\n\r]+")
DROP_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "spm",
}
LOW_SIGNAL_TECHNOLOGIES = {
    "全球",
    "中国",
    "美国",
    "公开材料",
    "公司动态",
    "资本动态",
    "持续更新",
    "API",
    "Agent",
    "Agents",
    "Introducing",
}
PERSON_NOISE_RE = re.compile(
    r"(?:\b(?:company|business|corporate|development|sales|marketing|senior|"
    r"vice|president|officer|cfo|cto|ceo|team|leadership|management|class|"
    r"deepmind|anthropic|openai|post|times|news|media|university|institute|"
    r"foundation|labs?|inc|corp)\b|"
    r"模型|技术|系统|平台|算法|公司|集团|实验室|团队|研究|产品|新闻|网络|芯片|"
    r"机器人|智能|工程|资本|基金|大学|学院|协会|部门)",
    re.IGNORECASE,
)
COMPANY_NAME_CUE_RE = re.compile(
    r"(?:\b(?:inc\.?|corp\.?|corporation|company|labs?|systems?|technologies|"
    r"ventures?|capital|partners?|robotics|energy|biosciences?|ai)\b|"
    r"公司|集团|科技|资本|创投|智能|机器人|能源|生物|实验室)$",
    re.IGNORECASE,
)
COMPANY_NAME_NOISE = {
    "earlier",
    "london",
    "global",
    "company",
    "industry",
    "research",
    "enterprise",
    "cybersecurity",
    "中国",
    "美国",
    "全球",
}


class ManualTrackingError(ValueError):
    """A safe, user-facing validation error."""


def clean(value: Any, limit: int = 1200) -> str:
    return re.sub(
        r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))
    ).strip()[:limit]


def stable_id(prefix: str, *parts: Any, length: int = 20) -> str:
    material = "\x1f".join(clean(part, 4000).casefold() for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def _fnv36(value: str) -> str:
    number = 2166136261
    encoded = value.encode("utf-16-le")
    for index in range(0, len(encoded), 2):
        # Match JavaScript ``charCodeAt`` so new CJK-only track slugs are
        # compatible with ``lib/user-tracking.ts``.
        code_unit = encoded[index] | (encoded[index + 1] << 8)
        number ^= code_unit
        number = (number * 16777619) & 0xFFFFFFFF
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""
    while number:
        number, remainder = divmod(number, 36)
        result = alphabet[remainder] + result
    return result or "0"


def slugify_track(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", clean(value, 60))
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold())
    ascii_slug = ascii_slug.strip("-")[:48]
    return ascii_slug or f"track-{_fnv36(value)}"


def split_values(value: Any, *, tracks: bool = False, limit: int = 40) -> list[str]:
    raw = str(value or "")
    pattern = TRACK_SPLIT_RE if tracks else SPLIT_RE
    values: list[str] = []
    seen: set[str] = set()
    for part in pattern.split(raw):
        item = clean(part, 240)
        key = item.casefold()
        if not item or key in seen:
            continue
        values.append(item)
        seen.add(key)
        if len(values) >= limit:
            break
    return values


def is_single_value(
    value: Any,
    *,
    allow_legal_company_comma: bool = False,
    allow_spaced_slash: bool = False,
) -> bool:
    raw = str(value or "")
    text = clean(raw, 240)
    if not text or CONTROL_RE.search(raw):
        return False
    if any(marker in text for marker in ("、", "，", ";", "；", "|", "｜")):
        return False
    if text.count("(") != text.count(")") or text.count("（") != text.count("）"):
        return False
    if not allow_spaced_slash and re.search(r"\s/\s", text):
        return False
    if "," in text and not (allow_legal_company_comma and LEGAL_COMPANY_SUFFIX_RE.fullmatch(text)):
        return False
    return bool(re.search(r"[A-Za-z0-9\u3400-\u9fff]", text))


def normalize_url(value: Any, *, required: bool = False) -> str:
    raw = clean(value, 1200)
    if not raw:
        if required:
            raise ManualTrackingError("信源 URL 不能为空。")
        return ""
    try:
        parsed = urlsplit(raw)
        port = parsed.port  # Force malformed ports to fail here.
    except ValueError as exc:
        raise ManualTrackingError("URL 格式无效。") from exc
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ManualTrackingError("URL 仅允许带主机名的 http/https 地址。")
    if parsed.username or parsed.password:
        raise ManualTrackingError("URL 不允许包含用户名或密码。")
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost" or host.endswith(
        (".localhost", ".local", ".internal", ".lan", ".home", ".corp")
    ):
        raise ManualTrackingError("URL 不允许指向本机地址。")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ManualTrackingError("URL 不允许指向私有、保留或回环 IP。")
    if address is None and "." not in host:
        raise ManualTrackingError("URL 主机名必须是公开的完整域名。")
    default_port = port is None or (parsed.scheme.casefold() == "https" and port == 443) or (
        parsed.scheme.casefold() == "http" and port == 80
    )
    netloc = host if default_port else f"{host}:{port}"
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in DROP_QUERY_KEYS
    ]
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.casefold(), netloc, path, urlencode(query), ""))


def infer_source_type(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.casefold().rstrip("/")
    query = {
        (clean(key, 80).casefold(), clean(value, 80).casefold())
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    }
    return (
        "rss"
        if (
            path.endswith((".rss", ".xml", ".atom"))
            or re.search(r"(?:^|/)feed(?:/|$)", path)
            or ("format", "rss") in query
            or ("output", "rss") in query
        )
        else "listing-search"
    )


def _required_mapping(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ManualTrackingError(f"{label} 必须是 JSON 对象。")
    return copy.deepcopy(payload)


def _load_state_json(path: Path, label: str) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManualTrackingError(f"{label} 不存在，拒绝创建空白替代文件。") from exc
    except OSError as exc:
        raise ManualTrackingError(f"无法读取 {label}。") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManualTrackingError(f"{label} 不是有效 JSON，拒绝用空数据覆盖。") from exc


def load_state() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    tracking = _required_mapping(
        _load_state_json(TRACKING_PATH, "user_tracking.json"),
        "user_tracking.json",
    )
    inbox = _required_mapping(
        _load_state_json(
            INBOX_PATH,
            "tracking_capture_inbox.json",
        ),
        "tracking_capture_inbox.json",
    )
    intents = _required_mapping(
        _load_state_json(
            INTENTS_PATH,
            "tracking_intents.json",
        ),
        "tracking_intents.json",
    )
    for payload, label in (
        (tracking, "user_tracking.json"),
        (inbox, "tracking_capture_inbox.json"),
        (intents, "tracking_intents.json"),
    ):
        schema_version = payload.get("schemaVersion")
        if type(schema_version) is not int or schema_version != 1:
            raise ManualTrackingError(
                f"{label}.schemaVersion={schema_version} 尚不受此写入器支持，拒绝降级写入。"
            )
    for payload, field, label in (
        (tracking, "tracks", "user_tracking.json.tracks"),
        (tracking, "sources", "user_tracking.json.sources"),
        (inbox, "records", "tracking_capture_inbox.json.records"),
        (intents, "entities", "tracking_intents.json.entities"),
        (intents, "memberships", "tracking_intents.json.memberships"),
    ):
        if not isinstance(payload.get(field), list):
            raise ManualTrackingError(f"{label} 必须是数组。")
    return tracking, inbox, intents


def allowed_actors(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    raw: list[Any] = []
    for field in ("actors", "admins", "allowedActors"):
        if isinstance(payload.get(field), list):
            raw.extend(payload[field])
    return {clean(actor, 80).casefold() for actor in raw if clean(actor, 80)}


def check_actor(actor: Any, triggering_actor: Any) -> tuple[str, str]:
    actor_name = clean(actor, 80)
    triggering_name = clean(triggering_actor, 80) or actor_name
    allowlist = allowed_actors(load_json(ADMINS_PATH, {}))
    if not allowlist:
        raise ManualTrackingError("管理员 allowlist 为空或不存在，拒绝执行。")
    denied = [
        name
        for name in (actor_name, triggering_name)
        if not name or name.casefold() not in allowlist
    ]
    if denied:
        raise ManualTrackingError("当前 GitHub actor 或 triggering actor 不在管理员 allowlist。")
    return actor_name, triggering_name


def unique_append(values: list[Any], value: str, *, field: str = "") -> bool:
    identity = (
        (lambda item: signal_identity(item, field))
        if field
        else normalize_identity
    )
    key = identity(value)
    if any(identity(item) == key for item in values):
        return False
    values.append(value)
    return True


def _track_index(tracking: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_slug: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for raw in tracking.get("tracks", []):
        if not isinstance(raw, dict):
            continue
        slug = clean(raw.get("slug"), 80)
        name = clean(raw.get("name"), 80)
        if not slug or not name:
            continue
        by_slug[slug] = raw
        aliases[slug.casefold()] = slug
        aliases[name.casefold()] = slug
    return by_slug, aliases


def resolve_tracks(tracking: Mapping[str, Any], values: Iterable[str]) -> list[str]:
    by_slug, aliases = _track_index(tracking)
    result: list[str] = []
    for raw in values:
        value = clean(raw, 80)
        slug = aliases.get(value.casefold())
        if not slug or slug not in by_slug:
            raise ManualTrackingError(f"目标赛道不存在：{value}")
        if slug not in result:
            result.append(slug)
    return result


def _valid_keywords(raw: Any) -> list[str]:
    result: list[str] = []
    identities: set[str] = set()
    for item in split_values(raw, limit=30):
        if not is_single_value(item):
            raise ManualTrackingError(
                f"关键字必须是一项完整技术，不能包含复合列表或分隔符：{item}"
            )
        parsed = _validate_technology(item)
        identity = signal_identity(parsed, "keywords")
        if identity not in identities:
            result.append(parsed)
            identities.add(identity)
    return result


def _validate_technology(value: str) -> str:
    parsed = parse_tracking_keyword(value)
    if not parsed:
        raise ManualTrackingError(f"技术名称无效或过于宽泛：{value}")
    if parsed.casefold() in {item.casefold() for item in LOW_SIGNAL_TECHNOLOGIES}:
        raise ManualTrackingError(f"技术名称属于低信号地域或事件词：{value}")
    if re.fullmatch(r"(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])", parsed):
        raise ManualTrackingError(f"日期不能作为追踪技术：{value}")
    return parsed


def _validate_person(value: str) -> str:
    parsed = parse_person_label(value)
    if not parsed:
        raise ManualTrackingError("人物名称或账号格式无效。")
    display_name = clean(parsed.get("displayName"), 120)
    if display_name and PERSON_NOISE_RE.search(display_name):
        raise ManualTrackingError("人物名称包含职位、机构或技术术语，需要先做实体消歧。")
    if display_name:
        cjk_name = re.fullmatch(r"[\u3400-\u9fff·•]{2,10}", display_name)
        latin_words = display_name.split()
        latin_name = 2 <= len(latin_words) <= 5 and all(
            re.fullmatch(r"[A-Za-z][A-Za-z'.-]*", word) for word in latin_words
        )
        if not cjk_name and not latin_name:
            raise ManualTrackingError("人物名称不像完整姓名，需要提供规范姓名或账号。")
    return str(parsed["normalized"])


def _is_recommendation_value(field: str, value: str) -> bool:
    if not is_single_value(
        value, allow_legal_company_comma=field == "sampleCompanies"
    ):
        return False
    try:
        if field == "keywords":
            _validate_technology(value)
        elif field == "people":
            _validate_person(value)
        elif field == "sampleCompanies":
            normalized = clean(value, 160).casefold()
            if normalized in COMPANY_NAME_NOISE:
                return False
            if len(value) > 80 or len(value.split()) > 7:
                return False
            # Names without an explicit company cue remain eligible when they
            # look like a compact proper brand, but sentence fragments do not.
            if not COMPANY_NAME_CUE_RE.search(value):
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9&+.'-]{1,30}(?:\s+[A-Z0-9][A-Za-z0-9&+.'-]{0,30}){0,3}", value) is None:
                    if re.fullmatch(r"[\u3400-\u9fff]{2,12}", value) is None:
                        return False
    except ManualTrackingError:
        return False
    return True


def _normalized_input(args: argparse.Namespace, tracking: Mapping[str, Any]) -> dict[str, Any]:
    kind = clean(args.kind, 30).casefold()
    if kind not in KINDS:
        raise ManualTrackingError(f"kind 必须是以下之一：{', '.join(sorted(KINDS))}")
    name = clean(args.name, 160)
    _, known_track_aliases = _track_index(tracking)
    known_track_name = kind == "track" and name.casefold() in known_track_aliases
    if not is_single_value(
        name,
        allow_legal_company_comma=kind == "company",
        allow_spaced_slash=known_track_name,
    ):
        raise ManualTrackingError("名称必须是单一、完整的对象，不能粘贴列表或残缺括号。")
    if len(name) < 2:
        raise ManualTrackingError("名称至少需要两个有效字符。")

    keywords = _valid_keywords(args.keywords)
    if kind == "technology":
        name = _validate_technology(name)
        if not keywords:
            keywords = [name]
    elif kind == "person":
        name = _validate_person(name)
    elif kind == "track" and not keywords and not known_track_name:
        raise ManualTrackingError("新赛道必须至少提供一个有效关键字。")

    source_url = normalize_url(args.source_url, required=kind in {"company", "source"})
    category = clean(args.source_category, 30).casefold() or "media"
    if category not in SOURCE_CATEGORIES:
        raise ManualTrackingError("source-category 必须是 media/company/person。")
    region_key = clean(args.region, 30).casefold() or "global"
    if region_key not in REGIONS:
        raise ManualTrackingError("region 必须是 China/US/global（或中国/美国/全球）。")
    reasons = split_values(args.reasons, tracks=True, limit=12)
    if not reasons:
        raise ManualTrackingError("请至少选择一个受控追踪原因。")
    unknown_reasons = [reason for reason in reasons if reason not in ALLOWED_REASONS]
    if unknown_reasons:
        raise ManualTrackingError(
            "追踪原因必须使用历史七类枚举；未知值：" + "、".join(unknown_reasons)
        )
    note = clean(args.note, 800)
    if any(
        (ord(character) < 32 and character not in "\r\n\t")
        or ord(character) == 127
        for character in str(args.note or "")
    ):
        raise ManualTrackingError("备注包含不允许的控制字符。")

    target_values = split_values(args.tracks, tracks=True, limit=20)
    target_slugs = resolve_tracks(tracking, target_values)
    if kind != "track" and not target_slugs:
        raise ManualTrackingError("请至少指定一个现有目标赛道。")
    if kind == "track":
        # Existing track names are treated as an idempotent update.  Otherwise
        # generate a unique custom slug; explicit targets become graph links.
        existing_tracks, aliases = _track_index(tracking)
        track_slug = aliases.get(name.casefold(), "")
        if track_slug:
            name = clean(existing_tracks[track_slug].get("name"), 80)
        if not track_slug:
            base = slugify_track(name)
            existing = {clean(row.get("slug"), 80) for row in tracking.get("tracks", []) if isinstance(row, dict)}
            track_slug = base
            suffix = 2
            while track_slug in existing:
                track_slug = f"{base}-{suffix}"
                suffix += 1
    else:
        track_slug = ""

    return {
        "kind": kind,
        "name": name,
        "trackSlugs": target_slugs,
        "trackSlug": track_slug,
        "keywords": keywords,
        "sourceUrl": source_url,
        "sourceCategory": category,
        "sourceType": infer_source_type(source_url) if kind == "source" else "",
        "region": REGIONS[region_key],
        "reasons": reasons,
        "note": note,
    }


def _text_terms(value: Any) -> set[str]:
    text = clean(value, 1000).casefold()
    return {
        term
        for term in re.findall(r"[a-z0-9]{2,}|[\u3400-\u9fff]{2,}", text)
        if term
    }


def _add_recommendation(
    bucket: dict[str, dict[str, Any]],
    *,
    key: str,
    name: str,
    score: float,
    reason: str,
    **metadata: Any,
) -> None:
    if not key or not name:
        return
    row = bucket.setdefault(key, {"name": name, "score": 0.0, "reasons": [], **metadata})
    row["score"] = round(float(row["score"]) + score, 3)
    if reason and reason not in row["reasons"]:
        row["reasons"].append(reason)
    for metadata_key, metadata_value in metadata.items():
        if isinstance(metadata_value, list) and isinstance(row.get(metadata_key), list):
            for item in metadata_value:
                if item not in row[metadata_key]:
                    row[metadata_key].append(item)


def recommendations(
    tracking: Mapping[str, Any],
    intents: Mapping[str, Any],
    request: Mapping[str, Any],
    manual_profile: Mapping[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Rank related objects without granting automatic write permission."""

    track_rows, _ = _track_index(tracking)
    query_terms = _text_terms(" ".join([request["name"], *request["keywords"]]))
    selected = set(request["trackSlugs"])
    manual_tracks = (
        manual_profile.get("tracks", {})
        if isinstance(manual_profile, Mapping)
        and isinstance(manual_profile.get("tracks"), dict)
        else {}
    )
    company_lookup = company_index(load_json(COMPANY_REGISTRY_PATH, {}))
    people_lookup = people_index(load_json(PEOPLE_PATH, {}))

    def held_identities(slug: str, field: str) -> set[str]:
        row = manual_tracks.get(slug, {})
        held = row.get("held", {}) if isinstance(row, dict) else {}
        values = held.get(field, []) if isinstance(held, dict) else []
        return (
            {
                signal_identity(value, field)
                for value in values
                if signal_identity(value, field)
            }
            if isinstance(values, list)
            else set()
        )

    def is_held(slug: str, field: str, value: str) -> bool:
        if signal_identity(value, field) in held_identities(slug, field):
            return True
        return field == "sources" and source_host(value) in manual_held_source_hosts(
            dict(manual_profile or {}), slug
        )

    def canonical_runtime_value(
        field: str, value: str, track: Mapping[str, Any]
    ) -> str:
        """Only surface runtime relations backed by the canonical registries.

        The legacy flat arrays contain historical auto-discovery pollution.  A
        company/person therefore needs a unique canonical record whose sector
        agrees with the track.  Technologies have no registry yet, so only the
        protected core prefix is considered by the caller.
        """

        track_name = clean(track.get("name"), 80)
        if field == "sampleCompanies":
            rows = company_lookup.get(normalize_identity(value), [])
            if len(rows) != 1 or normalize_identity(rows[0].get("sector")) != normalize_identity(
                track_name
            ):
                return ""
            return clean(rows[0].get("name"), 160)
        if field == "people":
            parsed = parse_person_label(value)
            display_name = clean(parsed.get("displayName"), 160) if parsed else ""
            rows = people_lookup.get(normalize_identity(display_name), [])
            if len(rows) != 1:
                return ""
            sectors = rows[0].get("sectors", [])
            if not isinstance(sectors, list) or normalize_identity(track_name) not in {
                normalize_identity(sector) for sector in sectors
            }:
                return ""
            return clean(rows[0].get("name"), 160)
        return value
    if request["kind"] == "track" and request["trackSlug"] in track_rows:
        selected.add(request["trackSlug"])

    track_scores: dict[str, dict[str, Any]] = {}
    ranked_slugs: list[str] = []
    for slug, track in track_rows.items():
        terms = _text_terms(
            " ".join(
                [
                    clean(track.get("name"), 80),
                    *[clean(v, 120) for v in track.get("keywords", []) if clean(v, 120)],
                    *[clean(v, 120) for v in track.get("people", []) if clean(v, 120)],
                    *[clean(v, 120) for v in track.get("sampleCompanies", []) if clean(v, 120)],
                ]
            )
        )
        overlap = len(query_terms & terms)
        score = (100.0 if slug in selected else 0.0) + overlap * 8.0
        manual_row = manual_tracks.get(slug, {})
        approved = manual_row.get("approved", {}) if isinstance(manual_row, dict) else {}
        request_identity = normalize_identity(
            request["sourceUrl"] if request["kind"] == "source" else request["name"]
        )
        manual_values = {
            normalize_identity(value)
            for values in approved.values()
            if isinstance(values, list)
            for value in values
            if normalize_identity(value)
        } if isinstance(approved, dict) else set()
        manual_exact = bool(request_identity and request_identity in manual_values)
        if manual_exact:
            score += 18.0
        related_score = 0.0
        if isinstance(manual_row, dict):
            for related in manual_row.get("relatedTracks", []):
                if (
                    isinstance(related, dict)
                    and clean(related.get("slug"), 80) in selected
                ):
                    count = int(related.get("count") or 0)
                    # A single legacy bulk capture is too weak to establish a
                    # durable cross-track relation; require repeat evidence.
                    if count >= 2:
                        related_score += min(12.0, float(count) * 3.0)
        score += related_score
        if score:
            _add_recommendation(
                track_scores,
                key=slug,
                name=clean(track.get("name"), 80),
                score=score,
                reason="已明确选择" if slug in selected else "名称或关键字相关",
                slug=slug,
            )
            if manual_exact:
                _add_recommendation(
                    track_scores,
                    key=slug,
                    name=clean(track.get("name"), 80),
                    score=0,
                    reason="历史手动追踪已确认同一对象",
                    slug=slug,
                )
            if related_score:
                _add_recommendation(
                    track_scores,
                    key=slug,
                    name=clean(track.get("name"), 80),
                    score=0,
                    reason="历史手动追踪显示赛道关联",
                    slug=slug,
                )
    ranked_slugs = [
        row["slug"]
        for row in sorted(track_scores.values(), key=lambda row: (-row["score"], row["name"]))
    ][:8]
    if not ranked_slugs:
        ranked_slugs = list(track_rows)[:4]

    buckets: dict[str, dict[str, dict[str, Any]]] = {
        "technologies": {},
        "companies": {},
        "people": {},
        "sources": {},
    }
    for rank, slug in enumerate(ranked_slugs):
        track = track_rows[slug]
        weight = 12.0 if slug in selected else max(1.0, 6.0 - rank)
        for field, bucket_name in (
            ("keywords", "technologies"),
            ("sampleCompanies", "companies"),
            ("people", "people"),
        ):
            limit = 8 if field == "keywords" else 20
            for value in track.get(field, [])[:limit] if isinstance(track.get(field), list) else []:
                name = canonical_runtime_value(field, clean(value, 160), track)
                if not name or is_held(slug, field, name):
                    continue
                if not _is_recommendation_value(field, name):
                    continue
                if not name or normalize_identity(name) == normalize_identity(request["name"]):
                    continue
                _add_recommendation(
                    buckets[bucket_name],
                    key=f"{slug}:{signal_identity(name, field)}",
                    name=name,
                    score=weight,
                    reason=f"与「{clean(track.get('name'), 80)}」同属一个赛道",
                    trackSlugs=[slug],
                )
        manual_row = manual_tracks.get(slug, {})
        approved = manual_row.get("approved", {}) if isinstance(manual_row, dict) else {}
        trusted_manual = {
            signal_identity(row.get("value"), field)
            for row in manual_row.get("seedTerms", [])
            if isinstance(row, dict)
            and row.get("kind") == field
            and (row.get("pinned") is True or float(row.get("score") or 0) >= 2.0)
        }
        for field, bucket_name in (
            ("keywords", "technologies"),
            ("sampleCompanies", "companies"),
            ("people", "people"),
        ):
            values = approved.get(field, []) if isinstance(approved, dict) else []
            for value in values if isinstance(values, list) else []:
                name = clean(value, 160)
                if (
                    not _is_recommendation_value(field, name)
                    or signal_identity(name, field) not in trusted_manual
                    or is_held(slug, field, name)
                    or normalize_identity(name) == normalize_identity(request["name"])
                ):
                    continue
                _add_recommendation(
                    buckets[bucket_name],
                    key=f"{slug}:{signal_identity(name, field)}",
                    name=name,
                    score=5.0,
                    reason="历史手动追踪已确认",
                    trackSlugs=[slug],
                )
    track_names = {clean(track_rows[slug].get("name"), 80): slug for slug in ranked_slugs}
    for source in tracking.get("sources", []):
        if not isinstance(source, dict):
            continue
        sector = clean(source.get("sector"), 80)
        slug = track_names.get(sector)
        if not slug:
            continue
        name = clean(source.get("name"), 160)
        url = clean(source.get("url"), 1200)
        if (
            is_held(slug, "sources", url)
            or is_held(slug, "sources", name)
        ):
            continue
        key = f"{slug}:{normalize_identity(url) or normalize_identity(name)}"
        _add_recommendation(
            buckets["sources"],
            key=key,
            name=name,
            score=20.0 if slug in selected else 6.0,
            reason=f"已服务于「{sector}」",
            url=url,
            trackSlugs=[slug],
        )
        manual_row = manual_tracks.get(slug, {})
        affinity_rows = (
            manual_row.get("sourceHosts", []) if isinstance(manual_row, dict) else []
        )
        host = (urlsplit(url).hostname or "").casefold().removeprefix("www.") if url else ""
        affinity = sum(
            int(row.get("count") or 0)
            for row in affinity_rows
            if isinstance(row, dict)
            and clean(row.get("host"), 200).casefold().removeprefix("www.") == host
        )
        if affinity:
            _add_recommendation(
                buckets["sources"],
                key=key,
                name=name,
                score=min(12.0, float(affinity) * 2.0),
                reason="历史手动追踪反复采用该信源域名",
                url=url,
                trackSlugs=[slug],
            )

    # Durable manual edges are stronger than legacy flat arrays.  They can also
    # recommend source/actor/technology objects that are still in review.
    entities = {
        clean(row.get("id"), 240): row
        for row in intents.get("entities", [])
        if isinstance(row, dict) and clean(row.get("id"), 240)
    }
    for membership in intents.get("memberships", []):
        if not isinstance(membership, dict):
            continue
        membership_state = clean(membership.get("state"), 30)
        if membership_state in {"rejected", "expired"}:
            continue
        slug = clean(membership.get("trackId"), 160).removeprefix("track:")
        if slug not in ranked_slugs:
            continue
        entity = entities.get(clean(membership.get("entityId"), 240))
        if not entity:
            continue
        kind = clean(entity.get("kind"), 30)
        bucket_name = {
            "technology": "technologies",
            "company": "companies",
            "person": "people",
            "source": "sources",
        }.get(kind)
        if not bucket_name:
            continue
        name = clean(entity.get("name"), 160)
        if normalize_identity(name) == normalize_identity(request["name"]):
            continue
        _add_recommendation(
            buckets[bucket_name],
            key=f"{slug}:{clean(entity.get('id'), 240)}",
            name=name,
            score=12.0 if membership_state == "active" else 4.0,
            reason="人工追踪关系" if membership_state == "active" else "待审核的人工追踪关系",
            url=clean(entity.get("url"), 1200),
            trackSlugs=[slug],
        )

    output: dict[str, list[dict[str, Any]]] = {
        "tracks": sorted(track_scores.values(), key=lambda row: (-row["score"], row["name"]))[:8]
    }
    for bucket_name, rows in buckets.items():
        output[bucket_name] = sorted(
            rows.values(), key=lambda row: (-row["score"], row["name"])
        )[:12]
    return output


def _entity_id(
    request: Mapping[str, Any], resolution: Mapping[str, Any] | None = None
) -> str:
    if request["kind"] == "track":
        return f"track:{request['trackSlug']}"
    if request["kind"] == "technology":
        return stable_id(
            "technology", signal_identity(request["name"], "keywords")
        )
    expected_type = LEGACY_TYPE_BY_KIND.get(request["kind"], request["kind"])
    resolution_source = (
        clean(resolution.get("source"), 40) if isinstance(resolution, Mapping) else ""
    )
    canonical_sources = {
        "company": {"company-registry", "human-decision"},
        "person": {"people-registry", "human-decision"},
    }
    if (
        isinstance(resolution, Mapping)
        and clean(resolution.get("entityType"), 30) == expected_type
        and clean(resolution.get("targetId"), 240)
        and resolution_source in canonical_sources.get(request["kind"], {resolution_source})
    ):
        return clean(resolution.get("targetId"), 240)
    identity = request["sourceUrl"] if request["kind"] == "source" else request["name"]
    return stable_id(f"{request['kind']}", identity)


def _same_entity_identity(entity: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    if clean(entity.get("kind"), 30) != request["kind"]:
        return False
    if request["kind"] == "source":
        return bool(
            source_host(entity.get("url"))
            and clean(entity.get("url"), 1200).casefold().rstrip("/")
            == request["sourceUrl"].casefold().rstrip("/")
        )
    field = "keywords" if request["kind"] == "technology" else ""
    identity = (
        (lambda value: signal_identity(value, field))
        if field
        else normalize_identity
    )
    candidates = [entity.get("name")]
    if isinstance(entity.get("aliases"), list):
        candidates.extend(entity["aliases"])
    return bool(identity(request["name"])) and any(
        identity(value) == identity(request["name"]) for value in candidates
    )


def _merge_entity_rows(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    aliases = target.setdefault("aliases", [])
    if not isinstance(aliases, list):
        raise ManualTrackingError(f"实体 {target.get('id')} 的 aliases 不是数组。")
    source_name = clean(source.get("name"), 160)
    if source_name and normalize_identity(source_name) != normalize_identity(target.get("name")):
        unique_append(aliases, source_name)
    for alias in source.get("aliases", []) if isinstance(source.get("aliases"), list) else []:
        unique_append(aliases, clean(alias, 160))
    keywords = target.setdefault("keywords", [])
    if not isinstance(keywords, list):
        raise ManualTrackingError(f"实体 {target.get('id')} 的 keywords 不是数组。")
    for keyword in source.get("keywords", []) if isinstance(source.get("keywords"), list) else []:
        unique_append(keywords, clean(keyword, 120), field="keywords")
    for key, value in source.items():
        if key not in {"id", "name", "aliases", "keywords", "state"} and key not in target:
            target[key] = copy.deepcopy(value)
    states = {clean(target.get("state"), 30), clean(source.get("state"), 30)}
    if "active" in states:
        target["state"] = "active"
    elif "review" in states:
        target["state"] = "review"
    elif "rejected" in states:
        target["state"] = "rejected"


def _merge_membership_rows(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    origins = target.setdefault("origins", [])
    if not isinstance(origins, list):
        raise ManualTrackingError(f"关系 {target.get('id')} 的 origins 不是数组。")
    known = {
        clean(row.get("id"), 160)
        for row in origins
        if isinstance(row, dict) and clean(row.get("id"), 160)
    }
    for origin in source.get("origins", []) if isinstance(source.get("origins"), list) else []:
        origin_id = clean(origin.get("id"), 160) if isinstance(origin, dict) else ""
        if isinstance(origin, dict) and origin_id not in known:
            origins.append(copy.deepcopy(origin))
            known.add(origin_id)
    states = {clean(target.get("state"), 30), clean(source.get("state"), 30)}
    if "active" in states:
        target["state"] = "active"
    elif "review" in states:
        target["state"] = "review"
    elif "rejected" in states:
        target["state"] = "rejected"
    target["pinned"] = target.get("pinned") is True or source.get("pinned") is True
    confidence_rank = {"verified": 4, "high": 3, "medium": 2, "low": 1}
    confidences = [
        clean(target.get("confidence"), 30),
        clean(source.get("confidence"), 30),
    ]
    target["confidence"] = max(
        confidences, key=lambda value: confidence_rank.get(value, 0)
    )


def _migrate_provisional_entity(
    intents: dict[str, Any], request: Mapping[str, Any], canonical_id: str
) -> bool:
    """Collapse a review-time ID into the later canonical registry ID."""

    if request["kind"] not in {"company", "person"}:
        return False
    provisional_id = stable_id(request["kind"], request["name"])
    provisional_sources = {"explicit-type", "source-context", "unresolved"}
    entities = intents["entities"]
    matches = [
        row
        for row in entities
        if isinstance(row, dict)
        and clean(row.get("id"), 240) != canonical_id
        and clean(row.get("id"), 240) == provisional_id
        and clean(row.get("resolutionSource"), 40) in provisional_sources
        and _same_entity_identity(row, request)
    ]
    if not matches:
        return False
    legacy_ids = {clean(row.get("id"), 240) for row in matches}
    target = next(
        (
            row
            for row in entities
            if isinstance(row, dict) and clean(row.get("id"), 240) == canonical_id
        ),
        None,
    )
    if target is None:
        target = matches[0]
        target["id"] = canonical_id
        sources = matches[1:]
    else:
        sources = matches
    for source in sources:
        _merge_entity_rows(target, source)
        entities.remove(source)

    memberships = intents["memberships"]
    for membership in list(memberships):
        if (
            membership not in memberships
            or not isinstance(membership, dict)
            or clean(membership.get("entityId"), 240) not in legacy_ids
        ):
            continue
        membership["entityId"] = canonical_id
        membership["id"] = stable_id(
            "membership",
            membership.get("trackId"),
            canonical_id,
            membership.get("role"),
        )
        duplicate = next(
            (
                row
                for row in memberships
                if row is not membership
                and isinstance(row, dict)
                and clean(row.get("id"), 240) == membership["id"]
            ),
            None,
        )
        if duplicate is not None:
            _merge_membership_rows(duplicate, membership)
            memberships.remove(membership)
    return True


def _upsert_entity(
    intents: dict[str, Any],
    request: Mapping[str, Any],
    resolution: Mapping[str, Any],
    entity_id: str,
    actor: str,
    now: str,
    state: str,
) -> tuple[str, bool]:
    entities = intents["entities"]
    entity = next(
        (row for row in entities if isinstance(row, dict) and clean(row.get("id"), 240) == entity_id),
        None,
    )
    origin_material = json.dumps(
        {
            "actor": actor.casefold(),
            "entityId": entity_id,
            "requestedName": request["name"],
            "tracks": sorted(request["trackSlugs"]),
            "keywords": sorted(request["keywords"], key=str.casefold),
            "evidenceUrl": request["sourceUrl"],
            "sourceCategory": request["sourceCategory"],
            "sourceType": request["sourceType"],
            "region": request["region"],
            "reasons": sorted(request["reasons"]),
            "note": request["note"],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    entity_origin = {
        "id": stable_id("origin", origin_material),
        "origin": "manual",
        "actor": actor,
        "at": now,
        "evidenceUrl": request["sourceUrl"],
        "reasons": list(request["reasons"]),
        "note": request["note"],
    }
    expected_type = LEGACY_TYPE_BY_KIND.get(request["kind"], request["kind"])
    canonical_name = (
        clean(resolution.get("canonicalName"), 160)
        if clean(resolution.get("entityType"), 30) == expected_type
        else ""
    ) or request["name"]
    initial_aliases = (
        [request["name"]]
        if normalize_identity(canonical_name) != normalize_identity(request["name"])
        else []
    )
    if entity is None:
        entity = {
            "id": entity_id,
            "kind": request["kind"],
            "name": canonical_name,
            "aliases": initial_aliases,
            "keywords": list(request["keywords"]),
            "state": state,
            "resolutionSource": clean(resolution.get("source"), 40),
            "resolutionStatus": clean(resolution.get("status"), 30),
            "createdAt": now,
            "createdBy": actor,
        }
        if request["kind"] == "source":
            entity.update(
                {
                    "url": request["sourceUrl"],
                    "sourceType": request["sourceType"],
                    "sourceCategory": request["sourceCategory"],
                    "region": request["region"],
                }
            )
        if request["kind"] == "track":
            entity.update(
                {
                    "trackSlug": request["trackSlug"],
                    "relatedTrackIds": [f"track:{slug}" for slug in request["trackSlugs"]],
                    "origins": [entity_origin],
                }
            )
        entities.append(entity)
        return entity_id, True

    before = json.dumps(entity, sort_keys=True, ensure_ascii=False)
    old_name = clean(entity.get("name"), 160)
    if not old_name:
        entity["name"] = canonical_name
    aliases = entity.setdefault("aliases", [])
    if not isinstance(aliases, list):
        raise ManualTrackingError(f"实体 {entity_id} 的 aliases 不是数组。")
    for alias in initial_aliases:
        unique_append(aliases, alias)
    if old_name and normalize_identity(old_name) != normalize_identity(canonical_name):
        unique_append(aliases, old_name)
        entity["name"] = canonical_name
    keywords = entity.setdefault("keywords", [])
    if not isinstance(keywords, list):
        raise ManualTrackingError(f"实体 {entity_id} 的 keywords 不是数组。")
    for keyword in request["keywords"]:
        unique_append(keywords, keyword, field="keywords")
    entity["resolutionSource"] = clean(resolution.get("source"), 40)
    entity["resolutionStatus"] = clean(resolution.get("status"), 30)
    if state == "active" or (state == "rejected" and entity.get("state") != "active"):
        entity["state"] = state
    if request["kind"] == "source":
        old_name = clean(entity.get("name"), 160)
        if old_name and normalize_identity(old_name) != normalize_identity(request["name"]):
            unique_append(aliases, old_name)
        entity["name"] = request["name"]
        entity["url"] = request["sourceUrl"]
        entity["sourceType"] = request["sourceType"]
        entity["sourceCategory"] = request["sourceCategory"]
        entity["region"] = request["region"]
    if request["kind"] == "track":
        entity.setdefault("trackSlug", request["trackSlug"])
        related = entity.setdefault("relatedTrackIds", [])
        if not isinstance(related, list):
            raise ManualTrackingError(f"实体 {entity_id} 的 relatedTrackIds 不是数组。")
        for slug in request["trackSlugs"]:
            if f"track:{slug}" not in related:
                related.append(f"track:{slug}")
        origins = entity.setdefault("origins", [])
        if not isinstance(origins, list):
            raise ManualTrackingError(f"实体 {entity_id} 的 origins 不是数组。")
        if not any(
            isinstance(row, dict) and row.get("id") == entity_origin["id"] for row in origins
        ):
            origins.append(entity_origin)
    return entity_id, before != json.dumps(entity, sort_keys=True, ensure_ascii=False)


def _upsert_memberships(
    intents: dict[str, Any],
    request: Mapping[str, Any],
    entity_id: str,
    actor: str,
    now: str,
    state: str,
    confidence: str,
) -> bool:
    if request["kind"] == "track":
        return False
    changed = False
    role = ROLE_BY_KIND[request["kind"]]
    origin_material = json.dumps(
        {
            "actor": actor.casefold(),
            "entityId": entity_id,
            "requestedName": request["name"],
            "tracks": sorted(request["trackSlugs"]),
            "keywords": sorted(request["keywords"], key=str.casefold),
            "evidenceUrl": request["sourceUrl"],
            "sourceCategory": request["sourceCategory"],
            "sourceType": request["sourceType"],
            "region": request["region"],
            "reasons": sorted(request["reasons"]),
            "note": request["note"],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    origin_id = stable_id("origin", origin_material)
    for slug in request["trackSlugs"]:
        membership_id = stable_id("membership", f"track:{slug}", entity_id, role)
        membership = next(
            (
                row
                for row in intents["memberships"]
                if isinstance(row, dict) and clean(row.get("id"), 240) == membership_id
            ),
            None,
        )
        if membership is None:
            membership = {
                "id": membership_id,
                "trackId": f"track:{slug}",
                "entityId": entity_id,
                "role": role,
                "state": state,
                "pinned": True,
                "confidence": confidence,
                "origins": [],
            }
            intents["memberships"].append(membership)
            changed = True
        before = json.dumps(membership, sort_keys=True, ensure_ascii=False)
        promoted = state == "active" and membership.get("state") != "active"
        state_changed = state in {"active", "rejected"} and membership.get("state") != state
        if state == "active" or (
            state == "rejected" and membership.get("state") != "active"
        ):
            membership["state"] = state
        membership["pinned"] = True
        if promoted or state_changed or not clean(membership.get("confidence"), 30):
            membership["confidence"] = confidence
        origins = membership.setdefault("origins", [])
        if not isinstance(origins, list):
            raise ManualTrackingError(f"关系 {membership_id} 的 origins 不是数组。")
        if not any(isinstance(row, dict) and row.get("id") == origin_id for row in origins):
            origins.append(
                {
                    "id": origin_id,
                    "origin": "manual",
                    "actor": actor,
                    "at": now,
                    "evidenceUrl": request["sourceUrl"],
                    "reasons": list(request["reasons"]),
                    "note": request["note"],
                }
            )
        if before != json.dumps(membership, sort_keys=True, ensure_ascii=False):
            changed = True
    return changed


def _apply_v1(
    tracking: dict[str, Any], request: Mapping[str, Any], resolution: Mapping[str, Any]
) -> bool:
    changed = False
    by_slug, _ = _track_index(tracking)
    if request["kind"] == "track":
        slug = request["trackSlug"]
        track = by_slug.get(slug)
        if track is None:
            track = {
                "slug": slug,
                "name": request["name"],
                "enabled": True,
                "custom": True,
                "keywords": [],
                "people": [],
                "sampleCompanies": [],
            }
            tracking["tracks"].append(track)
            changed = True
        for field in ("keywords", "people", "sampleCompanies"):
            if not isinstance(track.setdefault(field, []), list):
                raise ManualTrackingError(f"赛道 {slug} 的 {field} 不是数组。")
        for keyword in request["keywords"]:
            changed = unique_append(track["keywords"], keyword, field="keywords") or changed
        return changed

    if request["kind"] == "source":
        for slug in request["trackSlugs"]:
            track = by_slug[slug]
            source_id = stable_id("source-manual", request["sourceUrl"], slug, length=16)
            existing_source = next(
                (
                    row
                    for row in tracking["sources"]
                    if isinstance(row, dict) and clean(row.get("id"), 100) == source_id
                ),
                None,
            )
            if existing_source is not None:
                before = json.dumps(existing_source, sort_keys=True, ensure_ascii=False)
                source_keywords = existing_source.setdefault("keywords", [])
                if not isinstance(source_keywords, list):
                    raise ManualTrackingError(f"信源 {source_id} 的 keywords 不是数组。")
                for keyword in request["keywords"]:
                    unique_append(source_keywords, keyword, field="keywords")
                existing_source.update(
                    {
                        "name": request["name"],
                        "url": request["sourceUrl"],
                        "sourceType": request["sourceType"],
                        "sourceCategory": request["sourceCategory"],
                        "region": request["region"],
                        "sector": clean(track.get("name"), 80),
                        "company": request["name"] if request["sourceCategory"] == "company" else "",
                        "enabled": True,
                    }
                )
                changed = changed or before != json.dumps(
                    existing_source, sort_keys=True, ensure_ascii=False
                )
                continue
            tracking["sources"].append(
                {
                    "id": source_id,
                    "name": request["name"],
                    "url": request["sourceUrl"],
                    "sourceType": request["sourceType"],
                    "sourceCategory": request["sourceCategory"],
                    "region": request["region"],
                    "sector": clean(track.get("name"), 80),
                    "company": request["name"] if request["sourceCategory"] == "company" else "",
                    "ticker": "",
                    "keywords": list(request["keywords"]),
                    "enabled": True,
                    "origin": "owner-entered",
                }
            )
            changed = True
        return changed

    # A registry-backed reclassification is valuable, but must never put a
    # person/topic into sampleCompanies or vice versa.  Unreviewed company
    # candidates also stay out of the runtime projection.
    if not _resolution_is_compatible(request, resolution):
        return False
    value = clean(resolution.get("canonicalName"), 160) or request["name"]
    field = FIELD_BY_KIND[request["kind"]]
    for slug in request["trackSlugs"]:
        values = by_slug[slug].setdefault(field, [])
        if not isinstance(values, list):
            raise ManualTrackingError(f"赛道 {slug} 的 {field} 不是数组。")
        changed = unique_append(values, value) or changed
    return changed


def _resolution_is_compatible(
    request: Mapping[str, Any], resolution: Mapping[str, Any]
) -> bool:
    if request["kind"] not in LEGACY_TYPE_BY_KIND:
        return True
    if (
        resolution.get("status") != "resolved"
        or resolution.get("entityType") != LEGACY_TYPE_BY_KIND[request["kind"]]
    ):
        return False
    if request["kind"] == "company":
        # Source-context guesses are useful proposals, not permission to
        # bypass the existing company registry/review trust gate.
        return clean(resolution.get("source"), 40) in {
            "company-registry",
            "human-decision",
        }
    return True


def _capture_record(
    inbox: dict[str, Any],
    tracking: Mapping[str, Any],
    request: Mapping[str, Any],
    resolution: Mapping[str, Any],
    actor: str,
    now: str,
) -> tuple[bool, bool]:
    if request["kind"] not in LEGACY_TYPE_BY_KIND:
        return False, False
    # The v1 inbox requires an article URL.  A provenance-only manual intent
    # remains fully represented in the graph, but is not emitted as an invalid
    # legacy record when no evidence URL was supplied.
    if not request["sourceUrl"]:
        return False, False
    by_slug, _ = _track_index(tracking)
    legacy_type = LEGACY_TYPE_BY_KIND[request["kind"]]
    compatible = _resolution_is_compatible(request, resolution)
    status = "applied" if compatible else "queued"
    canonical = clean(resolution.get("canonicalName"), 160) or request["name"]
    capture_id = stable_id(
        "capture",
        legacy_type,
        request["name"],
        request["sourceUrl"],
        "|".join(sorted(request["trackSlugs"])),
        length=16,
    )
    field = FIELD_BY_KIND[request["kind"]]
    def same_capture(row: Mapping[str, Any]) -> bool:
        source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
        raw_selection = clean(row.get("rawSelection"), 160) or clean(
            row.get("canonicalName"), 160
        )
        field_identity = "keywords" if legacy_type == "topic" else ""
        identity = (
            (lambda value: signal_identity(value, field_identity))
            if field_identity
            else normalize_identity
        )
        return (
            clean(row.get("entityType"), 30) == legacy_type
            and identity(raw_selection) == identity(request["name"])
            and clean(source.get("url"), 1200).casefold().rstrip("/")
            == request["sourceUrl"].casefold().rstrip("/")
            and sorted(clean(slug, 80) for slug in row.get("trackSlugs", []))
            == sorted(request["trackSlugs"])
        )

    existing_record = next(
        (
            row
            for row in inbox["records"]
            if isinstance(row, dict)
            and (clean(row.get("id"), 160) == capture_id or same_capture(row))
        ),
        None,
    )
    if existing_record is not None:
        before = json.dumps(existing_record, sort_keys=True, ensure_ascii=False)
        existing_record["id"] = capture_id
        existing_record["canonicalName"] = canonical
        existing_record["rawSelection"] = request["name"]
        existing_record["status"] = status
        existing_record["appliedTo"] = (
            [f"{slug}:{field}" for slug in request["trackSlugs"]]
            if compatible
            else []
        )
        existing_record["resolution"] = dict(resolution)
        changed = before != json.dumps(existing_record, sort_keys=True, ensure_ascii=False)
        return changed, status == "queued"
    source_title = request["name"] if request["sourceUrl"] else "GitHub 内部手动追踪"
    inbox["records"].insert(
        0,
        {
            "id": capture_id,
            "entityType": legacy_type,
            "canonicalName": canonical,
            "rawSelection": request["name"],
            "aliases": [],
            "trackSlugs": list(request["trackSlugs"]),
            "trackNames": [clean(by_slug[slug].get("name"), 80) for slug in request["trackSlugs"]],
            "source": {
                "articleId": "",
                "title": source_title,
                "url": request["sourceUrl"],
                "summary": request["note"],
                "sourceName": "GitHub Actions · 内部手动追踪",
                "channel": "manual-tracking",
                "channelLabel": "内部管理",
                "eventType": "人工追踪",
            },
            "capturedAt": now,
            "capturedBy": actor,
            "status": status,
            "appliedTo": [f"{slug}:{field}" for slug in request["trackSlugs"]] if compatible else [],
            "reasons": list(request["reasons"]),
            "note": request["note"],
            "resolution": dict(resolution),
        },
    )
    return True, status == "queued"


def apply_request(
    tracking: dict[str, Any],
    inbox: dict[str, Any],
    intents: dict[str, Any],
    request: Mapping[str, Any],
    actor: str,
    now: str,
) -> dict[str, Any]:
    if request["kind"] in LEGACY_TYPE_BY_KIND:
        resolution = asdict(
            resolve_entity(
                LEGACY_TYPE_BY_KIND[request["kind"]],
                request["name"],
                {
                    "title": request["name"],
                    "summary": request["note"],
                    "url": request["sourceUrl"],
                    "sourceName": "GitHub Actions · 内部手动追踪",
                },
                tracking_payload=tracking,
            )
        )
        if request["kind"] == "technology" and _resolution_is_compatible(
            request, resolution
        ):
            resolution.update(
                {
                    "targetId": _entity_id(request, resolution),
                    "confidence": "high",
                    "source": "authenticated-manual-intent",
                    "reason": "管理员显式确认该技术对象，并通过追踪关键字校验。",
                }
            )
        compatible = _resolution_is_compatible(request, resolution)
        if compatible:
            state = "active"
        elif resolution["status"] == "rejected":
            state = "rejected"
        else:
            state = "review"
        confidence = clean(resolution.get("confidence"), 30) or "low"
    else:
        resolution = {
            "status": "resolved",
            "requestedType": request["kind"],
            "entityType": request["kind"],
            "canonicalName": request["name"],
            "targetId": _entity_id(request),
            "confidence": "verified",
            "source": "authenticated-manual-intent",
            "reason": "由 allowlist 内的管理员显式提交。",
            "decisionKey": normalize_identity(request["name"]),
            "reclassified": False,
        }
        state = "active"
        confidence = "verified"

    entity_id = _entity_id(request, resolution)
    migration_changed = _migrate_provisional_entity(intents, request, entity_id)
    entity_id, entity_changed = _upsert_entity(
        intents, request, resolution, entity_id, actor, now, state
    )
    membership_changed = _upsert_memberships(
        intents, request, entity_id, actor, now, state, confidence
    )
    config_changed = _apply_v1(tracking, request, resolution)
    inbox_changed, review_queued = _capture_record(
        inbox, tracking, request, resolution, actor, now
    )
    intents_changed = migration_changed or entity_changed or membership_changed
    if intents_changed:
        try:
            schema_version = int(intents.get("schemaVersion", 1) or 1)
        except (TypeError, ValueError):
            schema_version = 1
        intents["schemaVersion"] = max(1, schema_version)
        intents["updatedAt"] = now
    if inbox_changed:
        inbox["schemaVersion"] = 1
        inbox["generatedAt"] = now
    return {
        "changed": config_changed or inbox_changed or intents_changed,
        "configChanged": config_changed,
        "inboxChanged": inbox_changed,
        "intentsChanged": intents_changed,
        "reviewQueued": review_queued or state == "review",
        "resolution": resolution,
        "entityId": entity_id,
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authenticated internal manual tracking")
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--kind", required=True, choices=sorted(KINDS))
    parser.add_argument("--name", required=True)
    parser.add_argument("--tracks", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--source-category", default="media")
    parser.add_argument("--region", default="global")
    parser.add_argument("--reasons", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--triggering-actor", default="")
    parser.add_argument("--now", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        actor, triggering_actor = check_actor(args.actor, args.triggering_actor)
        tracking, inbox, intents = load_state()
        request = _normalized_input(args, tracking)
        manual_profile = build_manual_feedback(inbox, intents, tracking)
        recs = recommendations(tracking, intents, request, manual_profile)
        result: dict[str, Any] = {
            "ok": True,
            "mode": args.mode,
            "actor": actor,
            "triggeringActor": triggering_actor,
            "request": request,
            "changed": False,
            "configChanged": False,
            "inboxChanged": False,
            "intentsChanged": False,
            "reviewQueued": False,
            "recommendations": recs,
            "manualFeedback": {
                "rawHistoryRecords": manual_profile.get("rawHistoryRecords", 0),
                "historyRecords": manual_profile.get("historyRecords", 0),
                "ignoredHistoryRecords": manual_profile.get("ignoredHistoryRecords", 0),
                "appliedSignals": manual_profile.get("appliedSignals", 0),
                "heldSignals": manual_profile.get("heldSignals", 0),
            },
        }
        if args.mode == "validate":
            preview = apply_request(
                copy.deepcopy(tracking),
                copy.deepcopy(inbox),
                copy.deepcopy(intents),
                request,
                actor,
                clean(args.now, 80) or "validation-preview",
            )
            result["preview"] = preview
        elif args.mode == "apply":
            now = clean(args.now, 80) or datetime.now(timezone.utc).isoformat(timespec="seconds")
            applied = apply_request(tracking, inbox, intents, request, actor, now)
            result.update(applied)
            # Write only the files that actually changed.  This keeps a repeated
            # dispatch a byte-for-byte no-op and narrows the workflow commit.
            if applied["configChanged"]:
                write_json_atomic(TRACKING_PATH, tracking)
            if applied["inboxChanged"]:
                write_json_atomic(INBOX_PATH, inbox)
            if applied["intentsChanged"]:
                write_json_atomic(INTENTS_PATH, intents)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ManualTrackingError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "changed": False,
                    "configChanged": False,
                    "inboxChanged": False,
                    "intentsChanged": False,
                    "reviewQueued": False,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
