#!/usr/bin/env python3
"""Persistent, public-safe thesis observation memory for Research Agent.

The model's ``analysis.thesisUpdates`` are run-local. This wrapper turns those
updates into a bounded observation ledger without pretending that every entity
has exactly one timeless thesis. Identical observations are reaffirmed; changed
wording or direction creates a new observation linked to the prior observation
for that entity.

Historical observations store compact evidence snapshots rather than run-local
Evidence IDs, so they remain auditable after the next daily report replaces the
current Evidence ledger.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


THESIS_MEMORY_SCHEMA_VERSION = 1
MAX_THESIS_OBSERVATIONS = 120
MAX_EVIDENCE_PER_OBSERVATION = 6
MAX_EVIDENCE_HISTORY_PER_OBSERVATION = 10

_ORIGINAL_GENERATE_REPORT: Any = None
_INSTALLED_AGENT_ID: int | None = None
_AGENT: Any = None


def _text(value: Any, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _normalized(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", _text(value, 2400).casefold())


def _observation_id(entity: str, direction: str, statement: str) -> str:
    material = "|".join((_normalized(entity), direction, _normalized(statement)))
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]
    return f"thesis-{digest}"


def _verification_status(row: Mapping[str, Any]) -> str:
    explicit = _text(row.get("verificationStatus"), 80)
    if explicit:
        return explicit
    review = _text(row.get("reviewStatus"), 80)
    if review in {"reviewed", "approved"}:
        return "reviewed"
    if review == "rejected" or row.get("qualityStatus") == "rejected":
        return "rejected"
    if (
        row.get("publicationTier") == "verified_change"
        and row.get("qualityStatus") == "passed"
        and row.get("supportStatus") == "supports"
    ):
        return "auto_verified"
    return "candidate"


def _evidence_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": _text(row.get("title") or row.get("sourceName"), 300),
        "url": _text(row.get("url"), 1200),
        "sourceName": _text(row.get("sourceName"), 180),
        "publishedAt": _text(row.get("publishedAt"), 80),
        "eventDate": _text(row.get("eventDate"), 80),
        "verificationStatus": _verification_status(row),
    }


def _snapshot_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("url"), 1200) or "|".join(
        (_normalized(row.get("sourceName")), _normalized(row.get("title")))
    )


def _merge_evidence(
    existing: Iterable[Mapping[str, Any]], incoming: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for raw in [*existing, *incoming]:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        key = _snapshot_key(row)
        if not key:
            continue
        rows[key] = row
    return list(rows.values())[-MAX_EVIDENCE_HISTORY_PER_OBSERVATION:]


def _normalize_previous_memory(previous_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    memory = previous_report.get("thesisMemory")
    if not isinstance(memory, Mapping):
        return []
    observations = memory.get("observations")
    if not isinstance(observations, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in observations[-MAX_THESIS_OBSERVATIONS:]:
        if not isinstance(raw, Mapping):
            continue
        observation_id = _text(raw.get("id"), 100)
        entity = _text(raw.get("entity"), 180)
        statement = _text(raw.get("statement"), 1200)
        if not observation_id or not entity or not statement:
            continue
        result.append(dict(raw))
    return result


def build_thesis_memory(
    previous_report: Mapping[str, Any], current_report: Mapping[str, Any]
) -> dict[str, Any]:
    generated_at = _text(current_report.get("generatedAt"), 80)
    observations = _normalize_previous_memory(previous_report)
    by_id = {_text(row.get("id"), 100): row for row in observations}

    latest_by_entity: dict[str, dict[str, Any]] = {}
    for row in observations:
        entity_key = _normalized(row.get("entity"))
        if not entity_key:
            continue
        previous = latest_by_entity.get(entity_key)
        if previous is None or _text(row.get("lastSeenAt"), 80) >= _text(previous.get("lastSeenAt"), 80):
            latest_by_entity[entity_key] = row

    evidence_rows = current_report.get("evidence")
    evidence_by_id = {
        _text(row.get("id"), 100): row
        for row in evidence_rows
        if isinstance(row, Mapping) and _text(row.get("id"), 100)
    } if isinstance(evidence_rows, list) else {}

    analysis = current_report.get("analysis")
    updates = analysis.get("thesisUpdates") if isinstance(analysis, Mapping) else []
    if not isinstance(updates, list):
        updates = []

    current_ids: list[str] = []
    for raw in updates:
        if not isinstance(raw, Mapping):
            continue
        entity = _text(raw.get("entity"), 180)
        direction = _text(raw.get("direction"), 40) or "neutral"
        statement = _text(raw.get("statement"), 1200)
        if not entity or not statement:
            continue
        observation_id = _observation_id(entity, direction, statement)
        entity_key = _normalized(entity)
        prior = latest_by_entity.get(entity_key)
        evidence_ids = raw.get("evidenceIds") if isinstance(raw.get("evidenceIds"), list) else []
        current_evidence = [
            _evidence_snapshot(evidence_by_id[evidence_id])
            for evidence_id in (_text(value, 100) for value in evidence_ids)
            if evidence_id in evidence_by_id
        ][:MAX_EVIDENCE_PER_OBSERVATION]

        existing = by_id.get(observation_id)
        if existing is not None:
            existing["lastSeenAt"] = generated_at
            existing["observationCount"] = int(existing.get("observationCount") or 1) + 1
            existing["evidence"] = _merge_evidence(existing.get("evidence") or [], current_evidence)
            existing["lastTransition"] = (
                "reaffirmed" if prior is None or prior.get("id") == observation_id else "returned"
            )
            if prior is not None and prior.get("id") != observation_id:
                existing["supersedesId"] = _text(prior.get("id"), 100)
            row = existing
        else:
            transition = "initiated"
            supersedes_id = ""
            if prior is not None:
                supersedes_id = _text(prior.get("id"), 100)
                transition = (
                    "direction_changed"
                    if _text(prior.get("direction"), 40) != direction
                    else "revised"
                )
            row = {
                "id": observation_id,
                "entity": entity,
                "direction": direction,
                "statement": statement,
                "firstSeenAt": generated_at,
                "lastSeenAt": generated_at,
                "observationCount": 1,
                "lastTransition": transition,
                "evidence": current_evidence,
            }
            if supersedes_id:
                row["supersedesId"] = supersedes_id
            observations.append(row)
            by_id[observation_id] = row

        latest_by_entity[entity_key] = row
        if observation_id not in current_ids:
            current_ids.append(observation_id)

    observations.sort(
        key=lambda row: (_text(row.get("lastSeenAt"), 80), _text(row.get("id"), 100))
    )
    observations = observations[-MAX_THESIS_OBSERVATIONS:]
    retained_ids = {_text(row.get("id"), 100) for row in observations}
    current_ids = [item for item in current_ids if item in retained_ids]
    return {
        "schemaVersion": THESIS_MEMORY_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "currentObservationIds": current_ids,
        "observationCount": len(observations),
        "observations": observations,
    }


def generate_report(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    output_value = kwargs.get("output_path")
    previous_report: dict[str, Any] = {}
    if output_value is not None and _AGENT is not None:
        previous_report = _AGENT.load_json(Path(output_value), required=False)

    report, snapshot = _ORIGINAL_GENERATE_REPORT(*args, **kwargs)
    report["thesisMemory"] = build_thesis_memory(previous_report, report)
    return report, snapshot


def install_thesis_memory(agent: Any) -> None:
    """Install the persistent thesis-memory wrapper exactly once."""

    global _AGENT, _ORIGINAL_GENERATE_REPORT, _INSTALLED_AGENT_ID
    if _INSTALLED_AGENT_ID == id(agent):
        return
    _AGENT = agent
    _ORIGINAL_GENERATE_REPORT = agent.generate_report
    agent.generate_report = generate_report
    _INSTALLED_AGENT_ID = id(agent)
