#!/usr/bin/env python3
"""Persist exact public homepage events for long-lived Native Research links.

The ledger is deliberately bounded and event-ID keyed. It never performs fuzzy
same-company substitution. Current snapshots remain authoritative; the ledger
only supplies an exact historical event after it leaves the rolling window.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = 1
RETENTION_DAYS = 180
MAX_EVENTS = 2500
MAX_BYTES = 4_000_000
EVENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,319}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
REJECTED = {"rejected", "invalid", "低可信"}
ARTICLE_PATH = "public/data/articles.json"
RANKED_PATH = "public/data/ranked-intelligence.json"
LEDGER_PATH = "public/data/research_event_ledger.json"


def record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rows(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def clean(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def public_url(value: Any) -> str:
    raw = clean(value, 2400)
    try:
        parsed = urlsplit(raw)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return ""
        host = parsed.hostname.lower()
        if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or "." not in host:
            return ""
        if "/alerts/feeds/" in parsed.path:
            return ""
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.query, ""))
    except ValueError:
        return ""


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_list(value: Any, limit: int = 16) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in value if isinstance(value, list) else []:
        item = clean(raw, 180)
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def safe_related(value: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in rows(value):
        url = public_url(raw.get("url") or raw.get("href"))
        if not url or url in seen:
            continue
        seen.add(url)
        result.append({
            "name": clean(raw.get("name") or raw.get("source"), 160),
            "url": url,
            "level": clean(raw.get("level"), 100) or "待交叉验证",
            "platform": clean(raw.get("platform"), 100),
            "title": clean(raw.get("title"), 300),
            "publishedAt": clean(raw.get("publishedAt"), 80),
        })
        if len(result) >= 12:
            break
    return result


def rejected(event: dict[str, Any]) -> bool:
    for key in ("qualityStatus", "verificationStatus", "reviewStatus", "publicationTier"):
        value = clean(event.get(key), 80).casefold()
        if value in REJECTED:
            return True
    return False


def normalize_article_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    event_id = clean(raw.get("id"), 320)
    title = clean(raw.get("title"), 500)
    summary = clean(raw.get("summary") or raw.get("description"), 3000)
    source = record(raw.get("source"))
    url = public_url(source.get("url") or raw.get("url"))
    if not EVENT_RE.fullmatch(event_id) or not title or not summary or not url:
        return None
    output: dict[str, Any] = {
        "id": event_id,
        "title": title,
        "summary": summary,
        "type": clean(raw.get("type"), 80) or "公司动态",
        "region": clean(raw.get("region"), 80) or "全球",
        "sector": clean(raw.get("sector"), 120) or "科技产业",
        "company": clean(raw.get("company"), 180),
        "sourceId": clean(raw.get("sourceId"), 180),
        "publishedAt": clean(raw.get("publishedAt"), 80),
        "importance": max(0, min(100, safe_int(raw.get("importance"), 0))),
        "source": {
            "name": clean(source.get("name"), 180),
            "url": url,
            "level": clean(source.get("level"), 120),
            "platform": clean(source.get("platform"), 120),
        },
        "curated": bool(raw.get("curated")),
        "mentionedCompanies": safe_list(raw.get("mentionedCompanies")),
        "mentionedPeople": safe_list(raw.get("mentionedPeople")),
        "matchedTrackingTerms": safe_list(raw.get("matchedTrackingTerms"), 24),
        "eventClusterId": clean(raw.get("eventClusterId"), 220),
        "duplicateCount": max(1, safe_int(raw.get("duplicateCount"), 1)),
        "relatedSources": safe_related(raw.get("relatedSources")),
    }
    for key in ("qualityStatus", "verificationStatus", "reviewStatus", "publicationTier", "sourceRole"):
        value = clean(raw.get(key), 100)
        if value:
            output[key] = value
    return output


def mapped_event_type(values: Any) -> str:
    mapping = {
        "funding": "融资", "m&a": "并购", "merger": "并购", "acquisition": "并购",
        "ipo": "IPO", "product": "产品发布", "technology": "技术突破",
        "patent": "技术突破", "research": "论文", "policy": "政策",
        "personnel": "公司动态", "partnership": "商业进展", "production": "商业进展",
        "order": "商业进展", "market": "商业进展",
    }
    for raw in values if isinstance(values, list) else []:
        result = mapping.get(clean(raw, 80).casefold())
        if result:
            return result
    return "公司动态"


def normalize_ranked_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    raw_id = clean(raw.get("id"), 280)
    event_id = f"ranked-intelligence:{raw_id}"
    title = clean(raw.get("title"), 500)
    summary = clean(raw.get("summary"), 3000)
    url = public_url(raw.get("href"))
    if not raw_id or not EVENT_RE.fullmatch(event_id) or not title or not summary or not url:
        return None
    entities = rows(raw.get("entities"))
    companies = safe_list([row.get("name") for row in entities if row.get("objectType") == "company"])
    people = safe_list([row.get("name") for row in entities if row.get("objectType") == "person"])
    technologies = safe_list([row.get("name") for row in entities if row.get("objectType") == "technology"])
    tracks = safe_list(raw.get("tracks"), 8)
    return {
        "id": event_id,
        "title": title,
        "summary": summary,
        "type": mapped_event_type(raw.get("eventTypes")),
        "region": "全球",
        "sector": tracks[0] if tracks else "科技产业",
        "company": companies[0] if companies else "",
        "sourceId": "ranked-intelligence",
        "publishedAt": clean(raw.get("publishedAt"), 80),
        "importance": max(0, min(100, safe_int(raw.get("score"), 0))),
        "source": {
            "name": clean(raw.get("source"), 180),
            "url": url,
            "level": "待交叉验证",
            "platform": "Intelligence Inbox",
        },
        "curated": True,
        "mentionedCompanies": companies,
        "mentionedPeople": people,
        "matchedTrackingTerms": safe_list(technologies + tracks, 24),
        "eventClusterId": clean(raw.get("eventClusterId"), 220),
        "duplicateCount": max(1, safe_int(raw.get("duplicateCount"), 1)),
        "relatedSources": [
            {
                "name": clean(row.get("source"), 180),
                "url": public_url(row.get("href")),
                "level": "待交叉验证",
                "platform": "Intelligence Inbox",
                "title": clean(row.get("title"), 300),
                "publishedAt": clean(row.get("publishedAt"), 80),
            }
            for row in rows(raw.get("relatedSources"))
            if public_url(row.get("href"))
        ][:12],
    }


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def git_json(root: Path, sha: str, path: str) -> Any | None:
    if not SHA_RE.fullmatch(sha):
        raise ValueError("capture ref must be a full commit SHA")
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{sha}:{path}"], cwd=root, stderr=subprocess.DEVNULL,
            text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return json.loads(raw)


def blob_sha(root: Path, sha: str, path: str) -> str:
    if not SHA_RE.fullmatch(sha):
        return ""
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", f"{sha}:{path}"], cwd=root, stderr=subprocess.DEVNULL,
            text=True, timeout=10,
        ).strip()
        return value if SHA_RE.fullmatch(value) else ""
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def snapshot_events(payload: Any, dataset: str) -> tuple[str, list[dict[str, Any]]]:
    root = record(payload)
    generated_at = clean(root.get("generatedAt"), 80)
    if dataset == ARTICLE_PATH:
        values = [normalize_article_event(row) for row in rows(root.get("articles"))]
    elif dataset == RANKED_PATH:
        values = [normalize_ranked_event(row) for row in rows(root.get("items"))]
    else:
        raise ValueError("unsupported research event source")
    return generated_at, [value for value in values if value]


def parse_time(value: Any) -> datetime | None:
    text = clean(value, 80)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def current_head(root: Path) -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL,
            text=True, timeout=10,
        ).strip()
        return value if SHA_RE.fullmatch(value) else ""
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def valid_existing(value: Any) -> dict[str, Any]:
    payload = record(value)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        return {}
    result: dict[str, Any] = {}
    for event_id, raw in record(payload.get("events")).items():
        row = record(raw)
        event = record(row.get("event"))
        if not EVENT_RE.fullmatch(str(event_id)) or event.get("id") != event_id:
            continue
        if not normalize_article_event(event):
            continue
        result[event_id] = copy.deepcopy(row)
    return result


def build_ledger(root: Path, capture_ref: str = "") -> dict[str, Any]:
    ledger_path = root / LEDGER_PATH
    existing_payload = read_json(ledger_path, {})
    events = valid_existing(existing_payload)
    now = datetime.now(timezone.utc)
    head = current_head(root)

    snapshots: list[tuple[str, str, str, Any]] = []
    if capture_ref:
        for path in (ARTICLE_PATH, RANKED_PATH):
            value = git_json(root, capture_ref, path)
            if value is not None:
                snapshots.append((path, capture_ref, blob_sha(root, capture_ref, path), value))
    for path in (ARTICLE_PATH, RANKED_PATH):
        value = read_json(root / path, None)
        if value is not None:
            snapshots.append((path, head, blob_sha(root, head, path), value))

    for dataset, commit, blob, payload in snapshots:
        snapshot_time, current = snapshot_events(payload, dataset)
        observed_at = parse_time(snapshot_time) or now
        observed = observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        for event in current:
            event_id = str(event["id"])
            prior = record(events.get(event_id))
            first_seen = clean(prior.get("firstSeenAt"), 80) or observed
            events[event_id] = {
                "eventId": event_id,
                "firstSeenAt": first_seen,
                "lastSeenAt": observed,
                "sourceDataset": dataset,
                "snapshotGeneratedAt": snapshot_time or observed,
                "sourceCommit": commit,
                "sourceBlob": blob,
                "status": "rejected" if rejected(event) else "active",
                "event": event,
            }

    cutoff = now - timedelta(days=RETENTION_DAYS)
    retained: list[tuple[str, dict[str, Any]]] = []
    for event_id, row in events.items():
        seen = parse_time(row.get("lastSeenAt"))
        if seen and seen < cutoff:
            continue
        retained.append((event_id, row))
    retained.sort(key=lambda item: (clean(item[1].get("lastSeenAt"), 80), item[0]), reverse=True)
    retained = retained[:MAX_EVENTS]

    output = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "retentionDays": RETENTION_DAYS,
        "maxEvents": MAX_EVENTS,
        "events": dict(retained),
    }
    while len(json.dumps(output, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_BYTES and len(retained) > 1:
        retained.pop()
        output["events"] = dict(retained)
    return output


def validate_ledger(value: Any) -> dict[str, Any]:
    payload = record(value)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("research event ledger schemaVersion must be 1")
    if payload.get("retentionDays") != RETENTION_DAYS or payload.get("maxEvents") != MAX_EVENTS:
        raise ValueError("research event ledger policy mismatch")
    values = record(payload.get("events"))
    if len(values) > MAX_EVENTS:
        raise ValueError("research event ledger exceeds row budget")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError("research event ledger exceeds byte budget")
    for event_id, raw in values.items():
        row = record(raw)
        event = record(row.get("event"))
        if not EVENT_RE.fullmatch(str(event_id)) or row.get("eventId") != event_id or event.get("id") != event_id:
            raise ValueError(f"research event identity mismatch: {event_id}")
        normalized = normalize_article_event(event)
        if normalized is None:
            raise ValueError(f"research event is not safely researchable: {event_id}")
        if row.get("status") not in {"active", "rejected"}:
            raise ValueError(f"research event status invalid: {event_id}")
        if parse_time(row.get("firstSeenAt")) is None or parse_time(row.get("lastSeenAt")) is None:
            raise ValueError(f"research event timestamps invalid: {event_id}")
        if row.get("sourceDataset") not in {ARTICLE_PATH, RANKED_PATH}:
            raise ValueError(f"research event source invalid: {event_id}")
    return {"eventCount": len(values), "bytes": len(encoded)}


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def retained_event(root: Path, event_id: str) -> dict[str, Any] | None:
    path = root / LEDGER_PATH
    if not path.exists():
        return None
    payload = read_json(path, {})
    validate_ledger(payload)
    row = record(record(payload.get("events")).get(event_id))
    event = record(row.get("event"))
    if not row or row.get("status") != "active" or event.get("id") != event_id or rejected(event):
        return None
    return {
        **copy.deepcopy(event),
        "researchLedgerProvenance": {
            "firstSeenAt": clean(row.get("firstSeenAt"), 80),
            "lastSeenAt": clean(row.get("lastSeenAt"), 80),
            "sourceDataset": clean(row.get("sourceDataset"), 120),
            "snapshotGeneratedAt": clean(row.get("snapshotGeneratedAt"), 80),
            "sourceCommit": clean(row.get("sourceCommit"), 40),
            "sourceBlob": clean(row.get("sourceBlob"), 40),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--capture-ref", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = args.root / LEDGER_PATH

    if args.check:
        result = validate_ledger(read_json(path, {}))
        print(json.dumps(result, ensure_ascii=False))
        return 0

    result = build_ledger(args.root, args.capture_ref.strip())
    summary = validate_ledger(result)
    changed = read_json(path, {}) != result
    if args.write:
        atomic_write(path, result)
    print(json.dumps({**summary, "changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
