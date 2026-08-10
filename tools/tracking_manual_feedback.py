#!/usr/bin/env python3
"""Compile owner-entered tracking history into safe automatic-discovery signals.

The public site no longer contains a repository writer.  Historical browser
captures and the authenticated ``tracking_intents.json`` graph are nevertheless
valuable preference evidence.  This module turns that evidence into:

* pinned seed terms that automatic discovery should search first;
* held/rejected identities that automation must not silently activate;
* preferred source hosts and cross-track affinities for recommendations.

The compiler deliberately ignores composite or malformed historical values.  A
manual record is evidence, not permission to preserve old data pollution.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"
INTENTS_PATH = ROOT / "config" / "tracking_intents.json"
RUNTIME_CONFIG_PATH = ROOT / "config" / "user_tracking.json"

LEGACY_KIND_TO_FIELD = {
    "topic": "keywords",
    "company": "sampleCompanies",
    "person": "people",
}
ROLE_TO_FIELD = {
    "keyword": "keywords",
    "actor": "actors",
    "source-anchor": "sources",
}
LEGAL_COMPANY_SUFFIX_RE = re.compile(
    r"^[^,]+,\s*(?:Inc\.?|LLC|Ltd\.?|L\.P\.?|Corp\.?)$",
    re.IGNORECASE,
)


def _clean(value: Any, limit: int = 300) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", str(value or "")),
    ).strip()[:limit]


def normalize_identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", _clean(value).casefold())


def signal_identity(value: Any, field: str) -> str:
    if field == "keywords":
        # These marks distinguish real technologies: C, C++, C#, .NET and
        # A/B are not interchangeable identities.
        return re.sub(
            r"[^a-z0-9\u3400-\u9fff+#./]+",
            "",
            _clean(value).casefold(),
        )
    if field == "sources":
        return _clean(value, 1200).casefold().rstrip("/")
    return normalize_identity(value)


def source_host(value: Any) -> str:
    raw = _clean(value, 1200)
    if not raw:
        return ""
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    except ValueError:
        return ""
    return (parsed.hostname or "").casefold().removeprefix("www.")


def is_single_manual_value(value: Any) -> bool:
    """Reject list-shaped and syntactically broken historical identities.

    Commas remain valid only for common legal-company suffixes.  ``A/B Test
    Labs`` remains valid, while the old ``腾讯 / 元宝`` alias bundle does not.
    """

    raw = unicodedata.normalize("NFKC", str(value or ""))
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        return False
    text = _clean(raw, 200)
    if not text or any(marker in text for marker in ("、", "，", ";", "；")):
        return False
    if text.count("(") != text.count(")") or text.count("（") != text.count("）"):
        return False
    if re.search(r"\s/\s", text):
        return False
    if "," in text and not LEGAL_COMPANY_SUFFIX_RE.fullmatch(text):
        return False
    return True


def _empty_track() -> dict[str, Any]:
    return {
        "approved": {
            "keywords": [],
            "people": [],
            "sampleCompanies": [],
            "sources": [],
        },
        "held": {
            "keywords": [],
            "people": [],
            "sampleCompanies": [],
            "sources": [],
        },
        "seedTerms": [],
        "sourceHosts": [],
        "relatedTracks": [],
    }


def build_manual_feedback(
    capture_payload: Any,
    intents_payload: Any,
    runtime_payload: Any | None = None,
) -> dict[str, Any]:
    approved: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    held: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    source_hosts: dict[str, Counter[str]] = defaultdict(Counter)
    related: dict[str, Counter[str]] = defaultdict(Counter)
    explicit_related: dict[str, Counter[str]] = defaultdict(Counter)
    legacy_relations: list[tuple[str, str, str, str]] = []
    reasons: Counter[str] = Counter()
    processed = 0
    history_records = 0
    applied_count = 0
    held_count = 0
    # v2 intent edges are the current decision.  Historical captures remain
    # useful frequency evidence, but cannot revive an edge that an owner has
    # since put on hold/rejected (or suppress one the owner pinned active).
    authoritative: dict[tuple[str, str, str], str] = {}
    runtime_present = isinstance(runtime_payload, dict)
    runtime_active: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    track_names: dict[str, str] = {}
    if runtime_present:
        for track in runtime_payload.get("tracks", []):
            if not isinstance(track, dict):
                continue
            slug = _clean(track.get("slug"), 120)
            if not slug:
                continue
            track_names[_clean(track.get("name"), 160)] = slug
            for field in ("keywords", "people", "sampleCompanies"):
                values = track.get(field, []) if isinstance(track.get(field), list) else []
                for value in values:
                    identity = signal_identity(value, field)
                    if identity:
                        runtime_active[slug][field].add(identity)
                    if field == "people":
                        without_handle = re.sub(r"\s+@\S+$", "", _clean(value, 200))
                        if normalize_identity(without_handle):
                            runtime_active[slug][field].add(normalize_identity(without_handle))
        for source in runtime_payload.get("sources", []):
            if not isinstance(source, dict):
                continue
            slug = track_names.get(_clean(source.get("sector"), 160), "")
            identity = normalize_identity(source.get("url"))
            if slug and identity:
                runtime_active[slug]["sources"].add(identity)

    def remember(
        *,
        slug: str,
        field: str,
        value: str,
        state: str,
        at: str,
        reason_values: list[str],
        host: str = "",
        pinned: bool = False,
    ) -> None:
        nonlocal processed
        slug = _clean(slug, 120)
        value = _clean(value, 200)
        if not slug or not value:
            return
        processed += 1
        target = approved if state == "active" else held
        identity = signal_identity(value, field)
        if not identity:
            return
        row = target[slug][field].setdefault(
            identity,
            {
                "value": value,
                "count": 0,
                "lastSeenAt": "",
                "reasonCount": 0,
                "pinned": False,
                "hosts": Counter(),
            },
        )
        row["count"] += 1
        row["lastSeenAt"] = max(str(row["lastSeenAt"]), _clean(at, 80))
        row["reasonCount"] += len([reason for reason in reason_values if _clean(reason, 80)])
        row["pinned"] = bool(row["pinned"] or pinned)
        if host:
            row["hosts"][host] += 1

    capture_records = (
        capture_payload.get("records", []) if isinstance(capture_payload, dict) else []
    )
    raw_history_records = sum(
        1 for record in capture_records if isinstance(record, dict)
    ) if isinstance(capture_records, list) else 0
    for record in capture_records if isinstance(capture_records, list) else []:
        # Count accepted historical records once even when the owner associated
        # one action with several tracks.
        if not isinstance(record, dict):
            continue
        field = LEGACY_KIND_TO_FIELD.get(_clean(record.get("entityType"), 30))
        value = _clean(record.get("canonicalName"), 200)
        if not field or not is_single_manual_value(value):
            continue
        history_records += 1
        status = _clean(record.get("status"), 30)
        requested_state = "active" if status == "applied" else "held"
        slugs = [
            _clean(slug, 120)
            for slug in record.get("trackSlugs", [])
            if _clean(slug, 120)
        ] if isinstance(record.get("trackSlugs"), list) else []
        source = record.get("source") if isinstance(record.get("source"), dict) else {}
        host = source_host(source.get("url"))
        record_reasons = (
            [_clean(reason, 80) for reason in record.get("reasons", [])]
            if isinstance(record.get("reasons"), list)
            else []
        )
        for reason in record_reasons:
            if reason:
                reasons[reason] += 1
        states: dict[str, str] = {}
        for slug in slugs:
            # An old "applied" record that was subsequently removed from the
            # runtime config is negative feedback, not an evergreen seed.  The
            # old admin UI produced several wrong-track and malformed entries
            # that owners later cleaned up.
            state = requested_state
            if (
                runtime_present
                and requested_state == "active"
                and signal_identity(value, field) not in runtime_active[slug][field]
            ):
                state = "held"
            states[slug] = state
        for slug in slugs:
            state = states[slug]
            remember(
                slug=slug,
                field=field,
                value=value,
                state=state,
                at=_clean(record.get("capturedAt"), 80),
                reason_values=record_reasons,
                host=host,
            )
            if state == "active":
                for other in slugs:
                    if other != slug and states.get(other) == "active":
                        legacy_relations.append(
                            (slug, other, field, signal_identity(value, field))
                        )

    entities = {
        _clean(row.get("id"), 240): row
        for row in (
            intents_payload.get("entities", []) if isinstance(intents_payload, dict) else []
        )
        if isinstance(row, dict) and _clean(row.get("id"), 240)
    }
    memberships = (
        intents_payload.get("memberships", []) if isinstance(intents_payload, dict) else []
    )
    for membership in memberships if isinstance(memberships, list) else []:
        if not isinstance(membership, dict):
            continue
        track_id = _clean(membership.get("trackId"), 160)
        slug = track_id.removeprefix("track:")
        entity = entities.get(_clean(membership.get("entityId"), 240))
        if not slug or not isinstance(entity, dict):
            continue
        role = _clean(membership.get("role"), 40)
        field = ROLE_TO_FIELD.get(role)
        kind = _clean(entity.get("kind"), 40)
        if field == "actors":
            field = "people" if kind == "person" else "sampleCompanies"
        if not field:
            continue
        value = _clean(
            entity.get("url") if field == "sources" else entity.get("name"),
            500,
        )
        if field != "sources" and not is_single_manual_value(value):
            continue
        origins = membership.get("origins", []) if isinstance(membership.get("origins"), list) else []
        origin_reasons: list[str] = []
        last_seen = ""
        evidence_host = ""
        for origin in origins:
            if not isinstance(origin, dict):
                continue
            last_seen = max(last_seen, _clean(origin.get("at"), 80))
            if not evidence_host:
                evidence_host = source_host(origin.get("evidenceUrl"))
            if isinstance(origin.get("reasons"), list):
                cleaned_reasons = [_clean(item, 80) for item in origin["reasons"]]
                origin_reasons.extend(cleaned_reasons)
                for reason in cleaned_reasons:
                    if reason:
                        reasons[reason] += 1
        state = "active" if _clean(membership.get("state"), 30) == "active" else "held"
        authoritative[(slug, field, signal_identity(value, field))] = state
        remember(
            slug=slug,
            field=field,
            value=value,
            state=state,
            at=last_seen or _clean(entity.get("createdAt"), 80),
            reason_values=origin_reasons,
            host=source_host(entity.get("url")) or evidence_host,
            pinned=membership.get("pinned", True) is True,
        )
        for keyword in entity.get("keywords", []) if isinstance(entity.get("keywords"), list) else []:
            keyword_value = _clean(keyword, 120)
            if is_single_manual_value(keyword_value):
                authoritative[(slug, "keywords", signal_identity(keyword_value, "keywords"))] = state
                remember(
                    slug=slug,
                    field="keywords",
                    value=keyword_value,
                    state=state,
                    at=last_seen or _clean(entity.get("createdAt"), 80),
                    reason_values=origin_reasons,
                    host=source_host(entity.get("url")) or evidence_host,
                    pinned=membership.get("pinned", True) is True,
                )
    # Track intents may have seed keywords without a membership edge.
    for entity in entities.values():
        if _clean(entity.get("kind"), 40) != "track":
            continue
        slug = _clean(entity.get("trackSlug"), 120)
        if not slug:
            continue
        for keyword in entity.get("keywords", []) if isinstance(entity.get("keywords"), list) else []:
            keyword_value = _clean(keyword, 120)
            if is_single_manual_value(keyword_value):
                state = "active" if _clean(entity.get("state"), 30) == "active" else "held"
                authoritative[(slug, "keywords", signal_identity(keyword_value, "keywords"))] = state
                remember(
                    slug=slug,
                    field="keywords",
                    value=keyword_value,
                    state=state,
                    at=_clean(entity.get("createdAt"), 80),
                    reason_values=[],
                    pinned=entity.get("pinned", True) is True,
                )
        if _clean(entity.get("state"), 30) == "active":
            related_ids = entity.get("relatedTrackIds", []) if isinstance(entity.get("relatedTrackIds"), list) else []
            for track_id in related_ids:
                other = _clean(track_id, 160).removeprefix("track:")
                if other and other != slug:
                    # A pinned v2 relation is an explicit current decision,
                    # stronger than one legacy multi-track capture.
                    explicit_related[slug][other] += 2
                    explicit_related[other][slug] += 2

    for (slug, field, identity), state in authoritative.items():
        opposite = held if state == "active" else approved
        opposite.get(slug, {}).get(field, {}).pop(identity, None)

    # Recompute positive aggregates from the final decision state.  This is
    # crucial when a v2 rejection supersedes an older applied browser capture:
    # the identity moves to held and must stop contributing host affinity,
    # cross-track relations and active-signal totals immediately.
    applied_count = 0
    held_count = 0
    for state_values, is_active in ((approved, True), (held, False)):
        for slug, fields in state_values.items():
            for rows in fields.values():
                for item in rows.values():
                    count = int(item.get("count") or 0)
                    if is_active:
                        applied_count += count
                        hosts = item.get("hosts")
                        if isinstance(hosts, Counter):
                            source_hosts[slug].update(hosts)
                    else:
                        held_count += count
    for slug, other, field, identity in legacy_relations:
        if identity in approved[slug][field] and identity in approved[other][field]:
            related[slug][other] += 1
    for slug, rows in explicit_related.items():
        related[slug].update(rows)

    track_slugs = set(approved) | set(held) | set(source_hosts) | set(related)
    tracks: dict[str, Any] = {}
    for slug in sorted(track_slugs):
        row = _empty_track()
        for state_name, state_values in (("approved", approved), ("held", held)):
            for field in row[state_name]:
                values = list(state_values[slug][field].values())
                values.sort(
                    key=lambda item: (
                        int(item["count"]),
                        int(item["reasonCount"]),
                        str(item["lastSeenAt"]),
                    ),
                    reverse=True,
                )
                row[state_name][field] = [item["value"] for item in values]

        seeds: list[dict[str, Any]] = []
        for field, kind_weight in (
            ("keywords", 1.25),
            ("sampleCompanies", 1.0),
            ("people", 1.0),
        ):
            for item in approved[slug][field].values():
                score = (
                    float(item["count"]) * kind_weight
                    + min(1.5, float(item["reasonCount"]) * 0.15)
                )
                seeds.append(
                    {
                        "value": item["value"],
                        "kind": field,
                        "score": round(score, 3),
                        "lastSeenAt": item["lastSeenAt"],
                        "pinned": bool(item["pinned"]),
                    }
                )
        seeds.sort(
            key=lambda item: (float(item["score"]), str(item["lastSeenAt"])),
            reverse=True,
        )
        row["seedTerms"] = seeds
        row["sourceHosts"] = [
            {"host": host, "count": count}
            for host, count in source_hosts[slug].most_common()
        ]
        row["relatedTracks"] = [
            {"slug": other, "count": count}
            for other, count in related[slug].most_common()
        ]
        tracks[slug] = row

    return {
        "schemaVersion": 1,
        "rawHistoryRecords": raw_history_records,
        "historyRecords": history_records,
        "ignoredHistoryRecords": max(0, raw_history_records - history_records),
        "processedSignals": processed,
        "appliedSignals": applied_count,
        "heldSignals": held_count,
        "reasonCounts": dict(reasons.most_common()),
        "tracks": tracks,
    }


def load_manual_feedback(
    capture_path: Path = CAPTURE_INBOX_PATH,
    intents_path: Path = INTENTS_PATH,
    runtime_path: Path = RUNTIME_CONFIG_PATH,
) -> dict[str, Any]:
    def load(path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return fallback

    return build_manual_feedback(
        load(capture_path, {"records": []}),
        load(intents_path, {"entities": [], "memberships": []}),
        load(runtime_path, None),
    )


def manual_seed_terms(profile: dict[str, Any], slug: str, limit: int = 6) -> list[str]:
    track = profile.get("tracks", {}).get(slug, {}) if isinstance(profile, dict) else {}
    rows = track.get("seedTerms", []) if isinstance(track, dict) else []
    return [
        _clean(row.get("value"), 160)
        for row in rows
        if (
            isinstance(row, dict)
            and _clean(row.get("value"), 160)
            # Legacy browser captures were noisy.  Only repeated/strongly
            # reasoned surviving history (score >= 2) gets query budget;
            # authenticated v2 owner pins qualify immediately.
            and (row.get("pinned") is True or float(row.get("score") or 0) >= 2.0)
        )
    ][: max(0, limit)]


def manual_held_values(profile: dict[str, Any], slug: str) -> set[str]:
    track = profile.get("tracks", {}).get(slug, {}) if isinstance(profile, dict) else {}
    held = track.get("held", {}) if isinstance(track, dict) else {}
    values: set[str] = set()
    if isinstance(held, dict):
        for field, rows in held.items():
            if isinstance(rows, list):
                values.update(
                    signal_identity(value, field)
                    for value in rows
                    if signal_identity(value, field)
                )
    return values


def manual_held_source_hosts(profile: dict[str, Any], slug: str) -> set[str]:
    track = profile.get("tracks", {}).get(slug, {}) if isinstance(profile, dict) else {}
    held = track.get("held", {}) if isinstance(track, dict) else {}
    rows = held.get("sources", []) if isinstance(held, dict) else []
    return {
        source_host(value)
        for value in rows
        if source_host(value)
    } if isinstance(rows, list) else set()


def manual_source_affinity(profile: dict[str, Any], slug: str, host: str) -> int:
    track = profile.get("tracks", {}).get(slug, {}) if isinstance(profile, dict) else {}
    rows = track.get("sourceHosts", []) if isinstance(track, dict) else []
    normalized_host = source_host(host)
    for row in rows:
        if isinstance(row, dict) and source_host(row.get("host")) == normalized_host:
            return int(row.get("count") or 0)
    return 0


if __name__ == "__main__":
    print(json.dumps(load_manual_feedback(), ensure_ascii=False, indent=2))
