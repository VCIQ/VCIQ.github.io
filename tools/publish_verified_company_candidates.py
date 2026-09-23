#!/usr/bin/env python3
"""Verify candidate profiles before staging a company-publication transaction.

A per-company crawl failure is a private hold, not permission to publish a partial
profile and not a reason to discard verified peers. Existing identity, evidence,
profile-status and global quality gates remain mandatory. No output file is
written until the complete proposed transaction passes those gates. The workflow
then validates the application and commits all outputs together.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlsplit

try:
    from . import onboard_company_candidates as onboarding
    from .crawl_venture_profiles import DEFAULT_USER_AGENT, OUTPUT_PATH, crawl_company, evaluate_quality
    from .ensure_venture_profile_coverage import build_repaired_snapshot, ensure_catalog_coverage
    from .venture_profile_extraction import CatalogCompany, CatalogInstitution, parse_catalog
except ImportError:
    import onboard_company_candidates as onboarding
    from crawl_venture_profiles import DEFAULT_USER_AGENT, OUTPUT_PATH, crawl_company, evaluate_quality
    from ensure_venture_profile_coverage import build_repaired_snapshot, ensure_catalog_coverage
    from venture_profile_extraction import CatalogCompany, CatalogInstitution, parse_catalog

Crawler = Callable[[CatalogCompany, str, int, dict[str, Any] | None], tuple[dict[str, Any], dict[str, Any]]]


def company_specs(registry: dict[str, Any]) -> list[CatalogCompany]:
    """Project the prospective registry without temporarily changing files."""
    return [
        CatalogCompany(
            slug=row["slug"], name=row["name"], english_name=row.get("englishName", ""),
            region=row.get("region", ""), sector=row.get("sector", ""),
            stage=row.get("stage", ""), status=row.get("status", ""),
            summary=row.get("summary", ""), product=row.get("product", ""),
            source_name=row.get("source", {}).get("name") or row["name"],
            source_url=row.get("source", {}).get("url", ""),
        )
        for row in registry["companies"]
    ]


def profile_error(company: CatalogCompany, profile: Any, status: Any) -> str:
    """Keep the existing onboarding gate; partial is deliberately not accepted."""
    if not isinstance(profile, dict) or not isinstance(status, dict):
        return "formal crawl did not return a profile and runtime status"
    if profile.get("slug") != company.slug or profile.get("name") != company.name:
        return "formal profile identity does not match the registry"
    if profile.get("status") not in {"ok", "retained", "fallback"}:
        return f"formal profile status is {profile.get('status')!r}; verification incomplete"
    if (status.get("kind"), status.get("slug"), status.get("status")) != (
        "company", company.slug, profile.get("status")
    ):
        return "formal profile and runtime status disagree"
    if not (profile.get("background") or profile.get("projectBackground")):
        return "formal profile has no background evidence"
    sources = profile.get("sources")
    if not isinstance(sources, list) or not sources or any(not isinstance(row, dict) for row in sources):
        return "formal profile has no usable source evidence"
    try:
        official_host = (urlsplit(company.source_url).hostname or "").lower()
        hosts = [(urlsplit(str(row.get("url", ""))).hostname or "").lower() for row in sources]
        if not official_host or not any(
            host and (host == official_host or host.endswith("." + official_host)
                      or official_host.endswith("." + host))
            for host in hosts
        ):
            return "formal profile has no source matching the verified official host"
        quality = evaluate_quality({company.slug: profile}, {}, 1, 0, [status])
    except (TypeError, ValueError, AttributeError) as error:
        return f"malformed formal evidence: {type(error).__name__}: {error}"
    if not quality.get("passed"):
        return "formal profile quality gate failed: " + json.dumps(quality, ensure_ascii=False)
    return ""


def verified_transaction(
    candidates: dict[str, Any], decisions: dict[str, Any], registry: dict[str, Any],
    official_sources: dict[str, Any], snapshot: dict[str, Any],
    institutions: Sequence[CatalogInstitution], *, crawler: Crawler | None = None,
    now: datetime | None = None, user_agent: str = DEFAULT_USER_AGENT, max_pages: int = 6,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return fully validated outputs; never mutate inputs or persist partial work."""
    now = now or datetime.now(UTC)
    timestamp = onboarding.now_iso(now)
    registry = onboarding.normalize_registry(registry)
    registry_errors = onboarding.validate_registry(registry)
    if registry_errors:
        raise ValueError("invalid existing registry: " + "; ".join(registry_errors))
    base_companies, _, _, base_quality, _ = ensure_catalog_coverage(
        snapshot, company_specs(registry), institutions, updated_at=timestamp,
    )
    if not base_quality.get("passed"):
        raise ValueError("existing profile quality gate failed: " + json.dumps(base_quality, ensure_ascii=False))

    next_decisions = onboarding.normalize_decisions(decisions)
    _, proposed_registry, _, proposed_report = onboarding.process_onboarding(
        candidates, next_decisions, registry, official_sources, now=now,
    )
    if proposed_report["failedCount"]:
        raise ValueError("onboarding request validation failed: " + json.dumps(proposed_report, ensure_ascii=False))

    crawl = crawler or crawl_company
    proposed_by_slug = {row["slug"]: row for row in proposed_registry["companies"]}
    specs = {row.slug: row for row in company_specs(proposed_registry)}
    verified: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    holds: list[dict[str, str]] = []
    for slug in proposed_report["publishedSlugs"]:
        company = specs[slug]
        key = proposed_by_slug[slug]["onboarding"]["candidateKey"]
        try:
            profile, runtime_status = crawl(company, user_agent, max_pages, copy.deepcopy(base_companies.get(slug)))
        except Exception as error:
            reason = f"formal crawl failed: {type(error).__name__}: {error}"
        else:
            reason = profile_error(company, profile, runtime_status)
            if not reason:
                verified[slug] = (copy.deepcopy(profile), copy.deepcopy(runtime_status))
                continue
        # Preserve human acceptance, reviewed fingerprint and requested profile.
        # attemptedAt participates in the existing never-attempted-first rotation.
        decision = next_decisions["decisions"][key]
        decision["onboarding"].update({
            "status": "awaiting_profile", "attemptedAt": timestamp,
            "publishedAt": "", "publishedSlug": "", "error": reason[:1000],
        })
        holds.append({"candidateKey": key, "slug": slug, "reason": reason[:1000]})

    next_decisions, next_registry, next_sources, report = onboarding.process_onboarding(
        candidates, next_decisions, registry, official_sources, now=now,
    )
    if report["failedCount"] or set(report["publishedSlugs"]) != set(verified):
        raise ValueError("verified onboarding transaction changed unexpectedly")

    proposed_snapshot = copy.deepcopy(snapshot)
    proposed_snapshot.setdefault("companies", {}).update({slug: pair[0] for slug, pair in verified.items()})
    statuses = {
        (row.get("kind"), row.get("slug")): copy.deepcopy(row)
        for row in proposed_snapshot.get("sourceStatus", []) if isinstance(row, dict)
    }
    for slug, (_, runtime_status) in verified.items():
        statuses[("company", slug)] = runtime_status
    proposed_snapshot["sourceStatus"] = list(statuses.values())
    companies, institution_profiles, statuses, quality, _ = ensure_catalog_coverage(
        proposed_snapshot, company_specs(next_registry), institutions, updated_at=timestamp,
    )
    if not quality.get("passed"):
        raise ValueError("proposed profile quality gate failed: " + json.dumps(quality, ensure_ascii=False))
    next_snapshot = build_repaired_snapshot(
        snapshot, companies, institution_profiles, statuses, quality, generated_at=timestamp,
    )
    report.update({"heldCount": len(holds), "holds": holds, "verifiedProfileCount": len(verified)})
    return next_decisions, next_registry, next_sources, next_snapshot, report


