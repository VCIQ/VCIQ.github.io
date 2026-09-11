#!/usr/bin/env python3
"""Bridge canonical Track/Technology objects into the Research Agent snapshot.

The canonical object identities are exported by the TypeScript public research
layer. This module deliberately does not re-implement that taxonomy in Python;
it only injects the exported records into the Research Agent snapshot and adds
research-object change/publication semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


OBJECT_SNAPSHOT_PATH = Path("work/research-agent/research_agent_objects.json")
CORE_OBJECT_DATASETS = {"track", "technology"}
OBJECT_EVENT_FIELDS = {"latestEvents"}
OBJECT_LABELS = {"track": "核心赛道", "technology": "核心技术"}

_AGENT: Any = None
_ORIGINAL_LOAD_INPUT_PAYLOADS: Any = None
_ORIGINAL_BUILD_SNAPSHOT: Any = None
_ORIGINAL_BUILD_SNAPSHOT_FROM_GIT: Any = None
_ORIGINAL_DIFF_SNAPSHOTS: Any = None
_ORIGINAL_PUBLICATION_TIER: Any = None
_INSTALLED_AGENT_ID: int | None = None
_CURRENT_OBJECT_SNAPSHOT: dict[str, Any] = {}


def _object_rows(payload: Mapping[str, Any], key: str) -> dict[str, dict[str, Any]]:
    raw = payload.get(key)
    if not isinstance(raw, Mapping):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for entity_id, value in raw.items():
        if isinstance(value, Mapping):
            rows[str(entity_id)] = _AGENT.canonicalize(dict(value))
    return rows


def _inject(snapshot: dict[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    tracks = _object_rows(payload, "tracks")
    technologies = _object_rows(payload, "technologies")
    if not tracks and not technologies and int(payload.get("schemaVersion") or 0) <= 0:
        return snapshot

    datasets = snapshot.get("datasets")
    if not isinstance(datasets, dict):
        datasets = {}
        snapshot["datasets"] = datasets
    datasets["track"] = tracks
    datasets["technology"] = technologies
    snapshot["stats"] = {
        name: len(rows) if isinstance(rows, Mapping) else 0
        for name, rows in datasets.items()
    }
    snapshot["contentHash"] = _AGENT.stable_hash(datasets)
    snapshot["researchObjectSnapshot"] = {
        "schemaVersion": int(payload.get("schemaVersion") or 1),
        "generatedAt": str(payload.get("generatedAt") or ""),
        "articleSnapshotDate": str(payload.get("articleSnapshotDate") or ""),
    }
    return snapshot


def load_input_payloads(root: Path) -> Any:
    global _CURRENT_OBJECT_SNAPSHOT
    base = _ORIGINAL_LOAD_INPUT_PAYLOADS(root)
    _CURRENT_OBJECT_SNAPSHOT = _AGENT.load_json(
        root / OBJECT_SNAPSHOT_PATH, required=False
    )
    return base


def build_snapshot(payloads: Any, generated_at: str) -> dict[str, Any]:
    snapshot = _ORIGINAL_BUILD_SNAPSHOT(payloads, generated_at)
    return _inject(snapshot, _CURRENT_OBJECT_SNAPSHOT)


def build_snapshot_from_git(root: Path, git_ref: str, generated_at: str) -> dict[str, Any]:
    # The canonical object bridge is intentionally transient and ignored by git.
    # A bootstrap git ref therefore has no object bridge to read. The first run
    # establishes these datasets as maintenance-only additions; subsequent runs
    # compare against the committed Research Agent snapshot produced by that run.
    return _ORIGINAL_BUILD_SNAPSHOT_FROM_GIT(root, git_ref, generated_at)


def _canonical_event_url(value: Any) -> str:
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
        "from",
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


def _event_identity(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    # URL is the strongest cross-run identity available here because upstream
    # event IDs may be regenerated while the underlying published item is the
    # same. Strip tracking parameters before falling back to stored IDs/titles.
    url = _canonical_event_url(value.get("url"))
    if url:
        return f"url:{url}"
    event_id = str(value.get("id") or "").strip()
    if event_id:
        return f"id:{event_id}"
    title = str(value.get("title") or "").strip().casefold()
    return f"title:{title}" if title else ""


def _new_object_events(change: Mapping[str, Any]) -> list[dict[str, Any]]:
    record = change.get("record")
    previous = change.get("_beforeRecord")
    after_events = record.get("latestEvents") if isinstance(record, Mapping) else None
    before_events = previous.get("latestEvents") if isinstance(previous, Mapping) else None
    if not isinstance(after_events, list):
        return []
    previous_ids = {
        _event_identity(event)
        for event in before_events or []
        if _event_identity(event)
    }
    return [
        dict(event)
        for event in after_events
        if isinstance(event, Mapping)
        and _event_identity(event)
        and _event_identity(event) not in previous_ids
    ]


def _latest_event_importance(events: list[Mapping[str, Any]]) -> int:
    values = [int(event.get("importance") or 0) for event in events]
    return max(values, default=0)


def _reclassify_object_change(change: dict[str, Any]) -> None:
    dataset = str(change.get("dataset") or "")
    if dataset not in CORE_OBJECT_DATASETS:
        return
    change["entityType"] = OBJECT_LABELS[dataset]
    action = str(change.get("action") or "")
    fields = {str(field) for field in change.get("changedFields", [])}
    new_events = _new_object_events(change) if "latestEvents" in fields else []
    if action == "updated" and new_events:
        change["changeType"] = "external_event"
        change["classificationReason"] = "研究对象出现新的可追溯公开事件"
        change["isResearchCandidate"] = True
        change["summary"] = f"{change.get('entityName') or OBJECT_LABELS[dataset]} 新增 {len(new_events)} 条可追溯公开事件。"
        event_importance = _latest_event_importance(new_events)
        if event_importance:
            change["importance"] = max(int(change.get("importance") or 0), event_importance)
        record = change.get("record")
        if isinstance(record, Mapping):
            evidence_record = dict(record)
            evidence_record["latestEvents"] = new_events
            change["record"] = evidence_record
        return
    change["changeType"] = "data_maintenance"
    change["classificationReason"] = "研究对象目录或研究属性维护"
    change["isResearchCandidate"] = False


def diff_snapshots(previous: Mapping[str, Any], current: Mapping[str, Any]) -> list[dict[str, Any]]:
    changes = _ORIGINAL_DIFF_SNAPSHOTS(previous, current)
    for change in changes:
        _reclassify_object_change(change)
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


def publication_tier(dataset: str, sources: Any) -> str:
    rows = list(sources)
    if dataset in CORE_OBJECT_DATASETS:
        supporting = [row for row in rows if row.get("supportStatus") == "supports"]
        if not supporting:
            return "rejected"
        if any(_AGENT._is_verified_source(row) for row in supporting):
            return "verified_change"
        return "candidate"
    return _ORIGINAL_PUBLICATION_TIER(dataset, rows)


def research_scope(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Expose four core research-object coverages from the same snapshot."""

    datasets = snapshot.get("datasets")
    if not isinstance(datasets, Mapping):
        datasets = {}

    def entry(key: str, label: str, active_note: str, pending_note: str) -> dict[str, Any]:
        rows = datasets.get(key)
        if isinstance(rows, Mapping):
            return {
                "label": label,
                "status": "active",
                "count": len(rows),
                "note": active_note,
            }
        return {
            "label": label,
            "status": "pending-artifact",
            "count": None,
            "note": pending_note,
        }

    return {
        "technology": entry(
            "technology",
            "核心技术",
            "已由公开核心技术目录进入每日对象快照与变化检测。",
            "等待 canonical research-object snapshot 接入。",
        ),
        "track": entry(
            "track",
            "核心赛道",
            "已由公开赛道目录进入每日对象快照与变化检测。",
            "等待 canonical research-object snapshot 接入。",
        ),
        "person": entry(
            "person",
            "核心人物",
            "已进入每日实体快照与变化检测。",
            "人物快照待同步。",
        ),
        "ventureCompany": entry(
            "ventureCompany",
            "核心公司",
            "已进入每日实体快照与变化检测。",
            "公司快照待同步。",
        ),
    }


