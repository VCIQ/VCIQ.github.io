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
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
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
EVENT_LEDGER_SCHEMA_VERSION = 1
EVENT_LEDGER_RETENTION_DAYS = 180
MAX_EVENT_LEDGER_ENTRIES = 600
MAX_EVENT_ALIASES = 16
MAX_EVENT_TITLE_ALIASES = 8
MAX_EVENT_EVIDENCE_SUMMARIES = 8
MAX_PENDING_PUBLICATIONS = MAX_EVENT_LEDGER_ENTRIES

EVENT_URL_TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "spm",
    "from",
    "ref",
    "source",
}

CONFLICT_SCALAR_FIELDS = {
    "status",
    "ipoStatus",
    "listingStatus",
    "financingStatus",
    "role",
    "position",
    "stage",
    "round",
    "valuation",
    "amount",
}

GENERIC_EVENT_ENTITIES = {
    "",
    "科技产业",
    "人工智能",
    "全球",
    "行业",
    "市场",
}

CORRECTION_CUE_PATTERN = re.compile(
    r"(?:更正|勘误|澄清|撤回|撤销|辟谣|retract(?:ion|ed)?|correction|corrected)",
    flags=re.IGNORECASE,
)

IPO_STAGE_PATTERNS: tuple[tuple[str, int, re.Pattern[str]], ...] = (
    ("withdrawn", -1, re.compile(r"撤回.{0,8}(?:上市|IPO)|终止.{0,8}(?:上市|IPO)|上市失败|IPO失败|被否", re.IGNORECASE)),
    ("listed", 6, re.compile(r"正式上市|上市首日|上市次日|挂牌交易|IPO后股价|完成上市", re.IGNORECASE)),
    ("roadshow", 5, re.compile(r"路演|招股|定价", re.IGNORECASE)),
    ("inquiry", 4, re.compile(r"问询", re.IGNORECASE)),
    ("accepted", 3, re.compile(r"受理", re.IGNORECASE)),
    ("filed", 2, re.compile(r"递交.{0,8}(?:招股|上市)|提交.{0,8}(?:招股|上市)|申报.{0,8}IPO", re.IGNORECASE)),
    ("planning", 1, re.compile(r"计划上市|筹备上市|拟上市|推进.{0,8}IPO", re.IGNORECASE)),
)

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
AUTOMATED_REVIEW_STATUS = "automated_unreviewed"
PUBLICATION_TIERS = {
    "verified_change",
    "candidate",
    "external_clue",
    "rejected",
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
                    # Internal-only baseline used to bind rolling market-news
                    # evidence to rows that were actually added this run.
                    "_beforeRecord": before,
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


def _explicit_source_metadata(value: Mapping[str, Any]) -> dict[str, str]:
    """Copy explicit publisher/platform fields without inferring attribution."""

    def text(*keys: str) -> str:
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, Mapping):
                candidate = candidate.get("name") or candidate.get("publisher")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    fields = {
        "publisherName": text("publisherName", "publisher"),
        "originalPublisherName": text(
            "originalPublisherName", "originalPublisher"
        ),
        "platformName": text("platformName", "platform", "hostPlatform"),
        "sourceType": text("sourceType"),
        "sourceRole": text("sourceRole"),
    }
    return {key: item for key, item in fields.items() if item}


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
                **_explicit_source_metadata(value),
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
    if _is_discovery_only_evidence(candidate):
        issues.append("discovery_only")
    published_at = _parse_evidence_datetime(candidate.get("publishedAt"))
    if published_at is None:
        issues.append("missing_published_at")
    if as_of is not None and published_at is not None and published_at > as_of:
        issues.append("future_published_at")
    return issues


def _is_discovery_only_evidence(candidate: Mapping[str, Any]) -> bool:
    """Return whether a row is a discovery lead, not formal claim evidence."""

    role = str(candidate.get("sourceRole") or "").strip().casefold()
    if role == "discovery":
        return True
    grade = str(candidate.get("evidenceGrade") or "").strip().casefold()
    if grade in {"discovery", "发现线索", "线索", "d"}:
        return True
    return bool(re.match(r"^d(?:级|类|[-_\s:]|$)", grade))


def _evidence_canonical_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text.startswith(("http://", "https://")):
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    tracking_keys = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "ref",
        "source",
        "spm",
    }
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in tracking_keys
        )
    )
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/") or "/",
            query,
            "",
        )
    )


def _news_item_identity(value: Any) -> str:
    if not isinstance(value, Mapping):
        return f"value:{stable_hash(value)}"
    title = _normalize_identity(value.get("title"))
    raw_source = value.get("source") or value.get("publisher")
    if isinstance(raw_source, Mapping):
        raw_source = (
            raw_source.get("name")
            or raw_source.get("publisher")
            or raw_source.get("platform")
        )
    source = _normalize_identity(raw_source)
    if title:
        # The crawler may rotate hosts, paths, or signed query tokens while the
        # underlying news row is unchanged. Stable title + explicit source is
        # therefore the primary delta identity; URL is only a fallback.
        return f"title:{source}:{title}"
    url = _evidence_canonical_url(
        value.get("url") or value.get("sourceUrl") or value.get("originalPdfUrl")
    )
    if url:
        return f"url:{url}"
    return f"row:{stable_hash(value)}"


def _new_news_items(after: Any, before: Any) -> list[Any]:
    """Return a multiset-style after-before difference for rolling news rows."""

    after_rows = after if isinstance(after, list) else []
    before_rows = before if isinstance(before, list) else []
    remaining: dict[str, int] = {}
    for row in before_rows:
        key = _news_item_identity(row)
        remaining[key] = remaining.get(key, 0) + 1
    additions: list[Any] = []
    for row in after_rows:
        key = _news_item_identity(row)
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
            continue
        additions.append(row)
    return additions


def _market_news_evidence_record(
    record: Mapping[str, Any], previous_record: Mapping[str, Any] | None
) -> Mapping[str, Any]:
    """Limit market-company news evidence to newly added news rows."""

    if not isinstance(record.get("news"), list):
        return record
    before_news = previous_record.get("news") if previous_record else []
    prepared = dict(record)
    prepared["news"] = _new_news_items(record.get("news"), before_news)
    return prepared


