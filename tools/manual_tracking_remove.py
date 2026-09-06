#!/usr/bin/env python3
"""Validate or apply removal of one fixed watchlist object from one track.

This is the inverse companion to ``manual_tracking_entrypoint.py``.  It never
hard-deletes intent provenance.  When a matching intent membership exists, the
membership is moved to ``rejected`` and a public owner audit origin is appended.
That rejected state is authoritative for the existing manual-feedback pipeline,
so automatic discovery cannot silently revive an owner-removed relationship.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACKING = ROOT / "config" / "user_tracking.json"
DEFAULT_INTENTS = ROOT / "config" / "tracking_intents.json"

FIELD_BY_KIND = {
    "keyword": "keywords",
    "technology": "keywords",
    "person": "people",
    "company": "sampleCompanies",
}
ENTITY_KINDS = {
    "keyword": {"keyword", "technology", "topic"},
    "technology": {"keyword", "technology", "topic"},
    "person": {"person"},
    "company": {"company"},
}


class ManualTrackingRemovalError(ValueError):
    pass


def clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def display_identity(value: Any) -> str:
    return unicodedata.normalize("NFKC", clean(value, 300)).casefold()


def loose_identity(value: Any) -> str:
    text = display_identity(value)
    return "".join(character for character in text if character.isalnum() or "\u3400" <= character <= "\u9fff")


def split_pipe(value: Any, limit: int = 20) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in str(value or "").split("|"):
        item = clean(raw, 240)
        key = display_identity(item)
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualTrackingRemovalError(f"无法读取 {path.name}。") from exc
    if not isinstance(payload, dict):
        raise ManualTrackingRemovalError(f"{path.name} 顶层必须是对象。")
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def find_track(tracking: dict[str, Any], requested: str) -> dict[str, Any]:
    tracks = tracking.get("tracks")
    if not isinstance(tracks, list):
        raise ManualTrackingRemovalError("user_tracking.json.tracks 不是数组。")
    key = display_identity(requested)
    matches = [
        row
        for row in tracks
        if isinstance(row, dict)
        and key in {display_identity(row.get("slug")), display_identity(row.get("name"))}
    ]
    if len(matches) != 1:
        raise ManualTrackingRemovalError(f"目标赛道无法唯一解析：{requested}")
    return matches[0]


def remove_runtime_value(track: dict[str, Any], field: str, name: str) -> tuple[bool, str]:
    values = track.get(field)
    if not isinstance(values, list):
        raise ManualTrackingRemovalError(f"赛道字段 {field} 不是数组。")
    exact = display_identity(name)
    matched = [raw for raw in values if display_identity(raw) == exact]
    if not matched:
        return False, ""
    matched_name = clean(matched[0], 240)
    track[field] = [raw for raw in values if display_identity(raw) != exact]
    return True, matched_name


def matching_entity_ids(intents: dict[str, Any], kind: str, name: str) -> set[str]:
    entities = intents.get("entities")
    if not isinstance(entities, list):
        raise ManualTrackingRemovalError("tracking_intents.json.entities 不是数组。")
    exact = display_identity(name)
    loose = loose_identity(name)
    ids: set[str] = set()
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_kind = clean(entity.get("kind"), 40).casefold()
        if entity_kind not in ENTITY_KINDS[kind]:
            continue
        aliases = entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
        names = [entity.get("name"), *aliases]
        exact_match = any(display_identity(value) == exact for value in names if clean(value))
        loose_match = bool(loose) and any(loose_identity(value) == loose for value in names if clean(value))
        if exact_match or loose_match:
            entity_id = clean(entity.get("id"), 240)
            if entity_id:
                ids.add(entity_id)
    return ids


def reject_memberships(
    intents: dict[str, Any],
    *,
    entity_ids: set[str],
    track_slug: str,
    actor: str,
    triggering_actor: str,
    reasons: list[str],
    note: str,
    now: str,
) -> tuple[int, bool]:
    memberships = intents.get("memberships")
    if not isinstance(memberships, list):
        raise ManualTrackingRemovalError("tracking_intents.json.memberships 不是数组。")
    changed = False
    count = 0
    for membership in memberships:
        if not isinstance(membership, dict):
            continue
        if clean(membership.get("trackSlug"), 160) != track_slug:
            continue
        if clean(membership.get("entityId"), 240) not in entity_ids:
            continue
        count += 1
        if clean(membership.get("state"), 40).casefold() != "rejected":
            membership["state"] = "rejected"
            changed = True
        origins = membership.get("origins")
        if not isinstance(origins, list):
            origins = []
            membership["origins"] = origins
            changed = True
        audit = {
            "origin": "manual",
            "actor": actor,
            "triggeringActor": triggering_actor,
            "at": now,
            "reasons": reasons,
            "note": note,
            "decision": "remove-fixed-watch",
        }
        if not origins or origins[-1] != audit:
            origins.append(audit)
            changed = True
    return count, changed


def apply_removal(
    tracking: dict[str, Any],
    intents: dict[str, Any],
    *,
    kind: str,
    name: str,
    track_name: str,
    actor: str,
    triggering_actor: str,
    reasons: list[str],
    note: str,
    now: str | None = None,
) -> dict[str, Any]:
    if kind not in FIELD_BY_KIND:
        raise ManualTrackingRemovalError("移除仅支持 technology、keyword、person、company。")
    if len(clean(name, 240)) < 2:
        raise ManualTrackingRemovalError("名称至少需要两个有效字符。")
    if not reasons:
        raise ManualTrackingRemovalError("移除固定关注必须填写至少一个治理原因。")

    track = find_track(tracking, track_name)
    slug = clean(track.get("slug"), 160)
    field = FIELD_BY_KIND[kind]
    config_changed, runtime_name = remove_runtime_value(track, field, name)
    entity_ids = matching_entity_ids(intents, kind, runtime_name or name)
    membership_count, intents_changed = reject_memberships(
        intents,
        entity_ids=entity_ids,
        track_slug=slug,
        actor=actor,
        triggering_actor=triggering_actor,
        reasons=reasons,
        note=note,
        now=now or datetime.now(UTC).isoformat(),
    )
    changed = config_changed or intents_changed
    return {
        "ok": True,
        "changed": changed,
        "configChanged": config_changed,
        "inboxChanged": False,
        "intentsChanged": intents_changed,
        "reviewQueued": False,
        "operation": "remove-fixed-watch",
        "objectType": kind,
        "name": runtime_name or name,
        "trackSlug": slug,
        "field": field,
        "membershipCount": membership_count,
        "state": "rejected" if membership_count else "runtime-only-removed" if config_changed else "already-absent",
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--mode", choices=("validate", "apply"), required=True)
    result.add_argument("--kind", required=True)
    result.add_argument("--name", required=True)
    result.add_argument("--tracks", required=True)
    result.add_argument("--reasons", required=True)
    result.add_argument("--note", default="")
    result.add_argument("--actor", required=True)
    result.add_argument("--triggering-actor", required=True)
    result.add_argument("--tracking", type=Path, default=DEFAULT_TRACKING)
    result.add_argument("--intents", type=Path, default=DEFAULT_INTENTS)
    return result


def main() -> int:
    args = parser().parse_args()
    tracks = split_pipe(args.tracks, 3)
    if len(tracks) != 1:
        raise SystemExit("固定关注移除一次只能操作一个赛道。")
    reasons = split_pipe(args.reasons, 12)
    tracking = load_json(args.tracking)
    intents = load_json(args.intents)
    next_tracking = copy.deepcopy(tracking)
    next_intents = copy.deepcopy(intents)
    try:
        report = apply_removal(
            next_tracking,
            next_intents,
            kind=clean(args.kind, 40).casefold(),
            name=clean(args.name, 240),
            track_name=tracks[0],
            actor=clean(args.actor, 120),
            triggering_actor=clean(args.triggering_actor, 120),
            reasons=reasons,
            note=clean(args.note, 800),
        )
    except ManualTrackingRemovalError as exc:
        print(json.dumps({"ok": False, "changed": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    if args.mode == "apply" and report["changed"]:
        atomic_write_json(args.tracking, next_tracking)
        atomic_write_json(args.intents, next_intents)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
