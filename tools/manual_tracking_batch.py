#!/usr/bin/env python3
"""Atomic batch wrapper around the authenticated manual tracking writer.

The web admin can submit several candidates from one article while this command
preserves the single-object validation rules. Strict mode keeps the original
all-or-nothing semantics. ``skip`` mode is origin-aware:

* ``automatic`` rows may have discardable keyword noise removed and may be
  omitted if the canonical validator still rejects them.
* ``manual-confirmed`` rows may have machine-generated keyword noise removed,
  but any remaining validation error fails the whole batch.
* ``manual`` rows are never rewritten or silently skipped; any validation error
  fails the whole batch.

Every accepted row is still simulated as one transaction before anything is
persisted. Apply reports distinguish formal configuration changes, review-queue
entries, provenance-only records, unchanged requests, and skipped candidates.
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
TRACKING_ORIGINS = {"automatic", "manual", "manual-confirmed"}
REPAIRABLE_ORIGINS = {"automatic", "manual-confirmed"}
SKIPPABLE_ORIGINS = {"automatic"}
OUTCOMES = {"applied", "review", "recorded", "unchanged", "skipped"}
ORIGIN_LABELS = {
    "automatic": "自动候选",
    "manual": "人工输入",
    "manual-confirmed": "人工确认候选",
}


def clean(value: Any, limit: int = 1200) -> str:
    return manual.clean(value, limit)


def string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen = set()
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


def tracking_origin(
    index: int,
    row: Mapping[str, Any],
    invalid_policy: str,
) -> str:
    origin = clean(row.get("origin"), 40).casefold()
    if not origin:
        if invalid_policy == "strict":
            # The historic strict workflow predates origin tagging and was
            # already fail-closed. Preserve that safe direct-dispatch path.
            return "manual"
        raise manual.ManualTrackingError(
            f"第 {index} 个对象缺少 origin；请刷新追踪管理页面后重试。"
        )
    if origin not in TRACKING_ORIGINS:
        allowed = "、".join(sorted(TRACKING_ORIGINS))
        raise manual.ManualTrackingError(
            f"第 {index} 个对象的 origin 无效，必须是 {allowed} 之一。"
        )
    return origin


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


def audit_request(request: Mapping[str, Any], origin: str) -> dict[str, Any]:
    audited = dict(request)
    audited["origin"] = origin
    return audited


def skipped_record(index: int, row: Mapping[str, Any], error: Exception) -> dict[str, Any]:
    return {
        "index": index,
        "objectType": clean(row.get("objectType"), 30),
        "name": clean(row.get("name"), 160),
        "origin": clean(row.get("origin"), 40),
        "error": clean(error, 500),
    }


def outcome_reason(outcome: str, applied: Mapping[str, Any]) -> str:
    resolution = applied.get("resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    resolution_reason = clean(resolution.get("reason"), 500)
    if outcome == "review":
        return resolution_reason or "对象已进入实体解析审核队列，尚未写入正式追踪配置。"
    if outcome == "applied":
        return "已更新正式追踪配置。"
    if outcome == "recorded":
        changes: list[str] = []
        if applied.get("intentsChanged") is True:
            changes.append("tracking intent")
        if applied.get("inboxChanged") is True:
            changes.append("capture inbox")
        suffix = "、".join(changes) or "审计与来源记录"
        return f"未改动正式追踪配置，但已更新 {suffix}。"
    if outcome == "unchanged":
        return "请求与现有追踪状态一致，没有产生新的状态变化。"
    return "未通过规范校验，未写入任何状态。"


def applied_outcome(item: Mapping[str, Any]) -> dict[str, Any]:
    request = item.get("request")
    request = request if isinstance(request, Mapping) else {}
    applied = item.get("applied")
    applied = applied if isinstance(applied, Mapping) else {}
    resolution = applied.get("resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}

    if applied.get("reviewQueued") is True or clean(resolution.get("status"), 30) == "review":
        outcome = "review"
    elif applied.get("configChanged") is True:
        outcome = "applied"
    elif applied.get("changed") is True:
        outcome = "recorded"
    else:
        outcome = "unchanged"

    return {
        "index": int(item.get("index", 0) or 0),
        "objectType": clean(request.get("kind"), 40),
        "name": clean(request.get("name"), 160),
        "origin": clean(request.get("origin"), 40),
        "outcome": outcome,
        "reason": outcome_reason(outcome, applied),
        "targetId": clean(resolution.get("targetId"), 240)
        or clean(applied.get("entityId"), 240),
        "configChanged": applied.get("configChanged") is True,
        "inboxChanged": applied.get("inboxChanged") is True,
        "intentsChanged": applied.get("intentsChanged") is True,
        "reviewQueued": applied.get("reviewQueued") is True,
    }


def skipped_outcome(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "index": int(item.get("index", 0) or 0),
        "objectType": clean(item.get("objectType"), 40),
        "name": clean(item.get("name"), 160),
        "origin": clean(item.get("origin"), 40),
        "outcome": "skipped",
        "reason": clean(item.get("error"), 500)
        or "未通过规范校验，未写入任何状态。",
        "targetId": "",
        "configChanged": False,
        "inboxChanged": False,
        "intentsChanged": False,
        "reviewQueued": False,
    }


def outcome_breakdown(
    items: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> dict[str, Any]:
    outcomes = [applied_outcome(item) for item in items]
    outcomes.extend(skipped_outcome(item) for item in skipped)
    outcomes.sort(key=lambda item: int(item.get("index", 0) or 0))
    counts = {name: 0 for name in OUTCOMES}
    for item in outcomes:
        outcome = clean(item.get("outcome"), 30)
        if outcome in counts:
            counts[outcome] += 1
    return {
        "outcomes": outcomes,
        "appliedCount": counts["applied"],
        "reviewQueuedCount": counts["review"],
        "recordedCount": counts["recorded"],
        "unchangedCount": counts["unchanged"],
    }


def sanitize_machine_keywords(
    index: int,
    row: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Remove only keyword-level noise while preserving the candidate itself.

    This helper is used only for origins that may still contain machine-
    generated keyword fragments. Every surviving keyword is passed through the
    same technology validator used by the strict path.
    """

    prepared = dict(row)
    raw_keywords = string_list(row.get("keywords"), 30)
    if not raw_keywords:
        return prepared, None

    kept: list[str] = []
    identities: set[str] = set()
    removed: list[dict[str, str]] = []
    for keyword in raw_keywords:
        try:
            if not manual.is_single_value(keyword):
                raise manual.ManualTrackingError(
                    f"关键字必须是一项完整技术，不能包含复合列表或分隔符：{keyword}"
                )
            parsed = manual._validate_technology(keyword)
        except manual.ManualTrackingError as exc:
            removed.append({"value": keyword, "error": clean(exc, 300)})
            continue

        identity = manual.signal_identity(parsed, "keywords") or parsed.casefold()
        if identity in identities:
            continue
        identities.add(identity)
        kept.append(parsed)

    if not removed:
        return prepared, None

    prepared["keywords"] = kept
    return prepared, {
        "index": index,
        "objectType": clean(row.get("objectType"), 30),
        "name": clean(row.get("name"), 160),
        "origin": clean(row.get("origin"), 40),
        "field": "keywords",
        "removedKeywords": removed,
        "keptKeywordCount": len(kept),
    }


