#!/usr/bin/env python3
"""Govern the lifecycle of automatically discovered tracking seeds.

`config/user_tracking.json` deliberately keeps a compact string-list schema used by
runtime crawlers and UI code.  Provenance, confidence and expiry therefore live in
`config/tracking_auto_discovery.json`, which is the audit plane for automatic
additions.  This tool removes known low-signal seeds, expires stale automatic
entries without permanently tombstoning them, and backfills lifecycle metadata.

Owner-deleted or quality-rejected noise remains tombstoned so automatic discovery
cannot silently restore it.  Expired entries are *not* tombstoned: if fresh,
strong evidence appears later, normal discovery may add them again.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
LEDGER_PATH = ROOT / "config" / "tracking_auto_discovery.json"

LOW_SIGNAL_EXACT = {
    "here",
    "能力",
    "the us",
    "公开材料",
    "人物材料",
    "公司动态",
    "商业进展",
    "产品发布",
    "产业投资",
    "全球",
    "中国",
    "亿元",
    "万亿",
    "万亿美元",
    "comment",
    "from",
    "this",
    "call",
    "deployment",
    "results",
    "review",
    "video",
    "features",
    "llc",
    "inc",
}
BLOCKED_PEOPLE = {
    "the washington post @washingtonpost",
    "关注前沿科技",
}
DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AUTOMATIC_PERSON_NOISE_RE = re.compile(
    r"\b(?:class|presiden(?:t)?|governo(?:r)?|government)\b",
    re.IGNORECASE,
)

KIND_TTL_DAYS = {
    "keywords": 90,
    "people": 180,
    "sampleCompanies": 365,
    "sources": 365,
}
VERIFIED_TTL_DAYS = 365


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _load(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(fallback)


def _parse_time(value: Any, fallback: datetime) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _is_low_signal_keyword(value: Any) -> bool:
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    return _normalize(raw) in LOW_SIGNAL_EXACT or bool(DATE_ONLY_RE.fullmatch(raw))


def _is_blocked_person(value: Any) -> bool:
    return _normalize(value) in BLOCKED_PEOPLE


def _is_invalid_automatic_person(value: Any) -> bool:
    """Reject obvious role/page fragments only for audit-ledger automatic people."""
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    return bool(AUTOMATIC_PERSON_NOISE_RE.search(raw))


def _provenance(evidence: set[str]) -> tuple[str, float, int | None]:
    if any(
        marker.startswith("verified-")
        or marker in {
            "investment-institution-directory",
            "shared-directory-reference",
            "verified-company-profile",
            "verified-institution-profile",
            "verified-institution-team-page",
        }
        for marker in evidence
    ):
        return "auto:verified-directory", 0.97, VERIFIED_TTL_DAYS
    if {
        "sample-company-core-team",
        "public-social-identifier",
    } & evidence:
        return "auto:verified-team", 0.94, VERIFIED_TTL_DAYS
    if "wikidata-official-site" in evidence:
        return "auto:official-site", 0.93, VERIFIED_TTL_DAYS
    if "wikidata-social" in evidence:
        return "auto:verified-social", 0.90, VERIFIED_TTL_DAYS
    if any(marker.startswith("corpus-") for marker in evidence) and "news-confirmed" in evidence:
        return "auto:corpus+news", 0.88, None
    if any(marker.startswith("corpus-") for marker in evidence):
        return "auto:corpus", 0.78, None
    if "news-confirmed" in evidence:
        return "auto:news-confirmed", 0.80, None
    if "news-term" in evidence:
        return "auto:news-discovery", 0.68, None
    if evidence & {"baidu-suggest", "google-suggest", "openalex-related"}:
        return "auto:suggestion", 0.64, None
    if "wikipedia-morelike" in evidence:
        return "auto:reference", 0.58, None
    return "auto:unknown", 0.50, None


def _expiry_for(row: dict[str, Any], now: datetime) -> tuple[str, float, str]:
    evidence = {str(item) for item in row.get("evidence", []) if str(item)}
    provenance, confidence, override_days = _provenance(evidence)
    kind = str(row.get("kind") or "")
    ttl_days = override_days or KIND_TTL_DAYS.get(kind, 180)
    added_at = _parse_time(row.get("addedAt"), now)
    return provenance, confidence, _iso(added_at + timedelta(days=ttl_days))


def _config_values(track: dict[str, Any], kind: str, config: dict[str, Any]) -> list[str]:
    if kind == "sources":
        sector = _normalize(track.get("name"))
        return [
            str(source.get("url") or "")
            for source in config.get("sources", [])
            if isinstance(source, dict) and _normalize(source.get("sector")) == sector
        ]
    values = track.get(kind)
    return [str(value) for value in values] if isinstance(values, list) else []


def _remove_config_value(
    config: dict[str, Any], track: dict[str, Any], kind: str, value: str
) -> bool:
    target = _normalize(value)
    if kind == "sources":
        sector = _normalize(track.get("name"))
        before = len(config.get("sources", []))
        config["sources"] = [
            source
            for source in config.get("sources", [])
            if not (
                isinstance(source, dict)
                and _normalize(source.get("sector")) == sector
                and _normalize(source.get("url")) == target
            )
        ]
        return len(config.get("sources", [])) != before
    values = track.get(kind)
    if not isinstance(values, list):
        return False
    next_values = [item for item in values if _normalize(item) != target]
    if len(next_values) == len(values):
        return False
    track[kind] = next_values
    return True


def _removed_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("track") or ""),
        str(row.get("kind") or ""),
        _normalize(row.get("value")),
    )


def _tombstone(
    ledger: dict[str, Any],
    *,
    track: str,
    kind: str,
    value: str,
    reason: str,
    now: datetime,
) -> bool:
    removed = ledger.setdefault("removed", [])
    key = (track, kind, _normalize(value))
    if any(isinstance(row, dict) and _removed_key(row) == key for row in removed):
        return False
    removed.append(
        {
            "track": track,
            "kind": kind,
            "value": value,
            "removedAt": _iso(now),
            "reason": reason,
        }
    )
    return True


def govern(
    config: dict[str, Any],
    ledger: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    tracks = {
        str(track.get("slug") or ""): track
        for track in config.get("tracks", [])
        if isinstance(track, dict) and track.get("slug")
    }
    report: dict[str, Any] = {
        "metadataBackfilled": 0,
        "lowSignalRemoved": [],
        "blockedPeopleRemoved": [],
        "invalidAutomaticPeopleRemoved": [],
        "expiredRemoved": [],
        "tombstonesAdded": 0,
    }

    # Quality tombstones are sticky against stale concurrent writers. They are
    # deliberately narrower than ordinary owner removals: only values previously
    # rejected by seed governance as invalid person identities are force-pruned.
    invalid_person_tombstones: dict[str, set[str]] = {}
    for raw in ledger.get("removed", []):
        if not isinstance(raw, dict):
            continue
        if (
            str(raw.get("kind") or "") != "people"
            or str(raw.get("reason") or "") != "seed-governance-invalid-person"
        ):
            continue
        slug = str(raw.get("track") or "")
        value = _normalize(raw.get("value"))
        if slug and value:
            invalid_person_tombstones.setdefault(slug, set()).add(value)

    # Immediate defensive cleanup also covers values that predate the audit ledger.
    for slug, track in tracks.items():
        for value in list(_config_values(track, "keywords", config)):
            if not _is_low_signal_keyword(value):
                continue
            if _remove_config_value(config, track, "keywords", value):
                report["lowSignalRemoved"].append({"track": slug, "value": value})
            if _tombstone(
                ledger,
                track=slug,
                kind="keywords",
                value=value,
                reason="seed-governance-low-signal",
                now=now,
            ):
                report["tombstonesAdded"] += 1
        for value in list(_config_values(track, "people", config)):
            blocked_person = _is_blocked_person(value)
            invalid_tombstone = _normalize(value) in invalid_person_tombstones.get(slug, set())
            if not blocked_person and not invalid_tombstone:
                continue
            if _remove_config_value(config, track, "people", value):
                target = (
                    report["blockedPeopleRemoved"]
                    if blocked_person
                    else report["invalidAutomaticPeopleRemoved"]
                )
                target.append({"track": slug, "value": value})
            if blocked_person and _tombstone(
                ledger,
                track=slug,
                kind="people",
                value=value,
                reason="seed-governance-invalid-person",
                now=now,
            ):
                report["tombstonesAdded"] += 1

    next_added: list[dict[str, Any]] = []
    for raw in ledger.get("added", []):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        slug = str(row.get("track") or "")
        kind = str(row.get("kind") or "")
        value = str(row.get("value") or "")
        track = tracks.get(slug)

        low_signal = kind == "keywords" and _is_low_signal_keyword(value)
        blocked_person = kind == "people" and _is_blocked_person(value)
        invalid_automatic_person = kind == "people" and _is_invalid_automatic_person(value)
        if low_signal or blocked_person or invalid_automatic_person:
            if track:
                removed = _remove_config_value(config, track, kind, value)
                if removed and invalid_automatic_person and not blocked_person:
                    report["invalidAutomaticPeopleRemoved"].append({"track": slug, "value": value})
            if _tombstone(
                ledger,
                track=slug,
                kind=kind,
                value=value,
                reason=(
                    "seed-governance-low-signal"
                    if low_signal
                    else "seed-governance-invalid-person"
                ),
                now=now,
            ):
                report["tombstonesAdded"] += 1
            continue

        provenance, confidence, expires_at = _expiry_for(row, now)
        metadata_changed = False
        if row.get("termProvenance") != provenance:
            row["termProvenance"] = provenance
            metadata_changed = True
        if float(row.get("confidence", -1) or -1) != confidence:
            row["confidence"] = confidence
            metadata_changed = True
        if row.get("expiresAt") != expires_at:
            row["expiresAt"] = expires_at
            metadata_changed = True
        if metadata_changed:
            report["metadataBackfilled"] += 1

        expires = _parse_time(expires_at, now)
        if expires <= now:
            if track and _remove_config_value(config, track, kind, value):
                report["expiredRemoved"].append(
                    {"track": slug, "kind": kind, "value": value}
                )
            # Expiry is intentionally not a tombstone. Fresh evidence may revive it.
            continue
        next_added.append(row)

    ledger["added"] = next_added
    if any(
        report[key]
        for key in (
            "metadataBackfilled",
            "lowSignalRemoved",
            "blockedPeopleRemoved",
            "invalidAutomaticPeopleRemoved",
            "expiredRemoved",
            "tombstonesAdded",
        )
    ):
        ledger["updatedAt"] = _iso(now)
    report["changed"] = bool(
        report["metadataBackfilled"]
        or report["lowSignalRemoved"]
        or report["blockedPeopleRemoved"]
        or report["invalidAutomaticPeopleRemoved"]
        or report["expiredRemoved"]
        or report["tombstonesAdded"]
    )
    return report


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    config = _load(CONFIG_PATH, None)
    ledger = _load(
        LEDGER_PATH,
        {"schemaVersion": 1, "updatedAt": "", "tracks": {}, "added": [], "removed": []},
    )
    if not isinstance(config, dict) or not isinstance(config.get("tracks"), list):
        print(json.dumps({"error": "config/user_tracking.json unreadable"}))
        return 1
    if not isinstance(ledger, dict):
        print(json.dumps({"error": "tracking_auto_discovery ledger unreadable"}))
        return 1

    report = govern(config, ledger)
    print(json.dumps(report, ensure_ascii=False))
    if args.check:
        return 1 if report["changed"] else 0
    if report["changed"]:
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        LEDGER_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
