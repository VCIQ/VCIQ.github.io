"""Bounded, reproducible tracking batches for owner-approved IPO watchlist.

The full source ledger remains in config/ipo_priority_watchlist_20261115.json.
Only unambiguous names are eligible for search. A daily slice is used to avoid
hundreds of extra RSS queries in a single collection run. This module does not
trigger any requests by itself.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "config" / "ipo_priority_watchlist_20261115.json"
CHUNK = 15
SLOTS = 3


def eligible_companies(path: Path = PATH) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("policy", {}).get("backendTrackingEnabled", False):
        return []
    seen: set[str] = set()
    result = []
    for item in payload.get("companies", []):
        name = str(item.get("name") or "").strip()
        if not name or item.get("ocrQuality") == "needs_manual_verification":
            continue
        normalized = "".join(name.split()).casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
    return result


def daily_tracks(day: date | None = None, path: Path = PATH) -> list[dict]:
    items = eligible_companies(path)
    if not items:
        return []
    if day is None:
        day = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    daily_capacity = CHUNK * SLOTS
    batches = (len(items) + daily_capacity - 1) // daily_capacity
    batch_index = (day.toordinal() - date(2026, 11, 16).toordinal()) % batches
    selected = items[batch_index * daily_capacity : (batch_index + 1) * daily_capacity]
    result = []
    for slot in range(SLOTS):
        chunk = selected[slot * CHUNK : (slot + 1) * CHUNK]
        if not chunk:
            continue
        result.append({
            "slug": f"ipo-owner-priority-{slot + 1}",
            "name": f"IPO重点关注第{slot + 1}组",
            "keywords": [],
            "people": [],
            "sampleCompanies": [item["name"] for item in chunk],
        })
    return result


if __name__ == "__main__":
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    names = eligible_companies()
    tracks = daily_tracks(today)
    print(json.dumps({
        "beijingDate": today.isoformat(),
        "uniqueEligibleCompanies": len(names),
        "dailySearchCompanies": sum(len(t["sampleCompanies"]) for t in tracks),
        "tracks": [t["slug"] for t in tracks],
    }, ensure_ascii=False))
