#!/usr/bin/env python3
"""Run the person profile refresh with active, public video-platform enrichment.

Before a normal refresh, the deterministic person research planner reads the previous
profile snapshot and produces bounded evidence-search questions. The daily scheduler then
allocates a limited number of active research query slots, and only scheduled queries are
fed into the existing identity-gated video discovery. Baseline person refresh behavior is
unchanged for people without an allocated active research slot.

Task-directed attempts are recorded in Outcome Memory only after a real executor call.
The memory measures research productivity and never changes factual verification state.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import refresh_people_profiles as core
from tools.person_research_agent import (
    ARTICLES_PATH,
    PEOPLE_PATH,
    build_agenda,
    load_json,
)
from tools.person_research_outcomes import (
    empty_memory,
    load_memory,
    record_attempts,
    write_memory,
)
from tools.person_research_scheduler import build_daily_queue, scheduled_queries_by_slug
from tools.person_video_discovery import build_video_query, discover_person_video_materials
from tools.wechat_channel_card_discovery import discover_embedded_wechat_video_materials

_BASE_ENRICH_CANDIDATE = core.enrich_candidate
_RESEARCH_QUERY_MAP: dict[str, list[str]] = {}
_RESEARCH_TASK_MAP: dict[str, dict[str, Any]] = {}
_RESEARCH_QUEUE_STATS: dict[str, int] = {}
_RESEARCH_MEMORY: dict[str, Any] = empty_memory()
_RESEARCH_ATTEMPTS: list[dict[str, Any]] = []
_RESEARCH_DATE = ""


def _scheduled_task_map(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in queue.get("queue") or []:
        if not isinstance(row, dict) or int(row.get("queryBudget") or 0) <= 0:
            continue
        slug = str(row.get("personSlug") or "").strip()
        if slug and slug not in result:
            result[slug] = row
    return result


def _load_active_research_queries() -> dict[str, list[str]]:
    global _RESEARCH_QUEUE_STATS, _RESEARCH_TASK_MAP, _RESEARCH_MEMORY, _RESEARCH_DATE
    people_payload = load_json(PEOPLE_PATH, {"people": []})
    agenda = build_agenda(
        people_payload,
        load_json(ARTICLES_PATH, {"articles": []}),
    )
    _RESEARCH_MEMORY = load_memory()
    queue = build_daily_queue(agenda, people_payload, _RESEARCH_MEMORY)
    _RESEARCH_TASK_MAP = _scheduled_task_map(queue)
    _RESEARCH_DATE = str(queue.get("researchDate") or "")
    _RESEARCH_QUEUE_STATS = {
        "people": int(queue.get("selectedPeopleCount") or 0),
        "tasks": int(queue.get("selectedTaskCount") or 0),
        "queries": int(queue.get("allocatedQuerySlots") or 0),
    }
    return scheduled_queries_by_slug(queue)


def _candidate_with_research_query(candidate: dict[str, Any]) -> dict[str, Any]:
    queries = _RESEARCH_QUERY_MAP.get(str(candidate.get("slug") or "")) or []
    if not queries:
        return candidate
    override = dict(candidate.get("override") or {})
    existing = [str(value) for value in override.get("videoQueries") or [] if str(value).strip()]
    # Existing hand-curated videoQueries retain precedence. Outcome Memory records the
    # query that was actually executed rather than assuming the scheduled text won.
    override["videoQueries"] = existing or [queries[0]]
    return {**candidate, "override": override}


def _previous_urls(previous: dict[str, Any] | None) -> set[str]:
    if not isinstance(previous, dict):
        return set()
    urls: set[str] = set()
    for material in previous.get("materials") or []:
        if isinstance(material, dict) and str(material.get("url") or "").strip():
            urls.add(str(material.get("url")).strip())
    return urls


def _platform_name(source: Any) -> str:
    text = str(source or "").strip().casefold()
    if text.startswith("youtube"):
        return "YouTube"
    if text.startswith("bilibili"):
        return "Bilibili"
    if "微信视频号" in str(source or ""):
        return "微信视频号"
    return ""


def _research_attempt_event(
    candidate: dict[str, Any],
    previous: dict[str, Any] | None,
    discovery_candidate: dict[str, Any],
    video_materials: list[dict[str, str]],
    *,
    direct_failed: bool,
) -> dict[str, Any] | None:
    slug = str(candidate.get("slug") or "").strip()
    task = _RESEARCH_TASK_MAP.get(slug)
    if not task:
        return None
    query = build_video_query(discovery_candidate)
    if not query:
        return None

    prior_urls = _previous_urls(previous)
    accepted_urls: list[str] = []
    seen: set[str] = set()
    for item in video_materials:
        url = str(item.get("url") or "").strip()
        if url and url not in seen:
            seen.add(url)
            accepted_urls.append(url)
    new_urls = {url for url in accepted_urls if url not in prior_urls}

    platforms: dict[str, dict[str, Any]] = {
        "YouTube": {
            "source": "YouTube",
            "rawRows": 0,
            "acceptedEvidenceCount": 0,
            "newEvidenceCount": 0,
            "failed": direct_failed,
            "acceptedUrls": [],
        },
        "Bilibili": {
            "source": "Bilibili",
            "rawRows": 0,
            "acceptedEvidenceCount": 0,
            "newEvidenceCount": 0,
            "failed": direct_failed,
            "acceptedUrls": [],
        },
        "微信视频号": {
            "source": "微信视频号",
            "rawRows": 0,
            "acceptedEvidenceCount": 0,
            "newEvidenceCount": 0,
            "failed": direct_failed,
            "acceptedUrls": [],
        },
    }
    for item in video_materials:
        platform = _platform_name(item.get("source"))
        url = str(item.get("url") or "").strip()
        if not platform or not url:
            continue
        row = platforms[platform]
        if url in row["acceptedUrls"]:
            continue
        row["acceptedUrls"].append(url)
        row["acceptedEvidenceCount"] += 1
        if url in new_urls:
            row["newEvidenceCount"] += 1

    return {
        "taskId": str(task.get("taskId") or ""),
        "personSlug": slug,
        "taskType": str(task.get("taskType") or ""),
        "executor": "person_video",
        "query": query,
        "researchDate": _RESEARCH_DATE,
        "attemptedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "acceptedEvidenceCount": len(accepted_urls),
        "newEvidenceCount": len(new_urls),
        "platforms": list(platforms.values()),
    }


def merge_video_materials(profile: dict[str, Any], video_materials: list[dict[str, str]]) -> dict[str, Any]:
    if not video_materials:
        return profile
    materials = core.dedupe_materials([*video_materials, *(profile.get("materials") or [])])
    speeches = [item for item in materials if item.get("type") in {"speech", "interview", "qa"}]
    sources = core.unique([
        *(profile.get("sources") or []),
        *(str(item.get("url") or "") for item in video_materials),
    ])
    status = (
        "complete"
        if profile.get("background") and len(materials) >= 4
        else "partial"
        if materials
        else "pending"
    )
    return {
        **profile,
        "materials": materials,
        "speeches": speeches,
        "sources": sources,
        "status": status,
    }


def enrich_candidate(
    candidate: dict[str, Any],
    previous: dict[str, Any] | None,
    articles: list[dict[str, Any]],
    offline: bool,
) -> dict[str, Any]:
    profile = _BASE_ENRICH_CANDIDATE(candidate, previous, articles, offline)
    if offline:
        return profile
    discovery_candidate = _candidate_with_research_query(candidate)
    video_materials: list[dict[str, str]] = []
    direct_failed = False
    try:
        video_materials.extend(discover_person_video_materials(discovery_candidate))
    except Exception:
        direct_failed = True
    attempt = _research_attempt_event(
        candidate,
        previous,
        discovery_candidate,
        video_materials,
        direct_failed=direct_failed,
    )
    if attempt:
        _RESEARCH_ATTEMPTS.append(attempt)
    if articles:
        try:
            video_materials.extend(
                discover_embedded_wechat_video_materials(discovery_candidate, articles)
            )
        except Exception:
            pass
    return merge_video_materials(profile, video_materials)


# The core builder resolves this global from its own module, so replace it once before
# exposing the ordinary build entry point.
core.enrich_candidate = enrich_candidate
build_payload = core.build_payload


def main() -> int:
    global _RESEARCH_QUERY_MAP, _RESEARCH_ATTEMPTS
    validate_only = "--validate-only" in sys.argv
    offline = "--offline" in sys.argv
    _RESEARCH_ATTEMPTS = []
    if not validate_only and not offline:
        _RESEARCH_QUERY_MAP = _load_active_research_queries()
        print(
            "Daily person research queue prepared: "
            f"{_RESEARCH_QUEUE_STATS.get('people', 0)} people / "
            f"{_RESEARCH_QUEUE_STATS.get('tasks', 0)} tasks / "
            f"{_RESEARCH_QUEUE_STATS.get('queries', 0)} active query slots."
        )
    result = core.main()
    if result == 0 and not validate_only and not offline and _RESEARCH_ATTEMPTS:
        added = record_attempts(_RESEARCH_MEMORY, _RESEARCH_ATTEMPTS)
        if added:
            write_memory(_RESEARCH_MEMORY)
        print(
            "Person research outcome memory: "
            f"{len(_RESEARCH_ATTEMPTS)} executor attempts observed / {added} new daily attempts recorded."
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
