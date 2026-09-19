#!/usr/bin/env python3
"""Replay legacy batch-confirmed company pins through the current trust gate.

Older manual-tracking batches lost ``origin=manual-confirmed`` before the request
reached the canonical writer.  The affected rows are still auditable because the
admin UI wrote a distinct capture note.  This migration replays only those
allowlisted manual captures.  The explicit follow decision is authoritative; machine identity enrichment
remains separate and cannot send that decision back for a second review.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

try:
    import manual_tracking as manual
    import manual_tracking_batch as batch
except ImportError:  # pragma: no cover
    from tools import manual_tracking as manual
    from tools import manual_tracking_batch as batch


ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"
INTENTS_PATH = ROOT / "config" / "tracking_intents.json"
ADMINS_PATH = ROOT / "config" / "tracking_admins.json"

LEGACY_CONFIRM_MARKER = "批量确认自动扩展为持续关注"


def _allowed_actors(payload: Mapping[str, Any]) -> set[str]:
    actors = payload.get("actors", [])
    if not isinstance(actors, list):
        return set()
    return {
        manual.clean(actor, 120).casefold()
        for actor in actors
        if manual.clean(actor, 120)
    }


def _legacy_confirmed_capture(
    row: Mapping[str, Any], allowed_actors: set[str]
) -> bool:
    source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
    actor = manual.clean(row.get("capturedBy"), 120)
    note = manual.clean(row.get("note"), 800)
    summary = manual.clean(source.get("summary"), 800)
    return bool(
        manual.clean(row.get("entityType"), 30) == "company"
        and actor.casefold() in allowed_actors
        and manual.clean(source.get("channel"), 80) == "manual-tracking"
        and LEGACY_CONFIRM_MARKER in (note or summary)
        and manual.clean(source.get("url"), 1200)
        and isinstance(row.get("trackSlugs"), list)
        and row.get("trackSlugs")
    )


def _request_from_capture(
    row: Mapping[str, Any], tracking: Mapping[str, Any], track_slugs: list[str]
) -> dict[str, Any]:
    source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
    name = manual.clean(row.get("rawSelection"), 160) or manual.clean(
        row.get("canonicalName"), 160
    )
    reasons = row.get("reasons") if isinstance(row.get("reasons"), list) else []
    note = manual.clean(row.get("note"), 800) or manual.clean(
        source.get("summary"), 800
    )
    row_for_batch = {
        "objectType": "company",
        "name": name,
        "targetTracks": track_slugs,
        "keywords": [],
        "sourceUrl": manual.clean(source.get("url"), 1200),
        "sourceCategory": "media",
        "region": "global",
        "reasons": [
            manual.clean(reason, 120)
            for reason in reasons
            if manual.clean(reason, 120)
        ],
        "note": note,
        "origin": "manual-confirmed",
    }
    args = batch.namespace_for(row_for_batch, "apply")
    request = manual._normalized_input(args, tracking)
    request["origin"] = "manual-confirmed"
    return request


def _review_track_slugs(
    row: Mapping[str, Any], intents: Mapping[str, Any]
) -> list[str]:
    """Return only still-pending pinned edges; never revive later removals."""

    name = manual.clean(row.get("rawSelection"), 160) or manual.clean(
        row.get("canonicalName"), 160
    )
    identity = manual.normalize_identity(name)
    if not identity:
        return []
    entities = intents.get("entities", [])
    memberships = intents.get("memberships", [])
    if not isinstance(entities, list) or not isinstance(memberships, list):
        return []

    matching_ids: set[str] = set()
    for entity in entities:
        if not isinstance(entity, Mapping) or entity.get("kind") != "company":
            continue
        names = [entity.get("name")]
        aliases = entity.get("aliases")
        if isinstance(aliases, list):
            names.extend(aliases)
        if any(manual.normalize_identity(value) == identity for value in names):
            entity_id = manual.clean(entity.get("id"), 240)
            if entity_id:
                matching_ids.add(entity_id)

    requested = {
        manual.clean(slug, 120)
        for slug in row.get("trackSlugs", [])
        if manual.clean(slug, 120)
    }
    vetoed = {
        str(m.get("trackId", "")).removeprefix("track:")
        for m in memberships if isinstance(m, Mapping)
        and m.get("entityId") in matching_ids
        and m.get("state") in {"rejected", "held", "disabled", "removed", "ignored"}
    }
    if any(isinstance(e, Mapping) and e.get("id") in matching_ids
           and e.get("state") in {"rejected", "held", "disabled", "removed", "ignored"} for e in entities):
        return []
    eligible: list[str] = []
    for membership in memberships:
        if not isinstance(membership, Mapping):
            continue
        track_id = manual.clean(membership.get("trackId"), 160)
        slug = track_id.removeprefix("track:")
        if (
            membership.get("entityId") in matching_ids
            and slug in requested
            and slug not in vetoed
            and membership.get("pinned") is True
            and manual.clean(membership.get("state"), 30) == "review"
        ):
            eligible.append(slug)
    return sorted(set(eligible), key=str.casefold)


def reconcile_legacy_manual_confirmed_tracking(
    tracking_payload: Mapping[str, Any],
    inbox_payload: Mapping[str, Any],
    intents_payload: Mapping[str, Any],
    admins_payload: Mapping[str, Any],
    *,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    tracking = copy.deepcopy(dict(tracking_payload))
    inbox = copy.deepcopy(dict(inbox_payload))
    intents = copy.deepcopy(dict(intents_payload))
    allowed = _allowed_actors(admins_payload)
    timestamp = now or datetime.now(UTC).isoformat(timespec="seconds")

    attempted: list[str] = []
    promoted: list[str] = []
    held: list[str] = []
    skipped: list[dict[str, str]] = []

    records = inbox.get("records", [])
    if not isinstance(records, list):
        records = []
        inbox["records"] = records

    for row in list(records):
        if not isinstance(row, dict) or not _legacy_confirmed_capture(row, allowed):
            continue
        name = manual.clean(row.get("rawSelection"), 160) or manual.clean(
            row.get("canonicalName"), 160
        )
        review_tracks = _review_track_slugs(row, intents)
        if not review_tracks:
            continue
        try:
            request = _request_from_capture(row, tracking, review_tracks)
            applied = manual.apply_request(
                tracking,
                inbox,
                intents,
                request,
                manual.clean(row.get("capturedBy"), 120),
                timestamp,
            )
        except manual.ManualTrackingError as exc:
            skipped.append({"name": name, "reason": manual.clean(exc, 500)})
            continue

        attempted.append(name)
        resolution = applied.get("resolution")
        resolution = resolution if isinstance(resolution, Mapping) else {}
        if applied.get("manualDecisionStatus") == "approved":
            promoted.append(name)
        else:
            held.append(name)

    report = {
        "eligibleCount": len(attempted),
        "promotedCount": len(set(promoted)),
        "promotedNames": sorted(set(promoted), key=str.casefold),
        "heldCount": len(set(held)),
        "heldNames": sorted(set(held), key=str.casefold),
        "skippedCount": len(skipped),
        "skipped": skipped,
    }
    return tracking, inbox, intents, report


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--inbox", type=Path, default=INBOX_PATH)
    parser.add_argument("--intents", type=Path, default=INTENTS_PATH)
    parser.add_argument("--admins", type=Path, default=ADMINS_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    current_tracking = manual.load_json(args.tracking, {"tracks": []})
    current_inbox = manual.load_json(
        args.inbox, {"schemaVersion": 1, "records": []}
    )
    current_intents = manual.load_json(
        args.intents, {"schemaVersion": 1, "entities": [], "memberships": []}
    )
    next_tracking, next_inbox, next_intents, report = (
        reconcile_legacy_manual_confirmed_tracking(
            current_tracking,
            current_inbox,
            current_intents,
            manual.load_json(args.admins, {"actors": []}),
        )
    )
    changed = (
        current_tracking != next_tracking
        or current_inbox != next_inbox
        or current_intents != next_intents
    )
    if args.check:
        if changed:
            raise SystemExit("legacy manual-confirmed tracking state is not reconciled")
        print(json.dumps({"valid": True, **report}, ensure_ascii=False, sort_keys=True))
        return 0

    if current_tracking != next_tracking:
        _write(args.tracking, next_tracking)
    if current_inbox != next_inbox:
        _write(args.inbox, next_inbox)
    if current_intents != next_intents:
        _write(args.intents, next_intents)
    print(json.dumps({"changed": changed, **report}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
