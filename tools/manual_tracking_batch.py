#!/usr/bin/env python3
"""Atomic batch wrapper around the authenticated manual tracking writer.

The web admin can submit several candidates from one article while this command
preserves the single-object validation rules. Strict mode keeps the original
all-or-nothing semantics. ``skip`` mode is intended for machine-generated
article candidates: invalid rows are rejected individually, while the valid
subset is still simulated as one transaction and only persisted after the whole
accepted subset succeeds.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

try:
    import manual_tracking as manual
except ImportError:  # pragma: no cover
    from tools import manual_tracking as manual


MAX_BATCH_SIZE = 20
MAX_BATCH_JSON_BYTES = 45_000
INVALID_POLICIES = {"strict", "skip"}


def clean(value: Any, limit: int = 1200) -> str:
    return manual.clean(value, limit)


def string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        item = clean(raw, 240)
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def parse_batch(raw: str) -> list[dict[str, Any]]:
    if len(raw.encode("utf-8")) > MAX_BATCH_JSON_BYTES:
        raise manual.ManualTrackingError("批量请求过大，请拆成两次提交。")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise manual.ManualTrackingError("batch-json 不是有效 JSON。") from exc
    if isinstance(payload, dict):
        payload = payload.get("requests")
    if not isinstance(payload, list):
        raise manual.ManualTrackingError("batch-json 必须是对象数组。")
    if not payload:
        raise manual.ManualTrackingError("批量人工追踪至少需要一个对象。")
    if len(payload) > MAX_BATCH_SIZE:
        raise manual.ManualTrackingError(f"单次最多提交 {MAX_BATCH_SIZE} 个追踪对象。")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(payload, start=1):
        if not isinstance(row, dict):
            raise manual.ManualTrackingError(f"第 {index} 个对象不是 JSON 对象。")
        rows.append(dict(row))
    return rows


def namespace_for(row: Mapping[str, Any], mode: str) -> argparse.Namespace:
    return argparse.Namespace(
        mode=mode,
        kind=clean(row.get("objectType"), 30),
        name=clean(row.get("name"), 160),
        tracks="|".join(string_list(row.get("targetTracks"), 20)),
        keywords="|".join(string_list(row.get("keywords"), 30)),
        source_url=clean(row.get("sourceUrl"), 1200),
        source_category=clean(row.get("sourceCategory"), 30) or "media",
        region=clean(row.get("region"), 30) or "全球",
        reasons="|".join(string_list(row.get("reasons"), 12)),
        note=clean(row.get("note"), 800),
        actor="",
        triggering_actor="",
        now="",
    )


def skipped_record(index: int, row: Mapping[str, Any], error: Exception) -> dict[str, Any]:
    return {
        "index": index,
        "objectType": clean(row.get("objectType"), 30),
        "name": clean(row.get("name"), 160),
        "error": clean(error, 500),
    }


def simulate_batch(
    rows: list[dict[str, Any]],
    tracking: dict[str, Any],
    inbox: dict[str, Any],
    intents: dict[str, Any],
    actor: str,
    now: str,
    *,
    invalid_policy: str = "strict",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize and apply in memory so later rows can reference earlier rows.

    In ``skip`` mode, a row rejected by the canonical single-object validator is
    recorded and omitted. Every accepted row still mutates only the in-memory
    simulation, so subsequent rows see the same state they would see on apply.
    """

    if invalid_policy not in INVALID_POLICIES:
        raise manual.ManualTrackingError("invalid-policy 必须是 strict 或 skip。")

    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        try:
            args = namespace_for(row, "validate")
            request = manual._normalized_input(args, tracking)
            manual_profile = manual.build_manual_feedback(inbox, intents, tracking)
            recs = manual.recommendations(tracking, intents, request, manual_profile)
            applied = manual.apply_request(tracking, inbox, intents, request, actor, now)
            results.append(
                {
                    "index": index,
                    "request": request,
                    "recommendations": recs,
                    "preview": applied,
                }
            )
        except manual.ManualTrackingError as exc:
            if invalid_policy == "strict":
                raise manual.ManualTrackingError(f"第 {index} 个对象：{exc}") from exc
            skipped.append(skipped_record(index, row, exc))

    if invalid_policy == "skip" and not results:
        details = "；".join(
            f"第 {item['index']} 个对象 {item['name'] or item['objectType']}：{item['error']}"
            for item in skipped[:3]
        )
        suffix = f"（{details}）" if details else ""
        raise manual.ManualTrackingError(f"整批对象均未通过验证，没有可安全写入的对象。{suffix}")
    return results, skipped


