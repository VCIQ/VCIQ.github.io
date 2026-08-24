#!/usr/bin/env python3
"""Validate and publish the public-safe Ranked Intelligence projection.

The producer lives in the private tracking-admin repository. This consumer is
intentionally strict because its output is committed to the public website.
Only public article metadata and coarse resolver/event-cluster results are
allowed through.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT_KEYS = {"schemaVersion", "generatedAt", "source", "contentHash", "items"}
ITEM_KEYS = {
    "id",
    "title",
    "summary",
    "href",
    "source",
    "publishedAt",
    "priority",
    "score",
    "eventTypes",
    "entities",
    "tracks",
    "eventClusterId",
    "duplicateCount",
    "relatedSources",
}
ENTITY_KEYS = {"objectType", "name"}
RELATED_SOURCE_KEYS = {"source", "href", "title", "publishedAt"}
ALLOWED_PRIORITIES = {"P0", "P1", "P2"}
ALLOWED_ENTITY_TYPES = {"company", "person", "technology"}
MAX_ITEMS = 24
MAX_RELATED_SOURCES = 3


def compact_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def unique_strings(value: Any, *, limit: int, text_limit: int = 160) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        item = compact_text(raw, text_limit)
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def http_url(value: Any) -> str:
    candidate = compact_text(value, 1600)
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("item href must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("item href must not contain URL credentials")
    return candidate


def iso_datetime(value: Any) -> str:
    candidate = compact_text(value, 80)
    if not candidate:
        raise ValueError("item publishedAt is required")
    parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("item publishedAt must include an explicit timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def reject_extra_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    extras = sorted(set(value) - allowed)
    if extras:
        raise ValueError(f"{label} contains non-public fields: {', '.join(extras)}")


def normalize_entity(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("entity must be an object")
    reject_extra_keys(value, ENTITY_KEYS, "entity")
    object_type = compact_text(value.get("objectType"), 32)
    name = compact_text(value.get("name"), 160)
    if object_type not in ALLOWED_ENTITY_TYPES or not name:
        raise ValueError("entity objectType/name is invalid")
    return {"objectType": object_type, "name": name}


def normalize_related_source(value: Any, primary_href: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("related source must be an object")
    reject_extra_keys(value, RELATED_SOURCE_KEYS, "related source")
    href = http_url(value.get("href"))
    if href == primary_href:
        raise ValueError("related source must not repeat the primary href")
    source = compact_text(value.get("source"), 160)
    if not source:
        source = urlsplit(href).hostname or ""
    return {
        "source": source,
        "href": href,
        "title": compact_text(value.get("title"), 240),
        "publishedAt": iso_datetime(value.get("publishedAt")),
    }


def normalize_item(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("projection item must be an object")
    reject_extra_keys(value, ITEM_KEYS, "projection item")

    title = compact_text(value.get("title"), 240)
    if not title:
        raise ValueError("item title is required")
    href = http_url(value.get("href"))
    source = compact_text(value.get("source"), 160)
    if not source:
        source = urlsplit(href).hostname or ""
    priority = compact_text(value.get("priority"), 8)
    if priority not in ALLOWED_PRIORITIES:
        raise ValueError("item priority is invalid")
    score = value.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("item score must be numeric")
    score = max(0, min(100, round(float(score))))

    entities_value = value.get("entities", [])
    if not isinstance(entities_value, list) or len(entities_value) > 8:
        raise ValueError("item entities exceeds the public projection limit")
    entities = [normalize_entity(entity) for entity in entities_value]

    event_cluster_id = compact_text(value.get("eventClusterId"), 160)
    duplicate_count = value.get("duplicateCount", 1)
    if isinstance(duplicate_count, bool) or not isinstance(duplicate_count, (int, float)):
        raise ValueError("item duplicateCount must be numeric")
    duplicate_count = max(1, min(1000, int(duplicate_count)))

    related_value = value.get("relatedSources", [])
    if not isinstance(related_value, list) or len(related_value) > MAX_RELATED_SOURCES:
        raise ValueError(
            f"item relatedSources must contain at most {MAX_RELATED_SOURCES} public sources"
        )
    related_sources: list[dict[str, str]] = []
    seen_related: set[str] = set()
    for raw in related_value:
        normalized = normalize_related_source(raw, href)
        if normalized["href"] in seen_related:
            continue
        seen_related.add(normalized["href"])
        related_sources.append(normalized)

    if duplicate_count < len(related_sources) + 1:
        duplicate_count = len(related_sources) + 1

    return {
        "id": compact_text(value.get("id"), 240) or event_cluster_id or href,
        "title": title,
        "summary": compact_text(value.get("summary"), 700),
        "href": href,
        "source": source,
        "publishedAt": iso_datetime(value.get("publishedAt")),
        "priority": priority,
        "score": score,
        "eventTypes": unique_strings(value.get("eventTypes", []), limit=6),
        "entities": entities,
        "tracks": unique_strings(value.get("tracks", []), limit=4),
        "eventClusterId": event_cluster_id,
        "duplicateCount": duplicate_count,
        "relatedSources": related_sources,
    }


def content_hash(items: list[dict[str, Any]]) -> str:
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("projection must be an object")
    reject_extra_keys(value, ROOT_KEYS, "projection")
    if value.get("schemaVersion") != 1:
        raise ValueError("projection schemaVersion must be 1")
    if value.get("source") != "google-alerts-rss":
        raise ValueError("projection source must be google-alerts-rss")
    raw_items = value.get("items")
    if not isinstance(raw_items, list) or len(raw_items) > MAX_ITEMS:
        raise ValueError(f"projection items must be an array with at most {MAX_ITEMS} items")
    items = [normalize_item(item) for item in raw_items]
    generated_at = compact_text(value.get("generatedAt"), 80)
    if generated_at:
        generated_at = iso_datetime(generated_at)
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "source": "google-alerts-rss",
        "contentHash": content_hash(items),
        "items": items,
    }


def load_input(args: argparse.Namespace) -> Any:
    if args.input_base64:
        decoded = base64.b64decode(args.input_base64, validate=True).decode("utf-8")
        return json.loads(decoded)
    if args.input:
        return json.loads(Path(args.input).read_text(encoding="utf-8"))
    return json.load(__import__("sys").stdin)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--input-base64")
    parser.add_argument("--path", default="public/data/ranked-intelligence.json")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.input and args.input_base64:
        parser.error("use only one of --input or --input-base64")

    projection = normalize_projection(load_input(args))
    output_path = Path(args.path)
    current_hash = ""
    if output_path.exists():
        try:
            current = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(current, dict):
                current_hash = str(current.get("contentHash") or "")
        except (OSError, json.JSONDecodeError):
            current_hash = ""

    changed = current_hash != projection["contentHash"]
    if args.write and changed:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(projection, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "ok": True,
        "changed": changed,
        "contentHash": projection["contentHash"],
        "itemCount": len(projection["items"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())