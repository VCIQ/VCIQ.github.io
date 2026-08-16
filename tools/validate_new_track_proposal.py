#!/usr/bin/env python3
"""Validate proposal-only custom tracking tracks without mutating production config."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import crawl_with_tracking as tracking  # noqa: E402
from tools import strict_tracking_config as strict  # noqa: E402
from tools import tracking_taxonomy as taxonomy  # noqa: E402

CONFIG_PATH = ROOT / "config" / "user_tracking.json"
PROPOSAL_PATH = ROOT / "config" / "user_tracking.new_tracks.batch2.json"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _normalized_existing_terms(tracks: list[dict[str, Any]]) -> set[str]:
    terms: set[str] = set()
    for track in tracks:
        terms.update(
            taxonomy.normalize_term(value)
            for value in [
                *taxonomy.name_aliases(track.get("name")),
                *track.get("keywords", []),
                *track.get("sampleCompanies", []),
                *track.get("people", []),
            ]
            if taxonomy.normalize_term(value)
        )
    return terms


def validate() -> dict[str, Any]:
    config = _load(CONFIG_PATH)
    proposal = _load(PROPOSAL_PATH)

    if proposal.get("mode") != "proposal-only":
        raise ValueError("batch 2 must remain proposal-only before activation")
    if proposal.get("guardrails", {}).get("productionApplied") is not False:
        raise ValueError("proposal cannot claim production activation")

    current_tracks = [row for row in config.get("tracks", []) if isinstance(row, dict)]
    proposed = [row for row in proposal.get("proposedTracks", []) if isinstance(row, dict)]
    if len(proposed) != 2:
        raise ValueError("batch 2 must contain exactly two proposed tracks")

    current_slugs = {str(row.get("slug") or "").strip() for row in current_tracks}
    current_names = {taxonomy.normalize_term(row.get("name")) for row in current_tracks}
    existing_terms = _normalized_existing_terms(current_tracks)

    proposal_slugs: set[str] = set()
    proposal_names: set[str] = set()
    collisions: list[str] = []

    for track in proposed:
        slug = str(track.get("slug") or "").strip()
        name = str(track.get("name") or "").strip()
        if not slug or not name:
            raise ValueError("proposed tracks require slug and name")
        if slug in current_slugs or slug in proposal_slugs:
            raise ValueError(f"track slug collision: {slug}")
        normalized_name = taxonomy.normalize_term(name)
        if normalized_name in current_names or normalized_name in proposal_names:
            raise ValueError(f"track name collision: {name}")
        proposal_slugs.add(slug)
        proposal_names.add(normalized_name)

        keywords = track.get("keywords", [])
        if not isinstance(keywords, list) or not keywords:
            raise ValueError(f"{slug} requires high-signal keywords")
        for keyword in keywords:
            parsed = strict.parse_tracking_keyword(keyword)
            if not parsed:
                raise ValueError(f"invalid tracking keyword in {slug}: {keyword}")
            normalized = taxonomy.normalize_term(parsed)
            if normalized in existing_terms:
                collisions.append(f"{slug}:keyword:{parsed}")

        companies = track.get("sampleCompanies", [])
        if not isinstance(companies, list) or not companies:
            raise ValueError(f"{slug} requires at least one sample company")
        for company in companies:
            normalized = taxonomy.normalize_term(company)
            if normalized in existing_terms:
                collisions.append(f"{slug}:company:{company}")

    if collisions:
        raise ValueError("exact production term collisions: " + ", ".join(collisions))

    merged_tracks = [*current_tracks, *proposed]
    generated = taxonomy.generated_track_sources(merged_tracks, tracking)
    generated_ids = {str(source.get("id") or "") for source in generated}
    discovery: dict[str, list[str]] = {}
    for slug in proposal_slugs:
        expected = taxonomy.expected_source_ids(slug)
        missing = [source_id for source_id in expected if source_id not in generated_ids]
        if missing:
            raise ValueError(f"{slug} missing generated discovery routes: {missing}")
        if len(expected) < 3:
            raise ValueError(f"{slug} has fewer than three expected discovery routes")
        discovery[slug] = expected

    listing_gate = proposal.get("listedCompanyQualityGate", {})
    if not isinstance(listing_gate, dict):
        raise ValueError("listedCompanyQualityGate must be an object")
    ticker = str(listing_gate.get("ticker") or "").strip()
    market = str(listing_gate.get("market") or "").strip()
    if market != "A股" or not re.fullmatch(r"\d{6}", ticker):
        raise ValueError("恒锋信息 listing quality gate requires a valid A-share ticker")

    duplicate_listing = any(
        isinstance(row, dict)
        and row.get("market") == market
        and str(row.get("ticker") or "").strip() == ticker
        for row in config.get("listedCompanies", [])
    )
    if duplicate_listing:
        raise ValueError(f"listed company already exists in production config: {market} {ticker}")

    return {
        "valid": True,
        "proposalVersion": proposal.get("proposalVersion"),
        "proposedTracks": sorted(proposal_slugs),
        "exactProductionTermCollisions": 0,
        "generatedDiscoveryRoutes": discovery,
        "listedCompanyGate": {
            "name": listing_gate.get("name"),
            "market": market,
            "ticker": ticker,
            "alreadyRegistered": False,
        },
    }


def main() -> int:
    try:
        result = validate()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
