#!/usr/bin/env python3
"""Validate or apply a durable owner rejection for one automatic tracking candidate.

This is the negative-feedback companion to ``manual_tracking.py``.  It is scoped
only to values that already exist in the automatic-discovery ledger (or are
already blocked, for idempotency).  Applying a rejection:

* records the value in ``ignoredRecommendations``;
* removes it from the current runtime track if automatic discovery had activated it;
* writes an automatic-discovery tombstone so the value cannot silently revive;
* records a rejected manual intent membership with an auditable owner origin.

The command never fetches evidence URLs and never broadens the candidate beyond
one explicitly selected track.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACKING = ROOT / "config" / "user_tracking.json"
DEFAULT_INTENTS = ROOT / "config" / "tracking_intents.json"
DEFAULT_LEDGER = ROOT / "config" / "tracking_auto_discovery.json"

FIELD_BY_KIND = {
    "technology": "keywords",
    "person": "people",
    "company": "sampleCompanies",
}
IGNORE_FIELD_BY_KIND = {
    "technology": "keywords",
    "person": "people",
    "company": "companies",
}
LEDGER_KIND_BY_KIND = dict(FIELD_BY_KIND)
ROLE_BY_KIND = {
    "technology": "keyword",
    "person": "actor",
    "company": "actor",
}
ENTITY_KINDS = {
    "technology": {"technology", "keyword", "topic"},
    "person": {"person"},
    "company": {"company"},
}


class ManualTrackingIgnoreError(ValueError):
    pass


def clean(value: Any, limit: int = 500) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).strip()[:limit]


def stable_id(prefix: str, *parts: Any, length: int = 20) -> str:
    material = "\x1f".join(clean(part, 4000).casefold() for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def signal_identity(value: Any, field: str) -> str:
    normalized = clean(value, 500).casefold()
    if field == "keywords":
        return re.sub(r"[^a-z0-9\u3400-\u9fff+#./]+", "", normalized)
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", normalized)


def split_pipe(value: Any, limit: int = 20) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in str(value or "").split("|"):
        item = clean(raw, 240)
        key = item.casefold()
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
        raise ManualTrackingIgnoreError(f"无法读取 {path.name}。") from exc
    if not isinstance(payload, dict):
        raise ManualTrackingIgnoreError(f"{path.name} 顶层必须是对象。")
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def find_track(tracking: dict[str, Any], requested: str) -> dict[str, Any]:
    tracks = tracking.get("tracks")
    if not isinstance(tracks, list):
        raise ManualTrackingIgnoreError("user_tracking.json.tracks 不是数组。")
    key = clean(requested, 160).casefold()
    matches = [
        row
        for row in tracks
        if isinstance(row, dict)
        and key in {clean(row.get("slug"), 160).casefold(), clean(row.get("name"), 160).casefold()}
    ]
    if len(matches) != 1:
        raise ManualTrackingIgnoreError(f"目标赛道无法唯一解析：{requested}")
    return matches[0]


def _parse_time(value: Any) -> float:
    raw = clean(value, 80)
    if not raw:
        return 0.0
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _ledger_row_matches(row: dict[str, Any], slug: str, ledger_kind: str, value: str) -> bool:
    if clean(row.get("track"), 160) != slug or clean(row.get("kind"), 80) != ledger_kind:
        return False
    return signal_identity(row.get("value"), ledger_kind) == signal_identity(value, ledger_kind)


def latest_auto_state(ledger: dict[str, Any], slug: str, ledger_kind: str, value: str) -> str:
    latest_state = ""
    latest_at = -1.0
    for row in ledger.get("added", []) if isinstance(ledger.get("added"), list) else []:
        if not isinstance(row, dict) or not _ledger_row_matches(row, slug, ledger_kind, value):
            continue
        at = _parse_time(row.get("addedAt"))
        if at >= latest_at:
            latest_state, latest_at = "added", at
    for row in ledger.get("removed", []) if isinstance(ledger.get("removed"), list) else []:
        if not isinstance(row, dict) or not _ledger_row_matches(row, slug, ledger_kind, value):
            continue
        at = _parse_time(row.get("removedAt") or row.get("updatedAt"))
        if at >= latest_at:
            latest_state, latest_at = "removed", at
    return latest_state


def _ignored_values(track: dict[str, Any], ignore_field: str) -> list[str]:
    ignored = track.get("ignoredRecommendations")
    if not isinstance(ignored, dict):
        return []
    values = ignored.get(ignore_field)
    return [clean(value, 240) for value in values] if isinstance(values, list) else []


def _is_ignored(track: dict[str, Any], ignore_field: str, runtime_field: str, value: str) -> bool:
    target = signal_identity(value, runtime_field)
    return any(signal_identity(item, runtime_field) == target for item in _ignored_values(track, ignore_field))


def _add_ignored(track: dict[str, Any], ignore_field: str, runtime_field: str, value: str) -> bool:
    ignored = track.get("ignoredRecommendations")
    if not isinstance(ignored, dict):
        ignored = {}
        track["ignoredRecommendations"] = ignored
    values = ignored.get(ignore_field)
    if not isinstance(values, list):
        values = []
        ignored[ignore_field] = values
    target = signal_identity(value, runtime_field)
    if any(signal_identity(item, runtime_field) == target for item in values):
        return False
    values.append(value)
    ignored[ignore_field] = values[:300]
    return True


def _remove_runtime_value(track: dict[str, Any], runtime_field: str, value: str) -> bool:
    values = track.get(runtime_field)
    if not isinstance(values, list):
        return False
    target = signal_identity(value, runtime_field)
    next_values = [item for item in values if signal_identity(item, runtime_field) != target]
    if len(next_values) == len(values):
        return False
    track[runtime_field] = next_values
    return True


def _append_tombstone(
    ledger: dict[str, Any], *, slug: str, ledger_kind: str, value: str, now: str
) -> bool:
    if latest_auto_state(ledger, slug, ledger_kind, value) == "removed":
        return False
    removed = ledger.setdefault("removed", [])
    if not isinstance(removed, list):
        raise ManualTrackingIgnoreError("tracking_auto_discovery.json.removed 不是数组。")
    removed.append(
        {
            "track": slug,
            "kind": ledger_kind,
            "value": value,
            "removedAt": now,
            "reason": "manual-ignore-auto-candidate",
        }
    )
    ledger["updatedAt"] = now
    return True


def _entity_identity(kind: str, value: Any) -> str:
    return signal_identity(value, "keywords" if kind == "technology" else kind)


def _find_or_create_entity(
    intents: dict[str, Any], *, kind: str, name: str, actor: str, now: str
) -> tuple[dict[str, Any], bool]:
    entities = intents.setdefault("entities", [])
    if not isinstance(entities, list):
        raise ManualTrackingIgnoreError("tracking_intents.json.entities 不是数组。")
    target = _entity_identity(kind, name)
    for entity in entities:
        if not isinstance(entity, dict) or clean(entity.get("kind"), 40) not in ENTITY_KINDS[kind]:
            continue
        aliases = entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
        if any(_entity_identity(kind, value) == target for value in [entity.get("name"), *aliases]):
            return entity, False

    entity_id = stable_id("technology", signal_identity(name, "keywords")) if kind == "technology" else stable_id(kind, name)
    entity = {
        "id": entity_id,
        "kind": kind,
        "name": name,
        "aliases": [],
        "keywords": [name] if kind == "technology" else [],
        "state": "rejected",
        "resolutionSource": "unresolved",
        "resolutionStatus": "rejected",
        "createdAt": now,
        "createdBy": actor,
    }
    entities.append(entity)
    return entity, True


def _reject_membership(
    intents: dict[str, Any], *, kind: str, name: str, slug: str, actor: str,
    triggering_actor: str, reasons: list[str], note: str, now: str
) -> bool:
    entity, entity_created = _find_or_create_entity(intents, kind=kind, name=name, actor=actor, now=now)
    entity_id = clean(entity.get("id"), 240)
    role = ROLE_BY_KIND[kind]
    memberships = intents.setdefault("memberships", [])
    if not isinstance(memberships, list):
        raise ManualTrackingIgnoreError("tracking_intents.json.memberships 不是数组。")
    membership_id = stable_id("membership", f"track:{slug}", entity_id, role)
    membership = next(
        (
            row
            for row in memberships
            if isinstance(row, dict)
            and (
                clean(row.get("id"), 240) == membership_id
                or (
                    clean(row.get("entityId"), 240) == entity_id
                    and clean(row.get("trackId"), 200).removeprefix("track:") == slug
                    and clean(row.get("role"), 40) == role
                )
            )
        ),
        None,
    )
    if membership is not None and clean(membership.get("state"), 40).casefold() == "active":
        raise ManualTrackingIgnoreError("该对象已被人工固定关注；请使用固定关注移除流程，而不是忽略自动候选。")

    changed = entity_created
    if membership is None:
        membership = {
            "id": membership_id,
            "trackId": f"track:{slug}",
            "entityId": entity_id,
            "role": role,
            "state": "rejected",
            "pinned": True,
            "confidence": "verified",
            "origins": [],
        }
        memberships.append(membership)
        changed = True
    else:
        before = json.dumps(membership, sort_keys=True, ensure_ascii=False)
        membership["trackId"] = f"track:{slug}"
        membership["state"] = "rejected"
        membership["pinned"] = True
        membership["confidence"] = "verified"
        membership.setdefault("origins", [])
        changed = changed or before != json.dumps(membership, sort_keys=True, ensure_ascii=False)

    origins = membership.get("origins")
    if not isinstance(origins, list):
        origins = []
        membership["origins"] = origins
        changed = True
    origin_material = json.dumps(
        {
            "actor": actor.casefold(),
            "entityId": entity_id,
            "trackId": f"track:{slug}",
            "decision": "ignore-auto-candidate",
            "reasons": sorted(reasons),
            "note": note,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    origin_id = stable_id("origin", origin_material)
    if not any(isinstance(origin, dict) and clean(origin.get("id"), 240) == origin_id for origin in origins):
        origins.append(
            {
                "id": origin_id,
                "origin": "manual",
                "actor": actor,
                "triggeringActor": triggering_actor,
                "at": now,
                "evidenceUrl": "",
                "reasons": reasons,
                "note": note,
                "decision": "ignore-auto-candidate",
            }
        )
        changed = True
    if clean(entity.get("state"), 40).casefold() != "active" and entity.get("state") != "rejected":
        entity["state"] = "rejected"
        changed = True
    return changed


def apply_ignore(
    tracking: dict[str, Any], intents: dict[str, Any], ledger: dict[str, Any], *,
    kind: str, name: str, track_name: str, actor: str, triggering_actor: str,
    reasons: list[str], note: str, now: str | None = None,
) -> dict[str, Any]:
    if kind not in FIELD_BY_KIND:
        raise ManualTrackingIgnoreError("自动候选忽略仅支持 technology、person、company。")
    name = clean(name, 240)
    if len(name) < 2:
        raise ManualTrackingIgnoreError("名称至少需要两个有效字符。")
    if not reasons:
        raise ManualTrackingIgnoreError("忽略自动候选必须填写至少一个治理原因。")

    track = find_track(tracking, track_name)
    slug = clean(track.get("slug"), 160)
    runtime_field = FIELD_BY_KIND[kind]
    ignore_field = IGNORE_FIELD_BY_KIND[kind]
    ledger_kind = LEDGER_KIND_BY_KIND[kind]
    auto_state = latest_auto_state(ledger, slug, ledger_kind, name)
    already_ignored = _is_ignored(track, ignore_field, runtime_field, name)
    if not auto_state and not already_ignored:
        raise ManualTrackingIgnoreError("该对象不是当前自动发现候选，不能通过自动候选忽略流程写入负反馈。")

    timestamp = now or datetime.now(UTC).isoformat()
    ignored_added = _add_ignored(track, ignore_field, runtime_field, name)
    runtime_removed = _remove_runtime_value(track, runtime_field, name)
    tombstone_added = _append_tombstone(
        ledger, slug=slug, ledger_kind=ledger_kind, value=name, now=timestamp
    ) if auto_state == "added" else False
    intents_changed = _reject_membership(
        intents,
        kind=kind,
        name=name,
        slug=slug,
        actor=actor,
        triggering_actor=triggering_actor,
        reasons=reasons,
        note=note,
        now=timestamp,
    )
    config_changed = ignored_added or runtime_removed
    ledger_changed = tombstone_added
    changed = config_changed or intents_changed or ledger_changed
    return {
        "ok": True,
        "changed": changed,
        "configChanged": config_changed,
        "intentsChanged": intents_changed,
        "ledgerChanged": ledger_changed,
        "operation": "ignore-auto-candidate",
        "objectType": kind,
        "name": name,
        "trackSlug": slug,
        "candidateState": auto_state or "already-ignored",
        "ignoredAdded": ignored_added,
        "runtimeRemoved": runtime_removed,
        "tombstoneAdded": tombstone_added,
        "state": "rejected" if changed else "already-blocked",
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
    result.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    tracks = split_pipe(args.tracks, 3)
    if len(tracks) != 1:
        raise SystemExit("自动候选忽略一次只能操作一个赛道。")
    reasons = split_pipe(args.reasons, 12)
    tracking = load_json(args.tracking)
    intents = load_json(args.intents)
    ledger = load_json(args.ledger)
    next_tracking = copy.deepcopy(tracking)
    next_intents = copy.deepcopy(intents)
    next_ledger = copy.deepcopy(ledger)
    try:
        report = apply_ignore(
            next_tracking,
            next_intents,
            next_ledger,
            kind=clean(args.kind, 40).casefold(),
            name=clean(args.name, 240),
            track_name=tracks[0],
            actor=clean(args.actor, 120),
            triggering_actor=clean(args.triggering_actor, 120),
            reasons=reasons,
            note=clean(args.note, 800),
        )
    except ManualTrackingIgnoreError as exc:
        print(json.dumps({"ok": False, "changed": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    if args.mode == "apply" and report["changed"]:
        atomic_write_json(args.tracking, next_tracking)
        atomic_write_json(args.intents, next_intents)
        atomic_write_json(args.ledger, next_ledger)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
