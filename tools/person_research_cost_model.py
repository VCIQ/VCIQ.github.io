#!/usr/bin/env python3
"""Cost-aware and confidence-calibrated strategy utilities for person research.

This layer learns only research execution cost and candidate yield. It never verifies a
fact, changes task status, or bypasses success criteria. Low-sample observations are
shrunk toward a neutral prior so one lucky search cannot become a permanent policy.
"""

from __future__ import annotations

from typing import Any

from tools.person_research_strategy_memory import (
    choose_query_strategy,
    classify_query_strategy,
    clean,
)

DEFAULT_COST_UNITS = 1.0
MAX_COST_UNITS = 10.0
COST_UNIT_MS = 10_000
CALIBRATION_PRIOR_YIELD_PER_COST = 0.5
CALIBRATION_PRIOR_STRENGTH = 4
MIN_RELIABLE_COST_SAMPLES = 3
HIGH_CONFIDENCE_COST_SAMPLES = 8


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number == number else fallback


def cost_units_from_duration(duration_ms: Any) -> float:
    duration = max(0.0, _number(duration_ms))
    if duration <= 0:
        return DEFAULT_COST_UNITS
    return round(min(MAX_COST_UNITS, max(DEFAULT_COST_UNITS, duration / COST_UNIT_MS)), 3)


def attempt_cost_units(attempt: dict[str, Any]) -> float:
    explicit = _number(attempt.get("queryCostUnits"))
    if explicit > 0:
        return round(min(MAX_COST_UNITS, max(DEFAULT_COST_UNITS, explicit)), 3)
    return cost_units_from_duration(attempt.get("durationMs"))


def strategy_confidence(sample_size: int) -> tuple[float, str]:
    count = max(0, int(sample_size or 0))
    weight = round(count / (count + CALIBRATION_PRIOR_STRENGTH), 3) if count else 0.0
    if count == 0:
        level = "unseen"
    elif count < MIN_RELIABLE_COST_SAMPLES:
        level = "low"
    elif count < HIGH_CONFIDENCE_COST_SAMPLES:
        level = "medium"
    else:
        level = "high"
    return weight, level


def calibrate_yield_per_cost(observed: Any, sample_size: int) -> float:
    count = max(0, int(sample_size or 0))
    raw = max(0.0, min(10.0, _number(observed, CALIBRATION_PRIOR_YIELD_PER_COST)))
    if count <= 0:
        return CALIBRATION_PRIOR_YIELD_PER_COST
    calibrated = (
        raw * count
        + CALIBRATION_PRIOR_YIELD_PER_COST * CALIBRATION_PRIOR_STRENGTH
    ) / (count + CALIBRATION_PRIOR_STRENGTH)
    return round(calibrated, 3)


def _matching_attempts(
    memory: dict[str, Any], task_type: str, strategy: str
) -> tuple[list[dict[str, Any]], bool]:
    attempts = [
        row for row in memory.get("attempts") or []
        if isinstance(row, dict) and bool(row.get("costMeasured"))
    ]
    task_specific = [
        row
        for row in attempts
        if clean(row.get("taskType"), 80) == task_type
        and (
            clean(row.get("queryStrategy"), 80)
            or classify_query_strategy(row.get("query"), task_type)
        )
        == strategy
    ]
    if task_specific:
        return task_specific, True
    global_strategy = [
        row
        for row in attempts
        if (
            clean(row.get("queryStrategy"), 80)
            or classify_query_strategy(row.get("query"), row.get("taskType"))
        )
        == strategy
    ]
    return global_strategy, False


def strategy_cost_stats(memory: dict[str, Any], task_type: str, strategy: str) -> dict[str, Any]:
    history, task_specific = _matching_attempts(memory, task_type, strategy)
    if not history:
        return {
            "sampleSize": 0,
            "taskSpecificHistory": False,
            "expectedCostUnits": DEFAULT_COST_UNITS,
            "averageDurationMs": 0,
        }
    costs = [attempt_cost_units(row) for row in history]
    durations = [
        max(0, int(_number(row.get("durationMs"))))
        for row in history
        if _number(row.get("durationMs")) > 0
    ]
    return {
        "sampleSize": len(history),
        "taskSpecificHistory": task_specific,
        "expectedCostUnits": round(sum(costs) / len(costs), 3),
        "averageDurationMs": round(sum(durations) / len(durations)) if durations else 0,
    }


def cost_efficiency_adjustment(sample_size: int, calibrated_yield_per_cost: float) -> int:
    """Return a small bounded score adjustment only after reliable measured history."""
    if sample_size < MIN_RELIABLE_COST_SAMPLES:
        return 0
    if calibrated_yield_per_cost >= 1.2:
        return 8
    if calibrated_yield_per_cost >= 0.75:
        return 5
    if calibrated_yield_per_cost >= 0.4:
        return 2
    if calibrated_yield_per_cost <= 0.15:
        return -6
    if calibrated_yield_per_cost <= 0.25:
        return -3
    return 0


