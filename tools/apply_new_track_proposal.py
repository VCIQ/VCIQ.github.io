#!/usr/bin/env python3
"""Apply a staged new-track proposal to a candidate tracking config.

The operation is additive-only: existing tracks/listed companies are not
modified or deleted; proposed tracks must use new slugs/names; and an explicit
listed-company quality gate may append one listing.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
PROPOSAL_PATH = ROOT / "config" / "user_tracking.new_tracks.batch2.json"


def clean(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalized(value: Any) -> str:
    return re.sub(r"[\s._:：\-—–/／|｜,，;；、&＆+＋()（）\[\]【】]+", "", clean(value).casefold())


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def production_track_shape(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": clean(raw.get("slug"), 80),
        "name": clean(raw.get("name"), 80),
        "enabled": raw.get("enabled", True) is not False,
        "custom": raw.get("custom", True) is not False,
        "keywords": list(raw.get("keywords", [])) if isinstance(raw.get("keywords"), list) else [],
        "people": list(raw.get("people", [])) if isinstance(raw.get("people"), list) else [],
        "sampleCompanies": list(raw.get("sampleCompanies", [])) if isinstance(raw.get("sampleCompanies"), list) else [],
    }


def listed_company_from_gate(gate: dict[str, Any], track_by_slug: dict[str, dict[str, Any]]) -> dict[str, Any]:
    slug = clean(gate.get("trackSlug"), 80)
    track = track_by_slug.get(slug)
    if not track:
        raise ValueError(f"listedCompanyQualityGate references unknown track slug: {slug}")
    name = clean(gate.get("name"), 120)
    ticker = clean(gate.get("ticker"), 32).upper()
    market = clean(gate.get("market"), 20)
    catalog_slug = clean(gate.get("catalogSlug"), 80)
    item_id = clean(gate.get("id"), 100)
    if not all((name, ticker, market, catalog_slug, item_id)):
        raise ValueError("listedCompanyQualityGate must specify id, catalogSlug, name, ticker and market")
    return {
        "id": item_id,
        "name": name,
        "ticker": ticker,
        "market": market,
        "sector": track["name"],
        "enabled": True,
        "custom": True,
        "catalogSlug": catalog_slug,
    }


def apply_proposal(tracking: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal.get("mode") != "proposal-only":
        raise ValueError("Batch 2 applicator requires mode=proposal-only")
    guardrails = proposal.get("guardrails")
    if not isinstance(guardrails, dict) or guardrails.get("productionApplied") is not False:
        raise ValueError("proposal must explicitly keep productionApplied=false")
    if guardrails.get("deleteExistingEntries") is not False or guardrails.get("modifyExistingTracks") is not False:
        raise ValueError("proposal must be additive-only")

    result = copy.deepcopy(tracking)
    tracks = result.get("tracks")
    listed = result.get("listedCompanies")
    if not isinstance(tracks, list) or not isinstance(listed, list):
        raise ValueError("tracking config requires tracks and listedCompanies arrays")

    existing_slugs = {normalized(item.get("slug")) for item in tracks if isinstance(item, dict) and clean(item.get("slug"))}
    existing_names = {normalized(item.get("name")) for item in tracks if isinstance(item, dict) and clean(item.get("name"))}
    proposed_tracks = proposal.get("proposedTracks")
    if not isinstance(proposed_tracks, list) or not proposed_tracks:
        raise ValueError("proposal requires proposedTracks")

    shaped_tracks: list[dict[str, Any]] = []
    for raw in proposed_tracks:
        if not isinstance(raw, dict):
            raise ValueError("every proposed track must be an object")
        track = production_track_shape(raw)
        slug_key = normalized(track["slug"])
        name_key = normalized(track["name"])
        if not slug_key or not name_key:
            raise ValueError("proposed track requires slug and name")
        if slug_key in existing_slugs:
            raise ValueError(f"track slug already exists: {track['slug']}")
        if name_key in existing_names:
            raise ValueError(f"track name already exists: {track['name']}")
        existing_slugs.add(slug_key)
        existing_names.add(name_key)
        shaped_tracks.append(track)

    tracks.extend(shaped_tracks)
    track_by_slug = {track["slug"]: track for track in shaped_tracks}
    gate = proposal.get("listedCompanyQualityGate")
    if isinstance(gate, dict) and gate.get("requiredBeforeProductionActivation") is True:
        candidate = listed_company_from_gate(gate, track_by_slug)
        candidate_ticker = (candidate["market"], candidate["ticker"])
        for row in listed:
            if not isinstance(row, dict):
                continue
            if (clean(row.get("market"), 20), clean(row.get("ticker"), 32).upper()) == candidate_ticker:
                raise ValueError(f"listed company ticker already exists: {candidate['market']} {candidate['ticker']}")
            if normalized(row.get("name")) == normalized(candidate["name"]):
                raise ValueError(f"listed company name already exists: {candidate['name']}")
            if clean(row.get("catalogSlug"), 80) == candidate["catalogSlug"]:
                raise ValueError(f"listed company catalogSlug already exists: {candidate['catalogSlug']}")
        listed.append(candidate)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--proposal", type=Path, default=PROPOSAL_PATH)
    parser.add_argument("--in-place", action="store_true")
    args = parser.parse_args()
    if not args.in_place:
        parser.error("this one-time applicator requires --in-place")
    tracking = load_json(args.tracking)
    proposal = load_json(args.proposal)
    activated = apply_proposal(tracking, proposal)
    args.tracking.write_text(json.dumps(activated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "addedTracks": len(activated.get("tracks", [])) - len(tracking.get("tracks", [])),
        "addedListedCompanies": len(activated.get("listedCompanies", [])) - len(tracking.get("listedCompanies", [])),
        "output": str(args.tracking),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
