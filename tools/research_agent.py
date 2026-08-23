#!/usr/bin/env python3
"""Generate a daily, evidence-linked investment research brief from VCIQ snapshots.

The agent is deliberately split into deterministic and model-assisted stages:

1. Build a compact, stable entity snapshot from the repository's public JSON.
2. Compare it with the previous agent snapshot (or bootstrap from a Git ref).
3. Rank material changes and construct an evidence package.
4. Ask an OpenAI-compatible SiliconFlow model for structured analysis.
5. Validate every model assertion against evidence IDs and publish static JSON.

The API key is read only from ``SILICONFLOW_API_KEY``. It is never serialized.
When the key is unavailable or the API fails, the command publishes a
transparent deterministic fallback instead of blocking the public data refresh.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "public" / "data" / "research_agent_daily.json"
DEFAULT_SNAPSHOT = ROOT / "public" / "data" / "research_agent_snapshot.json"
DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
DEFAULT_TIMEZONE = "Asia/Taipei"
SCHEMA_VERSION = 1
MAX_HISTORY = 30
MAX_CHANGES = 36
MAX_MODEL_CHANGES = 24
MAX_EVIDENCE_PER_CHANGE = 4

SOURCE_ONLY_FIELDS = {
    "source",
    "sources",
    "sourceUrls",
    "evidence",
    "materials",
}
IDENTITY_FIELDS = {
    "id",
    "slug",
    "name",
    "englishName",
    "aliases",
    "handles",
}
MAINTENANCE_FIELDS = {
    "warnings",
    "fallback",
    "discoveredVia",
    "listingRole",
    "trackingStatus",
    "reviewStatus",
}
UNUSABLE_EVIDENCE_GRADES = {
    "",
    "未分级",
    "unknown",
    "ungraded",
    "none",
    "n/a",
}

VOLATILE_KEYS = {
    "generatedAt",
    "updatedAt",
    "refreshedAt",
    "checkedAt",
    "lastCheckedAt",
    "lastAttemptAt",
    "completedAt",
    "archivedAt",
    "trackingEnrichedAt",
    "lastVerifiedAt",
    "lastSeenAt",
    "lastSuccessAt",
    "lastFailureAt",
    "runId",
    "commit",
    "refreshAudit",
    "firstSeenAt",
}

EVENT_DATASETS = {"institutionEvent", "listedDisclosure"}
ENTITY_LABELS = {
    "ventureCompany": "创业公司",
    "institution": "投资机构",
    "marketCompany": "上市公司",
    "person": "人物",
    "institutionEvent": "机构/资本事件",
    "listedDisclosure": "上市公司公告",
}


def _normalize_identity(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", str(value or "").casefold())


def _person_name_parts(value: Any) -> list[str]:
    """Return likely individual names contained in a malformed person label.

    Normal names can contain spaces, hyphens, middle dots, or an occasional
    comma (for example ``Last, First``). The bad ingestion rows seen in this
    dataset use Chinese list punctuation, repeated commas, or a trailing list
    separator. Those stronger signals are intentionally used to avoid rejecting
    legitimate international names.
    """

    name = re.sub(r"\s+", " ", str(value or "")).strip()
    if not name:
        return []
    strong_list_signal = bool(re.search(r"[、，；;\n]", name))
    repeated_ascii_commas = name.count(",") > 1 or name.endswith(",")
    if not strong_list_signal and not repeated_ascii_commas:
        return [name]
    return [
        part.strip(" \t、，,；;")
        for part in re.split(r"[、，,；;\n]+", name)
        if part.strip(" \t、，,；;")
    ]


def _is_multi_person_name(value: Any) -> bool:
    return len(_person_name_parts(value)) > 1 or bool(
        re.search(r"[、，,；;]\s*$", str(value or ""))
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _list_sort_key(value: Any) -> str:
    if isinstance(value, dict):
        for key in (
            "id",
            "slug",
            "url",
            "sourceUrl",
            "originalPdfUrl",
            "publishedAt",
            "date",
            "title",
            "name",
        ):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return f"{key}:{candidate}"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonicalize(value: Any) -> Any:
    """Remove execution noise and normalize unordered collections."""

    if isinstance(value, dict):
        return {
            str(key): canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in VOLATILE_KEYS and item not in (None, "")
        }
    if isinstance(value, list):
        normalized = [canonicalize(item) for item in value if item not in (None, "")]
        # Snapshot arrays are entity facts rather than editorial sequences.
        # Sorting prevents source-order changes from creating false research events.
        return sorted(normalized, key=_list_sort_key)
    if isinstance(value, float):
        return round(value, 6)
    return value


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _trim_text(value: Any, limit: int = 1200) -> Any:
    if not isinstance(value, str):
        return value
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _trim_collection(value: Any, limit: int) -> Any:
    if isinstance(value, list):
        return value[-limit:]
    return value


def compact_venture_company(record: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        "slug": record.get("slug"),
        "name": record.get("name"),
        "status": record.get("status"),
        "background": _trim_text(record.get("background")),
        "technology": _trim_text(record.get("technology")),
        "products": record.get("products", []),
        "team": record.get("team", []),
        "financing": record.get("financing", []),
        "capitalMarkets": record.get("capitalMarkets", []),
        "warnings": record.get("warnings", []),
        "sources": _trim_collection(record.get("sources", []), 24),
    }
    return canonicalize(fields)


def compact_institution(record: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        key: record.get(key)
        for key in (
            "id",
            "name",
            "aliases",
            "region",
            "type",
            "stages",
            "sectors",
            "profileSlug",
            "officialUrl",
            "officialDomains",
            "rankings",
            "reviewStatus",
        )
    }
    return canonicalize(fields)


def _latest_price_points(record: Mapping[str, Any], count: int = 2) -> list[Any]:
    history = record.get("priceHistory")
    if not isinstance(history, list):
        return []
    rows = [row for row in history if isinstance(row, dict)]
    rows.sort(key=lambda row: str(row.get("date", "")))
    return rows[-count:]


def compact_market_company(record: Mapping[str, Any]) -> dict[str, Any]:
    # Preserve all non-volatile market/profile fields but collapse the largest
    # time series to the latest two observations. This catches a daily move while
    # keeping the snapshot and model prompt bounded.
    fields = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key not in VOLATILE_KEYS and key != "priceHistory"
    }
    fields["priceHistory"] = _latest_price_points(record)
    if isinstance(fields.get("news"), list):
        fields["news"] = fields["news"][-12:]
    if isinstance(fields.get("sources"), list):
        fields["sources"] = fields["sources"][-16:]
    return canonicalize(fields)


def compact_person(record: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key not in VOLATILE_KEYS
    }
    for text_key in ("summary", "background"):
        fields[text_key] = _trim_text(fields.get(text_key), 1600)
    for list_key, limit in (
        ("speeches", 20),
        ("works", 20),
        ("books", 20),
        ("sources", 20),
    ):
        if isinstance(fields.get(list_key), list):
            fields[list_key] = fields[list_key][-limit:]
    return canonicalize(fields)


def compact_event(record: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key not in VOLATILE_KEYS
    }
    fields["summary"] = _trim_text(fields.get("summary"), 900)
    return canonicalize(fields)


def _mapping_rows(
    payload: Mapping[str, Any], key: str, compact: Any
) -> dict[str, dict[str, Any]]:
    raw = payload.get(key, {})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for entity_id, value in raw.items():
        if isinstance(value, dict):
            result[str(entity_id)] = compact(value)
    return result


def _list_rows(
    payload: Mapping[str, Any], key: str, compact: Any, id_keys: Iterable[str]
) -> dict[str, dict[str, Any]]:
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            continue
        entity_id = ""
        for id_key in id_keys:
            candidate = value.get(id_key)
            if candidate not in (None, ""):
                entity_id = str(candidate)
                break
        if not entity_id:
            entity_id = f"row-{index}-{stable_hash(value)}"
        result[entity_id] = compact(value)
    return result


def _person_record_score(record: Mapping[str, Any]) -> tuple[int, int, str]:
    sources = record.get("sources")
    source_count = len(sources) if isinstance(sources, list) else 0
    substantive_fields = sum(
        1
        for key, value in record.items()
        if key not in SOURCE_ONLY_FIELDS | IDENTITY_FIELDS and value not in (None, "", [], {})
    )
    # A deterministic final component makes selection independent of input order.
    return substantive_fields, source_count, stable_hash(record)


def _person_rows(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a person map while quarantining malformed and duplicate identities."""

    rows = _list_rows(payload, "people", compact_person, ("slug", "id", "name"))
    selected: dict[str, tuple[str, dict[str, Any]]] = {}
    for entity_id, record in rows.items():
        name = record.get("name")
        if not name or _is_multi_person_name(name):
            continue
        identity = _normalize_identity(name)
        if not identity:
            continue
        existing = selected.get(identity)
        if existing is None or _person_record_score(record) > _person_record_score(
            existing[1]
        ):
            selected[identity] = (entity_id, record)
    return {entity_id: record for entity_id, record in selected.values()}


