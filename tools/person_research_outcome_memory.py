#!/usr/bin/env python3
"""Persist bounded execution memory for person research attempts.

This file stores research-process outcomes, never factual verification. A successful
search means only that candidate evidence was discovered; it does not mark a research
task supported and cannot bypass the task's success criteria.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.person_research_cost_model import build_cost_stats, cost_units_from_duration
from tools.person_research_strategy_memory import (
    build_strategy_stats,
    classify_query_strategy,
    classify_source_type,
)

OUTPUT_PATH = ROOT / "public" / "data" / "person_research_outcomes.json"
MAX_ATTEMPTS = 500
ZERO_YIELD_COOLDOWN_DAYS = 3
ERROR_COOLDOWN_DAYS = 1
RECENT_MEMORY_DAYS = 14


def clean(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def load_memory(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _date(value: Any) -> dt.date | None:
    text = clean(value, 40)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number == number else fallback


def source_host(url: Any) -> str:
    try:
        return (urlparse(clean(url, 1000)).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _source_type_counts(value: Any, hosts: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    if isinstance(value, dict):
        for raw_type, raw_count in value.items():
            source_type = clean(raw_type, 80)
            if not source_type:
                continue
            try:
                count = max(0, min(50, int(raw_count or 0)))
            except (TypeError, ValueError):
                count = 0
            if count:
                result[source_type] = result.get(source_type, 0) + count
    if result:
        return result
    for host in hosts:
        source_type = classify_source_type(f"https://{host}")
        result[source_type] = result.get(source_type, 0) + 1
    return result


def normalize_attempt(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    task_id = clean(value.get("taskId"), 180)
    person_slug = clean(value.get("personSlug"), 180)
    research_date = clean(value.get("researchDate"), 10)
    outcome = clean(value.get("outcome"), 40)
    if not task_id or not person_slug or not _date(research_date) or outcome not in {"candidate_found", "no_evidence", "error"}:
        return None
    candidate_count = max(0, min(50, int(value.get("candidateCount") or 0)))
    hosts: list[str] = []
    for raw in value.get("sourceHosts") or []:
        host = clean(raw, 180).lower()
        if host and host not in hosts:
            hosts.append(host)
        if len(hosts) >= 8:
            break
    task_type = clean(value.get("taskType"), 80)
    query = clean(value.get("query"), 220)
    query_strategy = clean(value.get("queryStrategy"), 80) or classify_query_strategy(query, task_type)
    source_type_counts = _source_type_counts(value.get("sourceTypeCounts"), hosts)
    source_types: list[str] = []
    for raw in value.get("sourceTypes") or list(source_type_counts):
        source_type = clean(raw, 80)
        if source_type and source_type not in source_types:
            source_types.append(source_type)
        if len(source_types) >= 8:
            break
    duration_ms = max(0, min(600_000, int(_number(value.get("durationMs")))))
    explicit_cost = _number(value.get("queryCostUnits"))
    query_cost_units = (
        round(min(10.0, max(1.0, explicit_cost)), 3)
        if explicit_cost > 0
        else cost_units_from_duration(duration_ms)
    )
    return {
        "taskId": task_id,
        "taskType": task_type,
        "personSlug": person_slug,
        "researchDate": research_date,
        "query": query,
        "queryStrategy": query_strategy,
        "outcome": outcome,
        "candidateCount": candidate_count,
        "sourceHosts": hosts,
        "sourceTypes": source_types,
        "sourceTypeCounts": source_type_counts,
        "durationMs": duration_ms,
        "queryCostUnits": query_cost_units,
    }


def normalized_attempts(memory: dict[str, Any]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for raw in memory.get("attempts") or []:
        attempt = normalize_attempt(raw)
        if attempt:
            attempts.append(attempt)
    return attempts[-MAX_ATTEMPTS:]


def task_history(memory: dict[str, Any], task_id: str) -> list[dict[str, Any]]:
    return [attempt for attempt in normalized_attempts(memory) if attempt["taskId"] == task_id]


def task_memory_signal(memory: dict[str, Any], task_id: str, research_date: str) -> tuple[int, str, str]:
    """Return score adjustment, explanation and cooldown-until date."""
    today = _date(research_date)
    history = task_history(memory, task_id)
    if not today or not history:
        return 0, "", ""
    dated = [(attempt, _date(attempt["researchDate"])) for attempt in history]
    dated = [(attempt, day) for attempt, day in dated if day and day <= today]
    if not dated:
        return 0, "", ""
    latest, latest_day = max(dated, key=lambda item: item[1])
    age = (today - latest_day).days
    if latest["outcome"] == "candidate_found" and age <= 7:
        return 6, "近期主动检索已有候选产出，优先完成证据核验", ""
    if latest["outcome"] == "no_evidence" and age < ZERO_YIELD_COOLDOWN_DAYS:
        until = latest_day + dt.timedelta(days=ZERO_YIELD_COOLDOWN_DAYS)
        return -18, "近期主动检索零产出，进入短期冷却避免重复消耗预算", until.isoformat()
    if latest["outcome"] == "error" and age < ERROR_COOLDOWN_DAYS:
        until = latest_day + dt.timedelta(days=ERROR_COOLDOWN_DAYS)
        return -6, "最近一次执行异常，短暂冷却后重试", until.isoformat()
    recent_no_yield = sum(
        1 for attempt, day in dated
        if attempt["outcome"] == "no_evidence" and 0 <= (today - day).days <= RECENT_MEMORY_DAYS
    )
    if recent_no_yield >= 3:
        return -10, f"近 {RECENT_MEMORY_DAYS} 天已有 {recent_no_yield} 次零产出，降低重复检索优先级", ""
    return 0, "", ""


def append_attempt(memory: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_attempt(attempt)
    attempts = normalized_attempts(memory)
    if not normalized:
        return build_payload(attempts)
    identity = (
        normalized["taskId"], normalized["researchDate"], normalized["query"], normalized["outcome"]
    )
    if not any((row["taskId"], row["researchDate"], row["query"], row["outcome"]) == identity for row in attempts):
        attempts.append(normalized)
    return build_payload(attempts[-MAX_ATTEMPTS:])


def build_payload(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [attempt for raw in attempts if (attempt := normalize_attempt(raw))]
    task_stats: dict[str, dict[str, int]] = {}
    source_stats: dict[str, dict[str, int]] = {}
    for attempt in normalized:
        task = task_stats.setdefault(attempt["taskId"], {"attempts": 0, "candidateFound": 0, "noEvidence": 0, "errors": 0})
        task["attempts"] += 1
        if attempt["outcome"] == "candidate_found":
            task["candidateFound"] += 1
        elif attempt["outcome"] == "no_evidence":
            task["noEvidence"] += 1
        else:
            task["errors"] += 1
        for host in attempt.get("sourceHosts") or []:
            source = source_stats.setdefault(host, {"candidateAttempts": 0, "candidates": 0})
            source["candidateAttempts"] += 1
            source["candidates"] += attempt["candidateCount"]
    strategy_stats = build_strategy_stats(normalized)
    cost_stats = build_cost_stats(normalized)
    return {
        "schemaVersion": 3,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "attemptCount": len(normalized),
        "attempts": normalized,
        "taskStats": task_stats,
        "sourceStats": source_stats,
        **strategy_stats,
        **cost_stats,
        "methodology": (
            "仅记录研究执行产出与成本；candidate_found 代表找到候选材料，不代表事实 supported。"
            "查询策略、来源 ROI 与单位检索成本只用于排序与预算分配，不能绕过任务 successCriteria。"
        ),
    }


def write_memory(memory: dict[str, Any], path: Path = OUTPUT_PATH) -> None:
    payload = build_payload(normalized_attempts(memory))
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)
