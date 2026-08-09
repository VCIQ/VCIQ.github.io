#!/usr/bin/env python3
"""Promote reviewed company candidates into formal startup profiles.

A review decision alone is not enough to create a route.  Publication requires a
versioned onboarding request containing a canonical company identity, official
homepage and the evidence fingerprint that was reviewed.  Successful requests add
the company to the machine-readable registry, register official crawl sources,
create a transparent venture-profile fallback, and mark the decision ``published``.

``merged`` decisions are also reconciled automatically: candidate aliases are added
to the existing registry and official source entry without creating a duplicate page.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from .company_registry import (
        CATALOG_PATH,
        REGISTRY_PATH,
        clean,
        load_json,
        normalize_company,
        normalize_registry,
        public_http_url,
        unique,
        validate_registry,
        write_registry,
    )
    from .ensure_venture_profile_coverage import repair_snapshot
    from .resolve_company_entities import normalize_identity
except ImportError:
    from company_registry import (
        CATALOG_PATH,
        REGISTRY_PATH,
        clean,
        load_json,
        normalize_company,
        normalize_registry,
        public_http_url,
        unique,
        validate_registry,
        write_registry,
    )
    from ensure_venture_profile_coverage import repair_snapshot
    from resolve_company_entities import normalize_identity

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "config" / "company_candidate_review_queue.json"
DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"
OFFICIAL_SOURCES_PATH = ROOT / "config" / "official_company_sources.json"
REPORT_PATH = ROOT / "config" / "company_candidate_onboarding_state.json"
VALID_REVIEW_STATUSES = {"pending", "accepted", "rejected", "merged", "published"}
VALID_ONBOARDING_STATUSES = {
    "awaiting_profile",
    "requested",
    "published",
    "failed",
    "merged",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def decision_key(value: Any) -> str:
    return normalize_identity(clean(value, 160))


def candidate_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in payload.get("candidates", []):
        if not isinstance(raw, dict):
            continue
        key = decision_key(raw.get("decisionKey"))
        if key:
            result[key] = raw
    return result


def evidence_fingerprint(candidate: dict[str, Any]) -> str:
    payload = {
        "decisionKey": decision_key(candidate.get("decisionKey")),
        "score": max(0, min(100, int(candidate.get("score", 0) or 0))),
        "articleCount": max(0, int(candidate.get("articleCount", 0) or 0)),
        "sourceCount": max(0, int(candidate.get("sourceCount", 0) or 0)),
        "sourceArticleIds": sorted(
            clean(value, 300) for value in candidate.get("sourceArticleIds", []) if clean(value, 300)
        ),
        "sourceUrls": sorted(
            clean(value, 2_000) for value in candidate.get("sourceUrls", []) if clean(value, 2_000)
        ),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def normalize_profile(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    status = clean(row.get("status"), 40)
    if status not in {"运营中", "已上市"}:
        status = "运营中"
    aliases = unique(row.get("aliases") or [], 30)
    news_urls = unique(
        [public_http_url(url) for url in (row.get("newsUrls") or [])],
        20,
    )
    return {
        "slug": clean(row.get("slug"), 120).casefold(),
        "name": clean(row.get("name"), 240),
        "englishName": clean(row.get("englishName"), 240),
        "region": clean(row.get("region"), 80),
        "sector": clean(row.get("sector"), 120),
        "stage": clean(row.get("stage"), 80),
        "status": status,
        "founded": clean(row.get("founded"), 40),
        "headquarters": clean(row.get("headquarters"), 160),
        "summary": clean(row.get("summary"), 1_200),
        "product": clean(row.get("product"), 1_200),
        "homepage": public_http_url(row.get("homepage")),
        "newsUrls": news_urls,
        "aliases": aliases,
        "confidence": max(0.5, min(1.0, float(row.get("confidence", 0.9) or 0.9))),
    }


def validate_profile(profile: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not SLUG_RE.fullmatch(profile["slug"]):
        errors.append("invalid company slug")
    if len(profile["name"]) < 2:
        errors.append("canonical company name is required")
    if not profile["region"]:
        errors.append("region is required")
    if not profile["sector"]:
        errors.append("sector is required")
    if not profile["stage"]:
        errors.append("stage is required")
    if len(profile["summary"]) < 20:
        errors.append("summary must contain at least 20 characters")
    if len(profile["product"]) < 6:
        errors.append("product description must contain at least 6 characters")
    if not profile["homepage"]:
        errors.append("official homepage is required")

    candidate_name = clean(candidate.get("name"), 240)
    event_types = {clean(value, 80) for value in candidate.get("eventTypes", [])}
    if event_types == {"人物观点"} and normalize_identity(profile["name"]) == normalize_identity(candidate_name):
        errors.append("person-only candidate must be mapped to a canonical company entity")

    try:
        homepage_host = urlsplit(profile["homepage"]).hostname or ""
    except ValueError:
        homepage_host = ""
    if not homepage_host:
        errors.append("official homepage host is invalid")
    return errors


def normalize_decisions(payload: Any) -> dict[str, Any]:
    root = payload if isinstance(payload, dict) else {}
    raw_decisions = root.get("decisions") if isinstance(root.get("decisions"), dict) else {}
    decisions: dict[str, dict[str, Any]] = {}
    for raw_key, raw in raw_decisions.items():
        if not isinstance(raw, dict):
            continue
        key = decision_key(raw_key)
        status = clean(raw.get("status"), 30)
        if not key or status not in VALID_REVIEW_STATUSES:
            continue
        row = {
            "status": status,
            "note": clean(raw.get("note"), 500),
            "mergedSlug": clean(raw.get("mergedSlug"), 120),
            "decidedAt": clean(raw.get("decidedAt"), 80),
            "reviewedBy": clean(raw.get("reviewedBy"), 120),
        }
        onboarding = raw.get("onboarding") if isinstance(raw.get("onboarding"), dict) else {}
        if onboarding:
            onboarding_status = clean(onboarding.get("status"), 40)
            row["onboarding"] = {
                "status": onboarding_status
                if onboarding_status in VALID_ONBOARDING_STATUSES
                else "awaiting_profile",
                "mode": clean(onboarding.get("mode"), 20) or "create",
                "profile": normalize_profile(onboarding.get("profile")),
                "evidenceFingerprint": clean(onboarding.get("evidenceFingerprint"), 10_000),
                "requestedAt": clean(onboarding.get("requestedAt"), 80),
                "requestedBy": clean(onboarding.get("requestedBy"), 120),
                "publishedAt": clean(onboarding.get("publishedAt"), 80),
                "publishedSlug": clean(onboarding.get("publishedSlug"), 120),
                "error": clean(onboarding.get("error"), 1_000),
            }
        decisions[key] = row
    return {
        "schemaVersion": max(1, int(root.get("schemaVersion", 1) or 1)),
        "decisions": decisions,
    }


def official_source_entry(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": profile["slug"],
        "name": profile["name"],
        "region": profile["region"],
        "sector": profile["sector"],
        "homepage": profile["homepage"],
        "newsUrls": profile["newsUrls"] or [profile["homepage"]],
        "aliases": unique([profile["name"], profile["englishName"], *profile["aliases"]], 30),
        "articleUrlPatterns": [],
        "maxItems": 6,
        "maxAgeDays": 1095,
    }


def merge_official_source(payload: dict[str, Any], entry: dict[str, Any]) -> None:
    rows = payload.get("companies") if isinstance(payload.get("companies"), list) else []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict) or clean(raw.get("slug"), 120) != entry["slug"]:
            continue
        merged = deepcopy(raw)
        merged.update({key: value for key, value in entry.items() if value not in ("", [])})
        merged["aliases"] = unique([*(raw.get("aliases") or []), *entry["aliases"]], 40)
        merged["newsUrls"] = unique([*(raw.get("newsUrls") or []), *entry["newsUrls"]], 30)
        rows[index] = merged
        payload["companies"] = rows
        return
    rows.append(entry)
    payload["companies"] = rows


def add_aliases_to_existing(
    registry: dict[str, Any],
    official_sources: dict[str, Any],
    slug: str,
    candidate: dict[str, Any],
) -> bool:
    aliases = unique([candidate.get("name"), *(candidate.get("aliases") or [])], 30)
    changed = False
    target = next((row for row in registry["companies"] if row["slug"] == slug), None)
    if target is None:
        raise ValueError(f"merged company slug {slug!r} is not in company registry")
    next_aliases = unique([*target.get("aliases", []), *aliases], 50)
    if next_aliases != target.get("aliases", []):
        target["aliases"] = next_aliases
        changed = True
    for source in official_sources.get("companies", []):
        if isinstance(source, dict) and clean(source.get("slug"), 120) == slug:
            source_aliases = unique([*(source.get("aliases") or []), *aliases], 50)
            if source_aliases != source.get("aliases", []):
                source["aliases"] = source_aliases
                changed = True
            break
    return changed


def seed_shopify_request(
    decisions: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    *,
    now: str,
) -> bool:
    key = decision_key("shopify")
    decision = decisions["decisions"].get(key)
    candidate = candidates.get(key)
    if not decision or not candidate or decision.get("status") != "accepted":
        return False
    onboarding = decision.get("onboarding") if isinstance(decision.get("onboarding"), dict) else {}
    if onboarding.get("status") in {"requested", "published"}:
        return False
    decision["onboarding"] = {
        "status": "requested",
        "mode": "create",
        "profile": {
            "slug": "shopify",
            "name": "Shopify",
            "englishName": "Shopify",
            "region": "加拿大",
            "sector": "新消费",
            "stage": "已上市",
            "status": "已上市",
            "founded": "2006",
            "headquarters": "Ottawa, Canada",
            "summary": "为全球商家提供电商建站、支付、营销、线下零售和企业级商业基础设施。",
            "product": "Shopify 商业平台、在线商店、Shopify Payments、Shop Pay、POS 与企业级商业工具。",
            "homepage": "https://www.shopify.com/news/about-us",
            "newsUrls": [
                "https://www.shopify.com/news",
                "https://www.shopify.com/news/category/product-news",
                "https://www.shopify.com/investors",
            ],
            "aliases": ["Shopify Inc."],
            "confidence": 0.98,
        },
        "evidenceFingerprint": evidence_fingerprint(candidate),
        "requestedAt": now,
        "requestedBy": decision.get("reviewedBy") or "VCIQ",
        "publishedAt": "",
        "publishedSlug": "",
        "error": "",
    }
    return True


def process_onboarding(
    candidates_payload: dict[str, Any],
    decisions_payload: dict[str, Any],
    registry_payload: dict[str, Any],
    official_sources_payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    timestamp = now_iso(now)
    candidates = candidate_index(candidates_payload)
    decisions = normalize_decisions(decisions_payload)
    registry = normalize_registry(registry_payload)
    official_sources = deepcopy(official_sources_payload)
    if not isinstance(official_sources.get("companies"), list):
        official_sources["companies"] = []

    published_slugs: list[str] = []
    merged_slugs: list[str] = []
    awaiting_keys: list[str] = []
    failed: list[dict[str, str]] = []
    registry_by_slug = {row["slug"]: row for row in registry["companies"]}

    for key, decision in decisions["decisions"].items():
        candidate = candidates.get(key)
        status = decision.get("status")
        if status == "merged":
            if not candidate:
                continue
            slug = clean(decision.get("mergedSlug"), 120)
            existing_onboarding = (
                decision.get("onboarding")
                if isinstance(decision.get("onboarding"), dict)
                else {}
            )
            already_merged = (
                existing_onboarding.get("status") == "merged"
                and clean(existing_onboarding.get("publishedSlug"), 120) == slug
            )
            try:
                aliases_changed = add_aliases_to_existing(
                    registry, official_sources, slug, candidate
                )
            except ValueError as error:
                failed.append({"candidateKey": key, "error": str(error)})
                continue
            if already_merged and not aliases_changed:
                continue
            decision["onboarding"] = {
                "status": "merged",
                "mode": "merge",
                "profile": normalize_profile({}),
                "evidenceFingerprint": evidence_fingerprint(candidate),
                "requestedAt": (
                    clean(existing_onboarding.get("requestedAt"), 80)
                    or decision.get("decidedAt", "")
                ),
                "requestedBy": (
                    clean(existing_onboarding.get("requestedBy"), 120)
                    or decision.get("reviewedBy", "")
                ),
                "publishedAt": (
                    clean(existing_onboarding.get("publishedAt"), 80)
                    or timestamp
                ),
                "publishedSlug": slug,
                "error": "",
            }
            merged_slugs.append(slug)
            continue

        if status != "accepted":
            continue
        onboarding = decision.get("onboarding") if isinstance(decision.get("onboarding"), dict) else {}
        if onboarding.get("status") != "requested":
            awaiting_keys.append(key)
            continue
        if not candidate:
            failed.append({"candidateKey": key, "error": "candidate is absent from current review snapshot"})
            continue
        expected = clean(onboarding.get("evidenceFingerprint"), 10_000)
        actual = evidence_fingerprint(candidate)
        if not expected or expected != actual:
            failed.append({"candidateKey": key, "error": "candidate evidence changed after review"})
            continue
        profile = normalize_profile(onboarding.get("profile"))
        errors = validate_profile(profile, candidate)
        if profile["slug"] in registry_by_slug:
            existing = registry_by_slug[profile["slug"]]
            onboarding_source = existing.get("onboarding") if isinstance(existing.get("onboarding"), dict) else {}
            if onboarding_source.get("candidateKey") != key:
                errors.append("company slug already belongs to another registry entity; use merge")
        if errors:
            failed.append({"candidateKey": key, "error": "; ".join(errors)})
            continue

        company = normalize_company(
            {
                **profile,
                "source": {
                    "name": profile["name"],
                    "url": profile["homepage"],
                    "level": "官方披露",
                },
                "aliases": unique(
                    [
                        profile["name"],
                        profile["englishName"],
                        *profile["aliases"],
                        candidate.get("name"),
                        *(candidate.get("aliases") or []),
                    ],
                    50,
                ),
                "registrySource": "reviewed-candidate-onboarding",
                "onboarding": {
                    "candidateKey": key,
                    "reviewedBy": decision.get("reviewedBy", ""),
                    "decidedAt": decision.get("decidedAt", ""),
                    "publishedAt": timestamp,
                    "evidenceFingerprint": actual,
                },
            }
        )
        if profile["slug"] not in registry_by_slug:
            registry["companies"].append(company)
            registry_by_slug[profile["slug"]] = company
        merge_official_source(official_sources, official_source_entry(profile))
        decision["status"] = "published"
        decision["mergedSlug"] = profile["slug"]
        decision["onboarding"] = {
            **onboarding,
            "status": "published",
            "profile": profile,
            "publishedAt": timestamp,
            "publishedSlug": profile["slug"],
            "error": "",
        }
        published_slugs.append(profile["slug"])

    if failed:
        for item in failed:
            decision = decisions["decisions"].get(item["candidateKey"])
            if not decision:
                continue
            onboarding = decision.get("onboarding") if isinstance(decision.get("onboarding"), dict) else {}
            decision["onboarding"] = {
                **onboarding,
                "status": "failed",
                "error": item["error"],
            }

    registry = normalize_registry(registry)
    registry_errors = validate_registry(registry)
    if registry_errors:
        raise ValueError("; ".join(registry_errors[:20]))
    report = {
        "schemaVersion": 1,
        "generatedAt": timestamp,
        "publishedCount": len(set(published_slugs)),
        "publishedSlugs": sorted(set(published_slugs)),
        "mergedCount": len(set(merged_slugs)),
        "mergedSlugs": sorted(set(merged_slugs)),
        "awaitingProfileCount": len(set(awaiting_keys)),
        "awaitingProfileKeys": sorted(set(awaiting_keys)),
        "failedCount": len(failed),
        "failures": failed,
        "registryCompanyCount": len(registry["companies"]),
    }
    return decisions, registry, official_sources, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--official-sources", type=Path, default=OFFICIAL_SOURCES_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--seed-shopify", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    candidates_payload = load_json(args.candidates, {"candidates": []})
    decisions_payload = normalize_decisions(load_json(args.decisions, {"decisions": {}}))
    candidates = candidate_index(candidates_payload)
    timestamp = now_iso()
    seeded = False
    if args.seed_shopify:
        seeded = seed_shopify_request(decisions_payload, candidates, now=timestamp)

    next_decisions, next_registry, next_official, report = process_onboarding(
        candidates_payload,
        decisions_payload,
        load_json(args.registry, {"companies": []}),
        load_json(args.official_sources, {"companies": []}),
    )
    report["seededShopify"] = seeded

    if args.check:
        if report["failedCount"]:
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 1
        current_report = load_json(args.report, {})
        current_decisions = normalize_decisions(load_json(args.decisions, {}))
        current_registry = normalize_registry(load_json(args.registry, {}))
        if current_decisions != next_decisions or current_registry != next_registry:
            raise SystemExit("company candidate onboarding outputs are not current")
        if current_report and current_report.get("failedCount", 0):
            raise SystemExit("stored onboarding report contains failures")
        print(json.dumps({**report, "valid": True}, ensure_ascii=False, sort_keys=True))
        return 0

    write_json(args.decisions, next_decisions)
    write_registry(args.registry, next_registry)
    write_json(args.official_sources, next_official)
    repair_snapshot(catalog_path=args.catalog, check=False)
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report["failedCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
