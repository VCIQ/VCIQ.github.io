#!/usr/bin/env python3
"""Run person profile refresh with bounded active research outcome memory.

The daily scheduler allocates task-directed query slots. Only those scheduled attempts are
recorded in the outcome-memory ledger. Candidate discovery never changes supported state;
it only records research yield for future cooldown/retry and strategy decisions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import refresh_people_profiles as core
from tools.person_research_agent import ARTICLES_PATH, PEOPLE_PATH, build_agenda, load_json
from tools.person_research_outcome_memory import (
    OUTPUT_PATH as OUTCOME_MEMORY_PATH,
    append_attempt,
    load_memory,
    source_host,
    write_memory,
)
from tools.person_research_scheduler import build_daily_queue, scheduled_attempts_by_slug
from tools.person_research_strategy_memory import classify_source_type
from tools.person_video_discovery import discover_person_video_materials
from tools.wechat_channel_card_discovery import discover_embedded_wechat_video_materials

_BASE_ENRICH_CANDIDATE = core.enrich_candidate
_RESEARCH_ATTEMPT_MAP: dict[str, dict[str, str]] = {}
_RESEARCH_QUEUE_STATS: dict[str, int] = {}
_RESEARCH_DATE = ""
_OUTCOME_MEMORY: dict[str, Any] = {}


def _load_active_research_attempts() -> dict[str, dict[str, str]]:
    global _RESEARCH_QUEUE_STATS, _RESEARCH_DATE, _OUTCOME_MEMORY
    people_payload = load_json(PEOPLE_PATH, {"people": []})
    agenda = build_agenda(people_payload, load_json(ARTICLES_PATH, {"articles": []}))
    _OUTCOME_MEMORY = load_memory(OUTCOME_MEMORY_PATH)
    queue = build_daily_queue(agenda, people_payload, _OUTCOME_MEMORY)
    _RESEARCH_DATE = str(queue.get("researchDate") or "")
    _RESEARCH_QUEUE_STATS = {
        "people": int(queue.get("selectedPeopleCount") or 0),
        "tasks": int(queue.get("selectedTaskCount") or 0),
        "queries": int(queue.get("allocatedQuerySlots") or 0),
        "memory": int(queue.get("outcomeMemoryAttemptCount") or 0),
    }
    return scheduled_attempts_by_slug(queue)


def _candidate_with_research_query(candidate: dict[str, Any]) -> dict[str, Any]:
    """Bind the active discovery call to the exact scheduler-allocated query.

    Curated videoQueries remain part of the stored person configuration, but they do not
    replace the query whose cost/yield is being measured for this active research attempt.
    """
    attempt = _RESEARCH_ATTEMPT_MAP.get(str(candidate.get("slug") or "")) or {}
    query = str(attempt.get("query") or "").strip()
    if not query:
        return candidate
    override = dict(candidate.get("override") or {})
    override["videoQueries"] = [query]
    return {**candidate, "override": override}


def _record_research_attempt(slug: str, materials: list[dict[str, str]], had_error: bool) -> None:
    global _OUTCOME_MEMORY
    scheduled = _RESEARCH_ATTEMPT_MAP.get(slug)
    if not scheduled:
        return
    urls = [str(item.get("url") or "") for item in materials if str(item.get("url") or "").strip()]
    hosts: list[str] = []
    source_type_counts: dict[str, int] = {}
    for item in materials:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        host = source_host(url)
        if host and host not in hosts:
            hosts.append(host)
        source_type = classify_source_type(url, item.get("source"))
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
    outcome = "candidate_found" if urls else "error" if had_error else "no_evidence"
    _OUTCOME_MEMORY = append_attempt(_OUTCOME_MEMORY, {
        "taskId": scheduled.get("taskId"),
        "taskType": scheduled.get("taskType"),
        "personSlug": slug,
        "researchDate": _RESEARCH_DATE,
        "query": scheduled.get("query"),
        "queryStrategy": scheduled.get("queryStrategy"),
        "outcome": outcome,
        "candidateCount": len(urls),
        "sourceHosts": hosts,
        "sourceTypes": list(source_type_counts),
        "sourceTypeCounts": source_type_counts,
    })


def merge_video_materials(profile: dict[str, Any], video_materials: list[dict[str, str]]) -> dict[str, Any]:
    if not video_materials:
        return profile
    materials = core.dedupe_materials([*video_materials, *(profile.get("materials") or [])])
    speeches = [item for item in materials if item.get("type") in {"speech", "interview", "qa"}]
    sources = core.unique([
        *(profile.get("sources") or []),
        *(str(item.get("url") or "") for item in video_materials),
    ])
    status = "complete" if profile.get("background") and len(materials) >= 4 else "partial" if materials else "pending"
    return {**profile, "materials": materials, "speeches": speeches, "sources": sources, "status": status}


def enrich_candidate(
    candidate: dict[str, Any],
    previous: dict[str, Any] | None,
    articles: list[dict[str, Any]],
    offline: bool,
) -> dict[str, Any]:
    profile = _BASE_ENRICH_CANDIDATE(candidate, previous, articles, offline)
    if offline:
        return profile
    slug = str(candidate.get("slug") or "")
    discovery_candidate = _candidate_with_research_query(candidate)
    query_materials: list[dict[str, str]] = []
    embedded_materials: list[dict[str, str]] = []
    query_had_error = False
    try:
        query_materials.extend(discover_person_video_materials(discovery_candidate))
    except Exception:
        query_had_error = True
    if articles:
        try:
            embedded_materials.extend(discover_embedded_wechat_video_materials(discovery_candidate, articles))
        except Exception:
            pass
    query_materials = core.dedupe_materials(query_materials)
    embedded_materials = core.dedupe_materials(embedded_materials)
    _record_research_attempt(slug, query_materials, query_had_error)
    return merge_video_materials(profile, core.dedupe_materials([*query_materials, *embedded_materials]))


core.enrich_candidate = enrich_candidate
build_payload = core.build_payload


def main() -> int:
    global _RESEARCH_ATTEMPT_MAP
    validate_only = "--validate-only" in sys.argv
    offline = "--offline" in sys.argv
    active = not validate_only and not offline
    if active:
        _RESEARCH_ATTEMPT_MAP = _load_active_research_attempts()
        print(
            "Daily person research queue prepared: "
            f"{_RESEARCH_QUEUE_STATS.get('people', 0)} people / "
            f"{_RESEARCH_QUEUE_STATS.get('tasks', 0)} tasks / "
            f"{_RESEARCH_QUEUE_STATS.get('queries', 0)} active query slots / "
            f"{_RESEARCH_QUEUE_STATS.get('memory', 0)} prior attempts."
        )
    result = core.main()
    if active:
        write_memory(_OUTCOME_MEMORY, OUTCOME_MEMORY_PATH)
        print(f"Person research outcome memory written: {len(_OUTCOME_MEMORY.get('attempts') or [])} attempts.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