def prepared_row(
    index: int,
    row: Mapping[str, Any],
    invalid_policy: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    origin = tracking_origin(index, row, invalid_policy)
    prepared = dict(row)
    prepared["origin"] = origin
    if invalid_policy == "skip" and origin in REPAIRABLE_ORIGINS:
        prepared, repair = sanitize_machine_keywords(index, prepared)
        prepared["origin"] = origin
        if repair is not None:
            repair["origin"] = origin
        return prepared, repair
    return prepared, None


def simulate_batch(
    rows: list[dict[str, Any]],
    tracking: dict[str, Any],
    inbox: dict[str, Any],
    intents: dict[str, Any],
    actor: str,
    now: str,
    *,
    invalid_policy: str = "strict",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize and apply in memory so later rows can reference earlier rows.

    ``skip`` never weakens direct human input. Only ``automatic`` rows may be
    omitted after canonical validation fails. ``manual`` and
    ``manual-confirmed`` errors fail the whole transaction.
    """

    if invalid_policy not in INVALID_POLICIES:
        raise manual.ManualTrackingError("invalid-policy 必须是 strict 或 skip。")

    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    repaired: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        candidate_row, repair = prepared_row(index, row, invalid_policy)
        origin = clean(candidate_row.get("origin"), 40)
        try:
            args = namespace_for(candidate_row, "validate")
            request = manual._normalized_input(args, tracking)
            manual_profile = manual.build_manual_feedback(inbox, intents, tracking)
            recs = manual.recommendations(tracking, intents, request, manual_profile)
            applied = manual.apply_request(tracking, inbox, intents, request, actor, now)
            results.append(
                {
                    "index": index,
                    "request": audit_request(request, origin),
                    "recommendations": recs,
                    "preview": applied,
                }
            )
            if repair:
                repaired.append(repair)
        except manual.ManualTrackingError as exc:
            if invalid_policy == "strict" or origin not in SKIPPABLE_ORIGINS:
                label = ORIGIN_LABELS.get(origin, "人工输入")
                raise manual.ManualTrackingError(
                    f"第 {index} 个对象（{label}）：{exc}"
                ) from exc
            skipped.append(skipped_record(index, candidate_row, exc))

    if invalid_policy == "skip" and not results:
        details = "；".join(
            f"第 {item['index']} 个对象 {item['name'] or item['objectType']}：{item['error']}"
            for item in skipped[:3]
        )
        suffix = f"（{details}）" if details else ""
        raise manual.ManualTrackingError(f"整批对象均未通过验证，没有可安全写入的对象。{suffix}")
    return results, skipped, repaired


def apply_batch(
    rows: list[dict[str, Any]],
    tracking: dict[str, Any],
    inbox: dict[str, Any],
    intents: dict[str, Any],
    actor: str,
    now: str,
    *,
    invalid_policy: str = "strict",
) -> tuple[
    list[dict[str, Any]],
    dict[str, bool],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    # First validate the accepted transaction on copies. No persistent state is
    # touched until every accepted object passes and all cross-item references
    # resolve. Only rejected automatic candidates can be absent from persistence.
    preview_items, skipped, repaired = simulate_batch(
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
        candidate_row, _ = prepared_row(index, row, invalid_policy)
        origin = clean(candidate_row.get("origin"), 40)
        args = namespace_for(candidate_row, "apply")
        request = manual._normalized_input(args, tracking)
        manual_profile = manual.build_manual_feedback(inbox, intents, tracking)
        recs = manual.recommendations(tracking, intents, request, manual_profile)
        applied = manual.apply_request(tracking, inbox, intents, request, actor, now)
        item_results.append(
            {
                "index": index,
                "request": audit_request(request, origin),
                "recommendations": recs,
                "applied": applied,
            }
        )
        for key in flags:
            flags[key] = flags[key] or bool(applied.get(key, False))
    return item_results, flags, skipped, repaired


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
        help=(
            "strict rejects the whole batch; skip may sanitize and omit only "
            "origin=automatic rows, while manual rows remain fail-closed"
        ),
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
            "repairedCount": 0,
            "removedKeywordCount": 0,
            "appliedCount": 0,
            "reviewQueuedCount": 0,
            "recordedCount": 0,
            "unchangedCount": 0,
            "changed": False,
            "configChanged": False,
            "inboxChanged": False,
            "intentsChanged": False,
            "reviewQueued": False,
            "items": [],
            "outcomes": [],
            "skipped": [],
            "repaired": [],
        }
        if args.mode == "validate":
            items, skipped, repaired = simulate_batch(
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
            result["repaired"] = repaired
        else:
            now = clean(args.now, 80) or datetime.now(timezone.utc).isoformat(timespec="seconds")
            item_results, flags, skipped, repaired = apply_batch(
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
            result["repaired"] = repaired
            result.update(flags)
            result.update(outcome_breakdown(item_results, skipped))
            if flags["configChanged"]:
                manual.write_json_atomic(manual.TRACKING_PATH, tracking)
            if flags["inboxChanged"]:
                manual.write_json_atomic(manual.INBOX_PATH, inbox)
            if flags["intentsChanged"]:
                manual.write_json_atomic(manual.INTENTS_PATH, intents)
        result["acceptedCount"] = len(result["items"])
        result["skippedCount"] = len(result["skipped"])
        result["repairedCount"] = len(result["repaired"])
        result["removedKeywordCount"] = sum(
            len(item.get("removedKeywords", []))
            for item in result["repaired"]
            if isinstance(item, dict)
        )
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
