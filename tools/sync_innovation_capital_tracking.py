#!/usr/bin/env python3
"""Sync the reviewed innovation-capital universe into one backend tracking lane.

The lane is a tracking surface, not a new public research object. It combines:
- the reviewed five-broker innovation listing watchlist;
- the five counselling brokers themselves;
- capital institutions linked to those reviewed projects; and
- evidence-backed private Chinese hard-tech companies discovered from verified
  institution portfolios / company profiles.

Relationship semantics stay separate: tracking an institution does not promote
an institution-project candidate relationship to confirmed, and tracking a
company does not assert an IPO board, broker mandate, or listing outcome.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from .enrich_tracking_people_from_sample_companies import (
        add_ledger_entry,
        company_keys,
        load_json,
        normalized_key,
        now_iso,
    )
except ImportError:
    from enrich_tracking_people_from_sample_companies import (
        add_ledger_entry,
        company_keys,
        load_json,
        normalized_key,
        now_iso,
    )

ROOT = Path(__file__).resolve().parents[1]
SEEDS_PATH = ROOT / "config" / "innovation_capital_tracking_seeds.json"
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
LEDGER_PATH = ROOT / "config" / "tracking_auto_discovery.json"
COMPANY_REGISTRY_PATH = ROOT / "config" / "company_registry.json"
VENTURE_PROFILES_PATH = ROOT / "public" / "data" / "venture_profiles.json"
WATCHLIST_PATH = ROOT / "config" / "innovation_listing_watchlist.json"
LIFECYCLE_PATH = ROOT / "config" / "innovation_listing_lifecycle.json"

TRACK_SLUG = "innovation-capital"
TRACK_NAME = "科创资本"
POLICY_SECTOR_TAGS: dict[str, tuple[str, ...]] = {
    "AI / AGI": ("人工智能", "新一代信息技术"),
    "半导体": ("集成电路", "新一代信息技术"),
    "机器人": ("智能机器人", "具身智能"),
    "商业航天": ("航空航天",),
    "新能源": ("新型储能",),
    "新材料": ("新材料",),
    "生物科技": ("生物医药", "生物制造"),
    "智能制造": ("高端装备",),
}
NON_INDEPENDENT_COMPANY_SLUGS = {"doubao", "volcengine"}

LATE_STAGE_RE = re.compile(
    r"(?:Series\s*[DEFG]|(?:^|[^A-Za-z])[DEFG](?:\+{0,2})?(?:轮|\b)|"
    r"D轮|D\+轮|D\+\+轮|E轮|E\+轮|E\+\+轮|Pre[- ]?IPO|Growth|战略融资)",
    re.I,
)


def clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return []


def removed_keys(ledger: dict[str, Any], kind: str) -> set[str]:
    result: set[str] = set()
    for row in ledger.get("removed", []):
        if not isinstance(row, dict):
            continue
        if row.get("track") != TRACK_SLUG or row.get("kind") != kind:
            continue
        result.update(company_keys(row.get("value")))
        key = normalized_key(row.get("value"))
        if key:
            result.add(key)
    return result


def alias_index(seeds: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for section in ("brokers", "institutions"):
        for row in rows(seeds.get(section)):
            canonical = clean(row.get("name"), 160)
            if not canonical:
                continue
            aliases = [canonical, *(row.get("aliases") or [])]
            for alias in aliases:
                for key in company_keys(alias):
                    index[key] = canonical
    for row in rows(seeds.get("projects")):
        canonical = clean(row.get("name"), 160)
        for key in company_keys(canonical):
            index.setdefault(key, canonical)
    return index


def canonical_name(value: Any, aliases: dict[str, str]) -> str:
    name = clean(value, 160)
    for key in company_keys(name):
        if key in aliases:
            return aliases[key]
    return name


def opportunity_rows(
    registry_payload: Any,
    venture_payload: Any,
    seeds: dict[str, Any],
) -> list[dict[str, Any]]:
    companies = rows(registry_payload.get("companies") if isinstance(registry_payload, dict) else None)
    profiles = rows(venture_payload.get("companies") if isinstance(venture_payload, dict) else None)
    institutions = rows(venture_payload.get("institutions") if isinstance(venture_payload, dict) else None)
    profile_by_slug = {
        clean(row.get("slug"), 160): row
        for row in profiles
        if clean(row.get("slug"), 160)
    }

    reviewed_keys: set[str] = set()
    for row in rows(seeds.get("projects")):
        reviewed_keys.update(company_keys(row.get("name")))

    institution_aliases = alias_index({"institutions": seeds.get("institutions", [])})
    portfolio_links: dict[str, set[str]] = {}
    for institution in institutions:
        institution_name = canonical_name(institution.get("name"), institution_aliases)
        if not institution_name:
            continue
        matched_seed = any(
            key in institution_aliases
            for key in company_keys(institution.get("name"))
        )
        if not matched_seed:
            continue
        for item in rows(institution.get("portfolio")) + rows(institution.get("recentInvestments")):
            slug = clean(item.get("companySlug"), 160)
            if slug:
                portfolio_links.setdefault(slug, set()).add(institution_name)

    result: list[dict[str, Any]] = []
    for company in companies:
        name = clean(company.get("name"), 160)
        slug = clean(company.get("slug"), 160)
        region = clean(company.get("region"), 40)
        sector = clean(company.get("sector"), 80)
        status = clean(company.get("status"), 80)
        stage = clean(company.get("stage"), 80)
        company_identity_keys = set(company_keys(name))
        company_identity_keys.update(company_keys(company.get("englishName")))
        for alias in company.get("aliases", []) if isinstance(company.get("aliases"), list) else []:
            company_identity_keys.update(company_keys(alias))
        overlaps_reviewed = any(
            key in reviewed_keys
            or (
                len(key) >= 5
                and any(
                    len(reviewed) >= 5 and (key in reviewed or reviewed in key)
                    for reviewed in reviewed_keys
                )
            )
            for key in company_identity_keys
        )
        if not name or not slug or slug in NON_INDEPENDENT_COMPANY_SLUGS or overlaps_reviewed:
            continue
        if region not in {"中国", "中國", "香港"}:
            continue
        if status == "已上市" or stage == "已上市":
            continue
        policy_tags = list(POLICY_SECTOR_TAGS.get(sector, ()))
        if not policy_tags:
            continue

        profile = profile_by_slug.get(slug, {})
        capital = profile.get("capitalSummary") if isinstance(profile.get("capitalSummary"), dict) else {}
        round_values = [
            clean(value, 80)
            for value in capital.get("rounds", [])
            if clean(value, 80)
        ]
        for event in rows(profile.get("financing")):
            round_name = clean(event.get("round"), 80)
            if round_name:
                round_values.append(round_name)
        rounds = list(dict.fromkeys(round_values))
        late_rounds = [value for value in rounds if LATE_STAGE_RE.search(value)]
        evidence_score = int(profile.get("evidenceScore") or 0)
        backed_by = sorted(portfolio_links.get(slug, set()))

        score = 0
        signals: list[str] = []
        if late_rounds:
            score += 35
            signals.append("已识别D/E/Pre-IPO/Growth等成熟期融资信号")
        if backed_by:
            score += 18
            signals.append("命中科创资本机构的公开投资组合")
        if evidence_score >= 80:
            score += 15
        elif evidence_score >= 60:
            score += 10
        elif evidence_score >= 40:
            score += 5
        source = company.get("source") if isinstance(company.get("source"), dict) else {}
        if clean(source.get("level"), 80) in {"官方披露", "监管文件", "交易所公告"}:
            score += 12
            signals.append("公司身份有一级公开来源")
        if stage == "成长期":
            score += 8
        capital_markets = rows(profile.get("capitalMarkets"))
        if capital_markets:
            score += 12
            signals.append("已有资本市场公开事件")
        if score < 25:
            continue

        result.append(
            {
                "name": name,
                "slug": slug,
                "sector": sector,
                "policyThemes": policy_tags,
                "latestRound": clean(capital.get("latestRound"), 80),
                "latestDate": clean(capital.get("latestDate"), 40),
                "lateStageRounds": late_rounds,
                "institutionBackers": backed_by,
                "evidenceScore": evidence_score,
                "readinessScore": min(100, score),
                "signals": signals,
                "sourceUrl": clean(source.get("url"), 1200),
            }
        )
    result.sort(
        key=lambda row: (
            -int(bool(row["lateStageRounds"])),
            -int(bool(row["institutionBackers"])),
            -int(row["readinessScore"]),
            row["name"],
        )
    )
    return result


def sync(
    config: dict[str, Any],
    ledger: dict[str, Any],
    seeds: dict[str, Any],
    registry_payload: Any,
    venture_payload: Any,
) -> dict[str, Any]:
    tracks = config.setdefault("tracks", [])
    track = next(
        (
            row for row in tracks
            if isinstance(row, dict) and row.get("slug") == TRACK_SLUG
        ),
        None,
    )
    created = track is None
    if track is None:
        track = {
            "slug": TRACK_SLUG,
            "name": TRACK_NAME,
            "enabled": True,
            "custom": True,
            "keywords": [],
            "people": [],
            "sampleCompanies": [],
        }
        tracks.append(track)

    aliases = alias_index(seeds)
    blocked = removed_keys(ledger, "sampleCompanies")
    stamp = now_iso()

    desired: list[tuple[str, list[str]]] = []
    for row in rows(seeds.get("projects")):
        desired.append(
            (
                clean(row.get("name"), 160),
                ["verified-innovation-listing-project", "five-broker-project"],
            )
        )
    for row in rows(seeds.get("brokers")):
        desired.append(
            (
                canonical_name(row.get("name"), aliases),
                ["verified-innovation-broker", "five-broker-counselling"],
            )
        )
    for row in rows(seeds.get("institutions")):
        evidence = [
            "verified-innovation-capital-institution",
            "relationship-candidate-does-not-imply-confirmed",
        ]
        evidence.extend(
            f"institution-type:{clean(value, 80)}"
            for value in row.get("institutionTypes", [])
            if clean(value, 80)
        )
        desired.append((canonical_name(row.get("name"), aliases), evidence))

    opportunities = opportunity_rows(registry_payload, venture_payload, seeds)
    for row in opportunities:
        evidence = ["verified-company-profile", "innovation-capital-opportunity-pool"]
        if row["institutionBackers"]:
            evidence.append("verified-institution-portfolio-link")
        if row["lateStageRounds"]:
            evidence.append("late-stage-financing-signal")
        desired.append((row["name"], evidence))

    existing = track.setdefault("sampleCompanies", [])
    canonical_existing: list[str] = []
    seen: set[str] = set()
    merged_aliases: list[dict[str, str]] = []
    for raw in existing:
        raw_name = clean(raw, 160)
        name = canonical_name(raw_name, aliases)
        key = normalized_key(name)
        if not key or key in seen:
            if raw_name:
                merged_aliases.append({"from": raw_name, "to": name})
            continue
        if raw_name != name:
            merged_aliases.append({"from": raw_name, "to": name})
        seen.add(key)
        canonical_existing.append(name)

    added: list[str] = []
    evidence_by_name: dict[str, list[str]] = {}
    for name, evidence in desired:
        name = canonical_name(name, aliases)
        key = normalized_key(name)
        if not name or not key:
            continue
        evidence_by_name.setdefault(name, [])
        evidence_by_name[name].extend(evidence)
        candidate_keys = company_keys(name) | {key}
        if candidate_keys & blocked:
            continue
        if key not in seen:
            canonical_existing.append(name)
            seen.add(key)
            added.append(name)

    track["sampleCompanies"] = canonical_existing
    keyword_blocked = removed_keys(ledger, "keywords")
    keyword_seen = {normalized_key(value) for value in track.setdefault("keywords", [])}
    keyword_added: list[str] = []
    for raw in seeds.get("trackingKeywords", []):
        value = clean(raw, 120)
        key = normalized_key(value)
        if not value or not key or key in keyword_seen or key in keyword_blocked:
            continue
        track["keywords"].append(value)
        keyword_seen.add(key)
        keyword_added.append(value)

    for name in canonical_existing:
        evidence = evidence_by_name.get(name)
        if evidence:
            add_ledger_entry(
                ledger,
                TRACK_SLUG,
                "sampleCompanies",
                name,
                sorted(set(evidence)),
                stamp,
            )
    for keyword in keyword_added:
        add_ledger_entry(
            ledger,
            TRACK_SLUG,
            "keywords",
            keyword,
            ["verified-innovation-capital-taxonomy"],
            stamp,
        )

    if created or added or keyword_added or merged_aliases:
        ledger.setdefault("tracks", {}).setdefault(TRACK_SLUG, {})[
            "lastInnovationCapitalSyncAt"
        ] = stamp

    return {
        "changed": bool(created or added or keyword_added or merged_aliases),
        "createdTrack": created,
        "track": TRACK_SLUG,
        "seedProjects": len(rows(seeds.get("projects"))),
        "seedBrokers": len(rows(seeds.get("brokers"))),
        "seedInstitutions": len(rows(seeds.get("institutions"))),
        "opportunityProjects": len(opportunities),
        "addedSampleCompanies": added,
        "addedKeywords": keyword_added,
        "mergedAliases": merged_aliases,
        "sampleCompanyCount": len(track["sampleCompanies"]),
        "opportunities": opportunities,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    seeds = load_json(SEEDS_PATH, {})
    config = load_json(CONFIG_PATH, {})
    ledger = load_json(
        LEDGER_PATH,
        {"schemaVersion": 1, "updatedAt": "", "tracks": {}, "added": [], "removed": []},
    )
    registry = load_json(COMPANY_REGISTRY_PATH, {})
    venture = load_json(VENTURE_PROFILES_PATH, {})
    watchlist = load_json(WATCHLIST_PATH, {})
    lifecycle = load_json(LIFECYCLE_PATH, {})
    reviewed_projects: list[dict[str, Any]] = []
    if isinstance(watchlist, dict) and isinstance(watchlist.get("projects"), list):
        reviewed_projects.extend(
            {
                "name": row.get("company", ""),
                "broker": row.get("broker", ""),
                "sector": row.get("sector", ""),
                "route": row.get("route", ""),
                "pool": row.get("pool", ""),
                "stage": row.get("stage", ""),
                "sourceUrl": (
                    row.get("source", {}).get("url", "")
                    if isinstance(row.get("source"), dict)
                    else ""
                ),
            }
            for row in watchlist["projects"]
            if isinstance(row, dict)
        )
    if isinstance(lifecycle, dict) and isinstance(lifecycle.get("projects"), list):
        reviewed_projects.extend(
            {
                "name": row.get("company", ""),
                "broker": row.get("broker", ""),
                "sector": row.get("sector", ""),
                "route": row.get("route", ""),
                "pool": "lifecycle",
                "stage": row.get("stage", ""),
                "sourceUrl": (
                    row.get("sources", [{}])[0].get("url", "")
                    if isinstance(row.get("sources"), list)
                    and row.get("sources")
                    and isinstance(row.get("sources")[0], dict)
                    else ""
                ),
            }
            for row in lifecycle["projects"]
            if isinstance(row, dict)
        )
    if reviewed_projects:
        seeds = dict(seeds)
        seeds["projects"] = reviewed_projects
    if not isinstance(seeds, dict) or seeds.get("schemaVersion") != 1:
        raise SystemExit("innovation capital tracking seeds are missing or invalid")
    if not isinstance(config, dict) or not isinstance(config.get("tracks"), list):
        raise SystemExit("user tracking config is missing or invalid")
    if not isinstance(ledger, dict):
        raise SystemExit("tracking auto-discovery ledger is invalid")

    before_config = json.dumps(config, ensure_ascii=False, sort_keys=True)
    before_ledger = json.dumps(ledger, ensure_ascii=False, sort_keys=True)
    result = sync(config, ledger, seeds, registry, venture)
    changed = (
        before_config != json.dumps(config, ensure_ascii=False, sort_keys=True)
        or before_ledger != json.dumps(ledger, ensure_ascii=False, sort_keys=True)
    )
    result["changed"] = changed

    if args.check:
        if changed:
            print(json.dumps({**result, "ok": False}, ensure_ascii=False))
            return 1
        print(json.dumps({**result, "ok": True}, ensure_ascii=False))
        return 0

    if not args.dry_run and changed:
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        ledger["updatedAt"] = now_iso()
        LEDGER_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