def build_cost_stats(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_stats: dict[str, dict[str, float | int]] = {}
    task_strategy_stats: dict[str, dict[str, dict[str, float | int]]] = {}
    for row in attempts:
        if not isinstance(row, dict) or not bool(row.get("costMeasured")):
            continue
        task_type = clean(row.get("taskType"), 80) or "unknown"
        strategy = clean(row.get("queryStrategy"), 80) or classify_query_strategy(
            row.get("query"), task_type
        )
        cost = attempt_cost_units(row)
        duration = max(0, int(_number(row.get("durationMs"))))
        for bucket in (
            strategy_stats.setdefault(strategy, {"attempts": 0, "costUnits": 0.0, "durationMs": 0}),
            task_strategy_stats.setdefault(task_type, {}).setdefault(
                strategy, {"attempts": 0, "costUnits": 0.0, "durationMs": 0}
            ),
        ):
            bucket["attempts"] = int(bucket["attempts"]) + 1
            bucket["costUnits"] = float(bucket["costUnits"]) + cost
            bucket["durationMs"] = int(bucket["durationMs"]) + duration

    def finalize(bucket: dict[str, float | int]) -> None:
        count = max(1, int(bucket.get("attempts") or 0))
        bucket["averageCostUnits"] = round(float(bucket.get("costUnits") or 0) / count, 3)
        bucket["averageDurationMs"] = round(int(bucket.get("durationMs") or 0) / count)

    for bucket in strategy_stats.values():
        finalize(bucket)
    for task_map in task_strategy_stats.values():
        for bucket in task_map.values():
            finalize(bucket)
    return {
        "queryStrategyCostStats": strategy_stats,
        "taskStrategyCostStats": task_strategy_stats,
    }


def choose_cost_aware_query_strategy(
    memory: dict[str, Any], task_type: Any, queries: list[str]
) -> dict[str, Any]:
    kind = clean(task_type, 80)
    candidates: list[dict[str, Any]] = []
    for index, query in enumerate(queries):
        text = clean(query, 220)
        if not text:
            continue
        base = dict(choose_query_strategy(memory, kind, [text]))
        strategy = clean(base.get("strategy"), 80)
        cost = strategy_cost_stats(memory, kind, strategy)
        cost_samples = int(cost.get("sampleSize") or 0)
        expected_cost = max(DEFAULT_COST_UNITS, float(cost.get("expectedCostUnits") or DEFAULT_COST_UNITS))
        expected_yield = max(0.0, float(base.get("expectedYieldPerSlot") or 0.5))
        observed_yield_per_cost = round(expected_yield / expected_cost, 3)
        calibrated_yield_per_cost = calibrate_yield_per_cost(observed_yield_per_cost, cost_samples)
        confidence, confidence_level = strategy_confidence(cost_samples)
        cost_adjustment = cost_efficiency_adjustment(
            cost_samples, calibrated_yield_per_cost
        )
        base.update(
            {
                "costSampleSize": cost_samples,
                "expectedCostUnits": round(expected_cost, 3),
                "averageDurationMs": int(cost.get("averageDurationMs") or 0),
                "expectedYieldPerCost": observed_yield_per_cost,
                "calibratedYieldPerCost": calibrated_yield_per_cost,
                "strategyConfidence": confidence,
                "strategyConfidenceLevel": confidence_level,
                "costEfficiencyAdjustment": cost_adjustment,
                "costAwareRankingAdjustment": int(base.get("rankingAdjustment") or 0)
                + cost_adjustment,
                "originalIndex": index,
            }
        )
        candidates.append(base)

    if not candidates:
        empty = dict(choose_query_strategy(memory, kind, []))
        empty.update(
            {
                "costSampleSize": 0,
                "expectedCostUnits": DEFAULT_COST_UNITS,
                "averageDurationMs": 0,
                "expectedYieldPerCost": CALIBRATION_PRIOR_YIELD_PER_COST,
                "calibratedYieldPerCost": CALIBRATION_PRIOR_YIELD_PER_COST,
                "strategyConfidence": 0.0,
                "strategyConfidenceLevel": "unseen",
                "costEfficiencyAdjustment": 0,
                "costAwareRankingAdjustment": 0,
            }
        )
        return empty

    candidates.sort(
        key=lambda row: (
            -int(row.get("costAwareRankingAdjustment") or 0),
            -float(row.get("calibratedYieldPerCost") or CALIBRATION_PRIOR_YIELD_PER_COST),
            -float(row.get("strategyConfidence") or 0),
            -float(row.get("expectedYieldPerSlot") or 0),
            int(row.get("originalIndex") or 0),
        )
    )
    return dict(candidates[0])


def allocation_utility(research_score: int | float, calibrated_yield_per_cost: Any) -> float:
    """Combine research value with confidence-calibrated cost-adjusted expected yield.

    Unseen strategies use a neutral calibrated yield-per-cost=0.5. The multiplier is
    bounded so a cheap or lucky search can never overwhelm research importance.
    """
    score = max(0.0, _number(research_score))
    efficiency = min(2.0, max(0.0, _number(calibrated_yield_per_cost, CALIBRATION_PRIOR_YIELD_PER_COST)))
    return round(score * (0.5 + efficiency), 3)