def _flatten_disclosures(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    companies = payload.get("companies", {})
    if not isinstance(companies, dict):
        return {}
    events: dict[str, dict[str, Any]] = {}
    for company_slug, company in companies.items():
        if not isinstance(company, dict):
            continue
        raw_events = company.get("events", [])
        if not isinstance(raw_events, list):
            continue
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or f"{company_slug}-{stable_hash(event)}")
            row = dict(event)
            row.setdefault("companySlug", str(company_slug))
            row.setdefault("companyName", company.get("name"))
            events[event_id] = compact_event(row)
    return events


@dataclass(frozen=True)
class InputPayloads:
    venture_profiles: dict[str, Any]
    institution_entities: dict[str, Any]
    market_profiles: dict[str, Any]
    people: dict[str, Any]
    institution_events: dict[str, Any]
    listed_disclosures: dict[str, Any]


def load_input_payloads(root: Path) -> InputPayloads:
    data = root / "public" / "data"
    return InputPayloads(
        venture_profiles=load_json(data / "venture_profiles.json"),
        institution_entities=load_json(data / "institution_entities.json"),
        market_profiles=load_json(data / "market_profiles.json"),
        people=load_json(data / "people.json"),
        institution_events=load_json(data / "institution_events.json"),
        listed_disclosures=load_json(data / "listed_company_disclosures.json"),
    )


def build_snapshot(payloads: InputPayloads, generated_at: str) -> dict[str, Any]:
    datasets = {
        "ventureCompany": _mapping_rows(
            payloads.venture_profiles, "companies", compact_venture_company
        ),
        "institution": _list_rows(
            payloads.institution_entities,
            "entities",
            compact_institution,
            ("id", "profileSlug", "name"),
        ),
        "marketCompany": _mapping_rows(
            payloads.market_profiles, "profiles", compact_market_company
        ),
        "person": _person_rows(payloads.people),
        "institutionEvent": _list_rows(
            payloads.institution_events,
            "events",
            compact_event,
            ("id", "articleId", "title"),
        ),
        "listedDisclosure": _flatten_disclosures(payloads.listed_disclosures),
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "datasets": datasets,
        "stats": {name: len(rows) for name, rows in datasets.items()},
        "contentHash": stable_hash(datasets),
    }


def _git_json(root: Path, git_ref: str, relative_path: str) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{git_ref}:{relative_path}"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git show failed: {relative_path}")
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {git_ref}:{relative_path}")
    return value


def build_snapshot_from_git(root: Path, git_ref: str, generated_at: str) -> dict[str, Any]:
    data_prefix = "public/data"
    payloads = InputPayloads(
        venture_profiles=_git_json(root, git_ref, f"{data_prefix}/venture_profiles.json"),
        institution_entities=_git_json(root, git_ref, f"{data_prefix}/institution_entities.json"),
        market_profiles=_git_json(root, git_ref, f"{data_prefix}/market_profiles.json"),
        people=_git_json(root, git_ref, f"{data_prefix}/people.json"),
        institution_events=_git_json(root, git_ref, f"{data_prefix}/institution_events.json"),
        listed_disclosures=_git_json(
            root, git_ref, f"{data_prefix}/listed_company_disclosures.json"
        ),
    )
    return build_snapshot(payloads, generated_at)


def _entity_name(dataset: str, entity_id: str, record: Mapping[str, Any]) -> str:
    candidates: list[Any] = [
        record.get("name"),
        record.get("companyName"),
        record.get("title"),
        record.get("company", {}).get("name")
        if isinstance(record.get("company"), dict)
        else None,
        record.get("slug"),
        entity_id,
    ]
    for value in candidates:
        if value not in (None, ""):
            return str(value)
    return f"{ENTITY_LABELS.get(dataset, dataset)} {entity_id}"


def _top_level_changed_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    keys = sorted(set(before) | set(after))
    return [key for key in keys if canonicalize(before.get(key)) != canonicalize(after.get(key))]


def _short_value(value: Any, limit: int = 260) -> Any:
    if isinstance(value, str):
        return _trim_text(value, limit)
    if isinstance(value, list):
        compact = value[:6]
        if len(value) > 6:
            compact = [*compact, f"…另 {len(value) - 6} 项"]
        return compact
    if isinstance(value, dict):
        preferred = {
            key: value[key]
            for key in (
                "date",
                "close",
                "title",
                "name",
                "role",
                "documentType",
                "publishedAt",
                "status",
            )
            if key in value
        }
        return preferred or {key: value[key] for key in list(value)[:5]}
    return value


