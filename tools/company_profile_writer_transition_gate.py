"""Pure pre-PR reconciliation of an event-driven company profile refresh.

This only checks public in-memory JSON objects. It never loads production
files, contacts GitHub, starts a collector, updates queues or creates PRs.
The caller must preserve the *pre-crawl* selection snapshot separately:
after --mark-processed, selectedSlugs can already have become empty.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import re

RETENTION_DAYS = 90
MAX_SELECTED = 10
MAX_FINGERPRINTS = 2000
MAX_COMPANIES = 10000
MAX_RUN_DURATION = timedelta(minutes=90)
QUEUE_KEYS = frozenset({
    "schemaVersion", "generatedAt", "lookbackDays", "selectionLimit",
    "pendingCount", "selectedCount", "selectedSlugs", "lastProcessedAt",
    "entries", "processedEvents",
})
PROFILE_METADATA = frozenset({"generatedAt", "sourceStatus", "qualityGate"})


class TransitionError(ValueError):
    """Error strings are fixed codes; do not echo public articles or profiles."""


def _stamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 60:
        raise TransitionError("WRITER_TRANSITION_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise TransitionError("WRITER_TRANSITION_TIME_INVALID") from None
    if parsed.tzinfo is None:
        raise TransitionError("WRITER_TRANSITION_TIME_INVALID")
    return parsed.astimezone(UTC)


def _queue(value: object) -> dict[str, Any]:
    if (not isinstance(value, dict) or set(value) != QUEUE_KEYS
        or type(value.get("schemaVersion")) is not int
        or value["schemaVersion"] != 1
        or not isinstance(value.get("entries"), list)
        or len(value["entries"]) > 100
        or not isinstance(value.get("processedEvents"), dict)
        or len(value["processedEvents"]) > MAX_FINGERPRINTS
        or not isinstance(value.get("selectedSlugs"), list)):
        raise TransitionError("WRITER_TRANSITION_QUEUE_INVALID")
    _stamp(value["generatedAt"])
    return value


def _profiles(value: object) -> dict[str, Any]:
    if (not isinstance(value, dict) or value.get("schemaVersion") != 2
        or type(value.get("schemaVersion")) is not int
        or not isinstance(value.get("companies"), dict)
        or len(value["companies"]) > MAX_COMPANIES):
        raise TransitionError("WRITER_TRANSITION_PROFILES_INVALID")
    return value


def _slugs(values: object, *, limit: int = MAX_SELECTED) -> list[str]:
    if (not isinstance(values, list) or len(values) > limit
        or any(not isinstance(s, str) or not s or len(s) > 100
               or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", s) for s in values)
        or len(set(values)) != len(values)):
        raise TransitionError("WRITER_TRANSITION_SLUGS_INVALID")
    return values


def _selection(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Check the selection invariant of build_queue, including pending rows."""
    selected = _slugs(payload["selectedSlugs"])
    limit = payload.get("selectionLimit")
    count = payload.get("selectedCount")
    pending = payload.get("pendingCount")
    if (type(limit) is not int or not 0 <= limit <= MAX_SELECTED
        or type(count) is not int or count != len(selected)
        or type(pending) is not int or pending < len(payload["entries"])
        or len(payload["entries"]) != min(pending, 100)
        or count != min(limit, pending)):
        raise TransitionError("WRITER_TRANSITION_SELECTION_INVALID")
    entries = {}
    order = []
    for item in payload["entries"]:
        if not isinstance(item, dict):
            raise TransitionError("WRITER_TRANSITION_SELECTION_INVALID")
        slug = item.get("companySlug")
        if not isinstance(slug, str) or slug in entries:
            raise TransitionError("WRITER_TRANSITION_SELECTION_INVALID")
        _slugs([slug], limit=1)
        priority = item.get("priority")
        newest = item.get("newestPublishedAt")
        if (type(priority) is not int or not 1 <= priority <= 180
            or not isinstance(newest, str) or not newest or len(newest) > 60):
            raise TransitionError("WRITER_TRANSITION_SELECTION_INVALID")
        entries[slug] = item
        order.append(slug)
    canonical_order = sorted(order, key=lambda slug: (
        -entries[slug]["priority"], entries[slug]["newestPublishedAt"], slug,
    ))
    if order != canonical_order:
        raise TransitionError("WRITER_TRANSITION_SELECTION_INVALID")
    if selected != order[:len(selected)]:
        raise TransitionError("WRITER_TRANSITION_SELECTION_INVALID")
    for idx, slug in enumerate(order):
        expected_status = "selected" if idx < len(selected) else "pending"
        if entries[slug].get("status") != expected_status:
            raise TransitionError("WRITER_TRANSITION_SELECTION_INVALID")
    return selected, entries


