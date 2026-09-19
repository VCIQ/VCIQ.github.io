#!/usr/bin/env python3
"""Resolve captured names into versioned company, person or topic entities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = ROOT / "config" / "entity_resolution_decisions.json"
COMPANY_REGISTRY_PATH = ROOT / "config" / "company_registry.json"
PEOPLE_PATH = ROOT / "public" / "data" / "people.json"
TRACKING_PATH = ROOT / "config" / "user_tracking.json"

ENTITY_TYPES = {"company", "person", "topic"}
STATUSES = {"resolved", "review", "rejected"}
CONFIDENCES = {"verified", "high", "medium", "low"}

COMPANY_CUES = re.compile(
    r"公司|企业|集团|平台|实验室|研究院|基金|资本|创投|startup|company|platform|labs?\b|"
    r"technolog(?:y|ies)\b|systems?\b|capital\b|ventures?\b|foundation\b|inc\.?\b|"
    r"corp(?:oration)?\b|ltd\.?\b",
    re.IGNORECASE,
)
PERSON_CUES = re.compile(
    r"创始人|联合创始人|CEO|CTO|CFO|董事|高管|教授|研究员|工程师|作者|大佬|先锋|先生|女士|"
    r"founder|executive|professor|researcher|engineer|author",
    re.IGNORECASE,
)
TOPIC_CUES = re.compile(
    r"编程语言|语言|框架|协议|标准|技术|算法|模型|芯片架构|数据库|开源项目|软件包|工具链|"
    r"programming language|framework|protocol|standard|technology|algorithm|model|library|package|toolchain",
    re.IGNORECASE,
)
COMPANY_NAME_CUES = re.compile(
    r"(?:\b(?:Inc|Corp|Corporation|Ltd|LLC|Labs|Technologies|Systems|Capital|Ventures|Foundation)\b|"
    r"公司|集团|资本|基金|科技)$",
    re.IGNORECASE,
)


def clean(value: Any, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean(value, 300).casefold())


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


@dataclass(frozen=True)
class Resolution:
    status: str
    requestedType: str
    entityType: str
    canonicalName: str
    targetId: str
    confidence: str
    source: str
    reason: str
    decisionKey: str
    reclassified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _result(
    *,
    requested_type: str,
    name: str,
    status: str,
    entity_type: str,
    canonical_name: str,
    target_id: str = "",
    confidence: str = "low",
    source: str = "unresolved",
    reason: str = "",
) -> Resolution:
    return Resolution(
        status=status,
        requestedType=requested_type,
        entityType=entity_type,
        canonicalName=canonical_name,
        targetId=target_id,
        confidence=confidence,
        source=source,
        reason=reason,
        decisionKey=normalize_identity(name),
        reclassified=entity_type != requested_type,
    )


def normalize_decision_manifest(payload: Any) -> dict[str, dict[str, Any]]:
    raw = payload.get("decisions", {}) if isinstance(payload, dict) else {}
    if not isinstance(raw, dict):
        return {}
    decisions: dict[str, dict[str, Any]] = {}
    for raw_key, value in raw.items():
        if not isinstance(value, dict):
            continue
        status = clean(value.get("status"), 20)
        requested_type = clean(value.get("requestedType"), 20) or "company"
        entity_type = clean(value.get("entityType"), 20) or requested_type
        canonical_name = clean(value.get("canonicalName"), 160)
        if (
            status not in STATUSES
            or requested_type not in ENTITY_TYPES
            or entity_type not in ENTITY_TYPES
            or not canonical_name
        ):
            continue
        row = {
            "status": status,
            "requestedType": requested_type,
            "entityType": entity_type,
            "canonicalName": canonical_name,
            "targetId": clean(value.get("targetId"), 240),
            "aliases": [clean(alias, 240) for alias in value.get("aliases", []) if clean(alias, 240)]
            if isinstance(value.get("aliases"), list)
            else [],
            "confidence": clean(value.get("confidence"), 20)
            if clean(value.get("confidence"), 20) in CONFIDENCES
            else ("verified" if status == "resolved" else "low"),
            "note": clean(value.get("note"), 600),
        }
        keys = {normalize_identity(raw_key), normalize_identity(canonical_name)}
        keys.update(normalize_identity(alias) for alias in row["aliases"])
        for key in keys:
            if key:
                decisions[key] = row
    return decisions


def _add_index(index: dict[str, list[dict[str, Any]]], alias: Any, value: dict[str, Any]) -> None:
    key = normalize_identity(alias)
    if not key:
        return
    rows = index.setdefault(key, [])
    if value not in rows:
        rows.append(value)


def company_index(payload: Any) -> dict[str, list[dict[str, Any]]]:
    companies = payload.get("companies", []) if isinstance(payload, dict) else []
    index: dict[str, list[dict[str, Any]]] = {}
    for company in companies if isinstance(companies, list) else []:
        if not isinstance(company, dict):
            continue
        for alias in [
            company.get("name"),
            company.get("englishName"),
            company.get("slug"),
            *(company.get("aliases", []) if isinstance(company.get("aliases"), list) else []),
        ]:
            _add_index(index, alias, company)
    return index


def people_index(payload: Any) -> dict[str, list[dict[str, Any]]]:
    people = payload.get("people", []) if isinstance(payload, dict) else []
    index: dict[str, list[dict[str, Any]]] = {}
    for person in people if isinstance(people, list) else []:
        if not isinstance(person, dict):
            continue
        for alias in [
            person.get("name"),
            person.get("englishName"),
            person.get("slug"),
            *(person.get("aliases", []) if isinstance(person.get("aliases"), list) else []),
        ]:
            _add_index(index, alias, person)
    return index


def topic_index(payload: Any) -> dict[str, list[str]]:
    tracks = payload.get("tracks", []) if isinstance(payload, dict) else []
    index: dict[str, list[str]] = {}
    for track in tracks if isinstance(tracks, list) else []:
        if not isinstance(track, dict):
            continue
        values = [track.get("name")]
        if isinstance(track.get("keywords"), list):
            values.extend(track["keywords"])
        for raw in values:
            value = clean(raw, 160)
            key = normalize_identity(value)
            if not key or not value:
                continue
            rows = index.setdefault(key, [])
            if value not in rows:
                rows.append(value)
    return index


def source_text(source: Mapping[str, Any] | None) -> str:
    if not source:
        return ""
    return clean(
        " ".join(
            clean(source.get(key), 1200)
            for key in ("title", "summary", "eventType", "sourceName", "channel", "channelLabel", "url")
        ),
        4000,
    )


def context_window(context: str, name: str) -> str:
    index = context.casefold().find(clean(name, 200).casefold())
    if index < 0:
        return ""
    return context[max(0, index - 90) : min(len(context), index + len(name) + 90)]


def resolve_entity(
    requested_type: str,
    name: str,
    source: Mapping[str, Any] | None = None,
    *,
    decisions_payload: Any | None = None,
    company_registry_payload: Any | None = None,
    people_payload: Any | None = None,
    tracking_payload: Any | None = None,
) -> Resolution:
    requested_type = requested_type if requested_type in ENTITY_TYPES else "company"
    name = clean(name, 160)
    key = normalize_identity(name)
    if not key:
        return _result(
            requested_type=requested_type,
            name=name,
            status="rejected",
            entity_type=requested_type,
            canonical_name=name,
            reason="名称为空或无法形成稳定实体键。",
        )

    decisions = normalize_decision_manifest(
        decisions_payload if decisions_payload is not None else load_json(DECISIONS_PATH, {})
    )
    reviewed = decisions.get(key)
    if reviewed:
        return _result(
            requested_type=requested_type,
            name=name,
            status=reviewed["status"],
            entity_type=reviewed["entityType"],
            canonical_name=reviewed["canonicalName"],
            target_id=reviewed["targetId"],
            confidence=reviewed["confidence"],
            source="human-decision",
            reason=reviewed["note"] or "复用版本化人工解析决定。",
        )

    companies = company_index(
        company_registry_payload
        if company_registry_payload is not None
        else load_json(COMPANY_REGISTRY_PATH, {})
    ).get(key, [])
    if len(companies) == 1:
        company = companies[0]
        return _result(
            requested_type=requested_type,
            name=name,
            status="resolved",
            entity_type="company",
            canonical_name=clean(company.get("name"), 160),
            target_id=f"company:{clean(company.get('slug'), 160)}",
            confidence="verified",
            source="company-registry",
            reason="名称唯一命中正式公司注册表。",
        )
    if len(companies) > 1:
        return _result(
            requested_type=requested_type,
            name=name,
            status="review",
            entity_type=requested_type,
            canonical_name=name,
            source="company-registry",
            reason="名称同时命中多个正式公司别名，需要人工消歧。",
        )

    persons = people_index(
        people_payload if people_payload is not None else load_json(PEOPLE_PATH, {})
    ).get(key, [])
    if len(persons) == 1:
        person = persons[0]
        return _result(
            requested_type=requested_type,
            name=name,
            status="resolved",
            entity_type="person",
            canonical_name=clean(person.get("name"), 160),
            target_id=f"person:{clean(person.get('slug') or person.get('id'), 160)}",
            confidence="high",
            source="people-registry",
            reason="名称唯一命中正式人物目录。",
        )
    if len(persons) > 1:
        return _result(
            requested_type=requested_type,
            name=name,
            status="review",
            entity_type=requested_type,
            canonical_name=name,
            source="people-registry",
            reason="名称同时命中多个人物别名，需要人工消歧。",
        )

    # Institution identity is distinct from operating-company publication.
    if requested_type == "company":
        try:
            from .institution_identity import lookup as institution_lookup
        except ImportError:
            from institution_identity import lookup as institution_lookup
        institutions = institution_lookup(name)
        if institutions:
            unique = len(institutions) == 1
            institution = institutions[0]
            return _result(
                requested_type=requested_type, name=name,
                status="resolved" if unique else "review", entity_type="company",
                canonical_name=institution["name"] if unique else name,
                target_id=institution["targetId"] if unique else "",
                confidence="verified" if unique else "low", source="institution-directory",
                reason=("名称唯一命中已核验投资机构目录；仅解析机构身份，不代表公司档案发布。"
                        if unique else "名称命中多个投资机构，需要人工消歧。"),
            )

    topics = topic_index(
        tracking_payload if tracking_payload is not None else load_json(TRACKING_PATH, {})
    ).get(key, [])
    if len(topics) == 1:
        return _result(
            requested_type=requested_type,
            name=name,
            status="resolved",
            entity_type="topic",
            canonical_name=topics[0],
            target_id=f"topic:{key}",
            confidence="high",
            source="tracking-taxonomy",
            reason="名称唯一命中已审核追踪赛道或关键词。",
        )

    if requested_type in {"person", "topic"}:
        label = "人物" if requested_type == "person" else "技术／主题"
        return _result(
            requested_type=requested_type,
            name=name,
            status="resolved",
            entity_type=requested_type,
            canonical_name=name,
            target_id=f"{requested_type}:{key}",
            confidence="medium",
            source="explicit-type",
            reason=f"管理员显式选择“{label}”，且未与正式目录冲突。",
        )

    context = source_text(source)
    local = context_window(context, name)
    if PERSON_CUES.search(local) or TOPIC_CUES.search(local):
        return _result(
            requested_type=requested_type,
            name=name,
            status="review",
            entity_type=requested_type,
            canonical_name=name,
            confidence="low",
            source="source-context",
            reason=(
                "原文邻近语境更像人物，不能直接作为公司写入。"
                if PERSON_CUES.search(local)
                else "原文邻近语境更像技术、项目或工具，不能直接作为公司写入。"
            ),
        )
    if COMPANY_CUES.search(local) or COMPANY_NAME_CUES.search(name):
        return _result(
            requested_type=requested_type,
            name=name,
            status="resolved",
            entity_type="company",
            canonical_name=name,
            target_id=f"company-candidate:{key}",
            confidence="medium",
            source="source-context",
            reason="原文邻近语境存在公司、企业或平台表述，可进入候选审核。",
        )

    return _result(
        requested_type=requested_type,
        name=name,
        status="review",
        entity_type=requested_type,
        canonical_name=name,
        confidence="low",
        source="unresolved",
        reason="缺少正式目录命中或明确公司语境，暂存到实体解析审核队列。",
    )
