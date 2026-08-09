#!/usr/bin/env python3
"""Auto-accept audited human company additions after entity resolution.

VCIQ uses exception-based candidate review:

* a company explicitly captured by a human does not require a second human review;
* automatically discovered companies remain pending until reviewed;
* entity-type conflicts and ambiguous identities remain review-gated;
* formal company publication still requires the existing onboarding quality gate.

The trust signal is deliberately narrow. `sampleCompanies` is not provenance: both
humans and automation can write that derived tracking field. Automatic acceptance
therefore requires an auditable capture with a non-automation `capturedBy` actor.
Final review outcomes (accepted/rejected/merged/published) are never overwritten.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .entity_resolution import (
        COMPANY_REGISTRY_PATH,
        DECISIONS_PATH as ENTITY_DECISIONS_PATH,
        PEOPLE_PATH,
        TRACKING_PATH,
        clean,
        load_json,
        normalize_identity,
        resolve_entity,
    )
except ImportError:
    from entity_resolution import (  # type: ignore
        COMPANY_REGISTRY_PATH,
        DECISIONS_PATH as ENTITY_DECISIONS_PATH,
        PEOPLE_PATH,
        TRACKING_PATH,
        clean,
        load_json,
        normalize_identity,
        resolve_entity,
    )

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "config" / "company_candidate_review_queue.json"
COMPANY_DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"
CAPTURE_INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"

FINAL_REVIEW_STATUSES = {"accepted", "rejected", "merged", "published"}
TRUST_NOTE = (
    "管理员已显式添加该公司，且实体解析未发现类型或身份冲突；"
    "免二次人工复审。正式发布仍须通过自动建档、官方来源和质量门。"
)
AUTOMATION_ACTOR_MARKERS = (
    "bot",
    "github-actions",
    "automation",
    "crawler",
    "system",
)


def _capture_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("records", [])
    if not isinstance(rows, list):
        return {}
    return {
        clean(row.get("id"), 200): row
        for row in rows
        if isinstance(row, dict) and clean(row.get("id"), 200)
    }


def _decision_index(payload: Mapping[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    raw = payload.get("decisions", {})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for raw_key, value in raw.items():
        if not isinstance(value, dict):
            continue
        key = normalize_identity(raw_key)
        if key:
            result[key] = (str(raw_key), value)
    return result


def _is_manual_actor(value: Any) -> bool:
    """Require an explicit non-automation actor before capture evidence is trusted."""

    actor = clean(value, 120)
    if not actor:
        return False
    lowered = actor.casefold()
    return not any(marker in lowered for marker in AUTOMATION_ACTOR_MARKERS)


def _candidate_capture_resolution(
    candidate: Mapping[str, Any],
    capture_rows: Mapping[str, dict[str, Any]],
    *,
    entity_decisions_payload: Mapping[str, Any],
    company_registry_payload: Mapping[str, Any],
    people_payload: Mapping[str, Any],
    tracking_payload: Mapping[str, Any],
) -> tuple[bool, str, str, str, bool]:
    """Return trust, audit identity, reason, and whether capture evidence exists."""

    candidate_key = normalize_identity(candidate.get("decisionKey") or candidate.get("name"))
    raw_ids = candidate.get("captureIds", [])
    capture_ids = raw_ids if isinstance(raw_ids, list) else []
    saw_capture = False
    last_reason = ""
    for raw_id in capture_ids:
        capture = capture_rows.get(clean(raw_id, 200))
        if not capture:
            continue
        saw_capture = True
        actor = clean(capture.get("capturedBy"), 120)
        if not _is_manual_actor(actor):
            last_reason = "采集记录没有可验证的人工操作者，不能继承人工信任"
            continue
        embedded = capture.get("resolution") if isinstance(capture.get("resolution"), dict) else {}
        requested_type = clean(embedded.get("requestedType"), 20) or clean(
            capture.get("entityType"), 20
        )
        raw_name = clean(capture.get("rawSelection"), 160) or clean(
            capture.get("canonicalName"), 160
        )
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
        resolved_key = normalize_identity(resolution.canonicalName)
        if (
            resolution.status == "resolved"
            and resolution.entityType == "company"
            and resolved_key == candidate_key
        ):
            return (
                True,
                actor,
                clean(capture.get("capturedAt"), 80),
                "管理员文章采集已通过实体解析",
                True,
            )
        last_reason = resolution.reason or "管理员采集未解析为公司"
    return False, "", "", last_reason, saw_capture


def apply_manual_company_trust(
    candidates_payload: Mapping[str, Any],
    company_decisions_payload: Mapping[str, Any],
    tracking_payload: Mapping[str, Any],
    captures_payload: Mapping[str, Any],
    *,
    entity_decisions_payload: Mapping[str, Any],
    company_registry_payload: Mapping[str, Any],
    people_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an updated decision manifest plus an auditable policy report."""

    root = copy.deepcopy(company_decisions_payload) if isinstance(company_decisions_payload, Mapping) else {}
    if not isinstance(root, dict):
        root = {}
    raw_decisions = root.get("decisions")
    if not isinstance(raw_decisions, dict):
        raw_decisions = {}
        root["decisions"] = raw_decisions
    root["schemaVersion"] = max(1, int(root.get("schemaVersion", 1) or 1))

    capture_rows = _capture_index(captures_payload)
    decision_rows = _decision_index(root)

    trusted_keys: list[str] = []
    exception_rows: list[dict[str, str]] = []
    preserved_final_keys: list[str] = []
    provenance_pending_keys: list[str] = []

    candidates = candidates_payload.get("candidates", [])
    for candidate in candidates if isinstance(candidates, list) else []:
        if not isinstance(candidate, dict):
            continue
        key = normalize_identity(candidate.get("decisionKey") or candidate.get("name"))
        if not key:
            continue

        existing = decision_rows.get(key)
        existing_status = clean(existing[1].get("status"), 30) if existing else ""
        if existing_status in FINAL_REVIEW_STATUSES:
            preserved_final_keys.append(key)
            continue

        trusted, actor, decided_at, capture_reason, saw_capture = _candidate_capture_resolution(
            candidate,
            capture_rows,
            entity_decisions_payload=entity_decisions_payload,
            company_registry_payload=company_registry_payload,
            people_payload=people_payload,
            tracking_payload=tracking_payload,
        )
        if not trusted:
            if saw_capture:
                exception_rows.append(
                    {
                        "candidateKey": key,
                        "reason": capture_reason or "人工采集未通过实体冲突检查",
                    }
                )
            else:
                # `sampleCompanies` cannot distinguish a direct human edit from an
                # automatic discovery/reconciliation write. Keep it pending until
                # a dedicated human provenance record exists.
                provenance_pending_keys.append(key)
            continue

        raw_key = existing[0] if existing else key
        previous = copy.deepcopy(existing[1]) if existing else {}
        previous.update(
            {
                "status": "accepted",
                "note": TRUST_NOTE,
                "mergedSlug": clean(previous.get("mergedSlug"), 120),
                "decidedAt": (
                    decided_at
                    or clean(candidate.get("lastSeenAt"), 80)
                    or clean(candidates_payload.get("generatedAt"), 80)
                ),
                "reviewedBy": actor,
            }
        )
        raw_decisions[raw_key] = previous
        decision_rows[key] = (raw_key, previous)
        trusted_keys.append(key)

    report = {
        "trustedCount": len(trusted_keys),
        "trustedKeys": sorted(set(trusted_keys)),
        "captureTrustedCount": len(trusted_keys),
        "captureTrustedKeys": sorted(set(trusted_keys)),
        # Kept for machine-readable compatibility. Direct tracking values are no
        # longer a trust source because automation can write sampleCompanies.
        "trackingTrustedCount": 0,
        "trackingTrustedKeys": [],
        "manualExceptionCount": len(exception_rows),
        "manualExceptions": sorted(exception_rows, key=lambda row: row["candidateKey"]),
        "provenancePendingCount": len(set(provenance_pending_keys)),
        "provenancePendingKeys": sorted(set(provenance_pending_keys)),
        "preservedFinalCount": len(set(preserved_final_keys)),
    }
    return root, report


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=COMPANY_DECISIONS_PATH)
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--captures", type=Path, default=CAPTURE_INBOX_PATH)
    parser.add_argument("--entity-decisions", type=Path, default=ENTITY_DECISIONS_PATH)
    parser.add_argument("--companies", type=Path, default=COMPANY_REGISTRY_PATH)
    parser.add_argument("--people", type=Path, default=PEOPLE_PATH)
    args = parser.parse_args()

    current = load_json(args.decisions, {"schemaVersion": 1, "decisions": {}})
    next_payload, report = apply_manual_company_trust(
        load_json(args.candidates, {"candidates": []}),
        current,
        load_json(args.tracking, {"tracks": []}),
        load_json(args.captures, {"records": []}),
        entity_decisions_payload=load_json(args.entity_decisions, {"decisions": {}}),
        company_registry_payload=load_json(args.companies, {"companies": []}),
        people_payload=load_json(args.people, {"people": []}),
    )
    changed = current != next_payload
    if args.check:
        if changed:
            raise SystemExit("manual company trust decisions are not current")
        print(json.dumps({"valid": True, **report}, ensure_ascii=False, sort_keys=True))
        return 0

    if changed:
        _write_json(args.decisions, next_payload)
    print(json.dumps({"changed": changed, **report}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