def apply_batch(
    rows: list[dict[str, Any]],
    tracking: dict[str, Any],
    inbox: dict[str, Any],
    intents: dict[str, Any],
    actor: str,
    now: str,
    *,
    invalid_policy: str = "strict",
) -> tuple[list[dict[str, Any]], dict[str, bool], list[dict[str, Any]]]:
    # First validate the accepted transaction on copies. No persistent state is
    # touched until every accepted object passes and all cross-item references
    # resolve. In skip mode, rejected machine candidates never reach persistence.
    preview_items, skipped = simulate_batch(
        rows,
        copy.deepcopy(tracking),
        copy.deepcopy(inbox),
        copy.deepcopy(intents),
        actor,
        "validation-preview",
        invalid_policy=invalid_policy,
    )
    accepted_indices = {item["index"] for item in preview_items}

    item_results: list[dict[str, Any]] = []
    flags = {
        "changed": False,
        "configChanged": False,
        "inboxChanged": False,
        "intentsChanged": False,
        "reviewQueued": False,
    }
    for index, row in enumerate(rows, start=1):
        if index not in accepted_indices:
            continue
        args = namespace_for(row, "apply")
        request = manual._normalized_input(args, tracking)
        manual_profile = manual.build_manual_feedback(inbox, intents, tracking)
        recs = manual.recommendations(tracking, intents, request, manual_profile)
        applied = manual.apply_request(tracking, inbox, intents, request, actor, now)
        item_results.append(
            {
                "index": index,
                "request": request,
                "recommendations": recs,
                "applied": applied,
            }
        )
        for key in flags:
            flags[key] = flags[key] or bool(applied.get(key, False))
    return item_results, flags, skipped


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authenticated batch manual tracking")
    parser.add_argument("--mode", required=True, choices=["validate", "apply"])
    parser.add_argument("--batch-json", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--triggering-actor", default="")
    parser.add_argument(
        "--invalid-policy",
        default="strict",
        choices=sorted(INVALID_POLICIES),
        help="strict rejects the whole batch; skip omits invalid machine candidates",
    )
    parser.add_argument("--now", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        actor, triggering_actor = manual.check_actor(args.actor, args.triggering_actor)
        rows = parse_batch(args.batch_json)
        tracking, inbox, intents = manual.load_state()
        result: dict[str, Any] = {
            "ok": True,
            "mode": args.mode,
            "invalidPolicy": args.invalid_policy,
            "actor": actor,
            "triggeringActor": triggering_actor,
            "count": len(rows),
            "acceptedCount": 0,
            "skippedCount": 0,
            "changed": False,
            "configChanged": False,
            "inboxChanged": False,
            "intentsChanged": False,
            "reviewQueued": False,
            "items": [],
            "skipped": [],
        }
        if args.mode == "validate":
            items, skipped = simulate_batch(
                rows,
                copy.deepcopy(tracking),
                copy.deepcopy(inbox),
                copy.deepcopy(intents),
                actor,
                "validation-preview",
                invalid_policy=args.invalid_policy,
            )
            result["items"] = items
            result["skipped"] = skipped
        else:
            now = clean(args.now, 80) or datetime.now(timezone.utc).isoformat(timespec="seconds")
            item_results, flags, skipped = apply_batch(
                rows,
                tracking,
                inbox,
                intents,
                actor,
                now,
                invalid_policy=args.invalid_policy,
            )
            result["items"] = item_results
            result["skipped"] = skipped
            result.update(flags)
            if flags["configChanged"]:
                manual.write_json_atomic(manual.TRACKING_PATH, tracking)
            if flags["inboxChanged"]:
                manual.write_json_atomic(manual.INBOX_PATH, inbox)
            if flags["intentsChanged"]:
                manual.write_json_atomic(manual.INTENTS_PATH, intents)
        result["acceptedCount"] = len(result["items"])
        result["skippedCount"] = len(result["skipped"])
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except manual.ManualTrackingError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "changed": False,
                    "configChanged": False,
                    "inboxChanged": False,
                    "intentsChanged": False,
                    "reviewQueued": False,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
