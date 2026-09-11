#!/usr/bin/env python3
"""Evidence contract v2 annotations for Research Agent.

The existing evidence policy decides whether a row is usable and which publication
layer it belongs to. This wrapper adds two orthogonal dimensions without relaxing
that gate:

1. verificationStatus: candidate / auto_verified / cross_verified / reviewed /
   rejected. Publication eligibility is therefore no longer presented as a proxy
   for human-confirmed truth.
2. explicit temporal semantics: eventDate / pageCreatedAt / pageUpdatedAt /
   observedAt plus dateSource/dateConfidence. Legacy ``publishedAt`` is preserved
   for compatibility but is treated as an ambiguous source timestamp, never
   silently promoted to an event date.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping


_ORIGINAL_GENERATE_REPORT: Any = None
_INSTALLED_AGENT_ID: int | None = None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _verification_status(row: Mapping[str, Any]) -> str:
    review_status = _text(row.get("reviewStatus"))
    if (
        review_status == "rejected"
        or _text(row.get("qualityStatus")) == "rejected"
        or _text(row.get("publicationTier")) == "rejected"
    ):
        return "rejected"
    if review_status in {"reviewed", "approved"}:
        return "reviewed"

    explicit = _text(row.get("verificationStatus"))
    if explicit:
        return explicit

    if (
        _text(row.get("publicationTier")) == "verified_change"
        and _text(row.get("qualityStatus")) == "passed"
        and _text(row.get("supportStatus")) == "supports"
    ):
        return "auto_verified"
    return "candidate"


def _temporal_contract(row: MutableMapping[str, Any], observed_at: str) -> None:
    """Attach time semantics without guessing an event date from legacy fields."""

    if not _text(row.get("observedAt")) and observed_at:
        row["observedAt"] = observed_at

    if _text(row.get("dateSource")):
        if not _text(row.get("dateConfidence")):
            row["dateConfidence"] = "unknown"
        return

    if _text(row.get("eventDate")):
        row["dateSource"] = "event_date"
        row.setdefault("dateConfidence", "high")
        return
    if _text(row.get("pageUpdatedAt")):
        row["dateSource"] = "page_updated_at"
        row.setdefault("dateConfidence", "high")
        return
    if _text(row.get("pageCreatedAt")):
        row["dateSource"] = "page_created_at"
        row.setdefault("dateConfidence", "high")
        return
    if _text(row.get("publishedAt")):
        # Historical producers overloaded publishedAt with page, record, quote,
        # and source timestamps. Preserve it, but explicitly mark the semantics
        # as unresolved so the UI cannot call it the event date.
        row["dateSource"] = "legacy_published_at"
        row.setdefault("dateConfidence", "unknown")
        return
    if _text(row.get("observedAt")):
        row["dateSource"] = "observed_at"
        row.setdefault("dateConfidence", "high")


def annotate_report(report: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Upgrade an already-generated report in place to evidence contract v2."""

    report["evidenceContractVersion"] = 2
    observed_at = _text(report.get("generatedAt"))
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        return report

    for raw_row in evidence:
        if not isinstance(raw_row, MutableMapping):
            continue
        raw_row["verificationStatus"] = _verification_status(raw_row)
        _temporal_contract(raw_row, observed_at)
    return report


def generate_report(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    report, snapshot = _ORIGINAL_GENERATE_REPORT(*args, **kwargs)
    if isinstance(report, MutableMapping):
        annotate_report(report)
    return report, snapshot


def install_evidence_contract(agent: Any) -> None:
    """Install the v2 annotation wrapper once, outside the strict evidence gate."""

    global _ORIGINAL_GENERATE_REPORT, _INSTALLED_AGENT_ID
    if _INSTALLED_AGENT_ID == id(agent):
        return
    _ORIGINAL_GENERATE_REPORT = agent.generate_report
    agent.generate_report = generate_report
    _INSTALLED_AGENT_ID = id(agent)
