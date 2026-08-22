#!/usr/bin/env python3
"""Run the person profile refresh with active, public video-platform enrichment.

Before a normal refresh, the deterministic person research planner reads the previous
profile snapshot and produces bounded evidence-search questions. The highest-priority
video-compatible query is then fed into the existing identity-gated video discovery.
After the refreshed people snapshot is written, the agenda is rebuilt so open/closed
research gaps reflect the new evidence.
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
    research_queries_by_slug,
    write_agenda,
)
from tools.person_video_discovery import discover_person_video_materials
from tools.wechat_channel_card_discovery import discover_embedded_wechat_video_materials

_BASE_ENRICH_CANDIDATE = core.enrich_candidate
_RESEARCH_QUERY_MAP: dict[str, list[str]] = {}


def _load_active_research_queries() -> dict[str, list[str]]:
    agenda = build_agenda(
        load_json(PEOPLE_PATH, {"people": []}),
        load_json(ARTICLES_PATH, {"articles": []}),
    )
    return research_queries_by_slug(agenda)


def _candidate_with_research_query(candidate: dict[str, Any]) -> dict[str, Any]:
    queries = _RESEARCH_QUERY_MAP.get(str(candidate.get("slug") or "")) or []
    if not queries:
        return candidate
    override = dict(candidate.get("override") or {})
    existing = [str(value) for value in override.get("videoQueries") or [] if str(value).strip()]
    # Existing hand-curated videoQueries retain precedence. The active planner fills a
    # gap only when a curator has not already specified a stronger query.
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
    result = core.main()
    if result == 0 and not validate_only:
        agenda = write_agenda()
        print(
            "Rebuilt active person research agenda: "
            f"{agenda['taskCount']} tasks, {agenda['openTaskCount']} still open."
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
