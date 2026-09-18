#!/usr/bin/env python3
"""Persist cross-run source health, performance, quarantine and alert state."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .source_evidence import (
        VALID_EVIDENCE_GRADES,
        article_source_grade_index,
        classify_source_evidence,
    )
    from .source_performance import (
        DEFAULT_PERFORMANCE_POLICY,
        new_article_metrics,
        update_source_performance,
    )
    from .source_quality_reviews import (
        DEFAULT_REVIEW_PATH,
        load_review_manifest,
        review_index,
    )
except ImportError:
    from source_evidence import (
        VALID_EVIDENCE_GRADES,
        article_source_grade_index,
        classify_source_evidence,
    )
    from source_performance import (
        DEFAULT_PERFORMANCE_POLICY,
        new_article_metrics,
        update_source_performance,
    )
    from source_quality_reviews import (
        DEFAULT_REVIEW_PATH,
        load_review_manifest,
        review_index,
    )

try:
    from .source_health_summary import rebuild_source_health_summary
except ImportError:
    from source_health_summary import rebuild_source_health_summary

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
DEFAULT_STATE_PATH = ROOT / "public" / "data" / "source_health.json"
DEFAULT_POLICY_PATH = ROOT / "config" / "source_health_policy.json"
DEFAULT_TRACKING_CONFIG_PATH = ROOT / "config" / "user_tracking.json"
DEFAULT_SUMMARY_PATH = Path("/tmp/source-health-issue.md")

DEFAULT_POLICY = {
    "schemaVersion": 3,
    "failureThreshold": 3,
    "quarantineThreshold": 7,
    "recoverySuccessThreshold": 3,
    "inactivityDays": 30,
    "quarantineGrades": ["C", "D"],
    "criticalPlatforms": ["微信"],
    "criticalSourceIds": [],
    "countEmptyForCriticalSources": True,
    "alertOnRetainedPrevious": True,
    "alertOnExplicitError": True,
    "maximumMisattributionRate": 0.05,
    **DEFAULT_PERFORMANCE_POLICY,
}


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _accepted_count(status: dict[str, Any]) -> int:
    """Return this run's accepted count, excluding retained adaptive history."""

    if status.get("newAccepted") is not None:
        return _integer(status.get("newAccepted"))
    if status.get("acceptedBeforeRetention") is not None:
        return _integer(status.get("acceptedBeforeRetention"))
    return _integer(status.get("accepted"))


def _source_id(status: dict[str, Any]) -> str:
    return str(status.get("id") or status.get("sourceId") or status.get("name") or "").strip()


