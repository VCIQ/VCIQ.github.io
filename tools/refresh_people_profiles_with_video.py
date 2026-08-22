#!/usr/bin/env python3
"""Run the person profile refresh with active, public video-platform enrichment.

Before a normal refresh, the deterministic person research planner reads the previous
profile snapshot and produces bounded evidence-search questions. The daily scheduler then
allocates a limited number of active research query slots, and only scheduled queries are
fed into the existing identity-gated video discovery. Baseline person refresh behavior is
unchanged for people without an allocated active research slot.
"""

from __future__ import annotations

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
from tools.person_research_scheduler import build_daily_queue, scheduled_queries_by_slug
from tools.person_video_discovery import discover_person_video_materials
from tools.wechat_channel_card_discovery import discover_embedded_wechat_video_materials

_BASE_ENRICH_CANDIDATE = core.enrich_candidate
_RESEARCH_QUERY_MAP: dict[str, list[str]] = {}
_RESEARCH_QUEUE_STATS: dict[str, int] = {}


def _load_active_research_queries() -> dict[str, list[str]]:
    global _RESEARCH_QUEUE_STATS
    people_payload = load_json(PEOPLE_PATH, {"people": []})
    agenda = build_agenda(
        people_payload,
        load_json(ARTICLES_PATH, {"articles": []}),
    )
    queue = build_daily_queue(agenda, people_payload)
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
    # Existing hand-curated videoQueries retain precedence. The scheduler only fills a
    # research gap when a curator has not already specified a stronger query.
    override["videoQueries"] = existing or [queries[0]]
    return {**candidate, "override": override}


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
    try:
        video_materials.extend(discover_person_video_materials(discovery_candidate))
    except Exception:
        pass
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
    global _RESEARCH_QUERY_MAP
    validate_only = "--validate-only" in sys.argv
    offline = "--offline" in sys.argv
    if not validate_only and not offline:
        _RESEARCH_QUERY_MAP = _load_active_research_queries()
        print(
            "Daily person research queue prepared: "
            f"{_RESEARCH_QUEUE_STATS.get('people', 0)} people / "
            f"{_RESEARCH_QUEUE_STATS.get('tasks', 0)} tasks / "
            f"{_RESEARCH_QUEUE_STATS.get('queries', 0)} active query slots."
        )
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
