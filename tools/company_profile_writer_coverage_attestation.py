"""Offline, exact-data attestation of a pre-crawl catalog coverage repair.

The inputs must be obtained independently from the same pinned Git base and
the actual pre-crawl coverage step.  This module neither reads local files
nor contacts GitHub or source websites.  It does not authorize a PR, merge,
publication, or a production write.

Only additive missing-company fallback repair is eligible here. Institution
additions, deletion/replacement of existing profiles, and arbitrary metadata
changes remain blocked until separately designed review gates exist.
"""
from __future__ import annotations

import copy
from datetime import datetime

from .ensure_venture_profile_coverage import (
    build_repaired_snapshot, ensure_catalog_coverage,
)
from .venture_profile_extraction import parse_catalog
from .company_profile_writer_pinned_catalog import (
    PinnedCatalogError, pinned_catalog,
)
from .company_profile_writer_transition_gate import (
    MAX_RUN_DURATION, TransitionError, _stamp,
)


class CoverageError(ValueError):
    """Fixed codes only; never quote the underlying data or source URLs."""


def attest_coverage(
    base_profiles: dict,
    observed_profiles: dict,
    catalog: str,
    report: dict,
    *,
    updated_at: str,
    run_started_at: str,
    run_completed_at: str,
    registry_ts: str | None = None,
    registry: dict | None = None,
) -> dict:
    """Recompute the official pre-crawl repair and compare it exactly.

    `report` is the bounded JSON output of ensure_venture_profile_coverage,
    including the `changed` field.  The verified output is intentionally
    not an authorization to use any external data or to publish.
    """
    if (not isinstance(base_profiles, dict)
        or not isinstance(observed_profiles, dict)
        or not isinstance(report, dict)
        or not isinstance(catalog, str)):
        raise CoverageError("COVERAGE_INPUT_INVALID")
    try:
        started = _stamp(run_started_at)
        ended = _stamp(run_completed_at)
        repaired_at = _stamp(updated_at)
    except (TransitionError, TypeError):
        raise CoverageError("COVERAGE_TIME_INVALID") from None
    if (ended < started or ended - started > MAX_RUN_DURATION
        or not started <= repaired_at <= ended):
        raise CoverageError("COVERAGE_TIME_INVALID")

    try:
        companies, institutions = pinned_catalog(catalog, registry_ts, registry)
    except (PinnedCatalogError, ValueError, TypeError, RecursionError):
        raise CoverageError("COVERAGE_CATALOG_INVALID") from None
    if not companies or len({x.slug for x in companies}) != len(companies):
        raise CoverageError("COVERAGE_CATALOG_INVALID")
    if len({x.slug for x in institutions}) != len(institutions):
        raise CoverageError("COVERAGE_CATALOG_INVALID")
    if (not isinstance(base_profiles.get("companies"), dict)
        or not isinstance(base_profiles.get("institutions"), dict)
        or not isinstance(base_profiles.get("sourceStatus"), list)):
        raise CoverageError("COVERAGE_BASE_INVALID")

    try:
        comp, inst, statuses, quality, expected_report = ensure_catalog_coverage(
            copy.deepcopy(base_profiles), companies, institutions,
            updated_at=updated_at,
        )
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise CoverageError("COVERAGE_REBUILD_FAILED") from None
    if not quality.get("passed") or not expected_report.get("qualityPassed"):
        raise CoverageError("COVERAGE_QUALITY_FAILED")

    additions = expected_report["addedCompanies"]
    if (expected_report["addedInstitutions"]
        or set(base_profiles["companies"]) - {x.slug for x in companies}
        or set(base_profiles["institutions"]) - {x.slug for x in institutions}):
        raise CoverageError("COVERAGE_DELETIONS_OR_INSTITUTIONS_UNSUPPORTED")
    if len(additions) > 100 or len(set(additions)) != len(additions):
        raise CoverageError("COVERAGE_ADDITIONS_UNBOUNDED")
    if any(x in base_profiles["companies"] for x in additions):
        raise CoverageError("COVERAGE_REPLACEMENT_FORBIDDEN")
    missing = bool(additions or expected_report["addedStatuses"])
    expected_report = {**expected_report, "changed": missing}
    if report != expected_report:
        raise CoverageError("COVERAGE_REPORT_MISMATCH")

    expected_snapshot = (
        build_repaired_snapshot(
            copy.deepcopy(base_profiles), comp, inst, statuses, quality,
            generated_at=updated_at,
        ) if missing else base_profiles
    )
    if observed_profiles != expected_snapshot:
        raise CoverageError("COVERAGE_SNAPSHOT_MISMATCH")
    for slug, value in base_profiles["companies"].items():
        if observed_profiles["companies"].get(slug) != value:
            raise CoverageError("COVERAGE_REPLACEMENT_FORBIDDEN")
    return {
        "ok": True,
        "addedCompanySlugs": tuple(additions),
        "companyCount": len(comp),
        "needsReview": True,
        "mergeAuthorized": False,
        "publicationAuthorized": False,
    }