def install_research_object_scope(evidence_policy: Any) -> None:
    """Use four-object scope reporting without coupling the evidence module back here."""

    evidence_policy._research_scope = research_scope


def install_research_object_policy(agent: Any) -> None:
    """Install four-object snapshot/change semantics exactly once."""

    global _AGENT, _ORIGINAL_LOAD_INPUT_PAYLOADS, _ORIGINAL_BUILD_SNAPSHOT
    global _ORIGINAL_BUILD_SNAPSHOT_FROM_GIT, _ORIGINAL_DIFF_SNAPSHOTS
    global _ORIGINAL_PUBLICATION_TIER, _INSTALLED_AGENT_ID

    if _INSTALLED_AGENT_ID == id(agent):
        return
    _AGENT = agent
    _ORIGINAL_LOAD_INPUT_PAYLOADS = agent.load_input_payloads
    _ORIGINAL_BUILD_SNAPSHOT = agent.build_snapshot
    _ORIGINAL_BUILD_SNAPSHOT_FROM_GIT = agent.build_snapshot_from_git
    _ORIGINAL_DIFF_SNAPSHOTS = agent.diff_snapshots
    _ORIGINAL_PUBLICATION_TIER = agent._publication_tier
    agent.load_input_payloads = load_input_payloads
    agent.build_snapshot = build_snapshot
    agent.build_snapshot_from_git = build_snapshot_from_git
    agent.diff_snapshots = diff_snapshots
    agent._publication_tier = publication_tier
    _INSTALLED_AGENT_ID = id(agent)
