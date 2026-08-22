#!/usr/bin/env python3
"""Explainable query/source effectiveness for person research.

This module learns only from research-process outcomes. It estimates which bounded query
strategy and source type has historically produced candidate evidence. It never upgrades
candidate evidence to factual support and never bypasses task success criteria.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

QUERY_STRATEGY_LABELS = {
    "official_profile": "官方人物页",
    "personal_homepage": "个人主页",
    "role_official": "任职/官方核验",
    "topic_speech": "主题演讲",
    "topic_interview": "主题访谈",
    "full_context_interview": "完整上下文访谈",
    "paper_academic": "论文/学术材料",
    "latest_speech_interview": "近期演讲/访谈",
    "recency_year": "年份限定更新",
    "topic_direct": "主题直查",
    "topic_recent": "近期主题直查",
    "generic": "通用检索",
}

SOURCE_TYPE_LABELS = {
    "video_platform": "视频平台",
    "academic": "学术/研究来源",
    "official": "官方/机构来源",
    "social": "本人社交平台",
    "code": "代码/开发者来源",
    "media": "专业媒体",
    "general_web": "一般网页",
}

VIDEO_HOSTS = {
    "youtube.com",
    "youtu.be",
    "bilibili.com",
    "channels.weixin.qq.com",
    "v.qq.com",
}
ACADEMIC_HOSTS = {
    "arxiv.org",
    "doi.org",
    "semanticscholar.org",
    "scholar.google.com",
    "openreview.net",
}
SOCIAL_HOSTS = {"x.com", "twitter.com", "linkedin.com", "weibo.com"}
CODE_HOSTS = {"github.com", "gitlab.com"}
MEDIA_HOST_MARKERS = (
    "reuters.com",
    "bloomberg.com",
    "techcrunch.com",
    "wired.com",
    "theverge.com",
    "cnet.com",
    "zdnet.com",
    "techradar.com",
    "yahoo.com",
    "sina.com",
    "36kr.com",
    "tmtpost.com",
    "technode.com",
)

STRATEGY_PRIOR = {
    "official_profile": 3,
    "personal_homepage": 2,
    "role_official": 2,
    "full_context_interview": 3,
    "topic_speech": 2,
    "topic_interview": 1,
    "paper_academic": 2,
    "latest_speech_interview": 3,
    "recency_year": 1,
    "topic_direct": 0,
    "topic_recent": 0,
    "generic": 0,
}


def clean(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _host(url: Any) -> str:
    try:
        return (urlparse(clean(url, 1200)).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def classify_query_strategy(query: Any, task_type: Any = "") -> str:
    text = clean(query, 300).casefold()
    kind = clean(task_type, 80)
    if not text:
        return "generic"

    if "official profile" in text:
        return "official_profile"
    if "个人主页" in text or "homepage" in text:
        return "personal_homepage"
    if kind == "identity_verification" and ("任职" in text or "官方" in text or "appointment" in text):
        return "role_official"
    if "完整访谈" in text or "full interview" in text or "transcript" in text:
        return "full_context_interview"
    if re.search(r"\b(arxiv|paper|publication)\b", text) or "论文" in text:
        return "paper_academic"
    if "最新演讲" in text or "最新访谈" in text or "latest speech" in text or "latest interview" in text:
        return "latest_speech_interview"
    if "演讲" in text or re.search(r"\b(speech|keynote|talk)\b", text):
        return "topic_speech"
    if "访谈" in text or re.search(r"\binterview\b", text):
        return "topic_interview"
    if kind == "freshness_update" and re.search(r"\b20\d{2}\b", text):
        return "recency_year"
    if kind == "freshness_update":
        return "topic_recent"
    if kind in {"first_party_evidence", "viewpoint_verification", "identity_verification"}:
        return "topic_direct"
    return "generic"


def classify_source_type(url: Any, source: Any = "") -> str:
    host = _host(url)
    source_text = clean(source, 240).casefold()
    if host in VIDEO_HOSTS or any(host.endswith(f".{item}") for item in VIDEO_HOSTS):
        return "video_platform"
    if (
        host in ACADEMIC_HOSTS
        or any(host.endswith(f".{item}") for item in ACADEMIC_HOSTS)
        or host.endswith(".edu")
        or ".edu." in host
        or host.endswith(".ac.cn")
        or "大学" in source_text
        or "研究院" in source_text
        or "论文" in source_text
    ):
        return "academic"
    if host in CODE_HOSTS or any(host.endswith(f".{item}") for item in CODE_HOSTS):
        return "code"
    if host in SOCIAL_HOSTS or any(host.endswith(f".{item}") for item in SOCIAL_HOSTS):
        return "social"
    if "官方" in source_text or "official" in source_text or "本人" in source_text:
        return "official"
    if any(marker in host for marker in MEDIA_HOST_MARKERS) or any(
        marker in source_text for marker in ("媒体", "新闻", "财经", "technology review", "wired", "reuters", "bloomberg")
    ):
        return "media"
    return "general_web"


def _empty_stat() -> dict[str, Any]:
    return {
        "attempts": 0,
        "candidateFound": 0,
        "noEvidence": 0,
        "errors": 0,
        "candidates": 0,
        "successRate": 0.0,
        "averageCandidates": 0.0,
    }


def _finalize_stat(stat: dict[str, Any]) -> dict[str, Any]:
    attempts = int(stat.get("attempts") or 0)
    candidates = int(stat.get("candidates") or 0)
    success = int(stat.get("candidateFound") or 0)
    stat["successRate"] = round(success / attempts, 3) if attempts else 0.0
    stat["averageCandidates"] = round(candidates / attempts, 3) if attempts else 0.0
    return stat


def build_strategy_stats(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_stats: dict[str, dict[str, Any]] = {}
    task_strategy_stats: dict[str, dict[str, dict[str, Any]]] = {}
    source_type_stats: dict[str, dict[str, Any]] = {}
    task_totals: Counter[str] = Counter()
    task_source_success: dict[str, dict[str, int]] = {}
    task_source_candidates: dict[str, dict[str, int]] = {}

    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        task_type = clean(attempt.get("taskType"), 80) or "unknown"
        query = clean(attempt.get("query"), 300)
        strategy = clean(attempt.get("queryStrategy"), 80) or classify_query_strategy(query, task_type)
        outcome = clean(attempt.get("outcome"), 40)
        candidate_count = max(0, int(attempt.get("candidateCount") or 0))
        source_counts = attempt.get("sourceTypeCounts") if isinstance(attempt.get("sourceTypeCounts"), dict) else {}
        if not source_counts:
            source_counts = {clean(value, 80): 1 for value in attempt.get("sourceTypes") or [] if clean(value, 80)}

        task_totals[task_type] += 1
        for bucket in (
            strategy_stats.setdefault(strategy, _empty_stat()),
            task_strategy_stats.setdefault(task_type, {}).setdefault(strategy, _empty_stat()),
        ):
            bucket["attempts"] += 1
            bucket["candidates"] += candidate_count
            if outcome == "candidate_found":
                bucket["candidateFound"] += 1
            elif outcome == "no_evidence":
                bucket["noEvidence"] += 1
            elif outcome == "error":
                bucket["errors"] += 1

        for source_type, raw_count in source_counts.items():
            source_type = clean(source_type, 80)
            if not source_type:
                continue
            count = max(0, min(50, int(raw_count or 0)))
            source = source_type_stats.setdefault(source_type, {"yieldAttempts": 0, "candidates": 0})
            source["yieldAttempts"] += 1
            source["candidates"] += count
            task_source_success.setdefault(task_type, {})[source_type] = task_source_success.setdefault(task_type, {}).get(source_type, 0) + 1
            task_source_candidates.setdefault(task_type, {})[source_type] = task_source_candidates.setdefault(task_type, {}).get(source_type, 0) + count

    for stat in strategy_stats.values():
        _finalize_stat(stat)
    for task_map in task_strategy_stats.values():
        for stat in task_map.values():
            _finalize_stat(stat)

    for source in source_type_stats.values():
        attempts = int(source.get("yieldAttempts") or 0)
        source["averageCandidatesPerYield"] = round(int(source.get("candidates") or 0) / attempts, 3) if attempts else 0.0

    task_source_matrix: dict[str, dict[str, Any]] = {}
    for task_type, source_map in task_source_success.items():
        total = max(1, task_totals[task_type])
        task_source_matrix[task_type] = {}
        for source_type, success_attempts in source_map.items():
            task_source_matrix[task_type][source_type] = {
                "attempts": task_totals[task_type],
                "yieldAttempts": success_attempts,
                "yieldRate": round(success_attempts / total, 3),
                "candidates": task_source_candidates.get(task_type, {}).get(source_type, 0),
            }

    return {
        "queryStrategyStats": strategy_stats,
        "taskStrategyStats": task_strategy_stats,
        "sourceTypeStats": source_type_stats,
        "taskSourceMatrix": task_source_matrix,
    }


def _matching_attempts(memory: dict[str, Any], task_type: str, strategy: str) -> tuple[list[dict[str, Any]], bool]:
    attempts = [row for row in memory.get("attempts") or [] if isinstance(row, dict)]
    task_specific = [
        row for row in attempts
        if clean(row.get("taskType"), 80) == task_type
        and (clean(row.get("queryStrategy"), 80) or classify_query_strategy(row.get("query"), task_type)) == strategy
    ]
    if task_specific:
        return task_specific, True
    global_strategy = [
        row for row in attempts
        if (clean(row.get("queryStrategy"), 80) or classify_query_strategy(row.get("query"), row.get("taskType"))) == strategy
    ]
    return global_strategy, False


def _history_adjustment(attempts: list[dict[str, Any]]) -> tuple[int, float, float]:
    count = len(attempts)
    if not count:
        return 0, 0.5, 0.0
    successes = sum(1 for row in attempts if clean(row.get("outcome"), 40) == "candidate_found")
    candidates = sum(max(0, int(row.get("candidateCount") or 0)) for row in attempts)
    smoothed_success = (successes + 1) / (count + 2)
    average_candidates = candidates / count
    if count == 1:
        adjustment = 2 if successes else -2
    elif count == 2:
        adjustment = 4 if successes >= 1 else -4
    elif smoothed_success >= 0.65:
        adjustment = 8
    elif smoothed_success >= 0.4:
        adjustment = 3
    elif smoothed_success <= 0.2:
        adjustment = -8
    elif smoothed_success <= 0.3:
        adjustment = -4
    else:
        adjustment = 0
    return adjustment, round(smoothed_success, 3), round(average_candidates, 3)


def _top_source_type(memory: dict[str, Any], task_type: str) -> str:
    stats = build_strategy_stats([row for row in memory.get("attempts") or [] if isinstance(row, dict)])
    matrix = stats.get("taskSourceMatrix", {}).get(task_type, {})
    if not isinstance(matrix, dict) or not matrix:
        return ""
    return max(
        matrix,
        key=lambda source_type: (
            float((matrix.get(source_type) or {}).get("yieldRate") or 0),
            int((matrix.get(source_type) or {}).get("candidates") or 0),
            source_type,
        ),
    )


def choose_query_strategy(memory: dict[str, Any], task_type: Any, queries: list[str]) -> dict[str, Any]:
    kind = clean(task_type, 80)
    candidates: list[dict[str, Any]] = []
    for index, query in enumerate(queries):
        text = clean(query, 220)
        if not text:
            continue
        strategy = classify_query_strategy(text, kind)
        history, task_specific = _matching_attempts(memory, kind, strategy)
        history_adjustment, expected_success, average_candidates = _history_adjustment(history)
        prior = STRATEGY_PRIOR.get(strategy, 0)
        candidates.append({
            "query": text,
            "strategy": strategy,
            "strategyLabel": QUERY_STRATEGY_LABELS.get(strategy, strategy),
            "sampleSize": len(history),
            "taskSpecificHistory": task_specific,
            "historyAdjustment": history_adjustment,
            "priorAdjustment": prior,
            "rankingAdjustment": history_adjustment + prior,
            "expectedSuccessRate": expected_success,
            "averageCandidates": average_candidates,
            "expectedYieldPerSlot": round(expected_success * max(1.0, average_candidates), 3),
            "originalIndex": index,
        })
    if not candidates:
        return {
            "query": "",
            "strategy": "generic",
            "strategyLabel": QUERY_STRATEGY_LABELS["generic"],
            "sampleSize": 0,
            "taskSpecificHistory": False,
            "historyAdjustment": 0,
            "priorAdjustment": 0,
            "rankingAdjustment": 0,
            "expectedSuccessRate": 0.5,
            "averageCandidates": 0.0,
            "expectedYieldPerSlot": 0.5,
            "topSourceType": "",
            "topSourceTypeLabel": "",
        }
    candidates.sort(
        key=lambda row: (
            -int(row["rankingAdjustment"]),
            -float(row["expectedYieldPerSlot"]),
            int(row["originalIndex"]),
        )
    )
    best = dict(candidates[0])
    top_source = _top_source_type(memory, kind)
    best["topSourceType"] = top_source
    best["topSourceTypeLabel"] = SOURCE_TYPE_LABELS.get(top_source, top_source) if top_source else ""
    return best
