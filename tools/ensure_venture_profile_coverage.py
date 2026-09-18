#!/usr/bin/env python3
"""Repair missing catalog profiles before a partial venture refresh.

A partial company crawl still passes the repository's global quality gate. When
new catalog entities were added after the last full profile refresh, the current
snapshot can temporarily contain fewer profiles than the catalog. This module
adds transparent fallback skeletons for only those missing entities, retains all
existing evidence, and then applies the unchanged global coverage gate.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

try:
    from .crawl_venture_profiles import (
        CATALOG_PATH,
        OUTPUT_PATH,
        accepted_section_count,
        build_company_profile,
        build_institution_profile,
        evaluate_quality,
        load_snapshot,
        sanitize_product_items,
        sanitize_team_members,
        write_snapshot,
    )
    from .venture_profile_extraction import CatalogCompany, CatalogInstitution, parse_catalog
except ImportError:
    from crawl_venture_profiles import (
        CATALOG_PATH,
        OUTPUT_PATH,
        accepted_section_count,
        build_company_profile,
        build_institution_profile,
        evaluate_quality,
        load_snapshot,
        sanitize_product_items,
        sanitize_team_members,
        write_snapshot,
    )
    from venture_profile_extraction import CatalogCompany, CatalogInstitution, parse_catalog


def _status_key(value: dict[str, Any]) -> tuple[str, str]:
    return str(value.get("kind", "")), str(value.get("slug", ""))


def _fallback_status(
    kind: str,
    slug: str,
    name: str,
    profile: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "slug": slug,
        "name": name,
        "status": str(profile.get("status") or "fallback"),
        "fetchedPages": 0,
        "acceptedSections": accepted_section_count(profile, kind),
        "retainedPrevious": False,
        "elapsedSeconds": 0.0,
        "error": reason,
    }


def ensure_catalog_coverage(
    snapshot: dict[str, Any],
    companies: Sequence[CatalogCompany],
    institutions: Sequence[CatalogInstitution],
    *,
    updated_at: str,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    company_slugs = {company.slug for company in companies}
    institution_slugs = {institution.slug for institution in institutions}

    raw_companies = snapshot.get("companies", {})
    raw_institutions = snapshot.get("institutions", {})
    company_profiles = (
        {
            slug: copy.deepcopy(profile)
            for slug, profile in raw_companies.items()
            if slug in company_slugs and isinstance(profile, dict)
        }
        if isinstance(raw_companies, dict)
        else {}
    )
    institution_profiles = (
        {
            slug: copy.deepcopy(profile)
            for slug, profile in raw_institutions.items()
            if slug in institution_slugs and isinstance(profile, dict)
        }
        if isinstance(raw_institutions, dict)
        else {}
    )

    raw_statuses = snapshot.get("sourceStatus", [])
    status_map: dict[tuple[str, str], dict[str, Any]] = {}
    if isinstance(raw_statuses, list):
        for raw in raw_statuses:
            if not isinstance(raw, dict):
                continue
            key = _status_key(raw)
            if key[0] not in {"company", "institution"} or not key[1]:
                continue
            status_map[key] = copy.deepcopy(raw)

    added_companies: list[str] = []
    added_institutions: list[str] = []
    added_statuses: list[str] = []

    for company in companies:
        if company.slug not in company_profiles:
            profile = build_company_profile(
                company,
                [],
                ["目录已收录，但尚未完成首次公开页面档案抓取。"],
                updated_at,
            )
            # ``crawl_company`` applies these semantic guards after building a
            # profile. Coverage fallbacks bypass that crawler path, so mirror the
            # same guards here or a newly onboarded company's fallback can fail
            # the global semantic-noise gate before its first partial crawl runs.
            profile["team"] = sanitize_team_members(
                profile.get("team", []), company.aliases
            )
            profile["products"] = sanitize_product_items(
                profile.get("products", [])
            )
            company_profiles[company.slug] = profile
            added_companies.append(company.slug)
        key = ("company", company.slug)
        if key not in status_map:
            status_map[key] = _fallback_status(
                "company",
                company.slug,
                company.name,
                company_profiles[company.slug],
                "coverage fallback created before a partial company refresh",
            )
            added_statuses.append(f"company:{company.slug}")

    for institution in institutions:
        if institution.slug not in institution_profiles:
            profile = build_institution_profile(
                institution,
                [],
                companies,
                ["目录已收录，但尚未完成首次公开页面档案抓取。"],
                updated_at,
            )
            institution_profiles[institution.slug] = profile
            added_institutions.append(institution.slug)
        key = ("institution", institution.slug)
        if key not in status_map:
            status_map[key] = _fallback_status(
                "institution",
                institution.slug,
                institution.name,
                institution_profiles[institution.slug],
                "coverage fallback created before a partial institution refresh",
            )
            added_statuses.append(f"institution:{institution.slug}")

    statuses = sorted(
        status_map.values(),
        key=lambda item: (
            0 if item.get("kind") == "company" else 1,
            str(item.get("slug", "")),
        ),
    )
    quality = evaluate_quality(
        company_profiles,
        institution_profiles,
        len(companies),
        len(institutions),
        statuses,
    )
    report = {
        "addedCompanies": added_companies,
        "addedInstitutions": added_institutions,
        "addedStatuses": added_statuses,
        "companyCoverage": len(company_profiles),
        "institutionCoverage": len(institution_profiles),
        "runtimeStatusCoverage": len(statuses),
        "qualityPassed": bool(quality.get("passed")),
    }
    return company_profiles, institution_profiles, statuses, quality, report


def build_repaired_snapshot(
    previous: dict[str, Any],
    company_profiles: dict[str, dict[str, Any]],
    institution_profiles: dict[str, dict[str, Any]],
    statuses: Sequence[dict[str, Any]],
    quality: dict[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    """Return a standard venture snapshot while preserving unrelated metadata."""
    payload = copy.deepcopy(previous)
    payload.update(
        {
            "schemaVersion": max(1, int(previous.get("schemaVersion", 1) or 1)),
            "generatedAt": generated_at,
            "companies": dict(sorted(company_profiles.items())),
            "institutions": dict(sorted(institution_profiles.items())),
            "sourceStatus": list(statuses),
            "qualityGate": quality,
        }
    )
    return payload


def repair_snapshot(
    *,
    catalog_path: Path = CATALOG_PATH,
    snapshot_path: Path = OUTPUT_PATH,
    check: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    companies, institutions = parse_catalog(catalog_path.read_text(encoding="utf-8"))
    snapshot = load_snapshot(snapshot_path)
    updated_at = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat()
    company_profiles, institution_profiles, statuses, quality, report = ensure_catalog_coverage(
        snapshot,
        companies,
        institutions,
        updated_at=updated_at,
    )

    if not quality.get("passed"):
        return {**report, "changed": False}

    missing = bool(
        report["addedCompanies"]
        or report["addedInstitutions"]
        or report["addedStatuses"]
    )
    changed = False
    if not check and missing:
        payload = build_repaired_snapshot(
            snapshot,
            company_profiles,
            institution_profiles,
            statuses,
            quality,
            generated_at=updated_at,
        )
        changed = write_snapshot(payload, snapshot, snapshot_path)

    return {**report, "changed": changed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--snapshot", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    report = repair_snapshot(
        catalog_path=args.catalog,
        snapshot_path=args.snapshot,
        check=args.check,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("qualityPassed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
