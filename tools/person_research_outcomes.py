#!/usr/bin/env python3
"""Persist bounded outcome memory for task-directed person research attempts.

This module measures research productivity, not factual truth. An attempt is considered
productive only when the executor returns identity-gated evidence URLs that were not
already present before the attempt. Repeated zero-yield attempts can reduce scheduler
priority and temporarily withhold scarce active-query slots, but they never change a
research task's supported/candidate/open state.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "person_research_outcomes.json"

MAX_RECENT_ATTEMPTS_PER_TASK = 12
MAX_ATTEMPT_IDS_PER_TASK = 36
MAX_QUERY_LENGTH = 220
MAX_PLATFORM_ROWS = 8

METHODOLOGY = (
    "Outcome Memory 只衡量主动研究动作的产出效率，不判断事实真伪。"
    "只有通过现有人物身份门、且相对旧档案新增的公开 URL 才计为 new evidence；"
    "重复命中、零命中和执行失败分别记录。连续零新增只影响后续调度分数与主动检索冷却，"
    "不会改变 supported/candidate/open 等证据状态。"
)


def _clean(value: Any, limit: int = 800) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _integer(value: Any, minimum: int = 0, maximum: int = 1_000_000) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return minimum
    return min(maximum, max(minimum, number))


def _iso_date(value: Any) -> str:
    text = _clean(value, 40)[:10]
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return ""


def _iso_datetime(value: Any) -> str:
    text = _clean(value, 80)
    if not text:
        return ""
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def empty_memory() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "generatedAt": "",
        "taskOutcomes": {},
        "sourceStats": {},
        "methodology": METHODOLOGY,
    }


def _normalize_platform(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    source = _clean(value.get("source"), 100)
    if not source:
        return None
    accepted_urls = []
    seen: set[str] = set()
    for raw in value.get("acceptedUrls") or []:
        url = _clean(raw, 1_000)
        if not url or url in seen:
            continue
        seen.add(url)
        accepted_urls.append(url)
        if len(accepted_urls) >= MAX_PLATFORM_ROWS:
            break
    return {
        "source": source,
        "rawRows": _integer(value.get("rawRows"), 0, 10_000),
        "acceptedEvidenceCount": _integer(value.get("acceptedEvidenceCount"), 0, 100),
        "newEvidenceCount": _integer(value.get("newEvidenceCount"), 0, 100),
        "failed": bool(value.get("failed")),
        "acceptedUrls": accepted_urls,
    }


def _normalize_attempt(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    attempt_id = _clean(value.get("id"), 120)
    research_date = _iso_date(value.get("researchDate"))
    executor = _clean(value.get("executor"), 40)
    if not attempt_id or not research_date or executor != "person_video":
        return None
    platforms = [
        row
        for row in (_normalize_platform(item) for item in value.get("platforms") or [])
        if row
    ][:6]
    outcome = _clean(value.get("outcome"), 40)
    if outcome not in {"new_evidence", "rediscovered", "no_yield", "error"}:
        outcome = "no_yield"
    return {
        "id": attempt_id,
        "researchDate": research_date,
        "attemptedAt": _iso_datetime(value.get("attemptedAt")),
        "executor": "person_video",
        "query": _clean(value.get("query"), MAX_QUERY_LENGTH),
        "outcome": outcome,
        "acceptedEvidenceCount": _integer(value.get("acceptedEvidenceCount"), 0, 100),
        "newEvidenceCount": _integer(value.get("newEvidenceCount"), 0, 100),
        "platforms": platforms,
    }


def _normalize_task_outcome(task_id: str, value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    person_slug = _clean(value.get("personSlug"), 180)
    if not task_id or not person_slug:
        return None
    recent = [
        row
        for row in (_normalize_attempt(item) for item in value.get("recentAttempts") or [])
        if row
    ]
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(recent, key=lambda item: (item["attemptedAt"], item["id"])):
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        deduped.append(row)
    deduped = deduped[-MAX_RECENT_ATTEMPTS_PER_TASK:]
    attempt_ids = []
    for raw in value.get("attemptIds") or []:
        attempt_id = _clean(raw, 120)
        if attempt_id and attempt_id not in attempt_ids:
            attempt_ids.append(attempt_id)
    for row in deduped:
        if row["id"] not in attempt_ids:
            attempt_ids.append(row["id"])
    attempt_ids = attempt_ids[-MAX_ATTEMPT_IDS_PER_TASK:]
    last_outcome = _clean(value.get("lastOutcome"), 40)
    if last_outcome not in {"new_evidence", "rediscovered", "no_yield", "error", ""}:
        last_outcome = ""
    return {
        "taskId": task_id,
        "personSlug": person_slug,
        "taskType": _clean(value.get("taskType"), 80),
        "attempts": _integer(value.get("attempts")),
        "acceptedAttempts": _integer(value.get("acceptedAttempts")),
        "yieldingAttempts": _integer(value.get("yieldingAttempts")),
        "acceptedEvidenceCount": _integer(value.get("acceptedEvidenceCount")),
        "newEvidenceCount": _integer(value.get("newEvidenceCount")),
        "zeroYieldStreak": _integer(value.get("zeroYieldStreak"), 0, 100),
        "lastOutcome": last_outcome,
        "lastAttemptAt": _iso_datetime(value.get("lastAttemptAt")),
        "lastResearchDate": _iso_date(value.get("lastResearchDate")),
        "lastExecutor": "person_video" if value.get("lastExecutor") == "person_video" else "",
        "lastQuery": _clean(value.get("lastQuery"), MAX_QUERY_LENGTH),
        "nextEligibleDate": _iso_date(value.get("nextEligibleDate")),
        "attemptIds": attempt_ids,
        "recentAttempts": deduped,
    }


def _normalize_source_stats(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for source, raw in value.items():
        if not isinstance(raw, dict):
            continue
        name = _clean(source, 100)
        if not name:
            continue
        attempts = _integer(raw.get("attempts"))
        yielding = min(attempts, _integer(raw.get("yieldingAttempts")))
        result[name] = {
            "attempts": attempts,
            "yieldingAttempts": yielding,
            "failedAttempts": min(attempts, _integer(raw.get("failedAttempts"))),
            "rawRows": _integer(raw.get("rawRows")),
            "acceptedEvidenceCount": _integer(raw.get("acceptedEvidenceCount")),
            "newEvidenceCount": _integer(raw.get("newEvidenceCount")),
            "yieldRate": _ratio(yielding, attempts),
        }
    return result


def normalize_memory(payload: Any) -> dict[str, Any]:
    row = payload if isinstance(payload, dict) else {}
    task_outcomes: dict[str, dict[str, Any]] = {}
    raw_tasks = row.get("taskOutcomes") if isinstance(row.get("taskOutcomes"), dict) else {}
    for raw_id, value in raw_tasks.items():
        task_id = _clean(raw_id, 180)
        normalized = _normalize_task_outcome(task_id, value)
        if normalized:
            task_outcomes[task_id] = normalized
    return {
        "schemaVersion": 1,
        "generatedAt": _iso_datetime(row.get("generatedAt")),
        "taskOutcomes": task_outcomes,
        "sourceStats": _normalize_source_stats(row.get("sourceStats")),
        "methodology": METHODOLOGY,
    }


def load_memory(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    return normalize_memory(payload)


def _attempt_id(task_id: str, research_date: str, query: str) -> str:
    raw = f"{task_id}|{research_date}|{_clean(query, MAX_QUERY_LENGTH).casefold()}"
    return "person-research-attempt-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:14]


def _next_eligible_date(research_date: str, zero_yield_streak: int) -> str:
    parsed = _iso_date(research_date)
    if not parsed or zero_yield_streak < 2:
        return ""
    base = dt.date.fromisoformat(parsed)
    delay = 7 if zero_yield_streak >= 3 else 2
    return (base + dt.timedelta(days=delay)).isoformat()


def _classify_attempt(accepted: int, new_evidence: int, platforms: list[dict[str, Any]]) -> str:
    if new_evidence > 0:
        return "new_evidence"
    if accepted > 0:
        return "rediscovered"
    if platforms and all(bool(row.get("failed")) for row in platforms):
        return "error"
    return "no_yield"


def record_attempt(memory: dict[str, Any], event: dict[str, Any]) -> bool:
    """Merge one real executor attempt into memory; return False for a duplicate."""

    task_id = _clean(event.get("taskId"), 180)
    person_slug = _clean(event.get("personSlug"), 180)
    task_type = _clean(event.get("taskType"), 80)
    research_date = _iso_date(event.get("researchDate"))
    query = _clean(event.get("query"), MAX_QUERY_LENGTH)
    if not task_id or not person_slug or not research_date or not query:
        return False
    platforms = [
        row
        for row in (_normalize_platform(item) for item in event.get("platforms") or [])
        if row
    ][:6]
    accepted = _integer(event.get("acceptedEvidenceCount"), 0, 100)
    new_evidence = min(accepted, _integer(event.get("newEvidenceCount"), 0, 100))
    attempt_id = _attempt_id(task_id, research_date, query)

    tasks = memory.setdefault("taskOutcomes", {})
    current = _normalize_task_outcome(task_id, tasks.get(task_id, {})) or {
        "taskId": task_id,
        "personSlug": person_slug,
        "taskType": task_type,
        "attempts": 0,
        "acceptedAttempts": 0,
        "yieldingAttempts": 0,
        "acceptedEvidenceCount": 0,
        "newEvidenceCount": 0,
        "zeroYieldStreak": 0,
        "lastOutcome": "",
        "lastAttemptAt": "",
        "lastResearchDate": "",
        "lastExecutor": "",
        "lastQuery": "",
        "nextEligibleDate": "",
        "attemptIds": [],
        "recentAttempts": [],
    }
    if attempt_id in current.get("attemptIds", []):
        return False

    outcome = _classify_attempt(accepted, new_evidence, platforms)
    zero_streak = _integer(current.get("zeroYieldStreak"), 0, 100)
    if outcome == "new_evidence":
        zero_streak = 0
    elif outcome in {"rediscovered", "no_yield"}:
        zero_streak += 1

    attempted_at = _iso_datetime(event.get("attemptedAt")) or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    attempt = {
        "id": attempt_id,
        "researchDate": research_date,
        "attemptedAt": attempted_at,
        "executor": "person_video",
        "query": query,
        "outcome": outcome,
        "acceptedEvidenceCount": accepted,
        "newEvidenceCount": new_evidence,
        "platforms": platforms,
    }
    current.update({
        "personSlug": person_slug,
        "taskType": task_type,
        "attempts": _integer(current.get("attempts")) + 1,
        "acceptedAttempts": _integer(current.get("acceptedAttempts")) + (1 if accepted > 0 else 0),
        "yieldingAttempts": _integer(current.get("yieldingAttempts")) + (1 if new_evidence > 0 else 0),
        "acceptedEvidenceCount": _integer(current.get("acceptedEvidenceCount")) + accepted,
        "newEvidenceCount": _integer(current.get("newEvidenceCount")) + new_evidence,
        "zeroYieldStreak": zero_streak,
        "lastOutcome": outcome,
        "lastAttemptAt": attempted_at,
        "lastResearchDate": research_date,
        "lastExecutor": "person_video",
        "lastQuery": query,
        "nextEligibleDate": _next_eligible_date(research_date, zero_streak),
        "attemptIds": [*current.get("attemptIds", []), attempt_id][-MAX_ATTEMPT_IDS_PER_TASK:],
        "recentAttempts": [*current.get("recentAttempts", []), attempt][-MAX_RECENT_ATTEMPTS_PER_TASK:],
    })
    tasks[task_id] = current

    source_stats = memory.setdefault("sourceStats", {})
    for platform in platforms:
        source = platform["source"]
        stats = source_stats.setdefault(source, {
            "attempts": 0,
            "yieldingAttempts": 0,
            "failedAttempts": 0,
            "rawRows": 0,
            "acceptedEvidenceCount": 0,
            "newEvidenceCount": 0,
            "yieldRate": None,
        })
        stats["attempts"] = _integer(stats.get("attempts")) + 1
        stats["yieldingAttempts"] = _integer(stats.get("yieldingAttempts")) + (1 if platform["newEvidenceCount"] > 0 else 0)
        stats["failedAttempts"] = _integer(stats.get("failedAttempts")) + (1 if platform["failed"] else 0)
        stats["rawRows"] = _integer(stats.get("rawRows")) + platform["rawRows"]
        stats["acceptedEvidenceCount"] = _integer(stats.get("acceptedEvidenceCount")) + platform["acceptedEvidenceCount"]
        stats["newEvidenceCount"] = _integer(stats.get("newEvidenceCount")) + platform["newEvidenceCount"]
        stats["yieldRate"] = _ratio(stats["yieldingAttempts"], stats["attempts"])

    memory["generatedAt"] = attempted_at
    memory["methodology"] = METHODOLOGY
    return True


def record_attempts(memory: dict[str, Any], events: Iterable[dict[str, Any]]) -> int:
    added = 0
    for event in events:
        if isinstance(event, dict) and record_attempt(memory, event):
            added += 1
    return added


def task_feedback(memory: dict[str, Any], task_id: str, research_date: str) -> dict[str, Any]:
    current = (memory.get("taskOutcomes") or {}).get(task_id)
    if not isinstance(current, dict):
        return {
            "score": 0,
            "cooldownActive": False,
            "attempts": 0,
            "yieldingAttempts": 0,
            "zeroYieldStreak": 0,
            "lastOutcome": "",
            "lastAttemptAt": "",
            "nextEligibleDate": "",
            "reasons": [],
        }
    streak = _integer(current.get("zeroYieldStreak"), 0, 100)
    last_outcome = _clean(current.get("lastOutcome"), 40)
    score = 0
    reasons: list[str] = []
    if last_outcome == "new_evidence":
        score = 6
        reasons.append(f"上次主动检索新增 {max(1, _integer((current.get('recentAttempts') or [{}])[-1].get('newEvidenceCount')))} 条证据")
    elif last_outcome == "error":
        score = -1
        reasons.append("上次执行失败，不计入连续零产出")
    elif streak >= 3:
        score = -10
        reasons.append(f"连续 {streak} 次未发现新增证据")
    elif streak == 2:
        score = -6
        reasons.append("连续 2 次未发现新增证据")
    elif streak == 1:
        score = -2
        reasons.append("上次主动检索未发现新增证据")

    next_eligible = _iso_date(current.get("nextEligibleDate"))
    current_date = _iso_date(research_date)
    cooldown_active = bool(next_eligible and current_date and current_date < next_eligible)
    if cooldown_active:
        reasons.append(f"主动检索冷却至 {next_eligible}")
    return {
        "score": score,
        "cooldownActive": cooldown_active,
        "attempts": _integer(current.get("attempts")),
        "yieldingAttempts": _integer(current.get("yieldingAttempts")),
        "zeroYieldStreak": streak,
        "lastOutcome": last_outcome,
        "lastAttemptAt": _iso_datetime(current.get("lastAttemptAt")),
        "nextEligibleDate": next_eligible,
        "reasons": reasons[:2],
    }


def memory_summary(memory: dict[str, Any], research_date: str = "") -> dict[str, Any]:
    attempts = yielding = accepted = new_evidence = zero_yield = cooldown = 0
    for current in (memory.get("taskOutcomes") or {}).values():
        if not isinstance(current, dict):
            continue
        attempts += _integer(current.get("attempts"))
        yielding += _integer(current.get("yieldingAttempts"))
        accepted += _integer(current.get("acceptedEvidenceCount"))
        new_evidence += _integer(current.get("newEvidenceCount"))
        zero_yield += max(0, _integer(current.get("attempts")) - _integer(current.get("yieldingAttempts")))
        if task_feedback(memory, _clean(current.get("taskId"), 180), research_date).get("cooldownActive"):
            cooldown += 1
    sources = []
    for name, stats in (memory.get("sourceStats") or {}).items():
        if not isinstance(stats, dict):
            continue
        attempts_count = _integer(stats.get("attempts"))
        yielding_count = min(attempts_count, _integer(stats.get("yieldingAttempts")))
        sources.append({
            "source": _clean(name, 100),
            "attempts": attempts_count,
            "yieldingAttempts": yielding_count,
            "failedAttempts": min(attempts_count, _integer(stats.get("failedAttempts"))),
            "acceptedEvidenceCount": _integer(stats.get("acceptedEvidenceCount")),
            "newEvidenceCount": _integer(stats.get("newEvidenceCount")),
            "yieldRate": _ratio(yielding_count, attempts_count),
        })
    sources.sort(key=lambda row: (-row["newEvidenceCount"], -row["yieldingAttempts"], -row["attempts"], row["source"]))
    return {
        "attemptCount": attempts,
        "yieldingAttemptCount": yielding,
        "zeroYieldAttemptCount": zero_yield,
        "acceptedEvidenceCount": accepted,
        "newEvidenceCount": new_evidence,
        "cooldownTaskCount": cooldown,
        "sources": sources[:6],
    }


def write_memory(memory: dict[str, Any], path: Path = OUTPUT_PATH) -> None:
    normalized = normalize_memory(memory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
