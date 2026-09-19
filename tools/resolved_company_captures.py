#!/usr/bin/env python3
"""Filter manual captures through the shared cross-type entity resolver."""

from __future__ import annotations

import copy
from typing import Any

try:
    from .entity_resolution import clean, resolve_entity
except ImportError:
    from entity_resolution import clean, resolve_entity  # type: ignore


def resolved_company_captures(
    captures_payload: dict[str, Any],
    *,
    entity_decisions_payload: dict[str, Any],
    company_registry_payload: dict[str, Any],
    people_payload: dict[str, Any],
    tracking_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    output = copy.deepcopy(captures_payload)
    records = captures_payload.get("records", [])
    rows: list[dict[str, Any]] = []
    stats = {
        "captureCount": 0,
        "companyCount": 0,
        "reviewCount": 0,
        "reclassifiedCount": 0,
        "rejectedCount": 0,
    }
    for capture in records if isinstance(records, list) else []:
        if not isinstance(capture, dict):
            continue
        if clean(capture.get("status"), 20) not in {"queued", "applied"}:
            continue
        stats["captureCount"] += 1
        embedded = capture.get("resolution") if isinstance(capture.get("resolution"), dict) else {}
        requested_type = clean(embedded.get("requestedType"), 20) or clean(capture.get("entityType"), 20)
        raw_name = clean(capture.get("rawSelection"), 160) or clean(capture.get("canonicalName"), 160)
        source = capture.get("source") if isinstance(capture.get("source"), dict) else {}
        resolution = resolve_entity(
            requested_type,
            raw_name,
            source,
            decisions_payload=entity_decisions_payload,
            company_registry_payload=company_registry_payload,
            people_payload=people_payload,
            tracking_payload=tracking_payload,
        )
        if resolution.reclassified:
            stats["reclassifiedCount"] += 1
        if resolution.status == "review":
            stats["reviewCount"] += 1
            continue
        if resolution.status == "rejected":
            stats["rejectedCount"] += 1
            continue
        if resolution.targetId.startswith("institution:"):
            stats["institutionCount"] = stats.get("institutionCount", 0) + 1
            continue
        if resolution.entityType != "company":
            continue
        row = copy.deepcopy(capture)
        row["entityType"] = "company"
        row["canonicalName"] = resolution.canonicalName
        row["status"] = "applied"
        row["resolution"] = resolution.to_dict()
        rows.append(row)
        stats["companyCount"] += 1

    output["records"] = rows
    return output, stats