def _change_summary(
    dataset: str,
    action: str,
    name: str,
    changed_fields: list[str],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> str:
    label = ENTITY_LABELS.get(dataset, dataset)
    if action == "added":
        return f"新增{label}记录：{name}。"
    if action == "removed":
        return f"{label}记录移出当前快照：{name}。"
    field_text = "、".join(changed_fields[:6]) or "核心字段"
    suffix = "等" if len(changed_fields) > 6 else ""
    if dataset == "marketCompany" and "priceHistory" in changed_fields:
        points = after.get("priceHistory")
        if isinstance(points, list) and points and isinstance(points[-1], dict):
            latest = points[-1]
            date = latest.get("date", "最新交易日")
            close = latest.get("close")
            if close not in (None, ""):
                return f"{name} 更新至 {date}，最新收盘价为 {close}；同时变更字段：{field_text}{suffix}。"
    return f"{name} 的 {field_text}{suffix} 发生变化。"


def _evidence_grade(record: Mapping[str, Any]) -> str:
    source = record.get("source")
    if isinstance(source, dict):
        grade = source.get("evidenceGrade") or source.get("level")
        if grade:
            return str(grade)
    sources = record.get("sources")
    if isinstance(sources, list):
        for item in sources:
            if isinstance(item, dict) and (item.get("level") or item.get("evidenceGrade")):
                return str(item.get("level") or item.get("evidenceGrade"))
    return "未分级"


def _score_change(
    dataset: str,
    action: str,
    changed_fields: list[str],
    record: Mapping[str, Any],
) -> int:
    if dataset == "listedDisclosure":
        score = 96 if action == "added" else 72
        document_type = str(record.get("documentType") or "")
        if any(token in document_type for token in ("并购", "资产", "业绩", "监管", "诉讼")):
            score = min(100, score + 3)
        return score
    if dataset == "institutionEvent":
        grade = _evidence_grade(record).upper()
        base = {"A": 96, "B": 86, "C": 70, "D": 42}.get(grade[:1], 58)
        return base if action == "added" else max(38, base - 18)
    if dataset == "ventureCompany":
        weights = {
            "financing": 88,
            "capitalMarkets": 88,
            "team": 76,
            "products": 68,
            "technology": 68,
            "background": 55,
            "warnings": 48,
        }
        return max([weights.get(field, 52) for field in changed_fields] or [62])
    if dataset == "marketCompany":
        if any(field in changed_fields for field in ("company", "valuation", "financials")):
            return 72
        return 48
    if dataset == "person":
        if any(field in changed_fields for field in ("role", "organizations")):
            return 72
        if any(field in changed_fields for field in ("works", "books", "speeches")):
            return 60
        return 48
    if dataset == "institution":
        if any(field in changed_fields for field in ("rankings", "stages", "sectors")):
            return 64
        return 46
    return 50


def _classify_change(
    dataset: str,
    action: str,
    changed_fields: list[str],
    name: str,
) -> tuple[str, str]:
    fields = set(changed_fields)
    if fields and fields <= SOURCE_ONLY_FIELDS:
        return "source_refresh", "仅信源集合发生变化"
    if fields and fields <= IDENTITY_FIELDS | MAINTENANCE_FIELDS:
        return "entity_reconciliation", "仅实体标识或治理字段发生变化"

    if dataset == "person":
        if _is_multi_person_name(name):
            return "entity_reconciliation", "人物名称包含多个身份，已隔离"
        if action in {"added", "removed"}:
            return "data_maintenance", "人物档案增删不等同于现实人物事件"
        if fields & {"role", "organizations"}:
            return "external_event", "人物任职或组织关系发生可核验变化"
        return "data_maintenance", "人物资料补录或字段整理"

    if action == "removed":
        return "data_maintenance", "实体移出快照不代表现实事实撤销"
    if dataset in EVENT_DATASETS:
        if action == "added":
            return "external_event", "新增事件型记录"
        return "data_maintenance", "既有事件记录字段修订"
    if action == "added":
        return "data_maintenance", "新增实体档案不等同于新增现实事件"

    external_fields = {
        "ventureCompany": {
            "status",
            "technology",
            "products",
            "team",
            "financing",
            "capitalMarkets",
        },
        "marketCompany": {
            "priceHistory",
            "news",
            "financials",
            "valuation",
            "company",
        },
        "institution": {"rankings", "stages", "sectors"},
    }
    if fields & external_fields.get(dataset, set()):
        return "external_event", "包含可形成外部事实主张的字段变化"
    if fields & SOURCE_ONLY_FIELDS:
        return "source_refresh", "信源更新伴随非研究字段变化"
    return "data_maintenance", "结构化资料维护"


def _mark_person_reconciliations(
    changes: list[dict[str, Any]],
    previous_rows: Mapping[str, Any],
    current_rows: Mapping[str, Any],
) -> None:
    person_changes = [row for row in changes if row.get("dataset") == "person"]
    added = [row for row in person_changes if row.get("action") == "added"]
    removed = [row for row in person_changes if row.get("action") == "removed"]

    added_by_name: dict[str, list[dict[str, Any]]] = {}
    removed_by_name: dict[str, list[dict[str, Any]]] = {}
    categorized = [
        *((item, added_by_name) for item in added),
        *((item, removed_by_name) for item in removed),
    ]
    for row, target in categorized:
        key = _normalize_identity(row.get("entityName"))
        if key:
            target.setdefault(key, []).append(row)

    def mark(row: dict[str, Any], reason: str) -> None:
        row["changeType"] = "entity_reconciliation"
        row["classificationReason"] = reason
        row["isResearchCandidate"] = False

    # A stable person changing slug/id appears as a same-run remove/add pair.
    for identity in set(added_by_name) & set(removed_by_name):
        for row in added_by_name[identity] + removed_by_name[identity]:
            mark(row, "同一人物在本轮以不同实体标识增删")

    # Legacy corrupt rows may contain several people in one name and be replaced
    # by clean individual rows. Neither side is a publishable person event.
    for old in removed:
        parts = {
            _normalize_identity(part)
            for part in _person_name_parts(old.get("entityName"))
            if _normalize_identity(part)
        }
        matches = parts & set(added_by_name)
        if len(parts) > 1 or _is_multi_person_name(old.get("entityName")):
            mark(old, "多人物串联记录被拆分或移除")
            for identity in matches:
                for new in added_by_name[identity]:
                    mark(new, "由多人物串联记录拆分出的实体")

    # Defensive handling for legacy snapshots produced before duplicate
    # quarantine was introduced.
    for rows, side in ((previous_rows, "旧快照"), (current_rows, "新快照")):
        identities: dict[str, list[str]] = {}
        for entity_id, record in rows.items():
            if not isinstance(record, dict):
                continue
            identity = _normalize_identity(record.get("name"))
            if identity:
                identities.setdefault(identity, []).append(str(entity_id))
        duplicate_ids = {
            entity_id
            for entity_ids in identities.values()
            if len(entity_ids) > 1
            for entity_id in entity_ids
        }
        for row in person_changes:
            if str(row.get("entityId")) in duplicate_ids:
                mark(row, f"{side}存在重复人物实体")


def diff_snapshots(previous: Mapping[str, Any], current: Mapping[str, Any]) -> list[dict[str, Any]]:
    previous_datasets = previous.get("datasets", {})
    current_datasets = current.get("datasets", {})
    if not isinstance(previous_datasets, dict) or not isinstance(current_datasets, dict):
        return []

    changes: list[dict[str, Any]] = []
    for dataset in sorted(set(previous_datasets) | set(current_datasets)):
        before_rows = previous_datasets.get(dataset, {})
        after_rows = current_datasets.get(dataset, {})
        if not isinstance(before_rows, dict) or not isinstance(after_rows, dict):
            continue

        before_ids = set(before_rows)
        after_ids = set(after_rows)
        for entity_id in sorted(after_ids - before_ids):
            after = after_rows[entity_id]
            if not isinstance(after, dict):
                continue
            name = _entity_name(dataset, entity_id, after)
            score = _score_change(dataset, "added", list(after), after)
            changes.append(
                {
                    "id": f"chg-{stable_hash([dataset, entity_id, 'added', after])}",
                    "dataset": dataset,
                    "entityType": ENTITY_LABELS.get(dataset, dataset),
                    "entityId": entity_id,
                    "entityName": name,
                    "action": "added",
                    "changedFields": list(after)[:12],
                    "summary": _change_summary(dataset, "added", name, [], {}, after),
                    "importance": score,
                    "before": None,
                    "after": {key: _short_value(value) for key, value in list(after.items())[:10]},
                    "record": after,
                }
            )

        # Event removals commonly reflect rolling retention, not a reversed fact.
        if dataset not in EVENT_DATASETS:
            for entity_id in sorted(before_ids - after_ids):
                before = before_rows[entity_id]
                if not isinstance(before, dict):
                    continue
                name = _entity_name(dataset, entity_id, before)
                score = _score_change(dataset, "removed", list(before), before)
                changes.append(
                    {
                        "id": f"chg-{stable_hash([dataset, entity_id, 'removed', before])}",
                        "dataset": dataset,
                        "entityType": ENTITY_LABELS.get(dataset, dataset),
                        "entityId": entity_id,
                        "entityName": name,
                        "action": "removed",
                        "changedFields": list(before)[:12],
                        "summary": _change_summary(dataset, "removed", name, [], before, {}),
                        "importance": score,
                        "before": {key: _short_value(value) for key, value in list(before.items())[:10]},
                        "after": None,
                        "record": before,
                    }
                )

        for entity_id in sorted(before_ids & after_ids):
            before = before_rows[entity_id]
            after = after_rows[entity_id]
            if not isinstance(before, dict) or not isinstance(after, dict):
                continue
            if stable_hash(before) == stable_hash(after):
                continue
            changed_fields = _top_level_changed_fields(before, after)
            name = _entity_name(dataset, entity_id, after)
            score = _score_change(dataset, "updated", changed_fields, after)
            changes.append(
                {
                    "id": f"chg-{stable_hash([dataset, entity_id, changed_fields, after])}",
                    "dataset": dataset,
                    "entityType": ENTITY_LABELS.get(dataset, dataset),
                    "entityId": entity_id,
                    "entityName": name,
                    "action": "updated",
                    "changedFields": changed_fields,
                    "summary": _change_summary(
                        dataset, "updated", name, changed_fields, before, after
                    ),
                    "importance": score,
                    "before": {key: _short_value(before.get(key)) for key in changed_fields[:8]},
                    "after": {key: _short_value(after.get(key)) for key in changed_fields[:8]},
                    "record": after,
                }
            )

    for change in changes:
        change_type, reason = _classify_change(
            str(change.get("dataset", "")),
            str(change.get("action", "")),
            [str(field) for field in change.get("changedFields", [])],
            str(change.get("entityName", "")),
        )
        change["changeType"] = change_type
        change["classificationReason"] = reason
        change["isResearchCandidate"] = change_type == "external_event"

    previous_people = previous_datasets.get("person", {})
    current_people = current_datasets.get("person", {})
    _mark_person_reconciliations(
        changes,
        previous_people if isinstance(previous_people, dict) else {},
        current_people if isinstance(current_people, dict) else {},
    )

    changes.sort(
        key=lambda item: (
            item.get("changeType") == "external_event",
            int(item.get("importance", 0)),
            str(item.get("dataset", "")),
            str(item.get("entityName", "")),
        ),
        reverse=True,
    )
    return changes


def aggregate_external_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse same-company, same-day disclosures into one research event."""

    disclosure_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for change in changes:
        record = change.get("record")
        if (
            change.get("changeType") == "external_event"
            and change.get("dataset") == "listedDisclosure"
            and change.get("action") == "added"
            and isinstance(record, dict)
        ):
            company_key = str(
                record.get("companySlug") or change.get("entityName") or ""
            )
            published_at = str(record.get("publishedAt") or "")[:10]
            disclosure_groups.setdefault((company_key, published_at), []).append(change)
        else:
            passthrough.append(change)

    aggregated: list[dict[str, Any]] = list(passthrough)
    for (company_key, published_at), rows in disclosure_groups.items():
        if len(rows) == 1:
            aggregated.append(rows[0])
            continue
        first = rows[0]
        documents = [
            row["record"] for row in rows if isinstance(row.get("record"), dict)
        ]
        document_types = sorted(
            {
                str(document.get("documentType"))
                for document in documents
                if document.get("documentType")
            }
        )
        titles = [
            str(document.get("title"))
            for document in documents
            if document.get("title")
        ]
        entity_name = str(first.get("entityName") or company_key)
        date_text = f"（{published_at}）" if published_at else ""
        summary = f"{entity_name}{date_text}新增 {len(documents)} 份上市公司公告。"
        record = {
            "companySlug": company_key,
            "companyName": entity_name,
            "publishedAt": published_at,
            "documentCount": len(documents),
            "documentTypes": document_types,
            "documents": documents,
        }
        member_ids = [str(row["id"]) for row in rows]
        digest = stable_hash(
            ["listedDisclosureDigest", company_key, published_at, member_ids]
        )
        aggregated.append(
            {
                "id": f"chg-{digest}",
                "dataset": "listedDisclosure",
                "entityType": ENTITY_LABELS["listedDisclosure"],
                "entityId": (
                    f"disclosure-digest-{company_key}-"
                    f"{published_at or stable_hash(titles)}"
                ),
                "entityName": entity_name,
                "action": "added",
                "changedFields": [
                    "documents",
                    "documentTypes",
                    "publishedAt",
                ],
                "summary": summary,
                "importance": max(int(row.get("importance", 0)) for row in rows),
                "before": None,
                "after": {
                    "documentCount": len(documents),
                    "documentTypes": document_types,
                    "publishedAt": published_at,
                    "titles": titles,
                },
                "record": record,
                "changeType": "external_event",
                "classificationReason": "同一公司同日公告已聚合为一个研究事件",
                "isResearchCandidate": True,
                "groupSize": len(rows),
                "memberChangeIds": member_ids,
            }
        )

    aggregated.sort(
        key=lambda item: (
            item.get("changeType") == "external_event",
            int(item.get("importance", 0)),
            str(item.get("dataset", "")),
            str(item.get("entityName", "")),
        ),
        reverse=True,
    )
    return aggregated


def _walk_source_candidates(
    value: Any,
    path: tuple[str, ...] = (),
    inherited_title: str = "",
    inherited_date: str = "",
    inherited_grade: str = "",
) -> Iterable[dict[str, Any]]:
    """Yield source-like rows, including malformed rows for quality reporting."""

    if isinstance(value, dict):
        title = str(value.get("title") or inherited_title or "").strip()
        published_at = str(
            value.get("publishedAt") or value.get("date") or inherited_date or ""
        ).strip()
        grade = str(
            value.get("evidenceGrade")
            or value.get("level")
            or value.get("evidenceLabel")
            or inherited_grade
            or "未分级"
        ).strip()
        has_url_key = any(
            key in value for key in ("url", "sourceUrl", "originalPdfUrl")
        )
        source_container = any(
            part in {"source", "sources", "evidence"} for part in path
        )
        if has_url_key or source_container:
            raw_url = (
                value.get("url")
                or value.get("sourceUrl")
                or value.get("originalPdfUrl")
                or ""
            )
            yield {
                "sourceName": str(
                    value.get("name")
                    or value.get("source")
                    or value.get("publisher")
                    or value.get("platform")
                    or "原始信源"
                ),
                "title": title,
                "url": str(raw_url).strip(),
                "publishedAt": published_at,
                "evidenceGrade": grade,
                "_path": list(path),
                "_section": str(value.get("section") or "").strip(),
            }
        for key, item in value.items():
            yield from _walk_source_candidates(
                item,
                (*path, str(key)),
                title,
                published_at,
                grade if grade != "未分级" else inherited_grade,
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_source_candidates(
                item,
                (*path, str(index)),
                inherited_title,
                inherited_date,
                inherited_grade,
            )
    elif isinstance(value, str) and value.strip().startswith(("http://", "https://")):
        yield {
            "sourceName": "原始信源",
            "title": inherited_title,
            "url": value.strip(),
            "publishedAt": inherited_date,
            "evidenceGrade": inherited_grade or "未分级",
            "_path": list(path),
            "_section": "",
        }


def _parse_evidence_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _evidence_quality_issues(
    candidate: Mapping[str, Any], as_of: datetime | None
) -> list[str]:
    issues: list[str] = []
    url = str(candidate.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        issues.append("missing_or_invalid_url")
    if not str(candidate.get("title") or "").strip():
        issues.append("missing_title")
    grade = str(candidate.get("evidenceGrade") or "").strip().casefold()
    if grade in UNUSABLE_EVIDENCE_GRADES:
        issues.append("ungraded")
    published_at = _parse_evidence_datetime(candidate.get("publishedAt"))
    if published_at is None:
        issues.append("missing_published_at")
    if as_of is not None and published_at is not None and published_at > as_of:
        issues.append("future_published_at")
    return issues


def _candidate_claim_fields(
    candidate: Mapping[str, Any],
    changed_fields: Iterable[str],
    dataset: str,
    action: str,
) -> list[str]:
    fields = [str(field) for field in changed_fields]
    meaningful = [
        field
        for field in fields
        if field not in SOURCE_ONLY_FIELDS | IDENTITY_FIELDS | MAINTENANCE_FIELDS
    ]
    section = str(candidate.get("_section") or "")
    path = [str(part) for part in candidate.get("_path", [])]
    bound: list[str] = []
    if section and section in fields:
        bound.append(section)
    for part in path:
        if part in meaningful and part not in bound:
            bound.append(part)
    if dataset in EVENT_DATASETS and action == "added" and not bound:
        event_fields = {
            "title",
            "summary",
            "documentType",
            "publishedAt",
            "date",
            "documents",
            "documentTypes",
        }
        bound.extend(field for field in meaningful if field in event_fields)
    return bound


def extract_sources(
    record: Mapping[str, Any],
    limit: int = MAX_EVIDENCE_PER_CHANGE,
    *,
    changed_fields: Iterable[str] = (),
    dataset: str = "",
    action: str = "updated",
    as_of: datetime | str | None = None,
) -> list[dict[str, Any]]:
    as_of_datetime = (
        as_of
        if isinstance(as_of, datetime)
        else _parse_evidence_datetime(as_of) if as_of is not None else utc_now()
    )
    candidates: dict[str, dict[str, Any]] = {}
    for index, raw_candidate in enumerate(_walk_source_candidates(record)):
        candidate = dict(raw_candidate)
        candidate["claimFields"] = _candidate_claim_fields(
            candidate, changed_fields, dataset, action
        )
        candidate["qualityIssues"] = _evidence_quality_issues(
            candidate, as_of_datetime
        )
        candidate["qualityStatus"] = (
            "passed" if not candidate["qualityIssues"] else "rejected"
        )
        candidate["supportStatus"] = (
            "supports"
            if candidate["qualityStatus"] == "passed" and candidate["claimFields"]
            else "insufficient"
        )
        url = str(candidate.get("url") or "")
        dedupe_key = url or f"missing-url-{index}-{stable_hash(candidate)}"
        existing = candidates.get(dedupe_key)
        if existing is None:
            candidates[dedupe_key] = candidate
            continue
        merged_fields = sorted(
            set(existing.get("claimFields", [])) | set(candidate["claimFields"])
        )
        preferred = min(
            (existing, candidate),
            key=lambda item: (
                len(item.get("qualityIssues", [])),
                -len(str(item.get("title") or "")),
            ),
        )
        preferred = dict(preferred)
        preferred["claimFields"] = merged_fields
        preferred["supportStatus"] = (
            "supports"
            if preferred.get("qualityStatus") == "passed" and merged_fields
            else "insufficient"
        )
        candidates[dedupe_key] = preferred

    ordered = sorted(
        candidates.values(),
        key=lambda item: (
            item.get("supportStatus") != "supports",
            item.get("qualityStatus") != "passed",
            len(item.get("qualityIssues", [])),
            str(item.get("url", "")),
        ),
    )
    return ordered[:limit]


def build_evidence_package(
    changes: list[dict[str, Any]],
    *,
    as_of: datetime | str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public_changes: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    evidence_counter = 1

    for change in changes:
        sources = extract_sources(
            change.get("record", {}),
            changed_fields=change.get("changedFields", []),
            dataset=str(change.get("dataset", "")),
            action=str(change.get("action", "")),
            as_of=as_of,
        )
        evidence_ids: list[str] = []
        if not sources:
            sources = [
                {
                    "sourceName": "VCIQ 结构化实体快照",
                    "title": "仓库内结构化字段变化",
                    "url": "",
                    "publishedAt": "",
                    "evidenceGrade": "内部差异证据",
                    "claimFields": [],
                    "qualityIssues": ["no_external_evidence"],
                    "qualityStatus": "rejected",
                    "supportStatus": "insufficient",
                }
            ]
        source_rows: list[tuple[str, dict[str, Any]]] = []
        for source in sources:
            evidence_id = f"E{evidence_counter:03d}"
            evidence_counter += 1
            evidence_ids.append(evidence_id)
            source_rows.append((evidence_id, source))

        supported_fields = sorted(
            {
                field
                for _, source in source_rows
                if source.get("supportStatus") == "supports"
                for field in source.get("claimFields", [])
            }
        )
        raw_claim_fields = [
            str(field)
            for field in change.get("changedFields", [])
            if str(field)
            not in SOURCE_ONLY_FIELDS | IDENTITY_FIELDS | MAINTENANCE_FIELDS
        ]
        public_summary = str(change.get("summary", ""))
        if change.get("action") == "updated" and supported_fields:
            public_summary = _change_summary(
                str(change.get("dataset", "")),
                "updated",
                str(change.get("entityName", "")),
                supported_fields,
                change.get("before") if isinstance(change.get("before"), dict) else {},
                change.get("after") if isinstance(change.get("after"), dict) else {},
            )

        for evidence_id, source in source_rows:
            public_source = {
                key: value for key, value in source.items() if not key.startswith("_")
            }
            evidence.append(
                {
                    "id": evidence_id,
                    "changeId": change["id"],
                    "entityName": change["entityName"],
                    "claim": public_summary,
                    **public_source,
                }
            )

        claim_bindings = []
        for field in supported_fields:
            claim_bindings.append(
                {
                    "field": field,
                    "before": change.get("before", {}).get(field)
                    if isinstance(change.get("before"), dict)
                    else None,
                    "after": change.get("after", {}).get(field)
                    if isinstance(change.get("after"), dict)
                    else None,
                    "evidenceIds": [
                        evidence_id
                        for evidence_id, source in source_rows
                        if source.get("supportStatus") == "supports"
                        and field in source.get("claimFields", [])
                    ],
                }
            )
        supporting_ids = [
            evidence_id
            for evidence_id, source in source_rows
            if source.get("supportStatus") == "supports"
        ]
        public_change = {
                key: value
                for key, value in change.items()
                if key != "record"
            } | {
                "summary": public_summary,
                "claimFields": supported_fields,
                "claimBindings": claim_bindings,
                "unsupportedClaimFields": sorted(
                    set(raw_claim_fields) - set(supported_fields)
                ),
                "evidenceIds": evidence_ids,
                "supportingEvidenceIds": supporting_ids,
                "evidenceQuality": {
                    "status": "passed" if supporting_ids else "insufficient",
                    "supporting": len(supporting_ids),
                    "total": len(source_rows),
                },
                "eligibleForKeyDevelopment": bool(
                    change.get("changeType") == "external_event" and supporting_ids
                ),
            }
        public_changes.append(public_change)
    return public_changes, evidence


def _model_prompt(changes: list[dict[str, Any]], evidence: list[dict[str, Any]], as_of: str) -> str:
    package = {
        "asOf": as_of,
        "instructions": {
            "language": "简体中文",
            "scope": "仅基于证据包分析，不补充外部事实",
            "discipline": [
                "事实、推断和待验证事项必须分开表达",
                "每个判断必须引用至少一个 evidenceIds 中的证据编号",
                "低等级或内部差异证据不得写成确定性重大事实",
                "不提供买入、卖出、目标价或收益承诺",
            ],
            "outputShape": {
                "executiveSummary": "string",
                "keyDevelopments": [
                    {
                        "title": "string",
                        "assessment": "string",
                        "importance": "1-5 integer",
                        "confidence": "high|medium|low",
                        "entities": ["string"],
                        "evidenceIds": ["E001"],
                    }
                ],
                "thesisUpdates": [
                    {
                        "entity": "string",
                        "direction": "positive|negative|mixed|neutral",
                        "statement": "string",
                        "evidenceIds": ["E001"],
                    }
                ],
                "watchlist": [
                    {
                        "item": "string",
                        "reason": "string",
                        "nextEvidence": "string",
                        "evidenceIds": ["E001"],
                    }
                ],
                "risks": [
                    {
                        "risk": "string",
                        "reason": "string",
                        "evidenceIds": ["E001"],
                    }
                ],
                "methodologyNote": "string",
            },
        },
        "changes": changes[:MAX_MODEL_CHANGES],
        "evidence": evidence,
    }
    return json.dumps(package, ensure_ascii=False, separators=(",", ":"))


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


def call_siliconflow(
    *,
    api_key: str,
    base_url: str,
    model: str,
    reasoning_effort: str,
    prompt: str,
    timeout: float = 95.0,
    retries: int = 2,
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是严谨的科技与创投研究员。你只能使用用户提供的结构化证据，"
                    "必须输出合法 JSON，不得输出 Markdown，不得虚构来源或投资结论。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 3600,
        "response_format": {"type": "json_object"},
        "reasoning_effort": reasoning_effort,
    }
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        endpoint,
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "VCIQ-Research-Agent/1.0",
        },
    )

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            choices = payload.get("choices") if isinstance(payload, dict) else None
            if not isinstance(choices, list) or not choices:
                raise ValueError("SiliconFlow response has no choices")
            message = choices[0].get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ValueError("SiliconFlow response has no message content")
            result = _extract_json_object(message["content"])
            result["_usage"] = payload.get("usage", {})
            return result
        except HTTPError as exc:
            last_error = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= retries:
                break
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= retries:
                break
        time.sleep(2**attempt)
    raise RuntimeError(f"SiliconFlow request failed: {type(last_error).__name__}") from last_error


def _clean_text(value: Any, limit: int = 1200) -> str:
    return str(_trim_text(value if isinstance(value, str) else "", limit) or "").strip()


def sanitize_analysis(raw: Mapping[str, Any], valid_evidence_ids: set[str]) -> dict[str, Any]:
    def evidence_ids(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            str(item)
            for item in value
            if isinstance(item, str) and item in valid_evidence_ids
        ][:8]

    developments: list[dict[str, Any]] = []
    for item in raw.get("keyDevelopments", []) if isinstance(raw.get("keyDevelopments"), list) else []:
        if not isinstance(item, dict):
            continue
        ids = evidence_ids(item.get("evidenceIds"))
        if not ids:
            continue
        importance = item.get("importance", 3)
        try:
            importance = max(1, min(5, int(importance)))
        except (TypeError, ValueError):
            importance = 3
        confidence = str(item.get("confidence", "medium"))
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        entities = item.get("entities") if isinstance(item.get("entities"), list) else []
        developments.append(
            {
                "title": _clean_text(item.get("title"), 180),
                "assessment": _clean_text(item.get("assessment"), 900),
                "importance": importance,
                "confidence": confidence,
                "entities": [_clean_text(entity, 80) for entity in entities[:8] if _clean_text(entity, 80)],
                "evidenceIds": ids,
            }
        )

    deduplicated_developments: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for item in developments:
        key = (
            _normalize_identity(item["title"]),
            tuple(sorted(_normalize_identity(entity) for entity in item["entities"])),
        )
        existing = deduplicated_developments.get(key)
        if existing is None:
            deduplicated_developments[key] = item
            continue
        existing["evidenceIds"] = list(
            dict.fromkeys([*existing["evidenceIds"], *item["evidenceIds"]])
        )[:8]
        existing["importance"] = max(existing["importance"], item["importance"])

    thesis_updates: list[dict[str, Any]] = []
    for item in raw.get("thesisUpdates", []) if isinstance(raw.get("thesisUpdates"), list) else []:
        if not isinstance(item, dict):
            continue
        ids = evidence_ids(item.get("evidenceIds"))
        if not ids:
            continue
        direction = str(item.get("direction", "neutral"))
        if direction not in {"positive", "negative", "mixed", "neutral"}:
            direction = "neutral"
        thesis_updates.append(
            {
                "entity": _clean_text(item.get("entity"), 100),
                "direction": direction,
                "statement": _clean_text(item.get("statement"), 700),
                "evidenceIds": ids,
            }
        )

    watchlist: list[dict[str, Any]] = []
    for item in raw.get("watchlist", []) if isinstance(raw.get("watchlist"), list) else []:
        if not isinstance(item, dict):
            continue
        ids = evidence_ids(item.get("evidenceIds"))
        if not ids:
            continue
        watchlist.append(
            {
                "item": _clean_text(item.get("item"), 160),
                "reason": _clean_text(item.get("reason"), 600),
                "nextEvidence": _clean_text(item.get("nextEvidence"), 400),
                "evidenceIds": ids,
            }
        )

    risks: list[dict[str, Any]] = []
    for item in raw.get("risks", []) if isinstance(raw.get("risks"), list) else []:
        if not isinstance(item, dict):
            continue
        ids = evidence_ids(item.get("evidenceIds"))
        if not ids:
            continue
        risks.append(
            {
                "risk": _clean_text(item.get("risk"), 180),
                "reason": _clean_text(item.get("reason"), 600),
                "evidenceIds": ids,
            }
        )

    return {
        "mode": "model-analysis",
        "isResearchJudgment": True,
        "executiveSummary": _clean_text(raw.get("executiveSummary"), 1600),
        "keyDevelopments": list(deduplicated_developments.values())[:10],
        "thesisUpdates": thesis_updates[:10],
        "watchlist": watchlist[:10],
        "risks": risks[:10],
        "methodologyNote": _clean_text(raw.get("methodologyNote"), 700),
    }


def fallback_analysis(changes: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    if not changes:
        return {
            "mode": "structured-change-only",
            "isResearchJudgment": False,
            "executiveSummary": "本期没有通过证据质量门的外部事实候选。",
            "keyDevelopments": [],
            "thesisUpdates": [],
            "watchlist": [],
            "risks": [],
            "methodologyNote": f"结构化变化检查；{reason}。未执行生成式研判。",
        }

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for change in changes:
        key = (
            str(change.get("dataset", "")),
            _normalize_identity(change.get("entityName")),
            _normalize_identity(change.get("summary")),
        )
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = copy.deepcopy(change)
            continue
        existing["evidenceIds"] = list(
            dict.fromkeys(
                [*existing.get("evidenceIds", []), *change.get("evidenceIds", [])]
            )
        )[:8]

    developments = []
    for change in list(grouped.values())[:8]:
        developments.append(
            {
                "title": f"待复核｜{change['summary']}",
                "assessment": (
                    "这是通过基础证据质量门的外部事实候选，仅确认结构化字段变化；"
                    "当前未生成影响判断，不应视为研究结论。"
                ),
                "importance": max(1, min(5, round(int(change["importance"]) / 20))),
                "confidence": "low",
                "entities": [change["entityName"]],
                "evidenceIds": change.get("evidenceIds", [])[:4],
            }
        )
    return {
        "mode": "structured-change-only",
        "isResearchJudgment": False,
        "executiveSummary": (
            f"本期有 {len(changes)} 条外部事实候选通过基础证据质量门。"
            "当前为降级展示，仅列出字段变化，不提供模型研判或影响结论。"
        ),
        "keyDevelopments": developments,
        "thesisUpdates": [],
        "watchlist": [
            {
                "item": "复核高优先级变化的原始信源",
                "reason": "降级输出不包含研究判断，仍需人工核对证据是否完整支持对应字段。",
                "nextEvidence": "监管文件、公司公告或至少一个独立高等级来源。",
                "evidenceIds": changes[0].get("evidenceIds", [])[:4],
            }
        ],
        "risks": [],
        "methodologyNote": f"结构化变化降级展示；{reason}。未执行生成式研判。",
    }


def _dataset_counts(changes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for change in changes:
        dataset = str(change.get("dataset", "unknown"))
        counts[dataset] = counts.get(dataset, 0) + 1
    return counts


def _history_entry(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "date": report.get("asOfDate", ""),
        "generatedAt": report.get("generatedAt", ""),
        "runStatus": report.get("runStatus", ""),
        "changeCount": report.get("changeSummary", {}).get("total", 0)
        if isinstance(report.get("changeSummary"), dict)
        else 0,
        "executiveSummary": report.get("analysis", {}).get("executiveSummary", "")
        if isinstance(report.get("analysis"), dict)
        else "",
    }


def _merge_history(previous_report: Mapping[str, Any], current_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    old = previous_report.get("history", [])
    if isinstance(old, list):
        rows.extend(item for item in old if isinstance(item, dict))
    rows.append(_history_entry(current_report))
    deduplicated: dict[str, dict[str, Any]] = {}
    for row in rows:
        date = str(row.get("date") or row.get("generatedAt") or "")
        if date:
            deduplicated[date] = row
    return list(deduplicated.values())[-MAX_HISTORY:]


def generate_report(
    *,
    root: Path,
    output_path: Path,
    snapshot_path: Path,
    now: datetime,
    bootstrap_git_ref: str,
    offline: bool,
    max_changes: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = isoformat(now)
    current_snapshot = build_snapshot(load_input_payloads(root), generated_at)

    previous_snapshot = load_json(snapshot_path, required=False)
    baseline_source = "snapshot"
    previous_datasets = previous_snapshot.get("datasets")
    has_previous_rows = isinstance(previous_datasets, dict) and any(
        isinstance(rows, dict) and rows for rows in previous_datasets.values()
    )
    if not has_previous_rows:
        try:
            previous_snapshot = build_snapshot_from_git(
                root, bootstrap_git_ref, generated_at
            )
            baseline_source = f"git:{bootstrap_git_ref}"
        except (RuntimeError, ValueError, FileNotFoundError, json.JSONDecodeError):
            previous_snapshot = {
                "schemaVersion": SCHEMA_VERSION,
                "generatedAt": generated_at,
                "datasets": current_snapshot["datasets"],
                "stats": current_snapshot["stats"],
                "contentHash": current_snapshot["contentHash"],
            }
            baseline_source = "initialized-current"

    raw_changes = diff_snapshots(previous_snapshot, current_snapshot)
    aggregated_changes = aggregate_external_changes(raw_changes)
    research_candidates = [
        change
        for change in aggregated_changes
        if change.get("changeType") == "external_event"
    ]
    packaged_candidates, candidate_evidence = build_evidence_package(
        research_candidates, as_of=now
    )
    eligible_candidates = [
        change
        for change in packaged_candidates
        if change.get("eligibleForKeyDevelopment") is True
    ]
    changes = copy.deepcopy(eligible_candidates[: max(1, max_changes)])
    supporting_ids = {
        evidence_id
        for change in changes
        for evidence_id in change.get("supportingEvidenceIds", [])
    }
    for change in changes:
        change["evidenceIds"] = change.get("supportingEvidenceIds", [])
    evidence = [
        item
        for item in candidate_evidence
        if item.get("id") in supporting_ids
        and item.get("supportStatus") == "supports"
    ]

    api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    base_url = os.environ.get("SILICONFLOW_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model = os.environ.get("SILICONFLOW_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    reasoning_effort = os.environ.get("RESEARCH_AGENT_REASONING_EFFORT", "high").strip() or "high"
    if reasoning_effort not in {"high", "max"}:
        reasoning_effort = "high"

    run_status = "model"
    fallback_reason = ""
    usage: dict[str, Any] = {}
    if not changes:
        run_status = "no-material-change"
        analysis = fallback_analysis(changes, "本期无材料变化")
    elif offline:
        run_status = "offline-fallback"
        fallback_reason = "离线模式"
        analysis = fallback_analysis(changes, fallback_reason)
    elif not api_key:
        run_status = "missing-key-fallback"
        fallback_reason = "未配置 SILICONFLOW_API_KEY"
        analysis = fallback_analysis(changes, fallback_reason)
    else:
        try:
            raw_analysis = call_siliconflow(
                api_key=api_key,
                base_url=base_url,
                model=model,
                reasoning_effort=reasoning_effort,
                prompt=_model_prompt(changes, evidence, generated_at),
            )
            usage_value = raw_analysis.pop("_usage", {})
            usage = usage_value if isinstance(usage_value, dict) else {}
            analysis = sanitize_analysis(raw_analysis, {item["id"] for item in evidence})
            if changes and not analysis["keyDevelopments"]:
                raise ValueError("model returned no evidence-linked developments")
        except (RuntimeError, ValueError, KeyError) as exc:
            run_status = "api-fallback"
            fallback_reason = type(exc).__name__
            analysis = fallback_analysis(changes, "模型调用或结果校验失败")

    previous_report = load_json(output_path, required=False)
    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "asOfDate": now.astimezone(
            ZoneInfo(os.environ.get("RESEARCH_AGENT_TIMEZONE", DEFAULT_TIMEZONE))
        ).date().isoformat(),
        "runStatus": run_status,
        "baselineSource": baseline_source,
        "model": {
            "provider": "SiliconFlow",
            "name": model,
            "baseUrl": base_url,
            "reasoningEffort": reasoning_effort,
            "used": run_status == "model",
            "usage": usage,
        },
        "changeSummary": {
            "totalDetected": len(raw_changes),
            "total": len(changes),
            "byDataset": _dataset_counts(changes),
            "byChangeType": _dataset_counts(
                [
                    {"dataset": str(change.get("changeType", "unknown"))}
                    for change in raw_changes
                ]
            ),
            "externalCandidates": len(research_candidates),
            "qualityRejected": len(packaged_candidates) - len(eligible_candidates),
            "maintenanceExcluded": sum(
                change.get("changeType") != "external_event"
                for change in raw_changes
            ),
            "aggregatedEvents": max(
                0,
                sum(
                    change.get("changeType") == "external_event"
                    for change in raw_changes
                )
                - len(research_candidates),
            ),
            "highestImportance": max(
                (int(change.get("importance", 0)) for change in changes),
                default=0,
            ),
        },
        "analysis": analysis,
        "changes": changes,
        "evidence": evidence,
        "methodology": {
            "stages": [
                "stable entity snapshot",
                "person identity quarantine and duplicate reconciliation",
                "field-level change detection and semantic classification",
                "deterministic materiality ranking",
                "claim-field-evidence binding and evidence quality gate",
                "same-entity event aggregation",
                "LLM structured analysis",
                "evidence-ID validation",
            ],
            "fallbackReason": fallback_reason,
            "disclaimer": "信息仅供研究，不构成投资建议；关键事实应回溯原始信源。",
        },
    }
    report["history"] = _merge_history(previous_report, report)
    return report, current_snapshot


def validate_report(report: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("unsupported schemaVersion")
    if not isinstance(report.get("analysis"), dict):
        errors.append("analysis must be an object")
    changes = report.get("changes")
    evidence = report.get("evidence")
    if not isinstance(changes, list):
        errors.append("changes must be an array")
        changes = []
    if not isinstance(evidence, list):
        errors.append("evidence must be an array")
        evidence = []
    evidence_ids = {
        item.get("id")
        for item in evidence
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    evidence_by_id = {
        str(item.get("id")): item
        for item in evidence
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for change in changes:
        if not isinstance(change, dict):
            errors.append("change row must be an object")
            continue
        ids = change.get("evidenceIds")
        if not isinstance(ids, list) or not ids:
            errors.append(f"change {change.get('id')} has no evidenceIds")
        elif any(item not in evidence_ids for item in ids):
            errors.append(f"change {change.get('id')} references unknown evidence")
        if change.get("eligibleForKeyDevelopment") is True:
            if change.get("changeType") != "external_event":
                errors.append(
                    f"change {change.get('id')} is eligible but is not an external event"
                )
            bindings = change.get("claimBindings")
            if not isinstance(bindings, list) or not bindings:
                errors.append(f"change {change.get('id')} has no claim bindings")
            for evidence_id in ids if isinstance(ids, list) else []:
                row = evidence_by_id.get(str(evidence_id), {})
                if row.get("qualityStatus") != "passed" or row.get(
                    "supportStatus"
                ) != "supports":
                    errors.append(
                        f"change {change.get('id')} references rejected evidence"
                    )
    analysis = report.get("analysis", {})
    if isinstance(analysis, dict):
        for section in ("keyDevelopments", "thesisUpdates", "watchlist", "risks"):
            rows = analysis.get(section, [])
            if not isinstance(rows, list):
                errors.append(f"analysis.{section} must be an array")
                continue
            for row in rows:
                if not isinstance(row, dict):
                    errors.append(f"analysis.{section} row must be an object")
                    continue
                ids = row.get("evidenceIds")
                if not isinstance(ids, list) or not ids:
                    errors.append(f"analysis.{section} row has no evidenceIds")
                elif any(item not in evidence_ids for item in ids):
                    errors.append(f"analysis.{section} references unknown evidence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--bootstrap-git-ref", default="HEAD^")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-changes", type=int, default=MAX_CHANGES)
    parser.add_argument("--now", help="ISO-8601 time for deterministic tests/runs")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    output_path = (args.output or root / "public/data/research_agent_daily.json").resolve()
    snapshot_path = (args.snapshot or root / "public/data/research_agent_snapshot.json").resolve()

    if args.check:
        report = load_json(output_path)
        errors = validate_report(report)
        if errors:
            raise SystemExit("; ".join(errors))
        print(
            json.dumps(
                {
                    "passed": True,
                    "runStatus": report.get("runStatus"),
                    "changes": len(report.get("changes", [])),
                    "evidence": len(report.get("evidence", [])),
                },
                ensure_ascii=False,
            )
        )
        return 0

    now = datetime.fromisoformat(args.now) if args.now else utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    report, snapshot = generate_report(
        root=root,
        output_path=output_path,
        snapshot_path=snapshot_path,
        now=now,
        bootstrap_git_ref=args.bootstrap_git_ref,
        offline=args.offline,
        max_changes=max(1, args.max_changes),
    )
    errors = validate_report(report)
    if errors:
        raise SystemExit("; ".join(errors))
    atomic_write_json(output_path, report)
    atomic_write_json(snapshot_path, snapshot)
    print(
        json.dumps(
            {
                "runStatus": report["runStatus"],
                "detected": report["changeSummary"]["totalDetected"],
                "published": report["changeSummary"]["total"],
                "evidence": len(report["evidence"]),
                "output": str(output_path),
                "snapshot": str(snapshot_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