def _configured_source_present(
    runtime_id: str,
    configured_source_ids: set[str] | None,
) -> bool:
    if configured_source_ids is None:
        return True
    config_id = (
        runtime_id[len("user-source-") :]
        if runtime_id.startswith("user-source-")
        else runtime_id
    )
    return (
        not config_id.startswith("source-auto-")
        or config_id in configured_source_ids
    )


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _classification(
    status: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[bool, str]:
    state = str(status.get("status") or "unknown").casefold()
    source_id = _source_id(status)
    platform = str(status.get("platform") or "").strip()
    accepted = _accepted_count(status)
    retained_previous = bool(status.get("retainedPrevious"))
    critical = source_id in set(policy.get("criticalSourceIds", [])) or platform in set(
        policy.get("criticalPlatforms", [])
    )

    if policy.get("alertOnRetainedPrevious", True) and retained_previous:
        return True, "本轮抓取失败，继续保留上一版快照"
    if policy.get("alertOnExplicitError", True) and state in {"error", "failed"}:
        error = str(status.get("error") or "来源返回显式错误").strip()
        return True, error[:240]
    if (
        critical
        and policy.get("countEmptyForCriticalSources", True)
        and accepted <= 0
        and state in {"empty", "ok", "partial", "unknown"}
    ):
        return True, "关键来源本轮没有合格结果"
    return False, ""


def _evidence_grade(
    status: dict[str, Any],
    previous: dict[str, Any],
    grade_index: dict[str, str],
) -> str:
    source_id = _source_id(status)
    candidates = (
        str(status.get("evidenceGrade") or ""),
        grade_index.get(source_id, ""),
        str(previous.get("evidenceGrade") or ""),
    )
    for candidate in candidates:
        if candidate in VALID_EVIDENCE_GRADES:
            return candidate
    return classify_source_evidence(
        level=status.get("sourceLevel"),
        platform=status.get("platform"),
        source_name=status.get("name"),
        url=status.get("url"),
    )


def _inactive_days(value: Any, current_time: datetime) -> int:
    parsed = _parse_time(value)
    if parsed is None:
        return 0
    return max(0, (current_time.date() - parsed.date()).days)


def update_health(
    previous_payload: dict[str, Any],
    article_payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    now: datetime | None = None,
    manual_reviews: dict[str, dict[str, Any]] | None = None,
    configured_source_ids: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_time = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    timestamp = current_time.isoformat()
    threshold = max(1, _integer(policy.get("failureThreshold")) or 3)
    quarantine_threshold = max(
        threshold,
        _integer(policy.get("quarantineThreshold")) or 7,
    )
    recovery_threshold = max(
        1,
        _integer(policy.get("recoverySuccessThreshold")) or 3,
    )
    inactivity_threshold = max(1, _integer(policy.get("inactivityDays")) or 30)
    quarantine_grades = {
        str(value)
        for value in policy.get("quarantineGrades", ["C", "D"])
        if str(value) in VALID_EVIDENCE_GRADES
    }

    previous_sources = previous_payload.get("sources", {})
    previous_sources = previous_sources if isinstance(previous_sources, dict) else {}
    statuses = article_payload.get("sourceStatus", [])
    statuses = statuses if isinstance(statuses, list) else []
    grade_index = article_source_grade_index(article_payload)
    first_seen_metrics = new_article_metrics(
        article_payload,
        previous_generated_at=previous_payload.get("generatedAt"),
        now=current_time,
    )
    manual_reviews = manual_reviews or {}

    next_sources: dict[str, dict[str, Any]] = {}
    new_alerts: list[str] = []
    recoveries: list[str] = []
    quarantined_now: list[str] = []
    resumed_now: list[str] = []
    seen_ids: set[str] = set()

    for raw_status in statuses:
        if not isinstance(raw_status, dict):
            continue
        source_id = _source_id(raw_status)
        if not source_id:
            continue
        if not _configured_source_present(source_id, configured_source_ids):
            continue
        seen_ids.add(source_id)
        previous = previous_sources.get(source_id, {})
        previous = previous if isinstance(previous, dict) else {}
        unhealthy, failure_reason = _classification(raw_status, policy)
        previous_streak = _integer(previous.get("consecutiveFailures"))
        previous_active = bool(previous.get("alertActive"))
        previous_collection_state = str(previous.get("collectionState") or "active")
        previous_recovery = _integer(previous.get("recoverySuccesses"))
        accepted = _accepted_count(raw_status)
        state = str(raw_status.get("status") or "unknown")
        productive = (
            accepted > 0
            and state.casefold() in {"ok", "partial"}
            and not bool(raw_status.get("retainedPrevious"))
        )
        grade = _evidence_grade(raw_status, previous, grade_index)
        pausable = grade in quarantine_grades
        first_observed_at = previous.get("firstObservedAt") or timestamp

        if unhealthy:
            streak = previous_streak + 1
            recovery_successes = 0
            last_success_at = previous.get("lastSuccessAt")
            last_failure_at = timestamp
            if pausable and (
                streak >= quarantine_threshold
                or previous_collection_state in {"quarantined", "probation"}
            ):
                collection_state = "quarantined"
            else:
                collection_state = "active"
            reason = failure_reason
        else:
            streak = 0
            last_failure_at = previous.get("lastFailureAt")
            last_success_at = timestamp if productive else previous.get("lastSuccessAt")
            if pausable and previous_collection_state in {"quarantined", "probation"}:
                if productive:
                    recovery_successes = previous_recovery + 1
                    if recovery_successes >= recovery_threshold:
                        collection_state = "active"
                        recovery_successes = 0
                        resumed_now.append(source_id)
                        reason = ""
                    else:
                        collection_state = "probation"
                        reason = (
                            f"恢复探测 {recovery_successes}/{recovery_threshold}，"
                            "新内容继续隔离"
                        )
                else:
                    recovery_successes = previous_recovery
                    collection_state = previous_collection_state
                    reason = "恢复探测没有产生合格记录，新内容继续隔离"
            else:
                recovery_successes = 0
                collection_state = "active"
                reason = ""

        if collection_state == "quarantined" and previous_collection_state != "quarantined":
            quarantined_now.append(source_id)

        last_productive_at = timestamp if productive else previous.get("lastProductiveAt")
        activity_anchor = last_productive_at or first_observed_at
        inactive_days = _inactive_days(activity_anchor, current_time)
        priority = "low" if inactive_days >= inactivity_threshold else "normal"
        publication_eligible = collection_state == "active"
        alert_active = (
            unhealthy and streak >= threshold
        ) or collection_state in {"quarantined", "probation"}

        performance = update_source_performance(
            previous.get("performance") if isinstance(previous, dict) else None,
            raw_status,
            first_seen_metrics.get(source_id),
            evidence_grade=grade,
            collection_state=collection_state,
            priority=priority,
            manual_quality=manual_reviews.get(source_id),
            policy=policy,
            now=current_time,
        )

        if alert_active and not previous_active:
            new_alerts.append(source_id)
        if previous_active and not alert_active:
            recoveries.append(source_id)

        next_sources[source_id] = {
            "id": source_id,
            "name": str(raw_status.get("name") or previous.get("name") or source_id),
            "platform": str(raw_status.get("platform") or previous.get("platform") or ""),
            "evidenceGrade": grade,
            "lastStatus": state,
            "scanned": _integer(raw_status.get("scanned")),
            "accepted": accepted,
            "failed": _integer(raw_status.get("failed")),
            "candidateCount": _integer(raw_status.get("candidateCount")),
            "publishedCount": _integer(raw_status.get("publishedCount")),
            "duplicateCount": _integer(raw_status.get("duplicateCount")),
            "withheldCount": _integer(raw_status.get("withheldCount")),
            "consecutiveFailures": streak,
            "failureThreshold": threshold,
            "quarantineThreshold": quarantine_threshold,
            "recoverySuccessThreshold": recovery_threshold,
            "recoverySuccesses": recovery_successes,
            "collectionState": collection_state,
            "publicationEligible": publication_eligible,
            "priority": priority,
            "inactiveDays": inactive_days,
            "alertActive": alert_active,
            "reason": reason,
            "publicationWithheld": bool(raw_status.get("publicationWithheld")),
            "firstObservedAt": first_observed_at,
            "lastSeenAt": timestamp,
            "lastSuccessAt": last_success_at,
            "lastProductiveAt": last_productive_at,
            "lastFailureAt": last_failure_at,
            "performance": performance,
        }

    # Preserve sources missing from the current ledger instead of silently deleting
    # their cross-run streak, quarantine, performance or historical timestamps.
    for source_id, raw_previous in previous_sources.items():
        if source_id in seen_ids or not isinstance(raw_previous, dict):
            continue
        if not _configured_source_present(source_id, configured_source_ids):
            continue
        preserved = dict(raw_previous)
        preserved["missingFromCurrentRun"] = True
        next_sources[source_id] = preserved

    active_alerts = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if bool(entry.get("alertActive"))
    )
    previous_active_alerts = sorted(
        source_id
        for source_id, entry in previous_sources.items()
        if isinstance(entry, dict) and bool(entry.get("alertActive"))
    )
    quarantined_ids = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if str(entry.get("collectionState")) == "quarantined"
    )
    probation_ids = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if str(entry.get("collectionState")) == "probation"
    )
    low_priority_ids = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if str(entry.get("priority")) == "low"
    )
    performance_review_ids = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if isinstance(entry.get("performance"), dict)
        and bool(entry["performance"].get("reviewRequired"))
    )
    downgrade_candidate_ids = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if isinstance(entry.get("performance"), dict)
        and entry["performance"].get("reviewState") == "downgrade-candidate"
    )
    retirement_candidate_ids = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if isinstance(entry.get("performance"), dict)
        and entry["performance"].get("reviewState") == "retire-candidate"
    )
    monitor_ids = sorted(
        source_id
        for source_id, entry in next_sources.items()
        if isinstance(entry.get("performance"), dict)
        and entry["performance"].get("reviewState") == "monitor"
    )

    result = {
        "schemaVersion": 3,
        "generatedAt": timestamp,
        "failureThreshold": threshold,
        "quarantineThreshold": quarantine_threshold,
        "recoverySuccessThreshold": recovery_threshold,
        "inactivityDays": inactivity_threshold,
        "performanceWindowRuns": _integer(policy.get("performanceWindowRuns")) or 30,
        "sourceCount": len(next_sources),
        "activeAlertCount": len(active_alerts),
        "activeAlerts": active_alerts,
        "quarantinedSourceCount": len(quarantined_ids),
        "quarantinedSources": quarantined_ids,
        "probationSourceCount": len(probation_ids),
        "probationSources": probation_ids,
        "lowPrioritySourceCount": len(low_priority_ids),
        "lowPrioritySources": low_priority_ids,
        "performanceReviewSourceCount": len(performance_review_ids),
        "performanceReviewSources": performance_review_ids,
        "downgradeCandidateCount": len(downgrade_candidate_ids),
        "downgradeCandidates": downgrade_candidate_ids,
        "retirementCandidateCount": len(retirement_candidate_ids),
        "retirementCandidates": retirement_candidate_ids,
        "monitorSourceCount": len(monitor_ids),
        "monitorSources": monitor_ids,
        "sources": dict(sorted(next_sources.items())),
    }
    result = rebuild_source_health_summary(result)
    summary = {
        "activeAlerts": active_alerts,
        "newAlerts": sorted(new_alerts),
        "recoveries": sorted(recoveries),
        "quarantinedNow": sorted(quarantined_now),
        "resumedNow": sorted(resumed_now),
        "quarantinedSources": quarantined_ids,
        "probationSources": probation_ids,
        "lowPrioritySources": low_priority_ids,
        "performanceReviewSources": performance_review_ids,
        "downgradeCandidates": downgrade_candidate_ids,
        "retirementCandidates": retirement_candidate_ids,
        "monitorSources": monitor_ids,
        "alertChanged": active_alerts != previous_active_alerts,
        "generatedAt": timestamp,
    }
    return result, summary