def read_object(path: Path) -> dict[str, Any]:
    """Malformed or missing production inputs must not silently become empty data."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=onboarding.CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=onboarding.DECISIONS_PATH)
    parser.add_argument("--registry", type=Path, default=onboarding.REGISTRY_PATH)
    parser.add_argument("--official-sources", type=Path, default=onboarding.OFFICIAL_SOURCES_PATH)
    parser.add_argument("--snapshot", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=onboarding.REPORT_PATH)
    parser.add_argument("--catalog", type=Path, default=onboarding.CATALOG_PATH)
    parser.add_argument("--max-pages", type=int, default=6)
    args = parser.parse_args(argv)
    if not 1 <= args.max_pages <= 20:
        parser.error("--max-pages must be between 1 and 20")
    try:
        _, institutions = parse_catalog(args.catalog.read_text(encoding="utf-8"))
        if not institutions:
            raise ValueError("catalog parser found no institutions")
        outputs = verified_transaction(
            read_object(args.candidates), read_object(args.decisions), read_object(args.registry),
            read_object(args.official_sources), read_object(args.snapshot), institutions,
            user_agent=os.environ.get("VENTURE_PROFILE_USER_AGENT", "").strip() or DEFAULT_USER_AGENT,
            max_pages=args.max_pages,
        )
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"failedCount": 1, "changed": False, "error": str(error)}, ensure_ascii=False))
        return 1
    # All computations above are in memory. A subsequent application/check failure
    # still prevents the workflow's single repository commit, preserving fail-closed.
    decisions, registry, sources, snapshot, report = outputs
    onboarding.write_json(args.decisions, decisions)
    onboarding.write_registry(args.registry, registry)
    onboarding.write_json(args.official_sources, sources)
    onboarding.write_json(args.snapshot, snapshot)
    onboarding.write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