def _alias_values(record: Mapping[str, Any], entity_name: str) -> list[str]:
    values: list[str] = [entity_name]

    def append(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                append(item)

    for key in (
        "name",
        "companyName",
        "englishName",
        "aliases",
        "alias",
        "slug",
        "ticker",
        "symbol",
        "thsCode",
    ):
        append(record.get(key))
    company = record.get("company")
    if isinstance(company, Mapping):
        for key in ("name", "companyName", "englishName", "aliases", "alias"):
            append(company.get(key))
    return values


def _entity_aliases(record: Mapping[str, Any], entity_name: str) -> set[str]:
    aliases: set[str] = set()
    for raw_value in _alias_values(record, entity_name):
        normalized = _normalize_identity(raw_value)
        if not normalized:
            continue
        if normalized.isdigit() and len(normalized) < 5:
            continue
        if normalized.isascii() and len(normalized) < 4:
            continue
        aliases.add(normalized)

        # Market feeds often retain the full legal Chinese name while headlines
        # use the stable brand. Only apply conservative legal-name reductions.
        if re.search(r"[\u3400-\u9fff]", normalized):
            brand = re.sub(
                r"(?:集团)?(?:股份)?(?:有限责任)?有限公司$|股份有限公司$|有限公司$",
                "",
                normalized,
            )
            if len(brand) >= 4:
                aliases.add(brand)
            without_descriptor = re.sub(r"(?:科技|控股|集团|股份)$", "", brand)
            if len(without_descriptor) >= 4:
                aliases.add(without_descriptor)
            if without_descriptor.startswith("中科") and len(without_descriptor) >= 5:
                aliases.add(without_descriptor[2:])
    return aliases


def _candidate_is_market_news(candidate: Mapping[str, Any]) -> bool:
    return "news" in {str(part) for part in candidate.get("_path", [])}


def _entity_match_status(
    candidate: Mapping[str, Any],
    *,
    dataset: str,
    entity_name: str,
    record: Mapping[str, Any],
) -> str:
    if dataset != "marketCompany" or not _candidate_is_market_news(candidate):
        return "not_applicable"
    title = _normalize_identity(candidate.get("title"))
    aliases = _entity_aliases(record, entity_name)
    if title and any(alias in title for alias in aliases):
        return "matched"
    return "mismatched"


def _is_verified_source(source: Mapping[str, Any]) -> bool:
    role = str(source.get("sourceRole") or "").strip().casefold()
    if role == "primary":
        return True
    grade = str(source.get("evidenceGrade") or "").strip().casefold()
    if re.match(r"^[ab](?:级|类|[-_\s:]|$)", grade):
        return True
    return any(
        marker in grade
        for marker in (
            "官方",
            "监管",
            "交易所",
            "原始材料",
            "主体原始",
            "法定披露",
        )
    )


def _publication_tier(dataset: str, sources: Iterable[Mapping[str, Any]]) -> str:
    supporting = [
        source for source in sources if source.get("supportStatus") == "supports"
    ]
    if not supporting:
        return "rejected"
    if dataset == "intelligenceEvent":
        return "external_clue"
    if dataset in {"person", "ventureCompany"} and any(
        _is_verified_source(source) for source in supporting
    ):
        return "verified_change"
    return "candidate"


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
    entity_name: str = "",
    previous_record: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    changed_fields = tuple(str(field) for field in changed_fields)
    as_of_datetime = (
        as_of
        if isinstance(as_of, datetime)
        else _parse_evidence_datetime(as_of) if as_of is not None else utc_now()
    )
    evidence_record = (
        _market_news_evidence_record(record, previous_record)
        if dataset == "marketCompany" and "news" in set(changed_fields)
        else record
    )
    candidates: dict[str, dict[str, Any]] = {}
    for index, raw_candidate in enumerate(_walk_source_candidates(evidence_record)):
        candidate = dict(raw_candidate)
        candidate["claimFields"] = _candidate_claim_fields(
            candidate, changed_fields, dataset, action
        )
        candidate["entityMatchStatus"] = _entity_match_status(
            candidate,
            dataset=dataset,
            entity_name=entity_name,
            record=record,
        )
        candidate["qualityIssues"] = _evidence_quality_issues(
            candidate, as_of_datetime
        )
        if candidate["entityMatchStatus"] == "mismatched":
            candidate["qualityIssues"].append("entity_mismatch")
            candidate["claimFields"] = []
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
            entity_name=str(change.get("entityName", "")),
            previous_record=(
                change.get("_beforeRecord")
                if isinstance(change.get("_beforeRecord"), Mapping)
                else change.get("before")
                if isinstance(change.get("before"), Mapping)
                else None
            ),
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
                    "entityMatchStatus": "not_applicable",
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
        supporting_ids = [
            evidence_id
            for evidence_id, source in source_rows
            if source.get("supportStatus") == "supports"
        ]
        publication_tier = _publication_tier(
            str(change.get("dataset", "")),
            (source for _, source in source_rows),
        )
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
                    "publicationTier": (
                        publication_tier
                        if source.get("supportStatus") == "supports"
                        else "rejected"
                    ),
                    "reviewStatus": AUTOMATED_REVIEW_STATUS,
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
        public_change = {
                key: value
                for key, value in change.items()
                if key != "record" and not key.startswith("_")
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
                "publicationTier": publication_tier,
                "reviewStatus": AUTOMATED_REVIEW_STATUS,
                "eligibleForKeyDevelopment": bool(
                    change.get("changeType") == "external_event" and supporting_ids
                ),
            }
        record = change.get("record")
        if isinstance(record, Mapping):
            event_cluster_id = str(record.get("eventClusterId") or "").strip()
            if event_cluster_id:
                public_change["eventClusterId"] = event_cluster_id
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


def _normalized_event_text(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip().casefold()


def _normalized_event_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = re.sub(r"[|｜].*$", "", text)
    text = re.sub(
        r"[-—–]\s*[^-—–|｜]{0,24}(?:快讯|新闻|资讯|日报|周刊|观察|频道)\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = (
        text.replace("三分之一", "1/3")
        .replace("二分之一", "1/2")
        .replace("四分之一", "1/4")
        .replace("超过", "超")
        .replace("以来", "")
    )
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", text)


def _event_numeric_cues(value: Any) -> list[str]:
    text = (
        unicodedata.normalize("NFKC", str(value or ""))
        .casefold()
        .replace("三分之一", "1/3")
        .replace("二分之一", "1/2")
        .replace("四分之一", "1/4")
    )
    cues: set[str] = set()
    for cue in re.findall(r"\d+(?:[./]\d+)?%?", text):
        try:
            numeric = int(re.split(r"[./%]", cue, maxsplit=1)[0])
        except ValueError:
            numeric = -1
        if 1900 <= numeric <= 2099:
            continue
        cues.add(cue)
    return sorted(cues)


def _event_title_similarity(left: Any, right: Any) -> float:
    left_title = _normalized_event_title(left)
    right_title = _normalized_event_title(right)
    if not left_title or not right_title:
        return 0.0
    if left_title == right_title:
        return 1.0
    if left_title in right_title or right_title in left_title:
        return min(len(left_title), len(right_title)) / max(
            len(left_title), len(right_title)
        )

    def bigrams(text: str) -> set[str]:
        if len(text) < 2:
            return {text} if text else set()
        return {text[index : index + 2] for index in range(len(text) - 1)}

    left_bigrams = bigrams(left_title)
    right_bigrams = bigrams(right_title)
    if not left_bigrams or not right_bigrams:
        return 0.0
    overlap = len(left_bigrams & right_bigrams)
    return (2 * overlap) / (len(left_bigrams) + len(right_bigrams))


def _canonical_event_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text.startswith(("http://", "https://")):
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in EVENT_URL_TRACKING_PARAMETERS
            and not key.casefold().startswith("utm_")
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("", parts.netloc.casefold(), path, query, ""))


def _event_evidence_strength(value: Any) -> int:
    grade = _normalized_event_text(value)
    if grade in {"a", "a级", "a 級"} or "监管" in grade:
        return 5
    if grade in {"b", "b级", "b 級"} or any(
        cue in grade for cue in ("原始", "官方", "主体")
    ):
        return 4
    if grade in {"c", "c级", "c 級"} or any(
        cue in grade for cue in ("媒体", "数据库", "資料庫")
    ):
        return 2
    if grade in {"d", "d级", "d 級"} or any(
        cue in grade for cue in ("标题", "線索", "线索")
    ):
        return 1
    return 0


def _event_date(value: Any) -> str:
    parsed = _parse_evidence_datetime(value)
    return parsed.date().isoformat() if parsed is not None else ""


def _event_dates_close(left: str, right: str, maximum_days: int = 3) -> bool:
    try:
        return abs((date.fromisoformat(left) - date.fromisoformat(right)).days) <= maximum_days
    except ValueError:
        return False


def _event_entity_keys(change: Mapping[str, Any]) -> list[str]:
    dataset = str(change.get("dataset") or "")
    keys: set[str] = set()
    entity_id = _normalized_event_text(change.get("entityId"))
    entity_name = _normalized_event_text(change.get("entityName"))
    if dataset != "intelligenceEvent":
        if entity_id:
            keys.add(f"{dataset}:{entity_id}")
        if entity_name:
            keys.add(f"name:{entity_name}")

    after = change.get("after")
    if isinstance(after, Mapping):
        for field in ("companySlug", "company", "companyName"):
            raw_value = str(after.get(field) or "").strip()
            if raw_value in GENERIC_EVENT_ENTITIES:
                continue
            value = _normalized_event_text(raw_value)
            if value:
                keys.add(f"company:{value}")
        for field in ("mentionedCompanies", "mentionedPeople"):
            values = after.get(field)
            if not isinstance(values, list):
                continue
            for raw_value in values[:8]:
                value = _normalized_event_text(raw_value)
                if value and str(raw_value).strip() not in GENERIC_EVENT_ENTITIES:
                    keys.add(f"mention:{value}")
    return sorted(keys)


def _event_fingerprint_entity_keys(
    entity_keys: Iterable[Any], dataset: str = ""
) -> list[str]:
    """Prefer stable semantic entity keys over snapshot-row identifiers."""

    keys = sorted({str(value) for value in entity_keys if value})
    row_keys = [
        value
        for value in keys
        if not value.startswith(("company:", "name:", "mention:"))
    ]
    if row_keys and dataset not in EVENT_DATASETS:
        return row_keys
    for prefix in ("company:", "name:", "mention:"):
        preferred = [value for value in keys if value.startswith(prefix)]
        if preferred:
            return preferred
    return keys


def _event_entities_compatible(
    observation: Mapping[str, Any], entry: Mapping[str, Any]
) -> bool:
    current = {str(value) for value in observation.get("entityKeys", []) if value}
    previous = {str(value) for value in entry.get("entityKeys", []) if value}
    if not current or not previous:
        return True
    current_row_keys = {
        value
        for value in current
        if not value.startswith(("company:", "name:", "mention:"))
    }
    previous_row_keys = {
        value
        for value in previous
        if not value.startswith(("company:", "name:", "mention:"))
    }
    current_row_prefixes = {value.partition(":")[0] for value in current_row_keys}
    previous_row_prefixes = {value.partition(":")[0] for value in previous_row_keys}
    dataset = str(observation.get("dataset") or entry.get("dataset") or "")
    if (
        dataset not in EVENT_DATASETS
        and current_row_prefixes & previous_row_prefixes
    ):
        # Stable row IDs for the same dataset take precedence over a shared
        # display name, which is not unique for people or companies.
        return bool(current_row_keys & previous_row_keys)
    if current & previous:
        return True
    semantic_prefixes = ("company:", "name:", "mention:")
    current_values = {
        value.partition(":")[2]
        for value in current
        if value.startswith(semantic_prefixes)
    }
    previous_values = {
        value.partition(":")[2]
        for value in previous
        if value.startswith(semantic_prefixes)
    }
    return bool(current_values and previous_values and current_values & previous_values)


def _event_type_keys(change: Mapping[str, Any]) -> list[str]:
    keys: set[str] = set()
    after = change.get("after")
    if isinstance(after, Mapping):
        event_type = _normalized_event_text(after.get("type"))
        if event_type:
            keys.add(event_type)
    entity_type = _normalized_event_text(change.get("entityType"))
    if entity_type:
        keys.add(entity_type)
    return sorted(keys)


def _event_scalar_claims(
    change: Mapping[str, Any], evidence_id: str
) -> dict[str, str]:
    claims: dict[str, str] = {}
    bindings = change.get("claimBindings")
    if not isinstance(bindings, list):
        return claims
    dataset = str(change.get("dataset") or "")
    entity_id = str(change.get("entityId") or change.get("entityName") or "")
    for binding in bindings:
        if not isinstance(binding, Mapping):
            continue
        binding_ids = binding.get("evidenceIds")
        if isinstance(binding_ids, list) and evidence_id not in binding_ids:
            continue
        field = str(binding.get("field") or "")
        if field not in CONFLICT_SCALAR_FIELDS:
            continue
        after = binding.get("after")
        if not isinstance(after, (str, int, float, bool)):
            continue
        value = _normalized_event_text(after)
        if value:
            claims[f"{dataset}:{entity_id}:{field}"] = value
    return claims


def _event_ipo_stage(value: Any) -> tuple[str, int] | None:
    text = str(value or "")
    for label, rank, pattern in IPO_STAGE_PATTERNS:
        if pattern.search(text):
            return label, rank
    return None


def _event_observation_from_evidence_group(
    change: Mapping[str, Any],
    selected_evidence: list[Mapping[str, Any]],
    *,
    use_evidence_title: bool,
) -> dict[str, Any]:
    after = change.get("after")
    after_title = (
        str(after.get("title") or "").strip()
        if isinstance(after, Mapping)
        else ""
    )
    evidence_title_candidates = sorted(
        (
            str(evidence.get("title") or "").strip()
            for evidence in selected_evidence
            if str(evidence.get("title") or "").strip()
        ),
        key=lambda value: (_normalized_event_title(value), value),
    )
    semantic_title = (
        evidence_title_candidates[0]
        if use_evidence_title
        else after_title
        or (evidence_title_candidates[0] if evidence_title_candidates else "")
        or change.get("summary")
        or change.get("entityName")
        or ""
    )
    title = str(semantic_title or change.get("entityName") or "").strip()
    normalized_title = _normalized_event_title(title)
    entity_keys = _event_entity_keys(change)
    dataset = str(change.get("dataset") or "")
    fingerprint_entity_keys = _event_fingerprint_entity_keys(entity_keys, dataset)
    entity_id = str(change.get("entityId") or "")
    aliases: set[str] = set()
    source_aliases: list[str] = []
    evidence_ids: list[str] = []
    evidence_fingerprints: list[str] = []
    legacy_evidence_fingerprints: list[str] = []
    evidence_summaries: list[dict[str, str]] = []
    published_dates: list[str] = []
    scalar_claims: dict[str, str] = {}
    numeric_cues = set(_event_numeric_cues(title))
    strength = 0
    correction_cue = bool(CORRECTION_CUE_PATTERN.search(title))
    correction_strength = 0
    evidence_with_correction_cue = False
    title_aliases = {normalized_title} if normalized_title else set()

    for evidence in selected_evidence:
        evidence_id = str(evidence.get("id") or "")
        evidence_title = str(evidence.get("title") or title).strip()
        normalized_evidence_title = _normalized_event_title(evidence_title)
        if normalized_evidence_title:
            title_aliases.add(normalized_evidence_title)
        published_date = _event_date(evidence.get("publishedAt"))
        source_name = _normalized_event_text(evidence.get("sourceName"))
        canonical_url = _canonical_event_url(evidence.get("url"))
        source_alias = (
            f"src-{stable_hash(['event-source-v1', canonical_url])}"
            if canonical_url
            else ""
        )
        legacy_fingerprint = stable_hash(
            [
                "event-evidence-v1",
                source_name,
                normalized_evidence_title,
                published_date,
            ]
        )
        evidence_fingerprint = stable_hash(
            [
                "event-evidence-v1",
                source_name,
                normalized_evidence_title,
                published_date,
                fingerprint_entity_keys,
            ]
        )
        aliases.add(f"evd-{evidence_fingerprint}")
        if source_alias:
            aliases.add(source_alias)
            source_aliases.append(source_alias)
        evidence_ids.append(evidence_id)
        evidence_fingerprints.append(evidence_fingerprint)
        legacy_evidence_fingerprints.append(legacy_fingerprint)
        evidence_summaries.append(
            {
                key: str(value)
                for key, value in {
                    "sourceName": evidence.get("sourceName"),
                    "title": evidence.get("title"),
                    "url": evidence.get("url"),
                    "publishedAt": evidence.get("publishedAt"),
                    "evidenceGrade": evidence.get("evidenceGrade"),
                    "sourceRole": evidence.get("sourceRole"),
                }.items()
                if value not in (None, "")
            }
        )
        if published_date:
            published_dates.append(published_date)
        scalar_claims.update(_event_scalar_claims(change, evidence_id))
        numeric_cues.update(_event_numeric_cues(evidence_title))
        strength = max(
            strength, _event_evidence_strength(evidence.get("evidenceGrade"))
        )
        evidence_has_correction_cue = bool(
            CORRECTION_CUE_PATTERN.search(evidence_title)
        )
        correction_cue = correction_cue or evidence_has_correction_cue
        if evidence_has_correction_cue:
            evidence_with_correction_cue = True
            correction_strength = max(
                correction_strength,
                _event_evidence_strength(evidence.get("evidenceGrade")),
            )

    if (
        correction_cue
        and not evidence_with_correction_cue
        and len(selected_evidence) == 1
    ):
        correction_strength = strength

    event_cluster_id = _normalized_event_text(change.get("eventClusterId"))
    if event_cluster_id:
        aliases.add(
            f"cluster-{stable_hash(['event-cluster-v1', event_cluster_id])}"
        )
    if dataset in EVENT_DATASETS and entity_id:
        aliases.add(
            f"record-{stable_hash(['event-record-v1', dataset, entity_id])}"
        )

    after_published_date = (
        _event_date(after.get("publishedAt"))
        if isinstance(after, Mapping)
        else ""
    )
    published_date = (
        min(published_dates, default="")
        if use_evidence_title
        else after_published_date or min(published_dates, default="")
    )
    safe_event_ids = change.get("eventIds")
    preferred_event_ids = (
        [str(value) for value in safe_event_ids if value]
        if isinstance(safe_event_ids, list)
        else []
    )
    if not preferred_event_ids and change.get("eventId"):
        preferred_event_ids = [str(change.get("eventId"))]

    return {
        "changeId": str(change.get("id") or ""),
        "evidenceId": evidence_ids[0],
        "evidenceIds": list(dict.fromkeys(evidence_ids)),
        "dataset": dataset,
        "entityId": entity_id,
        "entityName": str(change.get("entityName") or ""),
        "title": title[:500],
        "normalizedTitle": normalized_title[:500],
        "titleAliases": sorted(title_aliases),
        "publishedDate": published_date,
        "publishedDates": list(dict.fromkeys(published_dates)),
        "entityKeys": entity_keys,
        "typeKeys": _event_type_keys(change),
        "numericCues": sorted(numeric_cues),
        "aliases": sorted(aliases),
        "sourceAlias": min(source_aliases, default=""),
        "evidenceFingerprint": evidence_fingerprints[0],
        "evidenceFingerprints": list(dict.fromkeys(evidence_fingerprints)),
        "legacyEvidenceFingerprints": list(
            dict.fromkeys(legacy_evidence_fingerprints)
        ),
        "evidenceSummaries": evidence_summaries,
        "strength": strength,
        "scalarClaims": scalar_claims,
        "claimFingerprint": stable_hash(
            ["event-claim-v1", normalized_title, scalar_claims]
        ),
        "ipoStage": _event_ipo_stage(title),
        "correctionCue": correction_cue,
        "correctionStrength": correction_strength,
        "summary": str(change.get("summary") or "")[:700],
        "preferredEventIds": preferred_event_ids,
        "allowFuzzyMatch": True,
        "sourceAliasNeedsTitleMatch": use_evidence_title,
        "fuzzyMatchThreshold": 0.86,
    }


def _event_observations(
    change: Mapping[str, Any], evidence_rows: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    raw_supporting_ids = change.get("supportingEvidenceIds")
    if isinstance(raw_supporting_ids, list):
        supporting_ids = {str(value) for value in raw_supporting_ids if value}
    else:
        # Reports written before the evidence gate only carried evidenceIds.
        legacy_ids = change.get("evidenceIds")
        supporting_ids = (
            {str(value) for value in legacy_ids if value}
            if isinstance(legacy_ids, list)
            else set()
        )
    selected_evidence = [
        evidence
        for evidence in evidence_rows
        if str(evidence.get("id") or "") in supporting_ids
    ]
    if not selected_evidence:
        return []

    split_market_news = bool(
        change.get("dataset") == "marketCompany"
        and "news" in {str(value) for value in change.get("changedFields", [])}
    )
    if not split_market_news:
        # One snapshot change is one semantic event. Its supporting sources are
        # confirmations of that event, not separate lifecycle transitions.
        return [
            _event_observation_from_evidence_group(
                change, selected_evidence, use_evidence_title=False
            )
        ]

    # A rolling market-news field can add several unrelated headlines in one
    # snapshot delta. Split those items by headline while retaining exact-title
    # corroboration as multiple evidence rows for the same semantic event.
    news_groups: dict[str, list[Mapping[str, Any]]] = {}
    for evidence in selected_evidence:
        title_key = _normalized_event_title(evidence.get("title"))
        if not title_key:
            title_key = _canonical_event_url(evidence.get("url"))
        if not title_key:
            title_key = stable_hash(evidence)
        news_groups.setdefault(title_key, []).append(evidence)
    observations = [
        _event_observation_from_evidence_group(
            change, group, use_evidence_title=True
        )
        for _, group in sorted(news_groups.items())
    ]
    legacy_event_ids = change.get("eventIds")
    if isinstance(legacy_event_ids, list) and len(legacy_event_ids) == len(
        observations
    ):
        for observation, event_id in zip(observations, legacy_event_ids):
            observation["preferredEventIds"] = [str(event_id)]
    return observations


def _new_event_id(observation: Mapping[str, Any]) -> str:
    preferred_ids = observation.get("preferredEventIds")
    if isinstance(preferred_ids, list) and len(preferred_ids) == 1:
        preferred_id = str(preferred_ids[0])
        if (
            preferred_id.startswith("evt-")
            and len(preferred_id) <= 160
            and re.fullmatch(r"evt-[A-Za-z0-9._:-]+", preferred_id)
        ):
            return preferred_id
    cluster_alias = next(
        (
            alias
            for alias in observation.get("aliases", [])
            if str(alias).startswith("cluster-")
        ),
        "",
    )
    seed: Any
    if cluster_alias:
        seed = ["event-v1", cluster_alias]
    else:
        seed = [
            "event-v1",
            observation.get("normalizedTitle"),
            observation.get("publishedDate"),
            observation.get("entityKeys", []),
            observation.get("numericCues", []),
            observation.get("typeKeys", []),
        ]
        if not observation.get("normalizedTitle"):
            seed.append(observation.get("sourceAlias"))
    return f"evt-{stable_hash(seed)}"


def _ledger_entry_dates(entry: Mapping[str, Any]) -> list[str]:
    dates = entry.get("publishedDates")
    values = [str(value) for value in dates if value] if isinstance(dates, list) else []
    published_date = str(entry.get("publishedDate") or "")
    if published_date and published_date not in values:
        values.append(published_date)
    return values


def _observation_matches_entry(
    observation: Mapping[str, Any], entry: Mapping[str, Any]
) -> tuple[int, float, str] | None:
    if not _event_entities_compatible(observation, entry):
        return None
    aliases = {str(value) for value in observation.get("aliases", []) if value}
    prior_aliases = {str(value) for value in entry.get("sourceAliases", []) if value}
    shared_aliases = aliases & prior_aliases
    strong_aliases = {
        value for value in shared_aliases if not value.startswith("src-")
    }
    if strong_aliases or (
        shared_aliases and observation.get("sourceAliasNeedsTitleMatch") is not True
    ):
        return 400, 1.0, "alias"

    published_date = str(observation.get("publishedDate") or "")
    prior_dates = _ledger_entry_dates(entry)
    dates_close = any(
        _event_dates_close(published_date, prior_date) for prior_date in prior_dates
    )
    if not dates_close:
        return None

    normalized_title = str(observation.get("normalizedTitle") or "")
    title_aliases = {
        str(value) for value in entry.get("titleAliases", []) if value
    }
    if normalized_title and normalized_title in title_aliases:
        return 300, 1.0, "exact_title"

    current_numbers = set(observation.get("numericCues", []))
    prior_numbers = set(entry.get("numericCues", []))
    numeric_conflict = bool(
        current_numbers and prior_numbers and not current_numbers.intersection(prior_numbers)
    )
    if numeric_conflict:
        return None

    entity_overlap = bool(
        set(observation.get("entityKeys", []))
        & set(entry.get("entityKeys", []))
    )
    if not entity_overlap:
        return None

    best_similarity = max(
        (
            _event_title_similarity(normalized_title, prior_title)
            for prior_title in title_aliases
        ),
        default=0.0,
    )
    fuzzy_threshold = float(observation.get("fuzzyMatchThreshold") or 0.86)
    if best_similarity >= fuzzy_threshold:
        return 200, best_similarity, "fuzzy_title"
    if (
        best_similarity >= 0.48
        and current_numbers
        and prior_numbers
        and current_numbers.intersection(prior_numbers)
        and published_date in prior_dates
    ):
        return 100, best_similarity, "entity_numeric"
    return None


def _match_event_entry(
    observation: Mapping[str, Any], events: Mapping[str, Mapping[str, Any]]
) -> tuple[str | None, str, list[str]]:
    candidates: list[tuple[int, float, str, str]] = []
    for event_id, entry in events.items():
        match = _observation_matches_entry(observation, entry)
        if match is None:
            continue
        score, similarity, kind = match
        candidates.append((score, similarity, str(event_id), kind))
    if not candidates:
        seeded_id = _new_event_id(observation)
        if seeded_id in events:
            return seeded_id, "seed", []
        return None, "new", []
    candidates.sort(reverse=True)
    top = candidates[0]
    tied = [row for row in candidates if row[:2] == top[:2]]
    if len(tied) > 1:
        return None, "ambiguous", sorted(row[2] for row in tied)
    return top[2], top[3], []


def _event_correction_target(
    observation: Mapping[str, Any], events: Mapping[str, Mapping[str, Any]]
) -> tuple[str | None, list[str]]:
    current_entities = set(observation.get("entityKeys", []))
    published_date = str(observation.get("publishedDate") or "")
    if not current_entities or not published_date:
        return None, []
    candidates: list[str] = []
    for event_id, entry in events.items():
        if not _event_entities_compatible(observation, entry):
            continue
        dates_close = any(
            _event_dates_close(
                published_date,
                prior_date,
                maximum_days=EVENT_LEDGER_RETENTION_DAYS,
            )
            for prior_date in _ledger_entry_dates(entry)
        )
        if not dates_close:
            continue

        normalized_title = str(observation.get("normalizedTitle") or "")
        title_similarity = max(
            (
                _event_title_similarity(normalized_title, str(prior_title))
                for prior_title in entry.get("titleAliases", [])
            ),
            default=0.0,
        )
        current_claims = observation.get("scalarClaims")
        prior_claims = entry.get("scalarClaims")
        claim_overlap = bool(
            isinstance(current_claims, Mapping)
            and isinstance(prior_claims, Mapping)
            and set(current_claims) & set(prior_claims)
        )
        current_types = set(observation.get("typeKeys", []))
        prior_types = set(entry.get("typeKeys", []))
        type_overlap = bool(current_types & prior_types)
        semantically_compatible = bool(
            claim_overlap
            or title_similarity >= 0.55
            or (type_overlap and title_similarity >= 0.35)
        )
        if semantically_compatible:
            candidates.append(str(event_id))
    if len(candidates) == 1:
        return candidates[0], []
    return None, sorted(candidates)


def _event_conflicts(
    observation: Mapping[str, Any],
    matched_event_id: str | None,
    events: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    related: set[str] = set()
    current_date = str(observation.get("publishedDate") or "")
    current_claims = observation.get("scalarClaims")
    if not isinstance(current_claims, Mapping):
        current_claims = {}

    for event_id, entry in events.items():
        prior_dates = _ledger_entry_dates(entry)
        same_effective_date = bool(current_date and current_date in prior_dates)
        prior_claims = entry.get("scalarClaims")
        if same_effective_date and isinstance(prior_claims, Mapping):
            for key in set(current_claims) & set(prior_claims):
                if str(current_claims[key]) == str(prior_claims[key]):
                    continue
                reasons.append(f"同一生效日的结构化字段 {key.rsplit(':', 1)[-1]} 取值冲突")
                related.add(str(event_id))

        current_stage = observation.get("ipoStage")
        prior_stage = entry.get("ipoStage")
        entity_overlap = bool(
            set(observation.get("entityKeys", []))
            & set(entry.get("entityKeys", []))
        )
        if (
            entity_overlap
            and isinstance(current_stage, (list, tuple))
            and len(current_stage) == 2
            and isinstance(prior_stage, (list, tuple))
            and len(prior_stage) == 2
        ):
            current_rank = int(current_stage[1])
            prior_rank = int(prior_stage[1])
            prior_date = max(prior_dates, default="")
            terminal_conflict = {current_rank, prior_rank} == {-1, 6}
            regression = bool(
                current_date
                and prior_date
                and current_date >= prior_date
                and current_rank >= 0
                and prior_rank >= 0
                and current_rank < prior_rank
            )
            if terminal_conflict or regression:
                reasons.append("IPO 状态出现互斥终态或时序回退")
                related.add(str(event_id))

    if matched_event_id and matched_event_id in related and len(related) == 1:
        # A same-URL claim revision still needs review, but retain the stable ID.
        related.add(matched_event_id)
    return list(dict.fromkeys(reasons)), sorted(related)


def _new_ledger_entry(
    event_id: str, observation: Mapping[str, Any], generated_at: str
) -> dict[str, Any]:
    published_date = str(observation.get("publishedDate") or "")
    normalized_title = str(observation.get("normalizedTitle") or "")
    published_dates = [
        str(value) for value in observation.get("publishedDates", []) if value
    ]
    if published_date and published_date not in published_dates:
        published_dates.append(published_date)
    evidence_fingerprints = [
        str(value)
        for value in observation.get("evidenceFingerprints", [])
        if value
    ]
    if not evidence_fingerprints and observation.get("evidenceFingerprint"):
        evidence_fingerprints = [str(observation.get("evidenceFingerprint"))]
    return {
        "eventId": event_id,
        "dataset": observation.get("dataset", ""),
        "entityId": observation.get("entityId", ""),
        "entityName": observation.get("entityName", ""),
        "title": observation.get("title", ""),
        "titleAliases": list(observation.get("titleAliases", []))
        or ([normalized_title] if normalized_title else []),
        "publishedDate": published_date,
        "publishedDates": published_dates,
        "entityKeys": list(observation.get("entityKeys", [])),
        "typeKeys": list(observation.get("typeKeys", [])),
        "numericCues": list(observation.get("numericCues", [])),
        "sourceAliases": list(observation.get("aliases", []))[:MAX_EVENT_ALIASES],
        "evidenceFingerprints": evidence_fingerprints,
        "evidenceSummaries": _merge_event_evidence_summaries(
            [], observation.get("evidenceSummaries", [])
        ),
        "claimFingerprint": observation.get("claimFingerprint", ""),
        "scalarClaims": dict(observation.get("scalarClaims", {})),
        "ipoStage": observation.get("ipoStage"),
        "firstSeenAt": generated_at,
        "lastSeenAt": generated_at,
        "lastPublishedAt": "",
        "lastLifecycle": "first_seen",
        "observationCount": max(1, len(evidence_fingerprints)),
        "confirmationCount": 0,
        "bestEvidenceStrength": int(observation.get("strength") or 0),
        "status": "active",
        "conflictStatus": "none",
        "conflictReasons": [],
        "relatedEventIds": [],
    }


def _merge_limited_strings(
    existing: Any, additions: Iterable[Any], limit: int
) -> list[str]:
    values: list[str] = []
    if isinstance(existing, list):
        values.extend(str(value) for value in existing if value)
    values.extend(str(value) for value in additions if value)
    return list(dict.fromkeys(values))[-limit:]


def _merge_event_evidence_summaries(
    existing: Any, additions: Any
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for collection in (existing, additions):
        if not isinstance(collection, list):
            continue
        for value in collection:
            if not isinstance(value, Mapping):
                continue
            row = {
                str(key): str(item)
                for key, item in value.items()
                if item not in (None, "")
            }
            if row:
                rows.append(row)
    deduplicated: dict[str, dict[str, str]] = {}
    for row in rows:
        key = stable_hash(
            [
                row.get("sourceName"),
                row.get("title"),
                _canonical_event_url(row.get("url")),
                _event_date(row.get("publishedAt")),
            ]
        )
        deduplicated[key] = row
    return list(deduplicated.values())[-MAX_EVENT_EVIDENCE_SUMMARIES:]


def _isolate_possible_conflict(
    events: dict[str, dict[str, Any]],
    event_id: str,
    related_event_ids: Iterable[Any],
    reasons: Iterable[Any],
) -> set[str]:
    involved_event_ids = {
        str(value) for value in [event_id, *related_event_ids] if value
    }
    normalized_reasons = [str(value) for value in reasons if value]
    for involved_event_id in involved_event_ids:
        involved_entry = events.get(involved_event_id)
        if not isinstance(involved_entry, dict):
            continue
        involved_entry["status"] = "needs_review"
        involved_entry["conflictStatus"] = "possible"
        involved_entry["conflictReasons"] = _merge_limited_strings(
            involved_entry.get("conflictReasons"), normalized_reasons, 8
        )
        involved_entry["relatedEventIds"] = _merge_limited_strings(
            involved_entry.get("relatedEventIds"),
            involved_event_ids - {involved_event_id},
            12,
        )
        involved_entry.pop("pendingLifecycle", None)
        involved_entry.pop("pendingSinceAt", None)
    return involved_event_ids


def _classify_event_observation(
    observation: Mapping[str, Any],
    events: dict[str, dict[str, Any]],
    generated_at: str,
    *,
    bootstrap: bool = False,
) -> dict[str, Any]:
    matched_event_id, match_kind, ambiguous_ids = _match_event_entry(
        observation, events
    )
    strength = int(observation.get("strength") or 0)
    strong_correction = bool(
        observation.get("correctionCue")
        and int(observation.get("correctionStrength") or 0) >= 4
    )
    supersedes_event_id = ""
    if matched_event_id is None and strong_correction:
        target_id, correction_candidates = _event_correction_target(
            observation, events
        )
        if target_id:
            supersedes_event_id = target_id
        elif correction_candidates:
            ambiguous_ids = list(dict.fromkeys([*ambiguous_ids, *correction_candidates]))

    if matched_event_id is None:
        event_id = _new_event_id(observation)
        if event_id in events:
            event_id = f"evt-{stable_hash([event_id, observation.get('sourceAlias')])}"
        entry = _new_ledger_entry(event_id, observation, generated_at)
        events[event_id] = entry
        lifecycle = "correction" if strong_correction and supersedes_event_id else "first_seen"
        evidence_is_new = True
        new_evidence_count = max(
            1, len(observation.get("evidenceFingerprints", []))
        )
        strength_increased = False
    else:
        event_id = matched_event_id
        entry = events[event_id]
        prior_evidence = {
            str(value) for value in entry.get("evidenceFingerprints", []) if value
        }
        current_fingerprints = [
            str(value)
            for value in observation.get("evidenceFingerprints", [])
            if value
        ]
        if not current_fingerprints and observation.get("evidenceFingerprint"):
            current_fingerprints = [str(observation.get("evidenceFingerprint"))]
        legacy_fingerprints = [
            str(value)
            for value in observation.get("legacyEvidenceFingerprints", [])
            if value
        ]
        new_evidence_count = sum(
            fingerprint not in prior_evidence
            and (
                index >= len(legacy_fingerprints)
                or legacy_fingerprints[index] not in prior_evidence
            )
            for index, fingerprint in enumerate(current_fingerprints)
        )
        evidence_is_new = new_evidence_count > 0
        prior_strength = int(entry.get("bestEvidenceStrength") or 0)
        strength_increased = strength > prior_strength
        same_claim = str(entry.get("claimFingerprint") or "") == str(
            observation.get("claimFingerprint") or ""
        )
        scalar_claims = observation.get("scalarClaims")
        prior_scalar_claims = entry.get("scalarClaims")
        structured_claim_changed = bool(
            isinstance(scalar_claims, Mapping)
            and scalar_claims
            and isinstance(prior_scalar_claims, Mapping)
            and dict(scalar_claims) != dict(prior_scalar_claims)
        )
        if strong_correction:
            lifecycle = "correction"
        elif same_claim and not evidence_is_new and not strength_increased:
            lifecycle = "duplicate"
        elif structured_claim_changed:
            lifecycle = "updated"
        elif match_kind == "alias" and not same_claim:
            lifecycle = "updated"
        else:
            # A distinct or stronger source confirms the same semantic event. It
            # improves support but is not a second formal change.
            lifecycle = "reconfirmed"
        pending_lifecycle = str(entry.get("pendingLifecycle") or "")
        if (
            pending_lifecycle in {"first_seen", "updated", "correction"}
            and EVENT_LIFECYCLE_PRIORITY.get(pending_lifecycle, -1)
            > EVENT_LIFECYCLE_PRIORITY.get(lifecycle, -1)
        ):
            lifecycle = pending_lifecycle

    reasons, related_event_ids = _event_conflicts(
        observation, matched_event_id or event_id, events
    )
    if ambiguous_ids:
        reasons.append("事件身份匹配到多个历史候选，未自动合并")
        related_event_ids = sorted(
            set([*related_event_ids, *ambiguous_ids])
        )
    if observation.get("correctionCue") and not strong_correction:
        reasons.append("低等级来源包含更正或撤回语义，需原始材料复核")
    if strong_correction:
        # A primary/regulatory correction is an explicit state transition, not
        # an unresolved conflict. Ambiguous correction targets remain review-only.
        if not ambiguous_ids:
            reasons = []
            related_event_ids = []

    entry = events[event_id]
    if (
        matched_event_id is not None
        and not strong_correction
        and (
            entry.get("conflictStatus") == "possible"
            or entry.get("status") == "needs_review"
        )
    ):
        reasons = list(
            dict.fromkeys([*entry.get("conflictReasons", []), *reasons])
        )
        related_event_ids = sorted(
            {
                *[str(value) for value in entry.get("relatedEventIds", []) if value],
                *related_event_ids,
            }
        )
        if not reasons:
            reasons = ["历史潜在冲突尚未完成复核"]

    conflict_status = "possible" if reasons else "none"
    previous_strength = int(entry.get("bestEvidenceStrength") or 0)
    entry["lastSeenAt"] = generated_at
    entry["lastLifecycle"] = lifecycle
    entry["sourceAliases"] = _merge_limited_strings(
        entry.get("sourceAliases"),
        observation.get("aliases", []),
        MAX_EVENT_ALIASES,
    )
    entry["evidenceFingerprints"] = _merge_limited_strings(
        entry.get("evidenceFingerprints"),
        observation.get("evidenceFingerprints", [])
        or [observation.get("evidenceFingerprint")],
        MAX_EVENT_ALIASES,
    )
    entry["evidenceSummaries"] = _merge_event_evidence_summaries(
        entry.get("evidenceSummaries"), observation.get("evidenceSummaries", [])
    )
    entry["titleAliases"] = _merge_limited_strings(
        entry.get("titleAliases"),
        observation.get("titleAliases", [])
        or [observation.get("normalizedTitle")],
        MAX_EVENT_TITLE_ALIASES,
    )
    entry["publishedDates"] = _merge_limited_strings(
        entry.get("publishedDates"),
        observation.get("publishedDates", [])
        or [observation.get("publishedDate")],
        8,
    )
    entry["entityKeys"] = _merge_limited_strings(
        entry.get("entityKeys"), observation.get("entityKeys", []), 16
    )
    entry["typeKeys"] = _merge_limited_strings(
        entry.get("typeKeys"), observation.get("typeKeys", []), 8
    )
    entry["numericCues"] = _merge_limited_strings(
        entry.get("numericCues"), observation.get("numericCues", []), 12
    )
    entry["bestEvidenceStrength"] = max(previous_strength, strength)
    if evidence_is_new:
        entry["observationCount"] = int(entry.get("observationCount") or 0) + (
            0 if matched_event_id is None else new_evidence_count
        )
    if lifecycle == "reconfirmed" and (evidence_is_new or strength_increased):
        entry["confirmationCount"] = int(entry.get("confirmationCount") or 0) + 1
    if lifecycle in {"updated", "correction"} and conflict_status == "none":
        entry["claimFingerprint"] = observation.get("claimFingerprint", "")
        entry["scalarClaims"] = dict(observation.get("scalarClaims", {}))
        entry["ipoStage"] = observation.get("ipoStage")
        entry["title"] = observation.get("title", "")
    elif strength > previous_strength and conflict_status == "none":
        entry["title"] = observation.get("title", entry.get("title", ""))
    if conflict_status == "possible":
        entry["status"] = "needs_review"
        entry["conflictStatus"] = "possible"
        entry["conflictReasons"] = _merge_limited_strings(
            entry.get("conflictReasons"), reasons, 8
        )
        entry["relatedEventIds"] = _merge_limited_strings(
            entry.get("relatedEventIds"), related_event_ids, 12
        )
    elif lifecycle == "correction":
        entry["status"] = "active"
        entry["conflictStatus"] = "none"
        entry["conflictReasons"] = []
        entry["relatedEventIds"] = []
        if supersedes_event_id and supersedes_event_id != event_id:
            entry["supersedesEventId"] = supersedes_event_id
            target = events.get(supersedes_event_id)
            if target is not None:
                target["status"] = "superseded"
                target["supersededByEventId"] = event_id
    if bootstrap:
        entry["lastPublishedAt"] = generated_at
    result = {
        "eventId": event_id,
        "evidenceId": str(observation.get("evidenceId") or ""),
        "evidenceIds": [
            str(value) for value in observation.get("evidenceIds", []) if value
        ],
        "lifecycle": lifecycle,
        "conflictStatus": conflict_status,
        "conflictReasons": reasons,
        "relatedEventIds": related_event_ids,
        "supersedesEventId": supersedes_event_id,
    }
    if (
        conflict_status == "none"
        and lifecycle in {"first_seen", "updated", "correction"}
    ):
        result["acceptedState"] = {
            "title": str(observation.get("title") or ""),
            "claimFingerprint": str(observation.get("claimFingerprint") or ""),
            "scalarClaims": copy.deepcopy(dict(observation.get("scalarClaims", {}))),
            "ipoStage": copy.deepcopy(observation.get("ipoStage")),
            "lastLifecycle": lifecycle,
        }
    return result


def _prune_event_ledger(
    events: Mapping[str, Mapping[str, Any]], generated_at: str
) -> dict[str, dict[str, Any]]:
    generated = _parse_evidence_datetime(generated_at)
    cutoff = (
        generated - timedelta(days=EVENT_LEDGER_RETENTION_DAYS)
        if generated is not None
        else None
    )
    rows: list[tuple[str, dict[str, Any]]] = []
    for event_id, raw_entry in events.items():
        if not isinstance(raw_entry, Mapping):
            continue
        entry = copy.deepcopy(dict(raw_entry))
        entry["eventId"] = str(entry.get("eventId") or event_id)
        last_seen = _parse_evidence_datetime(entry.get("lastSeenAt"))
        if cutoff is not None and last_seen is not None and last_seen < cutoff:
            continue
        rows.append((str(event_id), entry))
    rows.sort(
        key=lambda item: (str(item[1].get("lastSeenAt") or ""), item[0]),
        reverse=True,
    )
    return dict(rows[:MAX_EVENT_LEDGER_ENTRIES])


def _legacy_event_ledger(
    previous_report: Mapping[str, Any]
) -> dict[str, Any]:
    generated_at = str(previous_report.get("generatedAt") or "")
    events: dict[str, dict[str, Any]] = {}
    changes = previous_report.get("changes")
    evidence = previous_report.get("evidence")
    change_rows = [row for row in changes if isinstance(row, Mapping)] if isinstance(changes, list) else []
    evidence_rows = [row for row in evidence if isinstance(row, Mapping)] if isinstance(evidence, list) else []
    evidence_by_change: dict[str, list[Mapping[str, Any]]] = {}
    for row in evidence_rows:
        evidence_by_change.setdefault(str(row.get("changeId") or ""), []).append(row)
    for change in change_rows:
        for observation in _event_observations(
            change, evidence_by_change.get(str(change.get("id") or ""), [])
        ):
            result = _classify_event_observation(
                observation, events, generated_at, bootstrap=True
            )
            if result.get("conflictStatus") == "possible":
                _isolate_possible_conflict(
                    events,
                    str(result.get("eventId") or ""),
                    result.get("relatedEventIds", []),
                    result.get("conflictReasons", []),
                )
    return {
        "schemaVersion": EVENT_LEDGER_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "retentionDays": EVENT_LEDGER_RETENTION_DAYS,
        "events": _prune_event_ledger(events, generated_at),
    }


def _event_change_semantic_assignment_errors(
    change: Mapping[str, Any],
    evidence_rows: Iterable[Mapping[str, Any]],
    events: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Rebuild natural event matches without trusting stored event IDs."""

    event_ids = [str(value) for value in change.get("eventIds", []) if value]
    declared_events = {
        event_id: events[event_id]
        for event_id in event_ids
        if event_id in events and isinstance(events[event_id], Mapping)
    }
    if not event_ids or set(declared_events) != set(event_ids):
        return ["eventIds do not resolve to ledger entries"]
    observations = _event_observations(change, evidence_rows)
    if not observations:
        return ["payload and evidence do not produce an event observation"]
    naturally_matched_ids: set[str] = set()
    for raw_observation in observations:
        observation = copy.deepcopy(dict(raw_observation))
        # eventId/eventIds are compatibility hints for legacy migration only;
        # accepting them here would make this integrity check circular.
        observation["preferredEventIds"] = []
        matched_event_id, _, ambiguous_ids = _match_event_entry(
            observation, declared_events
        )
        if matched_event_id is None or ambiguous_ids:
            return ["payload and evidence do not naturally match declared eventIds"]
        entry = declared_events[matched_event_id]
        if str(entry.get("dataset") or "") != str(
            observation.get("dataset") or ""
        ):
            return ["payload dataset does not match declared ledger event"]
        naturally_matched_ids.add(matched_event_id)
    if naturally_matched_ids != set(event_ids):
        return ["payload observations do not exactly cover declared eventIds"]
    return []


def _event_ledger_entry_validation_errors(
    event_id: str, entry: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    if str(entry.get("eventId") or "") != event_id:
        errors.append("mismatched eventId")
    if _parse_evidence_datetime(entry.get("firstSeenAt")) is None:
        errors.append("invalid firstSeenAt")
    if _parse_evidence_datetime(entry.get("lastSeenAt")) is None:
        errors.append("invalid lastSeenAt")
    if not isinstance(entry.get("claimFingerprint"), str) or not entry.get(
        "claimFingerprint"
    ):
        errors.append("missing claimFingerprint")
    for field in (
        "titleAliases",
        "entityKeys",
        "sourceAliases",
        "evidenceFingerprints",
        "evidenceSummaries",
    ):
        if not isinstance(entry.get(field), list):
            errors.append(f"invalid {field}")
    if not isinstance(entry.get("scalarClaims"), Mapping):
        errors.append("invalid scalarClaims")
    if entry.get("status") not in {"active", "needs_review", "superseded"}:
        errors.append("invalid status")
    if entry.get("conflictStatus") not in {"none", "possible"}:
        errors.append("invalid conflictStatus")
    return errors


def _pending_publication_key(change: Mapping[str, Any]) -> str:
    event_ids = sorted(
        {str(value) for value in change.get("eventIds", []) if value}
    )
    return stable_hash(["pending-publication-v1", event_ids]) if event_ids else ""


def _event_change_identity_errors(change: Mapping[str, Any]) -> list[str]:
    """Validate the redundant public event identity/lifecycle fields.

    The singular fields are intentionally redundant for older consumers. A
    queued payload must not disagree with the arrays/maps that drive replay,
    history, and validation because that could bind one claim to another event.
    """

    errors: list[str] = []
    raw_event_ids = change.get("eventIds")
    if not isinstance(raw_event_ids, list) or not raw_event_ids:
        return ["missing eventIds"]
    event_ids = [str(value) for value in raw_event_ids if value]
    if (
        any(not isinstance(value, str) for value in raw_event_ids)
        or len(event_ids) != len(raw_event_ids)
        or len(set(event_ids)) != len(event_ids)
    ):
        errors.append("invalid or duplicate eventIds")

    raw_lifecycles = change.get("eventLifecycles")
    if not isinstance(raw_lifecycles, Mapping):
        errors.append("missing eventLifecycles")
        lifecycle_by_id: dict[str, str] = {}
    else:
        lifecycle_by_id = {
            str(event_id): str(lifecycle or "")
            for event_id, lifecycle in raw_lifecycles.items()
        }
        if (
            any(not isinstance(event_id, str) for event_id in raw_lifecycles)
            or len(lifecycle_by_id) != len(raw_lifecycles)
            or set(lifecycle_by_id) != set(event_ids)
        ):
            errors.append("eventLifecycles keys do not match eventIds")
        if any(
            lifecycle not in {"first_seen", "updated", "correction"}
            for lifecycle in lifecycle_by_id.values()
        ):
            errors.append("invalid event lifecycle")

    singular_event_id = str(change.get("eventId") or "")
    top_lifecycle = str(change.get("lifecycle") or "")
    if len(event_ids) == 1:
        event_id = event_ids[0]
        if singular_event_id != event_id:
            errors.append("eventId does not match eventIds")
        if top_lifecycle != lifecycle_by_id.get(event_id, ""):
            errors.append("lifecycle does not match eventLifecycles")
    else:
        if singular_event_id:
            errors.append("multi-event change must not have eventId")
        if top_lifecycle != "mixed":
            errors.append("multi-event change lifecycle must be mixed")
    return errors


def _change_claim_projection_errors(change: Mapping[str, Any]) -> list[str]:
    """Ensure public before/after payloads contain only evidence-bound fields."""

    bindings = change.get("claimBindings")
    if not isinstance(bindings, list) or not bindings:
        return ["missing claimBindings"]
    binding_fields = [
        str(binding.get("field") or "")
        for binding in bindings
        if isinstance(binding, Mapping) and binding.get("field")
    ]
    bound_field_set = set(binding_fields)
    if len(binding_fields) != len(bindings) or len(bound_field_set) != len(
        binding_fields
    ):
        return ["invalid or duplicate claim binding fields"]
    errors: list[str] = []
    for field_name in ("claimFields", "changedFields"):
        raw_fields = change.get(field_name)
        if (
            not isinstance(raw_fields, list)
            or len({str(value) for value in raw_fields if value}) != len(raw_fields)
            or {str(value) for value in raw_fields if value} != bound_field_set
        ):
            errors.append(f"{field_name} do not match claim binding fields")
    for side in ("before", "after"):
        payload = change.get(side)
        if payload is None:
            continue
        if not isinstance(payload, Mapping):
            errors.append(f"{side} must be an object or null")
            continue
        unsupported_fields = {str(value) for value in payload} - bound_field_set
        if unsupported_fields:
            errors.append(f"{side} contains fields without claim bindings")
    return errors


def _normalize_pending_publications(
    raw_pending: Any,
    events: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    if not isinstance(raw_pending, list):
        return []
    expanded_pending: list[dict[str, Any]] = []
    for raw_item in raw_pending:
        if not isinstance(raw_item, Mapping):
            continue
        change = raw_item.get("change")
        evidence = raw_item.get("evidence")
        if (
            not isinstance(change, Mapping)
            or not isinstance(evidence, list)
            or _event_change_identity_errors(change)
        ):
            continue
        raw_change_evidence_ids = change.get("evidenceIds")
        if not isinstance(raw_change_evidence_ids, list):
            continue
        declared_evidence_ids = [
            str(value) for value in raw_change_evidence_ids if value
        ]
        raw_evidence_ids = [
            str(row.get("id") or "")
            for row in evidence
            if isinstance(row, Mapping)
        ]
        if (
            len(declared_evidence_ids) != len(raw_change_evidence_ids)
            or len(set(declared_evidence_ids)) != len(declared_evidence_ids)
            or len(raw_evidence_ids) != len(evidence)
            or any(not evidence_id for evidence_id in raw_evidence_ids)
            or len(set(raw_evidence_ids)) != len(raw_evidence_ids)
            or set(raw_evidence_ids) != set(declared_evidence_ids)
        ):
            continue
        raw_evidence_by_id: dict[str, Mapping[str, Any]] = {}
        for row in evidence:
            if not isinstance(row, Mapping):
                continue
            evidence_id = str(row.get("id") or "")
            if evidence_id and evidence_id not in raw_evidence_by_id:
                raw_evidence_by_id[evidence_id] = row
        atoms = _atomize_pending_change(change, raw_evidence_by_id, events)
        for atom in atoms:
            atom_evidence_ids = {
                str(value) for value in atom.get("evidenceIds", []) if value
            }
            expanded_pending.append(
                {
                    "queuedAt": raw_item.get("queuedAt"),
                    "lastSeenAt": raw_item.get("lastSeenAt"),
                    "change": atom,
                    "evidence": [
                        row
                        for row in evidence
                        if isinstance(row, Mapping)
                        and str(row.get("id") or "") in atom_evidence_ids
                    ],
                }
            )
    generated = _parse_evidence_datetime(generated_at)
    cutoff = (
        generated - timedelta(days=EVENT_LEDGER_RETENTION_DAYS)
        if generated is not None
        else None
    )
    deduplicated: dict[str, dict[str, Any]] = {}
    for raw_item in expanded_pending:
        if not isinstance(raw_item, Mapping):
            continue
        change = raw_item.get("change")
        evidence = raw_item.get("evidence")
        if not isinstance(change, Mapping) or not isinstance(evidence, list):
            continue
        if _event_change_identity_errors(change):
            continue
        if (
            change.get("eligibleForKeyDevelopment") is not True
            or change.get("changeType") != "external_event"
            or change.get("publicationTier")
            not in (PUBLICATION_TIERS - {"rejected"})
        ):
            continue
        raw_change_evidence_ids = change.get("evidenceIds")
        if not isinstance(raw_change_evidence_ids, list):
            continue
        evidence_quality = change.get("evidenceQuality")
        if (
            not isinstance(evidence_quality, Mapping)
            or evidence_quality.get("status") != "passed"
            or evidence_quality.get("supporting")
            != len(raw_change_evidence_ids)
            or evidence_quality.get("total")
            != len(raw_change_evidence_ids)
        ):
            continue
        key = _pending_publication_key(change)
        queued_at = str(raw_item.get("queuedAt") or "")
        queued = _parse_evidence_datetime(queued_at)
        if not key or queued is None or (cutoff is not None and queued < cutoff):
            continue
        event_ids = [str(value) for value in change.get("eventIds", []) if value]
        if len(event_ids) != 1 or any(
            event_id not in events for event_id in event_ids
        ):
            continue
        if any(
            events[event_id].get("conflictStatus") == "possible"
            or events[event_id].get("status") != "active"
            for event_id in event_ids
        ):
            continue
        change_id = str(change.get("id") or "")
        change_evidence_ids = [
            str(value) for value in change.get("evidenceIds", []) if value
        ]
        supporting_evidence_ids = change.get("supportingEvidenceIds")
        normalized_supporting_evidence_ids = (
            [str(value) for value in supporting_evidence_ids if value]
            if isinstance(supporting_evidence_ids, list)
            else []
        )
        if (
            not isinstance(supporting_evidence_ids, list)
            or any(not isinstance(value, str) for value in supporting_evidence_ids)
            or len(normalized_supporting_evidence_ids)
            != len(supporting_evidence_ids)
            or len(set(normalized_supporting_evidence_ids))
            != len(normalized_supporting_evidence_ids)
            or set(normalized_supporting_evidence_ids) != set(change_evidence_ids)
        ):
            continue
        evidence_by_id: dict[str, Mapping[str, Any]] = {}
        valid_evidence = True
        for row in evidence:
            if not isinstance(row, Mapping):
                valid_evidence = False
                break
            evidence_id = str(row.get("id") or "")
            if (
                not evidence_id
                or evidence_id in evidence_by_id
                or str(row.get("changeId") or "") != change_id
                or row.get("qualityStatus") != "passed"
                or row.get("supportStatus") != "supports"
            ):
                valid_evidence = False
                break
            evidence_by_id[evidence_id] = row
        if (
            not valid_evidence
            or not change_evidence_ids
            or set(change_evidence_ids) != set(evidence_by_id)
        ):
            continue
        bindings = change.get("claimBindings")
        if not isinstance(bindings, list) or not bindings:
            continue
        binding_valid = True
        bound_evidence_ids: set[str] = set()
        for binding in bindings:
            if not isinstance(binding, Mapping):
                binding_valid = False
                break
            raw_binding_ids = binding.get("evidenceIds")
            if not isinstance(raw_binding_ids, list):
                binding_valid = False
                break
            normalized_binding_ids = [
                str(value) for value in raw_binding_ids if value
            ]
            if (
                any(not isinstance(value, str) for value in raw_binding_ids)
                or len(normalized_binding_ids) != len(raw_binding_ids)
                or len(set(normalized_binding_ids)) != len(normalized_binding_ids)
            ):
                binding_valid = False
                break
            binding_ids = set(normalized_binding_ids)
            field = str(binding.get("field") or "")
            if not binding_ids or not binding_ids <= set(change_evidence_ids):
                binding_valid = False
                break
            bound_evidence_ids.update(binding_ids)
            if any(
                not isinstance(evidence_by_id[evidence_id].get("claimFields"), list)
                or field not in {
                    str(value)
                    for value in evidence_by_id[evidence_id].get(
                        "claimFields", []
                    )
                }
                for evidence_id in binding_ids
            ):
                binding_valid = False
                break
        claim_fields = change.get("claimFields")
        binding_fields = {
            str(binding.get("field") or "")
            for binding in bindings
            if isinstance(binding, Mapping)
        }
        if (
            not binding_valid
            or bound_evidence_ids != set(change_evidence_ids)
            or not isinstance(claim_fields, list)
            or {str(value) for value in claim_fields if value} != binding_fields
        ):
            continue
        if _change_claim_projection_errors(change):
            continue
        if _event_change_semantic_assignment_errors(change, evidence, events):
            continue
        normalized_item = {
            "pendingId": f"pending-{key}",
            "queuedAt": queued_at,
            "lastSeenAt": str(raw_item.get("lastSeenAt") or queued_at),
            "change": copy.deepcopy(dict(change)),
            "evidence": [copy.deepcopy(dict(row)) for row in evidence],
        }
        existing_item = deduplicated.get(key)
        existing_change = (
            existing_item.get("change")
            if isinstance(existing_item, Mapping)
            and isinstance(existing_item.get("change"), Mapping)
            else {}
        )
        new_priority = EVENT_LIFECYCLE_PRIORITY.get(
            str(change.get("lifecycle") or ""), -1
        )
        existing_priority = EVENT_LIFECYCLE_PRIORITY.get(
            str(existing_change.get("lifecycle") or ""), -1
        )
        if (
            existing_item is None
            or new_priority > existing_priority
            or (
                new_priority == existing_priority
                and normalized_item["lastSeenAt"]
                >= str(existing_item.get("lastSeenAt") or "")
            )
        ):
            deduplicated[key] = normalized_item
    rows = sorted(
        deduplicated.values(),
        key=lambda item: (str(item.get("queuedAt") or ""), str(item["pendingId"])),
    )
    return rows[:MAX_PENDING_PUBLICATIONS]


def _load_event_ledger(
    previous_report: Mapping[str, Any], generated_at: str
) -> dict[str, Any]:
    raw_ledger = previous_report.get("eventLedger")
    if (
        isinstance(raw_ledger, Mapping)
        and raw_ledger.get("schemaVersion") == EVENT_LEDGER_SCHEMA_VERSION
        and isinstance(raw_ledger.get("events"), Mapping)
    ):
        normalized_events: dict[str, Mapping[str, Any]] = {}
        for raw_event_id, raw_entry in raw_ledger["events"].items():
            event_id = str(raw_event_id or "")
            if not event_id or not isinstance(raw_entry, Mapping):
                continue
            declared_event_id = str(raw_entry.get("eventId") or event_id)
            if declared_event_id != event_id:
                # A mismatched key can bind an observation to the wrong claim.
                # Drop it and allow conservative rediscovery instead.
                continue
            entry = copy.deepcopy(dict(raw_entry))
            entry["eventId"] = event_id
            if _event_ledger_entry_validation_errors(event_id, entry):
                continue
            normalized_events[event_id] = entry
        events = _prune_event_ledger(normalized_events, generated_at)
        pending_publications = _normalize_pending_publications(
            raw_ledger.get("pendingPublications"), events, generated_at
        )
        return {
            "schemaVersion": EVENT_LEDGER_SCHEMA_VERSION,
            "generatedAt": generated_at,
            "retentionDays": EVENT_LEDGER_RETENTION_DAYS,
            "events": events,
            "pendingPublications": pending_publications,
        }
    ledger = _legacy_event_ledger(previous_report)
    ledger["generatedAt"] = generated_at
    ledger["events"] = _prune_event_ledger(ledger.get("events", {}), generated_at)
    ledger["pendingPublications"] = []
    return ledger


EVENT_LIFECYCLE_PRIORITY = {
    "duplicate": 0,
    "reconfirmed": 1,
    "first_seen": 2,
    "updated": 3,
    "correction": 4,
}


def _filter_market_news_rows(value: Any, normalized_titles: set[str]) -> Any:
    if not isinstance(value, list) or not normalized_titles:
        return copy.deepcopy(value)
    matched: list[Any] = []
    for row in value:
        raw_title = row.get("title") if isinstance(row, Mapping) else row
        if _normalized_event_title(raw_title) in normalized_titles:
            matched.append(copy.deepcopy(row))
    return matched


def _build_public_event_change(
    candidate: Mapping[str, Any],
    event_ids: list[str],
    lifecycles: Mapping[str, str],
    formal_evidence_ids: set[str],
    events: Mapping[str, Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    generated_at: str,
    evidence_ids_by_event: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    public_candidate = copy.deepcopy(dict(candidate))
    raw_supporting_ids = candidate.get("supportingEvidenceIds")
    if not isinstance(raw_supporting_ids, list):
        raw_supporting_ids = candidate.get("evidenceIds")
    selected_ids = [
        str(evidence_id)
        for evidence_id in raw_supporting_ids
        if str(evidence_id) in formal_evidence_ids
    ] if isinstance(raw_supporting_ids, list) else []
    public_candidate["evidenceIds"] = selected_ids
    public_candidate["supportingEvidenceIds"] = selected_ids
    public_candidate["eventIds"] = event_ids
    public_candidate["eventLifecycles"] = dict(lifecycles)
    if evidence_ids_by_event is not None:
        public_candidate["_eventEvidenceIds"] = {
            event_id: [
                str(evidence_id)
                for evidence_id in evidence_ids_by_event.get(event_id, [])
                if str(evidence_id) in formal_evidence_ids
            ]
            for event_id in event_ids
        }
    public_candidate.pop("eventId", None)
    if len(event_ids) == 1:
        public_candidate["eventId"] = event_ids[0]
        public_candidate["lifecycle"] = lifecycles[event_ids[0]]
    else:
        public_candidate["lifecycle"] = "mixed"
    first_seen_values = [
        str(events[event_id].get("firstSeenAt") or "")
        for event_id in event_ids
        if event_id in events
    ]
    public_candidate["firstSeenAt"] = min(
        (value for value in first_seen_values if value), default=generated_at
    )
    public_candidate["lastSeenAt"] = generated_at
    bindings = public_candidate.get("claimBindings")
    if isinstance(bindings, list):
        filtered_bindings = []
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            binding_ids = [
                str(evidence_id)
                for evidence_id in binding.get("evidenceIds", [])
                if str(evidence_id) in formal_evidence_ids
            ]
            if not binding_ids:
                continue
            binding["evidenceIds"] = binding_ids
            filtered_bindings.append(binding)
        public_candidate["claimBindings"] = filtered_bindings
    public_bindings = public_candidate.get("claimBindings")
    bound_fields = list(
        dict.fromkeys(
            str(binding.get("field") or "")
            for binding in public_bindings
            if isinstance(binding, Mapping) and binding.get("field")
        )
    ) if isinstance(public_bindings, list) else []
    public_candidate["claimFields"] = bound_fields
    public_candidate["changedFields"] = bound_fields
    public_candidate.pop("unsupportedClaimFields", None)
    for side in ("before", "after"):
        payload = public_candidate.get(side)
        if isinstance(payload, Mapping):
            public_candidate[side] = {
                field: copy.deepcopy(payload[field])
                for field in bound_fields
                if field in payload
            }
    public_candidate["evidenceQuality"] = {
        "status": "passed",
        "supporting": len(selected_ids),
        "total": len(selected_ids),
    }
    if (
        public_candidate.get("dataset") == "marketCompany"
        and "news"
        in {str(value) for value in public_candidate.get("changedFields", [])}
    ):
        formal_news_titles = {
            _normalized_event_title(evidence_by_id[evidence_id].get("title"))
            for evidence_id in selected_ids
            if evidence_id in evidence_by_id
        }
        for side in ("before", "after"):
            payload = public_candidate.get(side)
            if isinstance(payload, Mapping) and isinstance(
                payload.get("news"), list
            ):
                filtered_payload = copy.deepcopy(dict(payload))
                filtered_payload["news"] = _filter_market_news_rows(
                    payload["news"], formal_news_titles
                )
                public_candidate[side] = filtered_payload
        filtered_bindings = public_candidate.get("claimBindings")
        if isinstance(filtered_bindings, list):
            for binding in filtered_bindings:
                if not isinstance(binding, dict) or binding.get("field") != "news":
                    continue
                binding["before"] = _filter_market_news_rows(
                    binding.get("before"), formal_news_titles
                )
                binding["after"] = _filter_market_news_rows(
                    binding.get("after"), formal_news_titles
                )
    return public_candidate


def _atomize_pending_change(
    change: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    events: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Split a queued multi-event package into independently replayable events."""

    event_ids = [str(value) for value in change.get("eventIds", []) if value]
    if not event_ids:
        return []
    if len(event_ids) == 1:
        atom = copy.deepcopy(dict(change))
        atom.pop("_eventEvidenceIds", None)
        return [atom]
    if not (
        change.get("dataset") == "marketCompany"
        and {str(value) for value in change.get("changedFields", [])} == {"news"}
    ):
        # Only rolling market news is currently projected into multiple
        # independent events. Other multi-event payloads need a dataset-specific
        # projector rather than copying a sibling's before/after claim.
        return []
    raw_bindings = change.get("claimBindings")
    if not isinstance(raw_bindings, list) or any(
        not isinstance(binding, Mapping) or binding.get("field") != "news"
        for binding in raw_bindings
    ):
        return []

    raw_change_evidence_ids = change.get("evidenceIds")
    if not isinstance(raw_change_evidence_ids, list):
        return []
    change_evidence_ids = [
        str(value) for value in raw_change_evidence_ids if value
    ]
    if (
        len(change_evidence_ids) != len(raw_change_evidence_ids)
        or len(set(change_evidence_ids)) != len(change_evidence_ids)
    ):
        return []
    raw_mapping = change.get("_eventEvidenceIds")
    evidence_ids_by_event: dict[str, list[str]] = {}
    if isinstance(raw_mapping, Mapping):
        if {str(value) for value in raw_mapping} != set(event_ids):
            return []
        for event_id in event_ids:
            raw_ids = raw_mapping.get(event_id)
            if isinstance(raw_ids, list):
                evidence_ids_by_event[event_id] = [
                    str(value)
                    for value in raw_ids
                    if str(value) in change_evidence_ids
                ]
                if (
                    len(evidence_ids_by_event[event_id]) != len(raw_ids)
                    or len(set(evidence_ids_by_event[event_id]))
                    != len(evidence_ids_by_event[event_id])
                ):
                    return []
    else:
        # Migrate queues written before atomization. Ledger fingerprints were
        # generated from each source row, so they provide an exact, stable
        # event-to-evidence join without trusting a rolling news-array position.
        for evidence_id in change_evidence_ids:
            row = evidence_by_id.get(evidence_id)
            if not isinstance(row, Mapping):
                continue
            observation = _event_observation_from_evidence_group(
                change, [row], use_evidence_title=True
            )
            fingerprints = {
                str(value)
                for value in observation.get("evidenceFingerprints", [])
                if value
            }
            normalized_title = str(observation.get("normalizedTitle") or "")
            matches: list[tuple[int, str]] = []
            for event_id in event_ids:
                entry = events.get(event_id)
                if not isinstance(entry, Mapping):
                    continue
                entry_fingerprints = {
                    str(value)
                    for value in entry.get("evidenceFingerprints", [])
                    if value
                }
                title_aliases = {
                    str(value) for value in entry.get("titleAliases", []) if value
                }
                score = 0
                if fingerprints & entry_fingerprints:
                    score = 2
                elif normalized_title and normalized_title in title_aliases:
                    score = 1
                if score:
                    matches.append((score, event_id))
            if matches:
                best_score = max(score for score, _ in matches)
                best_ids = [
                    event_id for score, event_id in matches if score == best_score
                ]
                if len(best_ids) == 1:
                    evidence_ids_by_event.setdefault(best_ids[0], []).append(
                        evidence_id
                    )

    assigned_evidence_ids = [
        evidence_id
        for event_id in event_ids
        for evidence_id in evidence_ids_by_event.get(event_id, [])
    ]
    if (
        any(not evidence_ids_by_event.get(event_id) for event_id in event_ids)
        or len(assigned_evidence_ids) != len(set(assigned_evidence_ids))
        or set(assigned_evidence_ids) != set(change_evidence_ids)
    ):
        # Ambiguous evidence must never be copied into multiple semantic claims.
        return []

    lifecycles = change.get("eventLifecycles")
    if not isinstance(lifecycles, Mapping):
        return []
    atoms: list[dict[str, Any]] = []
    for event_id in event_ids:
        selected_set = set(evidence_ids_by_event[event_id])
        selected_ids = [
            evidence_id
            for evidence_id in change_evidence_ids
            if evidence_id in selected_set
        ]
        if not selected_ids:
            return []
        atom = copy.deepcopy(dict(change))
        atom.pop("_eventEvidenceIds", None)
        atom["eventIds"] = [event_id]
        atom["eventId"] = event_id
        lifecycle = str(lifecycles.get(event_id) or "")
        atom["eventLifecycles"] = {event_id: lifecycle}
        atom["lifecycle"] = lifecycle
        atom["evidenceIds"] = selected_ids
        atom["supportingEvidenceIds"] = list(selected_ids)
        bindings = atom.get("claimBindings")
        if not isinstance(bindings, list):
            return []
        filtered_bindings: list[dict[str, Any]] = []
        for raw_binding in bindings:
            if not isinstance(raw_binding, Mapping):
                continue
            binding = copy.deepcopy(dict(raw_binding))
            binding_ids = [
                str(value)
                for value in binding.get("evidenceIds", [])
                if str(value) in selected_set
            ]
            if not binding_ids:
                continue
            binding["evidenceIds"] = binding_ids
            filtered_bindings.append(binding)
        if not filtered_bindings:
            return []
        atom["claimBindings"] = filtered_bindings
        atom["claimFields"] = list(
            dict.fromkeys(str(binding.get("field") or "") for binding in filtered_bindings)
        )
        atom["evidenceQuality"] = {
            "status": "passed",
            "supporting": len(selected_ids),
            "total": len(selected_ids),
        }
        if (
            atom.get("dataset") == "marketCompany"
            and "news" in {str(value) for value in atom.get("changedFields", [])}
        ):
            selected_titles = {
                _normalized_event_title(evidence_by_id[evidence_id].get("title"))
                for evidence_id in selected_ids
                if evidence_id in evidence_by_id
            }
            for side in ("before", "after"):
                payload = atom.get(side)
                if isinstance(payload, Mapping) and isinstance(
                    payload.get("news"), list
                ):
                    filtered_payload = copy.deepcopy(dict(payload))
                    filtered_payload["news"] = _filter_market_news_rows(
                        payload["news"], selected_titles
                    )
                    atom[side] = filtered_payload
            for binding in filtered_bindings:
                if binding.get("field") != "news":
                    continue
                binding["before"] = _filter_market_news_rows(
                    binding.get("before"), selected_titles
                )
                binding["after"] = _filter_market_news_rows(
                    binding.get("after"), selected_titles
                )
        atoms.append(atom)
    return atoms


def _prepare_pending_replays(
    ledger: Mapping[str, Any],
    events: dict[str, dict[str, Any]],
    candidate_evidence: list[dict[str, Any]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    pending = ledger.get("pendingPublications")
    if not isinstance(pending, list):
        return [], {}
    used_evidence_ids = {
        str(row.get("id") or "")
        for row in candidate_evidence
        if isinstance(row, Mapping) and row.get("id")
    }
    replay_counter = 1

    def next_evidence_id() -> str:
        nonlocal replay_counter
        while True:
            candidate = f"RPE{replay_counter:03d}"
            replay_counter += 1
            if candidate not in used_evidence_ids:
                used_evidence_ids.add(candidate)
                return candidate

    replay_changes: list[dict[str, Any]] = []
    queued_at_by_key: dict[str, str] = {}
    for item in pending:
        if not isinstance(item, Mapping):
            continue
        raw_change = item.get("change")
        raw_evidence = item.get("evidence")
        if not isinstance(raw_change, Mapping) or not isinstance(raw_evidence, list):
            continue
        event_ids = [
            str(value) for value in raw_change.get("eventIds", []) if value
        ]
        if not event_ids or any(
            event_id not in events
            or events[event_id].get("status") != "active"
            or events[event_id].get("conflictStatus") == "possible"
            for event_id in event_ids
        ):
            continue
        pending_key = _pending_publication_key(raw_change)
        queued_at_by_key[pending_key] = str(item.get("queuedAt") or generated_at)
        replay_change_id = f"pending-{pending_key}"
        evidence_id_map: dict[str, str] = {}
        replay_evidence: list[dict[str, Any]] = []
        for raw_row in raw_evidence:
            if not isinstance(raw_row, Mapping):
                continue
            old_evidence_id = str(raw_row.get("id") or "")
            new_evidence_id = next_evidence_id()
            evidence_id_map[old_evidence_id] = new_evidence_id
            row = copy.deepcopy(dict(raw_row))
            row["id"] = new_evidence_id
            row["changeId"] = replay_change_id
            replay_evidence.append(row)
        if len(evidence_id_map) != len(raw_evidence):
            continue
        change = copy.deepcopy(dict(raw_change))
        change["sourceChangeId"] = change.get("sourceChangeId") or change.get("id")
        change["id"] = replay_change_id
        change["evidenceIds"] = [
            evidence_id_map[str(value)]
            for value in change.get("evidenceIds", [])
            if str(value) in evidence_id_map
        ]
        change["supportingEvidenceIds"] = list(change["evidenceIds"])
        bindings = change.get("claimBindings")
        if isinstance(bindings, list):
            for binding in bindings:
                if not isinstance(binding, dict):
                    continue
                binding["evidenceIds"] = [
                    evidence_id_map[str(value)]
                    for value in binding.get("evidenceIds", [])
                    if str(value) in evidence_id_map
                ]
        change["lastSeenAt"] = generated_at
        change["replayedFromPending"] = True
        replay_changes.append(change)
        candidate_evidence.extend(replay_evidence)
        for event_id in event_ids:
            events[event_id].pop("pendingLifecycle", None)
            events[event_id].pop("pendingSinceAt", None)
    return replay_changes, queued_at_by_key


def _build_pending_publication(
    change: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    queued_at: str,
    generated_at: str,
) -> dict[str, Any] | None:
    event_ids = [str(value) for value in change.get("eventIds", []) if value]
    evidence_ids = [
        str(value) for value in change.get("evidenceIds", []) if value
    ]
    if not event_ids or not evidence_ids:
        return None
    evidence = [
        copy.deepcopy(dict(evidence_by_id[evidence_id]))
        for evidence_id in evidence_ids
        if evidence_id in evidence_by_id
    ]
    if len(evidence) != len(evidence_ids):
        return None
    payload = copy.deepcopy(dict(change))
    payload.pop("replayedFromPending", None)
    return {
        "pendingId": f"pending-{_pending_publication_key(payload)}",
        "queuedAt": queued_at,
        "lastSeenAt": generated_at,
        "change": payload,
        "evidence": evidence,
    }


def reconcile_event_ledger(
    previous_report: Mapping[str, Any],
    packaged_candidates: list[dict[str, Any]],
    candidate_evidence: list[dict[str, Any]],
    *,
    generated_at: str,
    publish_limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Assign stable cross-run event IDs and retain only material event changes.

    Evidence IDs remain run-local locators. Stable identity is carried by the
    bounded ledger and never replaces snapshot ``entityId`` values.
    """

    ledger = _load_event_ledger(previous_report, generated_at)
    events = ledger["events"]
    prior_last_published = {
        str(event_id): str(entry.get("lastPublishedAt") or "")
        for event_id, entry in events.items()
        if isinstance(entry, Mapping)
    }
    replay_changes, pending_queued_at_by_key = _prepare_pending_replays(
        ledger, events, candidate_evidence, generated_at
    )
    evidence_by_change: dict[str, list[Mapping[str, Any]]] = {}
    evidence_by_id: dict[str, Mapping[str, Any]] = {}
    for row in candidate_evidence:
        if not isinstance(row, Mapping):
            continue
        evidence_by_change.setdefault(str(row.get("changeId") or ""), []).append(row)
        evidence_id = str(row.get("id") or "")
        if evidence_id:
            evidence_by_id[evidence_id] = row

    formal_changes: list[dict[str, Any]] = replay_changes
    forced_pending_changes: list[dict[str, Any]] = []
    event_states: dict[str, str] = {
        str(event_id): str(lifecycle)
        for change in replay_changes
        for event_id, lifecycle in (
            change.get("eventLifecycles", {}).items()
            if isinstance(change.get("eventLifecycles"), Mapping)
            else []
        )
    }
    conflict_event_ids: set[str] = set()
    review_queue: list[dict[str, Any]] = []
    accepted_event_states: dict[str, tuple[int, int, dict[str, Any]]] = {}
    observation_sequence = 0

    for candidate in packaged_candidates:
        if candidate.get("eligibleForKeyDevelopment") is not True:
            continue
        observations = _event_observations(
            candidate,
            evidence_by_change.get(str(candidate.get("id") or ""), []),
        )
        results = [
            _classify_event_observation(observation, events, generated_at)
            for observation in observations
        ]
        for result in results:
            lifecycle = str(result.get("lifecycle") or "")
            accepted_state = result.get("acceptedState")
            if isinstance(accepted_state, Mapping):
                event_id = str(result.get("eventId") or "")
                score = (
                    EVENT_LIFECYCLE_PRIORITY.get(lifecycle, -1),
                    observation_sequence,
                )
                existing = accepted_event_states.get(event_id)
                if existing is None or score > existing[:2]:
                    accepted_event_states[event_id] = (
                        score[0],
                        score[1],
                        copy.deepcopy(dict(accepted_state)),
                    )
            observation_sequence += 1
        grouped: dict[str, list[dict[str, Any]]] = {}
        for result in results:
            grouped.setdefault(result["eventId"], []).append(result)

        formal_event_ids: list[str] = []
        formal_evidence_ids: set[str] = set()
        formal_evidence_ids_by_event: dict[str, set[str]] = {}
        formal_lifecycles: dict[str, str] = {}
        candidate_conflicts: list[dict[str, Any]] = []
        for event_id, event_results in grouped.items():
            lifecycle = max(
                (str(result["lifecycle"]) for result in event_results),
                key=lambda value: EVENT_LIFECYCLE_PRIORITY.get(value, -1),
            )
            current_state = event_states.get(event_id)
            if current_state is None or EVENT_LIFECYCLE_PRIORITY[lifecycle] > EVENT_LIFECYCLE_PRIORITY[current_state]:
                event_states[event_id] = lifecycle
            conflicts = [
                result
                for result in event_results
                if result.get("conflictStatus") == "possible"
            ]
            if conflicts:
                reasons = list(
                    dict.fromkeys(
                        reason
                        for result in conflicts
                        for reason in result.get("conflictReasons", [])
                    )
                )
                related = sorted(
                    {
                        related_id
                        for result in conflicts
                        for related_id in result.get("relatedEventIds", [])
                    }
                )
                involved_event_ids = _isolate_possible_conflict(
                    events, event_id, related, reasons
                )
                conflict_event_ids.update(involved_event_ids)
                conflict_evidence_ids = list(
                    dict.fromkeys(
                        str(evidence_id)
                        for result in event_results
                        for evidence_id in (
                            result.get("evidenceIds")
                            or [result.get("evidenceId")]
                        )
                        if evidence_id
                    )
                )
                candidate_conflicts.append(
                    {
                        "eventId": event_id,
                        "reasons": reasons,
                        "relatedEventIds": related,
                        "evidenceIds": conflict_evidence_ids,
                        "evidence": [
                            copy.deepcopy(dict(evidence_by_id[evidence_id]))
                            for evidence_id in conflict_evidence_ids[:8]
                            if evidence_id in evidence_by_id
                        ],
                        "historicalEvidence": _merge_event_evidence_summaries(
                            [],
                            [
                                summary
                                for involved_event_id in involved_event_ids
                                for summary in events.get(
                                    involved_event_id, {}
                                ).get("evidenceSummaries", [])
                            ],
                        ),
                    }
                )
                continue
            if lifecycle not in {"first_seen", "updated", "correction"}:
                continue
            formal_event_ids.append(event_id)
            formal_lifecycles[event_id] = lifecycle
            event_evidence_ids = {
                str(evidence_id)
                for result in event_results
                for evidence_id in (
                    result.get("evidenceIds") or [result.get("evidenceId")]
                )
                if evidence_id
            }
            formal_evidence_ids_by_event[event_id] = event_evidence_ids
            formal_evidence_ids.update(event_evidence_ids)

        if candidate_conflicts:
            review_queue.append(
                {
                    "changeId": candidate.get("id"),
                    "entityName": candidate.get("entityName"),
                    "summary": candidate.get("summary"),
                    "status": "possible_conflict",
                    "events": candidate_conflicts,
                }
            )
            # A packaged change can carry a shared summary/before/after object.
            # If any component is conflicted, do not leak that unsplit claim to
            # the model through another otherwise-formal component.
            safe_event_ids = [
                event_id
                for event_id in formal_event_ids
                if event_id not in conflict_event_ids
            ]
            safe_lifecycles = {
                event_id: formal_lifecycles[event_id]
                for event_id in safe_event_ids
            }
            safe_evidence_ids = {
                str(evidence_id)
                for event_id in safe_event_ids
                for result in grouped.get(event_id, [])
                for evidence_id in (
                    result.get("evidenceIds") or [result.get("evidenceId")]
                )
                if evidence_id
            }
            safe_evidence_ids_by_event = {
                event_id: {
                    str(evidence_id)
                    for result in grouped.get(event_id, [])
                    for evidence_id in (
                        result.get("evidenceIds") or [result.get("evidenceId")]
                    )
                    if evidence_id
                }
                for event_id in safe_event_ids
            }
            if safe_event_ids and safe_evidence_ids:
                forced_pending_changes.append(
                    _build_public_event_change(
                        candidate,
                        safe_event_ids,
                        safe_lifecycles,
                        safe_evidence_ids,
                        events,
                        evidence_by_id,
                        generated_at,
                        safe_evidence_ids_by_event,
                    )
                )
            for event_id in safe_event_ids:
                entry = events.get(event_id)
                if not isinstance(entry, dict):
                    continue
                entry["lastPublishedAt"] = prior_last_published.get(event_id, "")
                entry["pendingLifecycle"] = formal_lifecycles[event_id]
                entry.setdefault("pendingSinceAt", generated_at)
            continue
        if not formal_event_ids:
            continue
        formal_changes.append(
            _build_public_event_change(
                candidate,
                formal_event_ids,
                formal_lifecycles,
                formal_evidence_ids,
                events,
                evidence_by_id,
                generated_at,
                formal_evidence_ids_by_event,
            )
        )

    for event_id, (_, _, accepted_state) in accepted_event_states.items():
        entry = events.get(event_id)
        if (
            not isinstance(entry, dict)
            or event_id in conflict_event_ids
            or entry.get("status") != "active"
            or entry.get("conflictStatus") == "possible"
        ):
            continue
        entry.update(copy.deepcopy(accepted_state))

    # Keep the pre-filter atoms available for queueing. A later observation can
    # isolate one event in a multi-news change; its active siblings must remain
    # replayable even though the mixed public package is no longer publishable.
    queue_source_changes = list(formal_changes)
    current_formal_event_ids = {
        str(event_id)
        for change in formal_changes
        if change.get("replayedFromPending") is not True
        for event_id in change.get("eventIds", [])
        if event_id
    }
    formal_changes = [
        change
        for change in formal_changes
        if not (
            {str(event_id) for event_id in change.get("eventIds", [])}
            & conflict_event_ids
        )
        and not any(
            events.get(str(event_id), {}).get("status") == "superseded"
            for event_id in change.get("eventIds", [])
        )
        and not (
            change.get("replayedFromPending") is True
            and {
                str(event_id) for event_id in change.get("eventIds", [])
            }
            & current_formal_event_ids
        )
    ]
    preferred_single_change: dict[str, tuple[int, int]] = {}
    for index, change in enumerate(formal_changes):
        event_ids = [str(value) for value in change.get("eventIds", []) if value]
        if len(event_ids) != 1:
            continue
        event_id = event_ids[0]
        lifecycles = change.get("eventLifecycles")
        lifecycle = (
            str(lifecycles.get(event_id) or "")
            if isinstance(lifecycles, Mapping)
            else str(change.get("lifecycle") or "")
        )
        score = (EVENT_LIFECYCLE_PRIORITY.get(lifecycle, -1), index)
        if score > preferred_single_change.get(event_id, (-1, -1)):
            preferred_single_change[event_id] = score
    preferred_single_indices = {
        index for _, index in preferred_single_change.values()
    }
    formal_changes = [
        change
        for index, change in enumerate(formal_changes)
        if len([value for value in change.get("eventIds", []) if value]) != 1
        or index in preferred_single_indices
    ]
    all_formal_changes = formal_changes
    if publish_limit is not None:
        formal_changes = all_formal_changes[: max(0, int(publish_limit))]
    published_event_ids = {
        str(event_id)
        for change in formal_changes
        for event_id in change.get("eventIds", [])
        if event_id
    }
    for change in all_formal_changes:
        lifecycles = change.get("eventLifecycles")
        lifecycle_by_id = lifecycles if isinstance(lifecycles, Mapping) else {}
        for raw_event_id in change.get("eventIds", []):
            event_id = str(raw_event_id)
            entry = events.get(event_id)
            if not isinstance(entry, dict):
                continue
            if event_id in published_event_ids:
                entry["lastPublishedAt"] = generated_at
                entry.pop("pendingLifecycle", None)
                entry.pop("pendingSinceAt", None)
                continue
            lifecycle = str(lifecycle_by_id.get(event_id) or "first_seen")
            entry["lastPublishedAt"] = prior_last_published.get(event_id, "")
            entry["pendingLifecycle"] = lifecycle
            entry.setdefault("pendingSinceAt", generated_at)
    ledger["events"] = _prune_event_ledger(events, generated_at)
    pending_candidates: list[dict[str, Any]] = []
    for change in [*queue_source_changes, *forced_pending_changes]:
        for atom in _atomize_pending_change(
            change, evidence_by_id, ledger["events"]
        ):
            atom_event_ids = {
                str(value) for value in atom.get("eventIds", []) if value
            }
            if atom_event_ids & published_event_ids:
                continue
            pending_candidates.append(atom)
    raw_pending_publications: list[dict[str, Any]] = []
    for change in pending_candidates:
        event_ids = [str(value) for value in change.get("eventIds", []) if value]
        if not event_ids or any(
            event_id not in ledger["events"]
            or ledger["events"][event_id].get("status") != "active"
            or ledger["events"][event_id].get("conflictStatus") == "possible"
            for event_id in event_ids
        ):
            continue
        pending_key = _pending_publication_key(change)
        item = _build_pending_publication(
            change,
            evidence_by_id,
            pending_queued_at_by_key.get(pending_key, generated_at),
            generated_at,
        )
        if item is not None:
            raw_pending_publications.append(item)
    ledger["pendingPublications"] = _normalize_pending_publications(
        raw_pending_publications, ledger["events"], generated_at
    )
    queued_event_ids = {
        str(event_id)
        for item in ledger["pendingPublications"]
        for event_id in item.get("change", {}).get("eventIds", [])
        if event_id
    }
    for item in ledger["pendingPublications"]:
        change = item.get("change")
        if not isinstance(change, Mapping):
            continue
        lifecycles = change.get("eventLifecycles")
        lifecycle_by_id = lifecycles if isinstance(lifecycles, Mapping) else {}
        for raw_event_id in change.get("eventIds", []):
            event_id = str(raw_event_id)
            entry = ledger["events"].get(event_id)
            if not isinstance(entry, dict):
                continue
            entry["lastPublishedAt"] = prior_last_published.get(event_id, "")
            entry["pendingLifecycle"] = str(
                lifecycle_by_id.get(event_id) or "first_seen"
            )
            entry.setdefault("pendingSinceAt", str(item.get("queuedAt") or generated_at))
    for event_id, entry in ledger["events"].items():
        if event_id not in queued_event_ids:
            entry.pop("pendingLifecycle", None)
            entry.pop("pendingSinceAt", None)
    for change in formal_changes:
        change.pop("_eventEvidenceIds", None)
    ledger["generatedAt"] = generated_at
    diagnostics = {
        "newEvents": sum(
            lifecycle == "first_seen" and event_id in published_event_ids
            for event_id, lifecycle in event_states.items()
        ),
        "reconfirmations": sum(
            lifecycle == "reconfirmed" and event_id not in conflict_event_ids
            for event_id, lifecycle in event_states.items()
        ),
        "updates": sum(
            lifecycle == "updated" and event_id in published_event_ids
            for event_id, lifecycle in event_states.items()
        ),
        "corrections": sum(
            lifecycle == "correction" and event_id in published_event_ids
            for event_id, lifecycle in event_states.items()
        ),
        "possibleConflicts": len(conflict_event_ids),
        "duplicatesSuppressed": sum(
            lifecycle == "duplicate" and event_id not in conflict_event_ids
            for event_id, lifecycle in event_states.items()
        ),
        "observedEvents": len(event_states),
        "pendingPublications": len(ledger["pendingPublications"]),
        "reviewQueue": review_queue[:20],
    }
    return formal_changes, ledger, diagnostics


def _dataset_counts(changes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for change in changes:
        dataset = str(change.get("dataset", "unknown"))
        counts[dataset] = counts.get(dataset, 0) + 1
    return counts


def _history_entry(report: Mapping[str, Any]) -> dict[str, Any]:
    event_states: dict[str, str] = {}
    changes = report.get("changes")
    if isinstance(changes, list):
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            lifecycles = change.get("eventLifecycles")
            if isinstance(lifecycles, Mapping):
                for event_id, lifecycle in lifecycles.items():
                    if event_id:
                        event_states[str(event_id)] = str(lifecycle or "first_seen")
                continue
            event_id = str(change.get("eventId") or "")
            if event_id:
                event_states[event_id] = str(change.get("lifecycle") or "first_seen")
    change_summary = report.get("changeSummary")
    summary = change_summary if isinstance(change_summary, Mapping) else {}
    event_summary = {
        "newEvents": int(summary.get("newEvents") or 0),
        "reconfirmations": int(summary.get("reconfirmations") or 0),
        "updates": int(summary.get("updates") or 0),
        "corrections": int(summary.get("corrections") or 0),
        "possibleConflicts": int(summary.get("possibleConflicts") or 0),
        "duplicatesSuppressed": int(summary.get("duplicatesSuppressed") or 0),
    }
    return {
        "metricsVersion": 2,
        "date": report.get("asOfDate", ""),
        "generatedAt": report.get("generatedAt", ""),
        "runStatus": report.get("runStatus", ""),
        "changeCount": summary.get("total", 0),
        "executiveSummary": report.get("analysis", {}).get("executiveSummary", "")
        if isinstance(report.get("analysis"), dict)
        else "",
        "eventIds": list(event_states),
        "eventStates": [
            {"eventId": event_id, "lifecycle": lifecycle}
            for event_id, lifecycle in event_states.items()
        ],
        "verifiedChangeTotal": int(summary.get("verifiedChangeTotal") or 0),
        "candidateTotal": int(summary.get("candidateTotal") or 0),
        "auxiliaryLeadTotal": int(summary.get("auxiliaryLeadTotal") or 0),
        "rejectedTotal": int(summary.get("rejectedTotal") or 0),
        "eventSummary": event_summary,
    }


def _history_states(row: Mapping[str, Any]) -> dict[str, str]:
    states: dict[str, str] = {}
    values = row.get("eventStates")
    if isinstance(values, list):
        for value in values:
            if not isinstance(value, Mapping):
                continue
            event_id = str(value.get("eventId") or "")
            if event_id:
                states[event_id] = str(value.get("lifecycle") or "first_seen")
    if not states:
        event_ids = row.get("eventIds")
        if isinstance(event_ids, list):
            states.update(
                (str(event_id), "first_seen") for event_id in event_ids if event_id
            )
    return states


def _merge_same_day_history(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    merged = {**dict(previous), **dict(current)}
    previous_count = int(previous.get("changeCount") or 0)
    current_count = int(current.get("changeCount") or 0)
    previous_states = _history_states(previous)
    current_states = _history_states(current)
    current_is_material = bool(current_count or current_states)
    previous_is_legacy = int(previous.get("metricsVersion") or 0) < 2
    current_is_v2 = int(current.get("metricsVersion") or 0) >= 2

    if previous_is_legacy and previous_count and current_is_v2 and current_is_material:
        # Keep the new v2 metrics precise. The old same-day aggregate had mixed
        # semantics, so retain it separately instead of folding it into a
        # reviewed/candidate total or silently discarding it.
        merged["legacyChangeCount"] = int(
            previous.get("legacyChangeCount") or previous_count
        )
        return merged

    if (
        int(previous.get("metricsVersion") or 0) >= 2
        and previous_count
        and not previous_states
        and current_is_v2
        and current_is_material
    ):
        # Early v2 rows did not yet persist event IDs. Keep their typed totals
        # and diagnostics, but label the count as unidentified so it is never
        # mistaken for an event-level union.
        merged["changeCount"] = previous_count + current_count
        merged["unidentifiedChangeCount"] = int(
            previous.get("unidentifiedChangeCount") or previous_count
        ) + (current_count if not current_states else 0)
        if current_states:
            merged["eventIds"] = list(current_states)
            merged["eventStates"] = [
                {"eventId": event_id, "lifecycle": lifecycle}
                for event_id, lifecycle in current_states.items()
            ]
        for field in (
            "verifiedChangeTotal",
            "candidateTotal",
            "auxiliaryLeadTotal",
            "rejectedTotal",
        ):
            merged[field] = int(previous.get(field) or 0) + int(
                current.get(field) or 0
            )
        previous_event_summary = previous.get("eventSummary")
        current_event_summary = current.get("eventSummary")
        if isinstance(previous_event_summary, Mapping) or isinstance(
            current_event_summary, Mapping
        ):
            prior = (
                previous_event_summary
                if isinstance(previous_event_summary, Mapping)
                else {}
            )
            present = (
                current_event_summary
                if isinstance(current_event_summary, Mapping)
                else {}
            )
            merged["eventSummary"] = {
                key: int(prior.get(key) or 0) + int(present.get(key) or 0)
                for key in (
                    "newEvents",
                    "reconfirmations",
                    "updates",
                    "corrections",
                    "possibleConflicts",
                    "duplicatesSuppressed",
                )
            }
        return merged

    if not current_is_material and (previous_count or previous_states):
        for field in (
            "changeCount",
            "executiveSummary",
            "eventIds",
            "eventStates",
            "verifiedChangeTotal",
            "candidateTotal",
            "auxiliaryLeadTotal",
            "rejectedTotal",
            "eventSummary",
        ):
            if field in previous:
                merged[field] = copy.deepcopy(previous[field])
        previous_event_summary = previous.get("eventSummary")
        current_event_summary = current.get("eventSummary")
        if isinstance(current_event_summary, Mapping):
            prior = (
                previous_event_summary
                if isinstance(previous_event_summary, Mapping)
                else {}
            )
            merged["eventSummary"] = {
                key: int(prior.get(key) or 0)
                + int(current_event_summary.get(key) or 0)
                for key in (
                    "newEvents",
                    "reconfirmations",
                    "updates",
                    "corrections",
                    "possibleConflicts",
                    "duplicatesSuppressed",
                )
            }
        if int(previous.get("metricsVersion") or 0) < 2 and previous_count:
            # A legacy count combined verified, candidate, and auxiliary rows.
            # Do not relabel it as a v2 reviewed metric merely because the next
            # same-day run happened to produce no formal changes.
            merged.pop("metricsVersion", None)
            for field in (
                "verifiedChangeTotal",
                "candidateTotal",
                "auxiliaryLeadTotal",
                "rejectedTotal",
            ):
                merged.pop(field, None)
            merged["legacyChangeCount"] = previous_count
        return merged

    if previous_states or current_states:
        combined_states = {**previous_states, **current_states}
        merged["eventIds"] = list(combined_states)
        merged["eventStates"] = [
            {"eventId": event_id, "lifecycle": lifecycle}
            for event_id, lifecycle in combined_states.items()
        ]
        if previous_states and current_states:
            merged["changeCount"] = max(
                len(combined_states), previous_count, current_count
            )
        previous_event_summary = previous.get("eventSummary")
        current_event_summary = current.get("eventSummary")
        if isinstance(previous_event_summary, Mapping) and isinstance(
            current_event_summary, Mapping
        ):
            merged["eventSummary"] = {
                key: int(previous_event_summary.get(key) or 0)
                + int(current_event_summary.get(key) or 0)
                for key in (
                    "newEvents",
                    "reconfirmations",
                    "updates",
                    "corrections",
                    "possibleConflicts",
                    "duplicatesSuppressed",
                )
            }
        if (
            int(previous.get("metricsVersion") or 0) >= 2
            and int(current.get("metricsVersion") or 0) >= 2
        ):
            for field in (
                "verifiedChangeTotal",
                "candidateTotal",
                "auxiliaryLeadTotal",
                "rejectedTotal",
            ):
                merged[field] = int(previous.get(field) or 0) + int(
                    current.get(field) or 0
                )
    elif previous_count and current_count:
        # Legacy rows do not expose event IDs. Preserve both non-empty runs
        # without pretending they can be deterministically deduplicated.
        merged["changeCount"] = previous_count + current_count
    return merged


def _merge_history(
    previous_report: Mapping[str, Any], current_report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    old = previous_report.get("history", [])
    if isinstance(old, list):
        rows.extend(item for item in old if isinstance(item, dict))
    rows.append(_history_entry(current_report))
    deduplicated: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_date = str(row.get("date") or "").strip()
        date_key = raw_date[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", raw_date) else ""
        if not date_key:
            date_key = _event_date(row.get("generatedAt"))
        if date_key:
            normalized_row = copy.deepcopy(row)
            normalized_row["date"] = date_key
            existing = deduplicated.get(date_key)
            deduplicated[date_key] = (
                _merge_same_day_history(existing, normalized_row)
                if existing
                else normalized_row
            )
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
    previous_report = load_json(output_path, required=False)

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
    quality_eligible_candidates = [
        change
        for change in packaged_candidates
        if change.get("eligibleForKeyDevelopment") is True
    ]
    eligible_candidates, event_ledger, event_diagnostics = reconcile_event_ledger(
        previous_report,
        quality_eligible_candidates,
        candidate_evidence,
        generated_at=generated_at,
        publish_limit=max(1, max_changes),
    )
    changes = copy.deepcopy(eligible_candidates)
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

    if not changes and isinstance(analysis, dict):
        reconfirmations = int(event_diagnostics.get("reconfirmations") or 0)
        duplicates = int(event_diagnostics.get("duplicatesSuppressed") or 0)
        conflicts = int(event_diagnostics.get("possibleConflicts") or 0)
        if conflicts:
            analysis["executiveSummary"] = (
                f"本轮发现 {conflicts} 个潜在事实冲突，已转入待复核，"
                "未计入正式变化或模型研判。"
            )
        elif reconfirmations:
            analysis["executiveSummary"] = (
                f"本轮没有新的正式变化；{reconfirmations} 个既有事件获得再次确认。"
            )
        elif duplicates:
            analysis["executiveSummary"] = (
                f"本轮没有新的正式变化；已抑制 {duplicates} 个跨运行重复事件。"
            )

    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "asOfDate": now.astimezone(
            ZoneInfo(os.environ.get("RESEARCH_AGENT_TIMEZONE", DEFAULT_TIMEZONE))
        ).date().isoformat(),
        "runStatus": run_status,
        "reviewStatus": AUTOMATED_REVIEW_STATUS,
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
            "qualityRejected": len(packaged_candidates)
            - len(quality_eligible_candidates),
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
            "verifiedChangeTotal": sum(
                change.get("publicationTier") == "verified_change"
                for change in changes
            ),
            "candidateTotal": sum(
                change.get("publicationTier") == "candidate" for change in changes
            ),
            "auxiliaryLeadTotal": sum(
                change.get("publicationTier") == "external_clue"
                for change in changes
            ),
            "rejectedTotal": sum(
                change.get("publicationTier") == "rejected"
                for change in packaged_candidates
            ),
            "newEvents": int(event_diagnostics.get("newEvents") or 0),
            "reconfirmations": int(
                event_diagnostics.get("reconfirmations") or 0
            ),
            "updates": int(event_diagnostics.get("updates") or 0),
            "corrections": int(event_diagnostics.get("corrections") or 0),
            "possibleConflicts": int(
                event_diagnostics.get("possibleConflicts") or 0
            ),
            "duplicatesSuppressed": int(
                event_diagnostics.get("duplicatesSuppressed") or 0
            ),
        },
        "analysis": analysis,
        "changes": changes,
        "evidence": evidence,
        "eventLedger": event_ledger,
        "eventDiagnostics": event_diagnostics,
        "methodology": {
            "stages": [
                "stable entity snapshot",
                "person identity quarantine and duplicate reconciliation",
                "field-level change detection and semantic classification",
                "deterministic materiality ranking",
                "claim-field-evidence binding and evidence quality gate",
                "same-entity event aggregation",
                "stable cross-run event identity and lifecycle reconciliation",
                "conservative conflict review gate",
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
    ledger = report.get("eventLedger")
    ledger_events: Mapping[str, Any] | None = None
    if ledger is not None:
        if not isinstance(ledger, Mapping):
            errors.append("eventLedger must be an object")
        else:
            if ledger.get("schemaVersion") != EVENT_LEDGER_SCHEMA_VERSION:
                errors.append("eventLedger has unsupported schemaVersion")
            raw_events = ledger.get("events")
            if not isinstance(raw_events, Mapping):
                errors.append("eventLedger.events must be an object")
            else:
                ledger_events = raw_events
                for event_id, entry in raw_events.items():
                    if not isinstance(entry, Mapping):
                        errors.append(f"eventLedger event {event_id} must be an object")
                        continue
                    for issue in _event_ledger_entry_validation_errors(
                        str(event_id), entry
                    ):
                        errors.append(f"eventLedger event {event_id} has {issue}")
                raw_pending = ledger.get("pendingPublications")
                if raw_pending is not None:
                    if not isinstance(raw_pending, list):
                        errors.append("eventLedger.pendingPublications must be an array")
                    elif len(
                        _normalize_pending_publications(
                            raw_pending,
                            {
                                str(event_id): entry
                                for event_id, entry in raw_events.items()
                                if isinstance(entry, Mapping)
                            },
                            str(report.get("generatedAt") or ""),
                        )
                    ) != len(raw_pending):
                        errors.append(
                            "eventLedger.pendingPublications contains invalid or duplicate rows"
                        )
    evidence_ids: set[str] = set()
    evidence_by_id: dict[str, Mapping[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        evidence_id = str(item["id"])
        if evidence_id in evidence_ids:
            errors.append(f"duplicate evidence id {evidence_id}")
            continue
        evidence_ids.add(evidence_id)
        evidence_by_id[evidence_id] = item
    for change in changes:
        if not isinstance(change, dict):
            errors.append("change row must be an object")
            continue
        if ledger_events is not None:
            event_ids = change.get("eventIds")
            identity_issues = _event_change_identity_errors(change)
            for issue in identity_issues:
                errors.append(f"change {change.get('id')} has {issue}")
            if isinstance(event_ids, list) and event_ids and any(
                str(event_id) not in ledger_events for event_id in event_ids
            ):
                errors.append(f"change {change.get('id')} references unknown event")
            elif isinstance(event_ids, list) and event_ids:
                for event_id in event_ids:
                    ledger_entry = ledger_events.get(str(event_id))
                    if not isinstance(ledger_entry, Mapping):
                        continue
                    if (
                        ledger_entry.get("conflictStatus") == "possible"
                        or ledger_entry.get("status") == "needs_review"
                    ):
                        errors.append(
                            f"change {change.get('id')} publishes unresolved conflict"
                        )
                    elif ledger_entry.get("status") == "superseded":
                        errors.append(
                            f"change {change.get('id')} publishes superseded event"
                        )
        ids = change.get("evidenceIds")
        if not isinstance(ids, list) or not ids:
            errors.append(f"change {change.get('id')} has no evidenceIds")
        elif len({str(item) for item in ids}) != len(ids):
            errors.append(f"change {change.get('id')} has duplicate evidenceIds")
        elif any(item not in evidence_ids for item in ids):
            errors.append(f"change {change.get('id')} references unknown evidence")
        else:
            change_id = str(change.get("id") or "")
            for evidence_id in ids:
                row = evidence_by_id.get(str(evidence_id), {})
                if str(row.get("changeId") or "") != change_id:
                    errors.append(
                        f"change {change.get('id')} references evidence owned by another change"
                    )
        if change.get("eligibleForKeyDevelopment") is not True:
            errors.append(
                f"change {change.get('id')} is not eligible for formal publication"
            )
        if change.get("changeType") != "external_event":
            errors.append(
                f"change {change.get('id')} is not an external event"
            )
        publication_tier = change.get("publicationTier")
        publishable_tiers = PUBLICATION_TIERS - {"rejected"}
        if ledger_events is not None or publication_tier is not None:
            if publication_tier not in publishable_tiers:
                errors.append(
                    f"change {change.get('id')} has invalid publicationTier"
                )
            elif isinstance(ids, list) and all(
                str(evidence_id) in evidence_by_id for evidence_id in ids
            ):
                expected_tier = _publication_tier(
                    str(change.get("dataset") or ""),
                    [evidence_by_id[str(evidence_id)] for evidence_id in ids],
                )
                if publication_tier != expected_tier:
                    errors.append(
                        f"change {change.get('id')} publicationTier does not match dataset and evidence"
                    )
        if change.get("eligibleForKeyDevelopment") is True:
            bindings = change.get("claimBindings")
            if not isinstance(bindings, list) or not bindings:
                errors.append(f"change {change.get('id')} has no claim bindings")
                bindings = []
            change_evidence_ids = {
                str(evidence_id) for evidence_id in ids
            } if isinstance(ids, list) else set()
            supporting_ids = change.get("supportingEvidenceIds")
            if not isinstance(supporting_ids, list) or not supporting_ids:
                errors.append(
                    f"change {change.get('id')} has no supportingEvidenceIds"
                )
            else:
                normalized_supporting_ids = [
                    str(evidence_id) for evidence_id in supporting_ids
                ]
                if len(set(normalized_supporting_ids)) != len(
                    normalized_supporting_ids
                ):
                    errors.append(
                        f"change {change.get('id')} has duplicate supportingEvidenceIds"
                    )
                if set(normalized_supporting_ids) != change_evidence_ids:
                    errors.append(
                        f"change {change.get('id')} supportingEvidenceIds do not match evidenceIds"
                    )
            evidence_quality = change.get("evidenceQuality")
            if (
                not isinstance(evidence_quality, Mapping)
                or evidence_quality.get("status") != "passed"
                or evidence_quality.get("supporting") != len(change_evidence_ids)
                or evidence_quality.get("total") != len(change_evidence_ids)
            ):
                errors.append(
                    f"change {change.get('id')} has inconsistent evidenceQuality"
                )
            bound_evidence_ids: set[str] = set()
            binding_fields: set[str] = set()
            for binding in bindings if isinstance(bindings, list) else []:
                if not isinstance(binding, Mapping):
                    errors.append(
                        f"change {change.get('id')} has malformed claim binding"
                    )
                    continue
                binding_ids = binding.get("evidenceIds")
                if not isinstance(binding_ids, list) or not binding_ids:
                    errors.append(
                        f"change {change.get('id')} has claim binding without evidenceIds"
                    )
                    continue
                if len({str(evidence_id) for evidence_id in binding_ids}) != len(
                    binding_ids
                ):
                    errors.append(
                        f"change {change.get('id')} has duplicate claim binding evidenceIds"
                    )
                normalized_binding_ids = {
                    str(evidence_id) for evidence_id in binding_ids
                }
                bound_evidence_ids.update(normalized_binding_ids)
                if not normalized_binding_ids <= change_evidence_ids:
                    errors.append(
                        f"change {change.get('id')} claim binding escapes change evidenceIds"
                    )
                field = str(binding.get("field") or "")
                binding_fields.add(field)
                for evidence_id in normalized_binding_ids & evidence_ids:
                    claim_fields = evidence_by_id[evidence_id].get("claimFields")
                    if not isinstance(claim_fields, list) or field not in {
                        str(value) for value in claim_fields
                    }:
                        errors.append(
                            f"change {change.get('id')} claim binding field is unsupported by evidence {evidence_id}"
                        )
            if bound_evidence_ids != change_evidence_ids:
                errors.append(
                    f"change {change.get('id')} claim bindings do not exactly cover evidenceIds"
                )
            claim_fields = change.get("claimFields")
            if (
                not isinstance(claim_fields, list)
                or {str(value) for value in claim_fields if value} != binding_fields
            ):
                errors.append(
                    f"change {change.get('id')} claimFields do not match claim bindings"
                )
            if ledger_events is not None or publication_tier is not None:
                for issue in _change_claim_projection_errors(change):
                    errors.append(
                        f"change {change.get('id')} has invalid claim projection: {issue}"
                    )
            for evidence_id in ids if isinstance(ids, list) else []:
                row = evidence_by_id.get(str(evidence_id), {})
                if row.get("qualityStatus") != "passed" or row.get(
                    "supportStatus"
                ) != "supports":
                    errors.append(
                        f"change {change.get('id')} references rejected evidence"
                    )
            if ledger_events is not None:
                semantic_evidence = [
                    evidence_by_id[str(evidence_id)]
                    for evidence_id in ids
                    if str(evidence_id) in evidence_by_id
                ] if isinstance(ids, list) else []
                for issue in _event_change_semantic_assignment_errors(
                    change, semantic_evidence, ledger_events
                ):
                    errors.append(
                        f"change {change.get('id')} has event semantic mismatch: {issue}"
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
