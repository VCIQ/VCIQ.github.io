#!/usr/bin/env python3
"""Schedule a bounded daily queue from the active person research agenda.

The scheduler does not verify facts. It only ranks already-generated research tasks and
allocates a small number of active discovery slots. Every score is deterministic and
published as a component breakdown so the queue remains auditable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.person_research_agent import (
    OUTPUT_PATH as AGENDA_PATH,
    PEOPLE_PATH,
    clean,
    load_json,
    parse_date,
)

OUTPUT_PATH = ROOT / "public" / "data" / "person_research_queue.json"

MAX_DAILY_PEOPLE = 10
MAX_DAILY_TASKS = 20
MAX_TASKS_PER_PERSON = 2
MAX_ACTIVE_QUERY_SLOTS = 10
RECENT_WINDOW_DAYS = 30
DAY = 24 * 60 * 60

PRIORITY_SCORE = {"P0": 40, "P1": 28, "P2": 16, "P3": 8}
TYPE_SCORE = {
    "viewpoint_verification": 25,
    "execution_verification": 20,
    "identity_verification": 14,
    "first_party_evidence": 12,
    "freshness_update": 6,
}
STATUS_SCORE = {"candidate_found": 12, "open": 5, "blocked": -20}
VIDEO_TASK_TYPES = {"first_party_evidence", "viewpoint_verification", "freshness_update"}


def _person_map(people_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        clean(person.get("slug")): person
        for person in people_payload.get("people") or []
        if isinstance(person, dict) and clean(person.get("slug"))
    }


def _recent_material_stats(person: dict[str, Any], generated_at: str) -> tuple[int, int | None]:
    reference = parse_date(generated_at)
    if not reference:
        return 0, None
    dated: list[int] = []
    for material in person.get("materials") or []:
        if not isinstance(material, dict):
            continue
        timestamp = parse_date(material.get("date"))
        if timestamp:
            dated.append(timestamp)
    if not dated:
        return 0, None
    latest = max(dated)
    recent_count = sum(1 for value in dated if 0 <= reference - value <= RECENT_WINDOW_DAYS * DAY)
    return recent_count, max(0, int((reference - latest) / DAY))


def _recency_score(person: dict[str, Any], generated_at: str) -> tuple[int, list[str]]:
    recent_count, age_days = _recent_material_stats(person, generated_at)
    reasons: list[str] = []
    score = min(8, recent_count * 2)
    if age_days is not None:
        if age_days <= 7:
            score += 8
            reasons.append("近 7 天存在人物事件/材料")
        elif age_days <= 30:
            score += 5
            reasons.append("近 30 天存在人物事件/材料")
        elif age_days <= 90:
            score += 2
    if recent_count >= 2:
        reasons.append(f"近 30 天有 {recent_count} 条可定期资料")
    return min(score, 16), reasons


def _evidence_gap_score(task: dict[str, Any]) -> tuple[int, str]:
    task_type = clean(task.get("taskType"))
    basis = len(task.get("evidenceBasis") or [])
    candidates = len(task.get("candidateEvidence") or [])
    if task_type == "identity_verification":
        return 14, "身份/任职仍缺独立官方证据"
    if task_type == "first_party_evidence":
        if basis == 0:
            return 16, "尚无一手材料，证据缺口最大"
        return 8, "一手材料仍未达到关闭标准"
    if task_type == "viewpoint_verification":
        return 12, "观点变化候选需要回到完整上下文"
    if task_type == "execution_verification":
        if candidates:
            return 14, "已有候选执行证据，接近可验证状态"
        return 8, "人物表达尚缺独立组织执行证据"
    if task_type == "freshness_update":
        return 6, "近期证据窗口存在空缺"
    return 0, ""


def _cross_validation_score(task: dict[str, Any]) -> tuple[int, str]:
    task_type = clean(task.get("taskType"))
    if task_type == "execution_verification":
        return 15, "需要人物频道与公司/技术执行证据交叉验证"
    if task_type == "viewpoint_verification":
        return 12, "需要跨时间一手材料直接比较"
    return 0, ""


def _query_readiness_score(task: dict[str, Any]) -> tuple[int, str]:
    queries = [clean(value) for value in task.get("searchQueries") or [] if clean(value)]
    task_type = clean(task.get("taskType"))
    if task_type in VIDEO_TASK_TYPES and queries:
        return 6, "已有绑定人物身份的可执行检索词"
    if task_type in {"identity_verification", "execution_verification"}:
        return 3, "可进入官方来源/跨频道核验"
    return 0, ""


def _executor(task: dict[str, Any]) -> str:
    task_type = clean(task.get("taskType"))
    if task_type in VIDEO_TASK_TYPES and task.get("searchQueries"):
        return "person_video"
    if task_type == "execution_verification":
        return "cross_channel"
    return "official_source"


def score_task(
    task: dict[str, Any],
    person: dict[str, Any],
    generated_at: str,
) -> tuple[int, dict[str, int], list[str]]:
    priority = PRIORITY_SCORE.get(clean(task.get("priority")), 0)
    task_type = TYPE_SCORE.get(clean(task.get("taskType")), 0)
    status = STATUS_SCORE.get(clean(task.get("status")), 0)
    gap, gap_reason = _evidence_gap_score(task)
    recency, recency_reasons = _recency_score(person, generated_at)
    cross, cross_reason = _cross_validation_score(task)
    ready, ready_reason = _query_readiness_score(task)
    breakdown = {
        "priority": priority,
        "taskType": task_type,
        "status": status,
        "evidenceGap": gap,
        "recency": recency,
        "crossValidation": cross,
        "queryReadiness": ready,
    }
    reasons = [
        f"{clean(task.get('priority'))} 研究任务",
        gap_reason,
        *recency_reasons,
        cross_reason,
        ready_reason,
    ]
    return sum(breakdown.values()), breakdown, [reason for reason in reasons if reason][:5]


def build_daily_queue(agenda: dict[str, Any], people_payload: dict[str, Any]) -> dict[str, Any]:
    generated_at = clean(agenda.get("generatedAt") or people_payload.get("generatedAt"))
    people = _person_map(people_payload)
    candidates: list[dict[str, Any]] = []
    for slug, record in (agenda.get("people") or {}).items():
        if not isinstance(record, dict):
            continue
        person = people.get(str(slug), {})
        for task in record.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            status = clean(task.get("status"))
            if status in {"supported", "blocked"}:
                continue
            score, breakdown, reasons = score_task(task, person, generated_at)
            candidates.append({
                "personSlug": str(slug),
                "personName": clean(record.get("personName") or person.get("name"), 120),
                "taskId": clean(task.get("id"), 180),
                "taskType": clean(task.get("taskType"), 80),
                "priority": clean(task.get("priority"), 8),
                "status": status,
                "target": clean(task.get("target"), 180),
                "question": clean(task.get("question"), 520),
                "successCriteria": clean(task.get("successCriteria"), 620),
                "executor": _executor(task),
                "searchQueries": [clean(value, 220) for value in (task.get("searchQueries") or [])[:3] if clean(value)],
                "evidenceBasisCount": len(task.get("evidenceBasis") or []),
                "candidateEvidenceCount": len(task.get("candidateEvidence") or []),
                "score": score,
                "scoreBreakdown": breakdown,
                "whyNow": reasons,
                "personRoute": f"/people/{slug}/",
            })

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    candidates.sort(key=lambda row: (
        -int(row["score"]),
        priority_order.get(row["priority"], 9),
        row["personSlug"],
        row["taskId"],
    ))

    selected: list[dict[str, Any]] = []
    selected_people: set[str] = set()
    tasks_per_person: dict[str, int] = {}
    for row in candidates:
        slug = row["personSlug"]
        if tasks_per_person.get(slug, 0) >= MAX_TASKS_PER_PERSON:
            continue
        if slug not in selected_people and len(selected_people) >= MAX_DAILY_PEOPLE:
            continue
        selected.append(row)
        selected_people.add(slug)
        tasks_per_person[slug] = tasks_per_person.get(slug, 0) + 1
        if len(selected) >= MAX_DAILY_TASKS:
            break

    query_people: set[str] = set()
    allocated = 0
    for rank, row in enumerate(selected, start=1):
        row["rank"] = rank
        row["queryBudget"] = 0
        if (
            row["executor"] == "person_video"
            and row["searchQueries"]
            and row["personSlug"] not in query_people
            and allocated < MAX_ACTIVE_QUERY_SLOTS
        ):
            row["queryBudget"] = 1
            row["searchQueries"] = row["searchQueries"][:1]
            query_people.add(row["personSlug"])
            allocated += 1
        elif row["executor"] == "person_video":
            row["searchQueries"] = []

    try:
        parsed = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00")) if generated_at else dt.datetime.now(dt.timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        research_date = parsed.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except ValueError:
        research_date = dt.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()

    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "researchDate": research_date,
        "limits": {
            "people": MAX_DAILY_PEOPLE,
            "tasks": MAX_DAILY_TASKS,
            "tasksPerPerson": MAX_TASKS_PER_PERSON,
            "activeQuerySlots": MAX_ACTIVE_QUERY_SLOTS,
        },
        "candidateTaskCount": len(candidates),
        "selectedPeopleCount": len(selected_people),
        "selectedTaskCount": len(selected),
        "allocatedQuerySlots": allocated,
        "queue": selected,
        "methodology": (
            "队列只排序开放研究任务并分配有限主动检索槽位，不改变事实状态。"
            "分数由任务优先级、任务类型、状态、证据缺口、近期事件、跨频道验证价值和可执行性确定；"
            "supported/blocked 不进入今日执行队列。"
        ),
    }


def scheduled_queries_by_slug(queue: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in queue.get("queue") or []:
        if not isinstance(row, dict) or int(row.get("queryBudget") or 0) <= 0:
            continue
        slug = clean(row.get("personSlug"), 180)
        queries = [clean(value, 220) for value in row.get("searchQueries") or [] if clean(value)]
        if slug and queries:
            result.setdefault(slug, []).extend(queries[:1])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agenda", type=Path, default=AGENDA_PATH)
    parser.add_argument("--people", type=Path, default=PEOPLE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    queue = build_daily_queue(
        load_json(args.agenda, {"people": {}}),
        load_json(args.people, {"people": []}),
    )
    if args.check:
        if queue["selectedPeopleCount"] > MAX_DAILY_PEOPLE or queue["selectedTaskCount"] > MAX_DAILY_TASKS:
            print("Person research queue exceeds daily limits.")
            return 1
        if queue["allocatedQuerySlots"] > MAX_ACTIVE_QUERY_SLOTS:
            print("Person research queue exceeds active query budget.")
            return 1
        print(
            f"Validated person research queue: {queue['selectedPeopleCount']} people, "
            f"{queue['selectedTaskCount']} tasks, {queue['allocatedQuerySlots']} active queries."
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote daily person research queue: {queue['selectedPeopleCount']} people, "
        f"{queue['selectedTaskCount']} tasks, {queue['allocatedQuerySlots']} active queries -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