def render_issue_markdown(state: dict[str, Any], summary: dict[str, Any]) -> str:
    active_ids = summary.get("activeAlerts", [])
    lines = [
        "# 关键情报源连续异常",
        "",
        "该 Issue 由定时刷新工作流维护。连续异常达到阈值后告警；C/D 级来源达到隔离阈值后仅继续恢复探测，不发布新内容。",
        "",
    ]
    if not active_ids:
        lines.extend(["当前没有持续异常或恢复观察中的来源。", ""])
    else:
        lines.extend(
            [
                f"当前共有 **{len(active_ids)}** 个来源处于告警、隔离或恢复观察状态。",
                "",
                "| 来源 | 等级 | 平台 | 状态 | 连续异常 | 恢复进度 | 原因 | 最后有效产出 |",
                "|---|---|---|---|---:|---:|---|---|",
            ]
        )
        sources = state.get("sources", {})
        for source_id in active_ids:
            item = sources.get(source_id, {})
            reason = str(item.get("reason") or "未知").replace("|", "\\|")
            lines.append(
                "| {name} | {grade} | {platform} | {collection} | {streak} | {recovery}/{threshold} | {reason} | {productive} |".format(
                    name=str(item.get("name") or source_id).replace("|", "\\|"),
                    grade=str(item.get("evidenceGrade") or "D"),
                    platform=str(item.get("platform") or "—").replace("|", "\\|"),
                    collection=str(item.get("collectionState") or "active"),
                    streak=item.get("consecutiveFailures", 0),
                    recovery=item.get("recoverySuccesses", 0),
                    threshold=item.get("recoverySuccessThreshold", 0),
                    reason=reason,
                    productive=item.get("lastProductiveAt") or "尚无有效产出",
                )
            )
        lines.append("")
    lines.extend(
        [
            f"隔离来源：**{state.get('quarantinedSourceCount', 0)}**；恢复观察：**{state.get('probationSourceCount', 0)}**；低优先级：**{state.get('lowPrioritySourceCount', 0)}**。",
            "",
            f"效能人工审查：**{state.get('performanceReviewSourceCount', 0)}**；建议降级：**{state.get('downgradeCandidateCount', 0)}**；建议停用候选：**{state.get('retirementCandidateCount', 0)}**。系统只提出建议，不自动删除来源。",
            "",
            f"最后检查：`{summary.get('generatedAt', '')}`",
            "",
            "处理原则：不绕过验证码或访问限制；隔离时保留上一版已验证快照，连续三次产生有效记录后恢复发布。",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_github_output(path: str | None, summary: dict[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"active_count={len(summary.get('activeAlerts', []))}\n")
        handle.write(f"new_alert_count={len(summary.get('newAlerts', []))}\n")
        handle.write(f"recovery_count={len(summary.get('recoveries', []))}\n")
        handle.write(f"quarantine_count={len(summary.get('quarantinedSources', []))}\n")
        handle.write(f"probation_count={len(summary.get('probationSources', []))}\n")
        handle.write(
            f"performance_review_count={len(summary.get('performanceReviewSources', []))}\n"
        )
        handle.write(
            f"downgrade_candidate_count={len(summary.get('downgradeCandidates', []))}\n"
        )
        handle.write(
            f"retirement_candidate_count={len(summary.get('retirementCandidates', []))}\n"
        )
        handle.write(f"alert_changed={str(bool(summary.get('alertChanged'))).lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles", type=Path, default=DEFAULT_ARTICLES_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument(
        "--tracking-config",
        type=Path,
        default=DEFAULT_TRACKING_CONFIG_PATH,
    )
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()

    article_payload = _read_json(args.articles, {})
    previous_payload = _read_json(args.state, {})
    policy = dict(DEFAULT_POLICY)
    configured = _read_json(args.policy, {})
    if isinstance(configured, dict):
        policy.update(configured)
    manual_reviews = review_index(load_review_manifest(args.reviews))
    tracking_payload = _read_json(args.tracking_config, {})
    configured_source_ids = {
        str(source.get("id") or "")
        for source in tracking_payload.get("sources", [])
        if isinstance(source, dict)
        and str(source.get("id") or "").startswith("source-auto-")
    }

    state, summary = update_health(
        previous_payload,
        article_payload,
        policy,
        manual_reviews=manual_reviews,
        configured_source_ids=configured_source_ids,
    )
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(render_issue_markdown(state, summary), encoding="utf-8")
    _write_github_output(args.github_output, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
