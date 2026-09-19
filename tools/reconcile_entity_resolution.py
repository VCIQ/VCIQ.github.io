#!/usr/bin/env python3
"""Reconcile captured entities and tracking fields with the shared resolver."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .entity_resolution import (
        COMPANY_REGISTRY_PATH,
        DECISIONS_PATH,
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
        DECISIONS_PATH,
        PEOPLE_PATH,
        TRACKING_PATH,
        clean,
        load_json,
        normalize_identity,
        resolve_entity,
    )

try:
    from . import manual_follow_decision as follow_policy
except ImportError:
    import manual_follow_decision as follow_policy

ROOT = Path(__file__).resolve().parents[1]
INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"
FIELDS = {"sampleCompanies", "people", "keywords"}
FIELD_FOR_TYPE = {
    "company": "sampleCompanies",
    "person": "people",
    "topic": "keywords",
}
STATUS_FOR_RESOLUTION = {
    "resolved": "applied",
    "review": "queued",
    "rejected": "dismissed",
}
MAX_RECONCILIATION_ROUNDS = 8


def semantic(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: semantic(item)
            for key, item in sorted(value.items())
            if key != "generatedAt"
        }
    if isinstance(value, list):
        return [semantic(item) for item in value]
    return value


def unique(values: list[Any], limit: int = 100) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean(raw, 240)
        key = normalize_identity(value)
        if not value or not key or key in seen:
            continue
        result.append(value)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def remove_name(values: Any, name: str) -> list[str]:
    rows = values if isinstance(values, list) else []
    key = normalize_identity(name)
    return [clean(value, 240) for value in rows if normalize_identity(value) != key and clean(value, 240)]


def append_name(values: Any, name: str) -> list[str]:
    rows = [clean(value, 240) for value in values if clean(value, 240)] if isinstance(values, list) else []
    key = normalize_identity(name)
    if key and all(normalize_identity(value) != key for value in rows):
        rows.append(name)
    return rows


def track_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tracks = config.get("tracks", [])
    return {
        clean(track.get("slug"), 120): track
        for track in tracks
        if isinstance(track, dict) and clean(track.get("slug"), 120)
    } if isinstance(tracks, list) else {}


def reconcile_payloads(
    config_payload: dict[str, Any],
    inbox_payload: dict[str, Any],
    *,
    decisions_payload: dict[str, Any],
    company_registry_payload: dict[str, Any],
    people_payload: dict[str, Any],
    intents_payload: dict[str, Any] | None = None,
    admins_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    config = copy.deepcopy(config_payload)
    inbox = copy.deepcopy(inbox_payload)
    tracks = track_map(config)
    follow_states = follow_policy.scoped_follow_states(intents_payload or {}, admins_payload or {})
    records = inbox.get("records", []) if isinstance(inbox.get("records"), list) else []

    # Remove only values whose original capture explicitly recorded that placement.
    for record in records:
        if not isinstance(record, dict):
            continue
        old_name = clean(record.get("canonicalName"), 160)
        for raw_position in record.get("appliedTo", []) if isinstance(record.get("appliedTo"), list) else []:
            position = clean(raw_position, 200)
            if ":" not in position:
                continue
            slug, field = position.split(":", 1)
            track = tracks.get(slug)
            if not track or field not in FIELDS:
                continue
            track[field] = remove_name(track.get(field), old_name)

    # Resolution must not depend on capture order. Preload topic facts that are
    # already explicit or versioned before resolving company-shaped records.
    resolution_tracking = copy.deepcopy(config)
    resolution_tracks = track_map(resolution_tracking)
    raw_decisions = (
        decisions_payload.get("decisions", {})
        if isinstance(decisions_payload.get("decisions"), dict)
        else {}
    )
    for record in records:
        if not isinstance(record, dict):
            continue
        existing_resolution = (
            record.get("resolution") if isinstance(record.get("resolution"), dict) else {}
        )
        requested_type = clean(existing_resolution.get("requestedType"), 20) or clean(
            record.get("entityType"), 20
        )
        raw_name = clean(record.get("rawSelection"), 160) or clean(
            record.get("canonicalName"), 160
        )
        decision = raw_decisions.get(normalize_identity(raw_name))
        seed_name = ""
        if (
            isinstance(decision, dict)
            and clean(decision.get("status"), 20) == "resolved"
            and clean(decision.get("entityType"), 20) == "topic"
        ):
            seed_name = clean(decision.get("canonicalName"), 160) or raw_name
        elif requested_type == "topic" or (
            clean(existing_resolution.get("status"), 20) == "resolved"
            and clean(existing_resolution.get("entityType"), 20) == "topic"
        ):
            seed_name = clean(existing_resolution.get("canonicalName"), 160) or raw_name
        if not seed_name:
            continue
        for slug in unique(
            record.get("trackSlugs", [])
            if isinstance(record.get("trackSlugs"), list)
            else [],
            30,
        ):
            track = resolution_tracks.get(slug)
            if track:
                track["keywords"] = append_name(track.get("keywords"), seed_name)

    stats = {"resolved": 0, "review": 0, "rejected": 0, "reclassified": 0}
    next_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        existing_resolution = record.get("resolution") if isinstance(record.get("resolution"), dict) else {}
        requested_type = clean(existing_resolution.get("requestedType"), 20) or clean(record.get("entityType"), 20)
        raw_name = clean(record.get("rawSelection"), 160) or clean(record.get("canonicalName"), 160)
        source = record.get("source") if isinstance(record.get("source"), dict) else {}
        resolution = resolve_entity(
            requested_type,
            raw_name,
            source,
            decisions_payload=decisions_payload,
            company_registry_payload=company_registry_payload,
            people_payload=people_payload,
            tracking_payload=resolution_tracking,
        )
        stats[resolution.status] += 1
        if resolution.reclassified:
            stats["reclassified"] += 1

        next_record = copy.deepcopy(record)
        old_canonical = clean(record.get("canonicalName"), 160)
        canonical_name = resolution.canonicalName or raw_name
        aliases = record.get("aliases", []) if isinstance(record.get("aliases"), list) else []
        if old_canonical and normalize_identity(old_canonical) != normalize_identity(canonical_name):
            aliases = [*aliases, old_canonical]
        if raw_name and normalize_identity(raw_name) != normalize_identity(canonical_name):
            aliases = [*aliases, raw_name]

        track_slugs = unique(
            record.get("trackSlugs", []) if isinstance(record.get("trackSlugs"), list) else [],
            30,
        )
        applied_to: list[str] = []
        track_names: list[str] = []
        requested_field = FIELD_FOR_TYPE.get(requested_type, "")
        approved_tracks = {
            slug for slug in track_slugs
            if follow_states.get((slug, requested_field, follow_policy.identity(raw_name, requested_field))) == "approved"
        }
        follow_name = canonical_name if resolution.status == "resolved" and resolution.entityType == requested_type else raw_name
        blocked_tracks = set()
        for slug in track_slugs:
            track = tracks.get(slug)
            if not track:
                continue
            owner_state = follow_states.get((slug, requested_field, follow_policy.identity(raw_name, requested_field)))
            if owner_state == "blocked":
                blocked_tracks.add(slug)
                continue
            if slug in approved_tracks:
                field = requested_field
                value = follow_name
            elif resolution.status == "resolved":
                field = FIELD_FOR_TYPE[resolution.entityType]
                value = canonical_name
                if follow_states.get((slug, field, follow_policy.identity(value, field))) == "blocked":
                    continue
                # One legacy capture cannot represent two conflicting kinds.
                if approved_tracks and resolution.entityType != requested_type:
                    continue
            else:
                continue
            track[field] = append_name(track.get(field), value)
            applied_to.append(f"{slug}:{field}")
            track_name = clean(track.get("name"), 120)
            if track_name:
                track_names.append(track_name)

        next_record.update(
            {
                "entityType": resolution.entityType if resolution.status == "resolved" else requested_type,
                "canonicalName": canonical_name if resolution.status == "resolved" else raw_name,
                "rawSelection": raw_name,
                "aliases": unique(list(aliases), 30),
                "trackSlugs": track_slugs,
                "trackNames": unique(track_names or list(record.get("trackNames", [])), 30),
                "status": STATUS_FOR_RESOLUTION[resolution.status],
                "appliedTo": applied_to,
                "resolution": resolution.to_dict(),
            }
        )
        if approved_tracks:
            # The real machine result remains in resolution, even when review is
            # needed for identity enrichment. Follow approval has separate scope.
            next_record.update({
                "entityType": requested_type, "canonicalName": follow_name,
                "status": "applied", "manualDecisionStatus": "approved",
                "identityState": follow_policy.identity_state(resolution.to_dict(),
                    "technology" if requested_type == "topic" else requested_type),
            })
        else:
            next_record.pop("manualDecisionStatus", None)
            next_record.pop("identityState", None)
            if track_slugs and (blocked_tracks == set(track_slugs) or (resolution.status == "resolved" and not applied_to)):
                next_record["status"] = "dismissed"
        next_records.append(next_record)

    next_records.sort(
        key=lambda row: (
            clean(row.get("capturedAt"), 80),
            clean(row.get("canonicalName"), 160).casefold(),
        ),
        reverse=True,
    )
    inbox["schemaVersion"] = 1
    inbox["records"] = next_records
    follow_policy.project_follow_states(config, intents_payload or {}, admins_payload or {})
    return config, inbox, stats


def _state_fingerprint(config: dict[str, Any], inbox: dict[str, Any]) -> str:
    return json.dumps(
        [semantic(config), semantic(inbox)],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stabilize_payloads(
    config_payload: dict[str, Any],
    inbox_payload: dict[str, Any],
    *,
    decisions_payload: dict[str, Any],
    company_registry_payload: dict[str, Any],
    people_payload: dict[str, Any],
    intents_payload: dict[str, Any] | None = None,
    admins_payload: dict[str, Any] | None = None,
    max_rounds: int = MAX_RECONCILIATION_ROUNDS,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    """Run reconciliation until taxonomy-dependent resolutions reach one fixed point."""

    current_config = copy.deepcopy(config_payload)
    current_inbox = copy.deepcopy(inbox_payload)
    seen = {_state_fingerprint(current_config, current_inbox)}

    for round_number in range(1, max_rounds + 1):
        next_config, next_inbox, stats = reconcile_payloads(
            current_config,
            current_inbox,
            decisions_payload=decisions_payload,
            company_registry_payload=company_registry_payload,
            people_payload=people_payload,
            intents_payload=intents_payload, admins_payload=admins_payload,
        )
        if (
            semantic(current_config) == semantic(next_config)
            and semantic(current_inbox) == semantic(next_inbox)
        ):
            return next_config, next_inbox, {**stats, "rounds": round_number - 1}

        fingerprint = _state_fingerprint(next_config, next_inbox)
        if fingerprint in seen:
            raise RuntimeError("entity resolution reconciliation entered a cycle")
        seen.add(fingerprint)
        current_config = next_config
        current_inbox = next_inbox

    raise RuntimeError(
        f"entity resolution reconciliation did not converge within {max_rounds} rounds"
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--config", type=Path, default=TRACKING_PATH)
    parser.add_argument("--inbox", type=Path, default=INBOX_PATH)
    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    parser.add_argument("--companies", type=Path, default=COMPANY_REGISTRY_PATH)
    parser.add_argument("--people", type=Path, default=PEOPLE_PATH)
    parser.add_argument("--intents", type=Path, default=ROOT / "config/tracking_intents.json")
    parser.add_argument("--admins", type=Path, default=ROOT / "config/tracking_admins.json")
    args = parser.parse_args()
    # Do not silently discard durable manual approvals on a broken graph read.
    intents = json.loads(args.intents.read_text(encoding="utf-8"))
    admins = json.loads(args.admins.read_text(encoding="utf-8"))
    if not isinstance(intents, dict) or any(not isinstance(intents.get(k), list) for k in ("entities", "memberships")):
        raise SystemExit("invalid manual intent graph; refusing to reconcile")
    if not isinstance(admins, dict) or not isinstance(admins.get("actors"), list):
        raise SystemExit("invalid manual actor registry; refusing to reconcile")

    original_config = load_json(args.config, {"schemaVersion": 1, "tracks": []})
    original_inbox = load_json(args.inbox, {"schemaVersion": 1, "generatedAt": "", "records": []})
    next_config, next_inbox, stats = stabilize_payloads(
        original_config,
        original_inbox,
        decisions_payload=load_json(args.decisions, {"decisions": {}}),
        company_registry_payload=load_json(args.companies, {"companies": []}),
        people_payload=load_json(args.people, {"people": []}),
        intents_payload=intents, admins_payload=admins,
    )

    config_changed = semantic(original_config) != semantic(next_config)
    inbox_changed = semantic(original_inbox) != semantic(next_inbox)
    if args.check:
        if config_changed or inbox_changed:
            raise SystemExit("entity resolution reconciliation is not at a fixed point")
        print(json.dumps({"valid": True, **stats}, ensure_ascii=False, sort_keys=True))
        return 0

    if config_changed:
        write_json(args.config, next_config)
    if inbox_changed:
        next_inbox["generatedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
        write_json(args.inbox, next_inbox)
    print(
        json.dumps(
            {
                "configChanged": config_changed,
                "inboxChanged": inbox_changed,
                **stats,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
