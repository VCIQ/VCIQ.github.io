#!/usr/bin/env python3
"""Run person profile refresh with bounded active research outcome memory.

The daily scheduler allocates task-directed query slots. Only those scheduled attempts are
recorded in the outcome-memory ledger. Candidate discovery never changes supported state;
it only records research yield for future cooldown/retry and strategy decisions.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import refresh_people_profiles as core
from tools.person_research_agent import (
    ARTICLES_PATH,
    OUTPUT_PATH as AGENDA_OUTPUT_PATH,
    PEOPLE_PATH,
    atomic_write_json,
    build_agenda,
    load_json,
)
from tools.person_research_outcome_memory import (
    OUTPUT_PATH as OUTCOME_MEMORY_PATH,
    append_attempt,
    load_memory,
    source_host,
    write_memory,
)
from tools.person_research_scheduler import (
    OUTPUT_PATH as QUEUE_OUTPUT_PATH,
    build_daily_queue,
    scheduled_attempts_by_slug,
)
from tools.person_research_strategy_memory import classify_source_type
from tools.person_video_discovery import discover_person_video_materials
from tools.wechat_channel_card_discovery import discover_embedded_wechat_video_materials

_BASE_COLLECT_CANDIDATES = core.collect_candidates
_BASE_ENRICH_CANDIDATE = core.enrich_candidate
_RESEARCH_ATTEMPT_MAP: dict[str, dict[str, str]] = {}
_RESEARCH_QUEUE_STATS: dict[str, int] = {}
_RESEARCH_DATE = ""
_OUTCOME_MEMORY: dict[str, Any] = {}


def _has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def _has_latin(value: str) -> bool:
    return bool(re.search(r"[A-Za-z\u00c0-\u024f]", value))


def parse_tracking_identity(raw: str) -> tuple[str, str, str]:
    """Return canonical display name, English name and handle from a tracking seed.

    Legacy tracking configuration contains a few bilingual labels with a missing
    closing parenthesis. Treat a parenthetical as an identity split only when one
    side is CJK and the other is Latin, so role/status parentheticals remain intact.
    """
    label, handle = core.parse_tracking_label(str(raw or ""))
    match = re.match(r"^(.+?)\s*[（(]\s*([^()（）]+?)\s*[)）]?\s*$", label)
    if not match:
        english_name = label if _has_latin(label) and not _has_cjk(label) else ""
        return label.strip(), english_name.strip(), handle
    left = match.group(1).strip()
    right = match.group(2).strip()
    if _has_cjk(left) and _has_latin(right) and not _has_cjk(right):
        return left, right, handle
    if _has_latin(left) and not _has_cjk(left) and _has_cjk(right):
        return right, left, handle
    english_name = label if _has_latin(label) and not _has_cjk(label) else ""
    return label.strip(), english_name.strip(), handle


def collect_candidates(
    tracking: dict[str, Any], overrides: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Collect tracked people with canonical bilingual identities and stable slugs."""
    explicit_orgs = {core.normalize(value) for value in overrides.get("organizationAccounts") or []}
    override_index: dict[str, dict[str, Any]] = {}
    for item in overrides.get("people") or []:
        for alias in core.unique([
            item.get("canonicalName", ""),
            item.get("englishName", ""),
            *(item.get("aliases") or []),
        ]):
            override_index[core.normalize(alias)] = item

    grouped: dict[str, dict[str, Any]] = {}
    excluded: list[str] = []
    for track in tracking.get("tracks") or []:
        if track.get("enabled") is False:
            continue
        sector = str(track.get("name") or track.get("slug") or "未分类")
        for raw in track.get("people") or []:
            raw_text = str(raw)
            name, parsed_english_name, handle = parse_tracking_identity(raw_text)
            override = (
                override_index.get(core.normalize(name))
                or override_index.get(core.normalize(parsed_english_name))
                or override_index.get(core.normalize(raw_text))
            )
            if core.is_organization_account(raw_text, name, handle, explicit_orgs):
                excluded.append(raw_text)
                continue
            canonical = str((override or {}).get("canonicalName") or name).strip()
            english_name = str(
                (override or {}).get("englishName")
                or parsed_english_name
                or (canonical if _has_latin(canonical) and not _has_cjk(canonical) else "")
            ).strip()
            if not canonical:
                continue
            # Preserve existing public URLs: bilingual seeds historically derived
            # ASCII slugs from the English fragment even when the display name is CJK.
            slug = str(
                (override or {}).get("slug")
                or core.fallback_slug(canonical, handle or english_name)
            )
            entry = grouped.setdefault(slug, {
                "slug": slug,
                "name": canonical,
                "englishName": english_name or canonical,
                "aliases": [],
                "handles": [],
                "sectors": [],
                "override": override or {},
            })
            entry["aliases"] = core.unique([
                *entry["aliases"],
                name,
                parsed_english_name,
                canonical,
                english_name,
                str((override or {}).get("englishName") or ""),
                *((override or {}).get("aliases") or []),
            ])
            entry["handles"] = core.unique([
                *entry["handles"],
                handle,
                *((override or {}).get("handles") or []),
            ])
            entry["sectors"] = core.unique([*entry["sectors"], sector])
    return sorted(
        grouped.values(), key=lambda item: (item["sectors"][0], item["englishName"])
    ), core.unique(excluded)


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


def publish_research_plan(
    *,
    people_path: Path = PEOPLE_PATH,
    articles_path: Path = ARTICLES_PATH,
    agenda_path: Path = AGENDA_OUTPUT_PATH,
    queue_path: Path = QUEUE_OUTPUT_PATH,
    outcome_memory: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist the agenda and next queue from the same refreshed snapshot."""
    people_payload = load_json(people_path, {"people": []})
    agenda = build_agenda(
        people_payload,
        load_json(articles_path, {"articles": []}),
    )
    queue = build_daily_queue(
        agenda,
        people_payload,
        outcome_memory if outcome_memory is not None else load_memory(OUTCOME_MEMORY_PATH),
    )
    atomic_write_json(agenda_path, agenda)
    atomic_write_json(queue_path, queue)
    return agenda, queue


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


def _record_research_attempt(
    slug: str,
    materials: list[dict[str, str]],
    had_error: bool,
    duration_ms: int,
) -> None:
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
        "durationMs": max(0, int(duration_ms)),
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
    query_started = time.perf_counter()
    try:
        query_materials.extend(discover_person_video_materials(discovery_candidate))
    except Exception:
        query_had_error = True
    query_duration_ms = round((time.perf_counter() - query_started) * 1000)
    if articles:
        try:
            embedded_materials.extend(discover_embedded_wechat_video_materials(discovery_candidate, articles))
        except Exception:
            pass
    query_materials = core.dedupe_materials(query_materials)
    embedded_materials = core.dedupe_materials(embedded_materials)
    _record_research_attempt(slug, query_materials, query_had_error, query_duration_ms)
    return merge_video_materials(profile, core.dedupe_materials([*query_materials, *embedded_materials]))


core.collect_candidates = collect_candidates
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
    if active and result == 0:
        write_memory(_OUTCOME_MEMORY, OUTCOME_MEMORY_PATH)
        agenda, queue = publish_research_plan(outcome_memory=_OUTCOME_MEMORY)
        print(
            "Person research plan written: "
            f"{agenda.get('taskCount', 0)} agenda tasks / "
            f"{queue.get('selectedTaskCount', 0)} queued tasks / "
            f"{len(_OUTCOME_MEMORY.get('attempts') or [])} recorded attempts."
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