def check_transition(
    base_queue: object,
    pre_crawl_selection: object,
    candidate_queue: object,
    base_profiles: object,
    candidate_profiles: object,
    *,
    run_started_at: str | None = None,
    run_completed_at: str | None = None,
    coverage_slugs: list[str] | None = None,
) -> dict[str, int | bool]:
    """Verify selection intent, processed history and bounded company changes.

    run_* timestamps must come from a separately preserved execution record,
    not the article snapshot: generatedAt represents the source snapshot date
    and may be older than the actual mark-processed time.
    The caller must separately check the *actual* HEAD SHA of main against
    the candidate's base SHA. A successful result never authorizes a merge.
    """
    if run_started_at is None or run_completed_at is None:
        raise TransitionError("WRITER_TRANSITION_RUN_WINDOW_REQUIRED")
    started = _stamp(run_started_at)
    finished = _stamp(run_completed_at)
    if finished < started or finished - started > MAX_RUN_DURATION:
        raise TransitionError("WRITER_TRANSITION_RUN_WINDOW_INVALID")
    before = _queue(base_queue)
    intent = _queue(pre_crawl_selection)
    after = _queue(candidate_queue)
    profile_before = _profiles(base_profiles)
    profile_after = _profiles(candidate_profiles)

    _selection(before)
    selected, entries = _selection(intent)
    _selection(after)
    additional = _slugs([] if coverage_slugs is None else coverage_slugs, limit=100)
    if not (_stamp(before["generatedAt"]) <= _stamp(intent["generatedAt"])
            <= _stamp(after["generatedAt"])):
        raise TransitionError("WRITER_TRANSITION_CHRONOLOGY_INVALID")
    selected_set = set(selected)

    expected = {}
    for slug in selected:
        row = entries[slug]
        fingerprints = row.get("eventFingerprints")
        if (row.get("status") != "selected"
            or not isinstance(fingerprints, list)
            or not fingerprints or len(fingerprints) > MAX_FINGERPRINTS):
            raise TransitionError("WRITER_TRANSITION_INTENT_INVALID")
        for key in fingerprints:
            if (not isinstance(key, str) or len(key) != len(slug) + 41
                or not key.startswith(slug + ":")
                or not all(ch in "0123456789abcdef" for ch in key[len(slug) + 1:])
                or key in expected):
                raise TransitionError("WRITER_TRANSITION_INTENT_INVALID")
            expected[key] = slug

    history = before["processedEvents"]
    after_history = after["processedEvents"]
    intent_history = intent["processedEvents"]
    if not all(isinstance(r, dict) for r in history.values()):
        raise TransitionError("WRITER_TRANSITION_HISTORY_INVALID")
    # Selection must not mark an event before the crawl succeeds.
    if set(intent_history) - set(history):
        raise TransitionError("WRITER_TRANSITION_INTENT_INVALID")
    for key, value in intent_history.items():
        if key not in history or value != history[key]:
            raise TransitionError("WRITER_TRANSITION_INTENT_INVALID")
    if set(expected).intersection(history):
        raise TransitionError("WRITER_TRANSITION_DUPLICATE_EVENT")

    new = set(after_history) - set(history)
    if new != set(expected):
        raise TransitionError("WRITER_TRANSITION_PROCESSED_MISMATCH")
    # Retention uses the actual processing clock, not articles.generatedAt.
    cutoff = finished - timedelta(days=RETENTION_DAYS)
    for key, value in history.items():
        if key in after_history:
            if value != after_history[key]:
                raise TransitionError("WRITER_TRANSITION_HISTORY_REWRITTEN")
        elif _stamp(value.get("processedAt")) >= cutoff:
            raise TransitionError("WRITER_TRANSITION_RECENT_HISTORY_LOST")
    for key, slug in expected.items():
        value = after_history.get(key)
        if (not isinstance(value, dict)
            or value.get("companySlug") != slug
            or not isinstance(value.get("articleId"), str)):
            raise TransitionError("WRITER_TRANSITION_NEW_EVENT_INVALID")
        processed_at = _stamp(value.get("processedAt"))
        if not started <= processed_at <= finished:
            raise TransitionError("WRITER_TRANSITION_NEW_EVENT_INVALID")

    old_companies = profile_before["companies"]
    new_companies = profile_after["companies"]
    if set(old_companies) - set(new_companies):
        raise TransitionError("WRITER_TRANSITION_COMPANY_DELETED")
    changed = {slug for slug in set(old_companies) | set(new_companies)
               if old_companies.get(slug) != new_companies.get(slug)}
    if not changed.issubset(selected_set | set(additional)):
        raise TransitionError("WRITER_TRANSITION_UNRELATED_COMPANY_CHANGED")
    if set(profile_before) != set(profile_after):
        raise TransitionError("WRITER_TRANSITION_PROFILE_SHAPE_CHANGED")
    if any(profile_before[key] != profile_after[key]
           for key in profile_before if key not in PROFILE_METADATA | {"companies"}):
        raise TransitionError("WRITER_TRANSITION_PROFILE_METADATA_UNEXPECTED")
    return {
        "ok": True,
        "selectedCompanies": len(selected),
        "coverageCompanies": len(additional),
        "newProcessedEvents": len(new),
        "changedCompanies": len(changed),
        "mergeAuthorized": False,
        "publicationAuthorized": False,
    }
