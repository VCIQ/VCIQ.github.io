#!/usr/bin/env python3
"""Schedule bounded Research and Maintenance queues from the person agenda.

The scheduler does not verify facts. It ranks already-generated tasks, separates
substantive research from profile/evidence maintenance, and allocates a bounded
number of active discovery slots. Maintenance can use spare capacity but cannot
push high-value research work out of the Research lane.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.person_identity_contract import validate_generated_person_identity
from tools.person_research_agent import (
    OUTPUT_PATH as AGENDA_PATH,
    PEOPLE_PATH,
    atomic_write_json,
    clean,
    load_json,
    parse_date,
)
from tools.person_research_cost_model import (
    allocation_utility,
    choose_cost_aware_query_strategy,
)
from tools.person_research_outcome_memory import (
    OUTPUT_PATH as OUTCOME_MEMORY_PATH,
    load_memory,
    task_memory_signal,
)

OUTPUT_PATH = ROOT / "public" / "data" / "person_research_queue.json"

MAX_DAILY_PEOPLE = 10
MAX_DAILY_TASKS = 20
MAX_DAILY_RESEARCH_TASKS = 14
MAX_DAILY_MAINTENANCE_TASKS = 6
MAX_TASKS_PER_PERSON = 2
MAX_ACTIVE_QUERY_SLOTS = 10
MAX_MAINTENANCE_QUERY_SLOTS = 2
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
MAINTENANCE_TASK_TYPES = {"identity_verification", "freshness_update"}
WORKSTREAMS = {"research", "maintenance"}


def task_workstream(task: dict[str, Any]) -> str:
    explicit = clean(task.get("workstream"), 40)
    if explicit in WORKSTREAMS:
        return explicit
    return "maintenance" if clean(task.get("taskType"), 80) in MAINTENANCE_TASK_TYPES else "research"


def _person_map(people_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        clean(person.get("slug")): person
        for person in people_payload.get("people") or []
        if isinstance(person, dict) and clean(person.get("slug"))
    }


def _research_date(generated_at: str) -> str:
    try:
        parsed = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00")) if generated_at else dt.datetime.now(dt.timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except ValueError:
        return dt.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


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


def _cost_efficiency_score(strategy: dict[str, Any]) -> tuple[int, str]:
    sample_size = int(strategy.get("costSampleSize") or 0)
    score = int(strategy.get("costEfficiencyAdjustment") or 0)
    if sample_size < 2:
        return 0, ""
    ratio = float(strategy.get("expectedYieldPerCost") or 0)
    cost = float(strategy.get("expectedCostUnits") or 1)
    return score, f"单位成本预期候选产出 {ratio:.2f}（历史成本 {cost:.2f} 单位）"


def score_task(
    task: dict[str, Any],
    person: dict[str, Any],
    generated_at: str,
    memory: dict[str, Any] | None = None,
    research_date: str = "",
    strategy: dict[str, Any] | None = None,
) -> tuple[int, dict[str, int], list[str], str]:
    priority = PRIORITY_SCORE.get(clean(task.get("priority")), 0)
    task_type = TYPE_SCORE.get(clean(task.get("taskType")), 0)
    status = STATUS_SCORE.get(clean(task.get("status")), 0)
    gap, gap_reason = _evidence_gap_score(task)
    recency, recency_reasons = _recency_score(person, generated_at)
    cross, cross_reason = _cross_validation_score(task)
    ready, ready_reason = _query_readiness_score(task)
    memory_score, memory_reason, cooldown_until = task_memory_signal(
        memory or {}, clean(task.get("id"), 180), research_date
    )
    strategy = strategy or {}
    strategy_score = int(strategy.get("historyAdjustment") or 0)
    cost_score, cost_reason = _cost_efficiency_score(strategy)
    sample_size = int(strategy.get("sampleSize") or 0)
    strategy_reason = ""
    if sample_size:
        strategy_reason = (
            f"{clean(strategy.get('strategyLabel'), 80)} 历史 {sample_size} 次，"
            f"平滑候选命中率 {float(strategy.get('expectedSuccessRate') or 0):.0%}"
        )
    breakdown = {
        "priority": priority,
        "taskType": task_type,
        "status": status,
        "evidenceGap": gap,
        "recency": recency,
        "crossValidation": cross,
        "queryReadiness": ready,
        "researchOutcomeMemory": memory_score,
        "researchStrategyROI": strategy_score,
        "researchCostEfficiency": cost_score,
    }
    lane = "维护" if task_workstream(task) == "maintenance" else "研究"
    reasons = [
        f"{clean(task.get('priority'))} {lane}任务",
        gap_reason,
        *recency_reasons,
        cross_reason,
        ready_reason,
        memory_reason,
        strategy_reason,
        cost_reason,
    ]
    return sum(breakdown.values()), breakdown, [reason for reason in reasons if reason][:6], cooldown_until


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return (
        -int(row["score"]),
        -float(row.get("allocationUtility") or 0),
        -float(row.get("expectedYieldPerCost") or 0),
        priority_order.get(row["priority"], 9),
        row["personSlug"],
        row["taskId"],
    )


def _select_workstreams(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str]]:
    research = [row for row in candidates if row.get("workstream") == "research"]
    maintenance = [row for row in candidates if row.get("workstream") == "maintenance"]
    selected: list[dict[str, Any]] = []
    selected_people: set[str] = set()
    tasks_per_person: dict[str, int] = {}

    def add_rows(rows: list[dict[str, Any]], lane_limit: int, *, count_existing_lane: bool = True) -> None:
        lane_count = sum(1 for row in selected if row.get("workstream") == rows[0].get("workstream")) if rows and count_existing_lane else 0
        for row in rows:
            if len(selected) >= MAX_DAILY_TASKS or lane_count >= lane_limit:
                break
            slug = row["personSlug"]
            if tasks_per_person.get(slug, 0) >= MAX_TASKS_PER_PERSON:
                continue
            if slug not in selected_people and len(selected_people) >= MAX_DAILY_PEOPLE:
                continue
            if row in selected:
                continue
            selected.append(row)
            selected_people.add(slug)
            tasks_per_person[slug] = tasks_per_person.get(slug, 0) + 1
            lane_count += 1

    # Substantive research receives first claim on people/task capacity.
    add_rows(research, MAX_DAILY_RESEARCH_TASKS)
    add_rows(maintenance, MAX_DAILY_MAINTENANCE_TASKS)
    # Research can borrow unused maintenance capacity, but maintenance never
    # expands beyond its dedicated cap and therefore cannot crowd research out.
    if len(selected) < MAX_DAILY_TASKS:
        add_rows(research, MAX_DAILY_TASKS)
    return selected, selected_people


def _allocate_query_slots(selected: list[dict[str, Any]], research_date: str) -> set[str]:
    best_by_lane_person: dict[tuple[str, str], dict[str, Any]] = {}
    for row in selected:
        in_cooldown = bool(row.get("cooldownUntil") and row["cooldownUntil"] > research_date)
        if row["executor"] != "person_video" or not row["searchQueries"] or in_cooldown:
            continue
        key = (str(row.get("workstream") or "research"), row["personSlug"])
        previous = best_by_lane_person.get(key)
        if not previous or (
            float(row.get("allocationUtility") or 0),
            int(row.get("score") or 0),
            -int(row.get("rank") or 0),
        ) > (
            float(previous.get("allocationUtility") or 0),
            int(previous.get("score") or 0),
            -int(previous.get("rank") or 0),
        ):
            best_by_lane_person[key] = row

    def ordered(workstream: str) -> list[dict[str, Any]]:
        return sorted(
            [row for (lane, _), row in best_by_lane_person.items() if lane == workstream],
            key=lambda row: (
                -float(row.get("allocationUtility") or 0),
                -int(row.get("score") or 0),
                int(row.get("rank") or 0),
            ),
        )

    allocated_ids: set[str] = set()
    allocated_people: set[str] = set()
    for row in ordered("research"):
        if len(allocated_ids) >= MAX_ACTIVE_QUERY_SLOTS:
            break
        if row["personSlug"] in allocated_people:
            continue
        allocated_ids.add(row["taskId"])
        allocated_people.add(row["personSlug"])

    maintenance_allocated = 0
    for row in ordered("maintenance"):
        if len(allocated_ids) >= MAX_ACTIVE_QUERY_SLOTS or maintenance_allocated >= MAX_MAINTENANCE_QUERY_SLOTS:
            break
        if row["personSlug"] in allocated_people:
            continue
        allocated_ids.add(row["taskId"])
        allocated_people.add(row["personSlug"])
        maintenance_allocated += 1
    return allocated_ids


def build_daily_queue(
    agenda: dict[str, Any],
    people_payload: dict[str, Any],
    outcome_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = clean(agenda.get("generatedAt") or people_payload.get("generatedAt"))
    research_date = _research_date(generated_at)
    people = _person_map(people_payload)
    memory = outcome_memory or {}
    candidates: list[dict[str, Any]] = []
    for slug, record in (agenda.get("people") or {}).items():
        if not isinstance(record, dict):
            continue
        person = people.get(str(slug))
        # Reject stale agenda rows before ranking or allocating either workstream.
        # A display label in an old agenda is not a current person identity.
        if person is None or not validate_generated_person_identity(person)["valid"]:
            continue
        for task in record.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            status = clean(task.get("status"))
            if status in {"supported", "blocked"}:
                continue
            raw_queries = [clean(value, 220) for value in (task.get("searchQueries") or [])[:3] if clean(value)]
            strategy = choose_cost_aware_query_strategy(memory, clean(task.get("taskType"), 80), raw_queries)
            best_query = clean(strategy.get("query"), 220)
            ordered_queries = ([best_query] if best_query else []) + [value for value in raw_queries if value != best_query]
            score, breakdown, reasons, cooldown_until = score_task(
                task, person, generated_at, memory, research_date, strategy
            )
            expected_yield_per_cost = float(strategy.get("expectedYieldPerCost") or 0.5)
            utility = allocation_utility(score, expected_yield_per_cost)
            candidates.append({
                "personSlug": str(slug),
                "personName": clean(record.get("personName") or person.get("name"), 120),
                "taskId": clean(task.get("id"), 180),
                "taskType": clean(task.get("taskType"), 80),
                "workstream": task_workstream(task),
                "priority": clean(task.get("priority"), 8),
                "status": status,
                "target": clean(task.get("target"), 180),
                "question": clean(task.get("question"), 520),
                "successCriteria": clean(task.get("successCriteria"), 620),
                "executor": _executor(task),
                "searchQueries": ordered_queries[:3],
                "queryStrategy": clean(strategy.get("strategy"), 80),
                "queryStrategyLabel": clean(strategy.get("strategyLabel"), 120),
                "strategySampleSize": int(strategy.get("sampleSize") or 0),
                "costSampleSize": int(strategy.get("costSampleSize") or 0),
                "expectedSuccessRate": float(strategy.get("expectedSuccessRate") or 0.5),
                "expectedEvidenceYield": float(strategy.get("expectedYieldPerSlot") or 0.5),
                "queryUnitCost": float(strategy.get("expectedCostUnits") or 1.0),
                "expectedYieldPerCost": expected_yield_per_cost,
                "allocationUtility": utility,
                "averageQueryDurationMs": int(strategy.get("averageDurationMs") or 0),
                "topHistoricalSourceType": clean(strategy.get("topSourceType"), 80),
                "topHistoricalSourceTypeLabel": clean(strategy.get("topSourceTypeLabel"), 120),
                "evidenceBasisCount": len(task.get("evidenceBasis") or []),
                "candidateEvidenceCount": len(task.get("candidateEvidence") or []),
                "score": score,
                "scoreBreakdown": breakdown,
                "whyNow": reasons,
                "cooldownUntil": cooldown_until,
                "personRoute": f"/people/{slug}/",
            })

    candidates.sort(key=_candidate_sort_key)
    selected, selected_people = _select_workstreams(candidates)

    lane_ranks = {"research": 0, "maintenance": 0}
    for rank, row in enumerate(selected, start=1):
        row["rank"] = rank
        lane = str(row.get("workstream") or "research")
        lane_ranks[lane] += 1
        row["workstreamRank"] = lane_ranks[lane]
        row["queryBudget"] = 0

    allocated_ids = _allocate_query_slots(selected, research_date)
    for row in selected:
        if row["taskId"] in allocated_ids:
            row["queryBudget"] = 1
            row["searchQueries"] = row["searchQueries"][:1]
        elif row["executor"] == "person_video":
            row["searchQueries"] = []

    research_candidates = sum(row.get("workstream") == "research" for row in candidates)
    maintenance_candidates = sum(row.get("workstream") == "maintenance" for row in candidates)
    research_selected = sum(row.get("workstream") == "research" for row in selected)
    maintenance_selected = sum(row.get("workstream") == "maintenance" for row in selected)
    research_queries = sum(row.get("workstream") == "research" and row.get("queryBudget") == 1 for row in selected)
    maintenance_queries = sum(row.get("workstream") == "maintenance" and row.get("queryBudget") == 1 for row in selected)
    memory_attempts = len(memory.get("attempts") or [])
    return {
        "schemaVersion": 5,
        "generatedAt": generated_at,
        "researchDate": research_date,
        "limits": {
            "people": MAX_DAILY_PEOPLE,
            "tasks": MAX_DAILY_TASKS,
            "researchTasks": MAX_DAILY_RESEARCH_TASKS,
            "maintenanceTasks": MAX_DAILY_MAINTENANCE_TASKS,
            "tasksPerPerson": MAX_TASKS_PER_PERSON,
            "activeQuerySlots": MAX_ACTIVE_QUERY_SLOTS,
            "maintenanceQuerySlots": MAX_MAINTENANCE_QUERY_SLOTS,
        },
        "candidateTaskCount": len(candidates),
        "candidateResearchTaskCount": research_candidates,
        "candidateMaintenanceTaskCount": maintenance_candidates,
        "selectedPeopleCount": len(selected_people),
        "selectedTaskCount": len(selected),
        "selectedResearchTaskCount": research_selected,
        "selectedMaintenanceTaskCount": maintenance_selected,
        "allocatedQuerySlots": len(allocated_ids),
        "allocatedResearchQuerySlots": research_queries,
        "allocatedMaintenanceQuerySlots": maintenance_queries,
        "outcomeMemoryAttemptCount": memory_attempts,
        "queue": selected,
        "methodology": (
            "开放任务分为 Research 与 Maintenance 两条工作流：观点、执行和一手研究证据进入 Research；"
            "身份/任职核验与时效补齐进入 Maintenance。Research 先获得人物与任务容量，Maintenance 最多占 6 个日任务，"
            "且主动检索只使用 Research 未占用的剩余槽位（最多 2 个），因此维护工作不会挤占核心研究。"
            "两条工作流都继续使用可审计的 Research Score、历史策略与成本效率修正；candidate_found 仍不能绕过 successCriteria。"
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


def scheduled_attempts_by_slug(queue: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in queue.get("queue") or []:
        if not isinstance(row, dict) or int(row.get("queryBudget") or 0) <= 0:
            continue
        slug = clean(row.get("personSlug"), 180)
        queries = [clean(value, 220) for value in row.get("searchQueries") or [] if clean(value)]
        task_id = clean(row.get("taskId"), 180)
        if slug and task_id and queries and slug not in result:
            result[slug] = {
                "taskId": task_id,
                "taskType": clean(row.get("taskType"), 80),
                "workstream": task_workstream(row),
                "query": queries[0],
                "queryStrategy": clean(row.get("queryStrategy"), 80),
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agenda", type=Path, default=AGENDA_PATH)
    parser.add_argument("--people", type=Path, default=PEOPLE_PATH)
    parser.add_argument("--memory", type=Path, default=OUTCOME_MEMORY_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    queue = build_daily_queue(
        load_json(args.agenda, {"people": {}}),
        load_json(args.people, {"people": []}),
        load_memory(args.memory),
    )
    if args.check:
        if queue["selectedPeopleCount"] > MAX_DAILY_PEOPLE or queue["selectedTaskCount"] > MAX_DAILY_TASKS:
            print("Person research queue exceeds daily limits.")
            return 1
        if queue["selectedResearchTaskCount"] > MAX_DAILY_TASKS:
            print("Research workstream exceeds total daily limit.")
            return 1
        if queue["selectedMaintenanceTaskCount"] > MAX_DAILY_MAINTENANCE_TASKS:
            print("Maintenance workstream exceeds its daily limit.")
            return 1
        if queue["allocatedQuerySlots"] > MAX_ACTIVE_QUERY_SLOTS:
            print("Person research queue exceeds active query budget.")
            return 1
        if queue["allocatedMaintenanceQuerySlots"] > MAX_MAINTENANCE_QUERY_SLOTS:
            print("Maintenance workstream exceeds active query budget.")
            return 1
        print(
            f"Validated person research queue: {queue['selectedPeopleCount']} people, "
            f"{queue['selectedResearchTaskCount']} research + {queue['selectedMaintenanceTaskCount']} maintenance tasks, "
            f"{queue['allocatedQuerySlots']} active queries."
        )
        return 0
    atomic_write_json(args.output, queue)
    print(
        f"Wrote daily person research queue: {queue['selectedPeopleCount']} people, "
        f"{queue['selectedResearchTaskCount']} research + {queue['selectedMaintenanceTaskCount']} maintenance tasks, "
        f"{queue['allocatedQuerySlots']} active queries -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
