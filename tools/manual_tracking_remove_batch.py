#!/usr/bin/env python3
"""Atomically validate or apply up to 20 governed fixed-watch removals."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.manual_tracking_remove import (
    DEFAULT_INTENTS,
    DEFAULT_TRACKING,
    FIELD_BY_KIND,
    ManualTrackingRemovalError,
    apply_removal,
    atomic_write_json,
    clean,
    load_json,
    split_pipe,
)

MAX_BATCH = 20


def parse_batch(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManualTrackingRemovalError("批量移除 JSON 无法解析。") from exc
    if not isinstance(payload, list) or not payload:
        raise ManualTrackingRemovalError("批量移除必须是非空数组。")
    if len(payload) > MAX_BATCH:
        raise ManualTrackingRemovalError(f"单次最多处理 {MAX_BATCH} 条关系。")

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw_row in enumerate(payload, start=1):
        if not isinstance(raw_row, dict):
            raise ManualTrackingRemovalError(f"第 {index} 条必须是对象。")
        kind = clean(raw_row.get("objectType"), 40).casefold()
        if kind not in FIELD_BY_KIND:
            raise ManualTrackingRemovalError(f"第 {index} 条 objectType 不受支持。")
        name = clean(raw_row.get("name"), 240)
        track = clean(raw_row.get("targetTrack"), 240)
        if len(name) < 2 or not track:
            raise ManualTrackingRemovalError(f"第 {index} 条缺少有效 name/targetTrack。")
        raw_reasons = raw_row.get("reasons")
        if isinstance(raw_reasons, list):
            reasons = []
            for value in raw_reasons:
                reason = clean(value, 240)
                if reason and reason not in reasons:
                    reasons.append(reason)
                if len(reasons) >= 12:
                    break
        else:
            reasons = split_pipe(raw_reasons, 12)
        if not reasons:
            raise ManualTrackingRemovalError(f"第 {index} 条至少需要一个治理原因。")
        note = clean(raw_row.get("note"), 800)
        key = (kind, name.casefold(), track.casefold())
        if key in seen:
            raise ManualTrackingRemovalError(f"第 {index} 条与前面的关系重复。")
        seen.add(key)
        rows.append(
            {
                "objectType": kind,
                "name": name,
                "targetTrack": track,
                "reasons": reasons,
                "note": note,
            }
        )
    return rows


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--mode", choices=("validate", "apply"), required=True)
    result.add_argument("--batch-json", required=True)
    result.add_argument("--actor", required=True)
    result.add_argument("--triggering-actor", required=True)
    result.add_argument("--tracking", type=Path, default=DEFAULT_TRACKING)
    result.add_argument("--intents", type=Path, default=DEFAULT_INTENTS)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        rows = parse_batch(args.batch_json)
        tracking = load_json(args.tracking)
        intents = load_json(args.intents)
        next_tracking = copy.deepcopy(tracking)
        next_intents = copy.deepcopy(intents)
        now = datetime.now(UTC).isoformat()
        items = []
        for index, row in enumerate(rows, start=1):
            report = apply_removal(
                next_tracking,
                next_intents,
                kind=row["objectType"],
                name=row["name"],
                track_name=row["targetTrack"],
                actor=clean(args.actor, 120),
                triggering_actor=clean(args.triggering_actor, 120),
                reasons=row["reasons"],
                note=row["note"],
                now=now,
            )
            items.append({"index": index, "request": row, "report": report})
    except ManualTrackingRemovalError as exc:
        print(json.dumps({"ok": False, "changed": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    changed = next_tracking != tracking or next_intents != intents
    if args.mode == "apply" and changed:
        atomic_write_json(args.tracking, next_tracking)
        atomic_write_json(args.intents, next_intents)

    result = {
        "ok": True,
        "mode": args.mode,
        "count": len(items),
        "changed": changed if args.mode == "apply" else False,
        "previewChanged": changed,
        "changedCount": sum(1 for item in items if item["report"].get("changed")),
        "unchangedCount": sum(1 for item in items if not item["report"].get("changed")),
        "items": items,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
