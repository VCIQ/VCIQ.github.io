#!/usr/bin/env python3
"""Strict STAR Market prospectus crawler entry point.

The network, retention and privacy implementation remains in
``crawl_star_market_investors_legacy``. This entry point replaces only the
shareholder extraction and validation layer: public candidates must come from an
explicit pre/post-IPO shareholder table row, and legal names must be resolved by
the prospectus definitions or the shareholder's own basic-information block.
"""

from __future__ import annotations

import re
from typing import Any

try:
    from . import crawl_star_market_investors_legacy as legacy
    from . import star_market_prospectus_parser as prospectus_parser
except ImportError:
    import crawl_star_market_investors_legacy as legacy
    import star_market_prospectus_parser as prospectus_parser

# CNINFO's resilient transport now exposes ordered endpoint tuples. The legacy STAR
# network layer still resolves the pre-refactor scalar names, so retain those names
# as aliases for the preferred HTTPS endpoints until that layer is migrated.
if not hasattr(legacy.cninfo, "STOCK_LIST_URL"):
    legacy.cninfo.STOCK_LIST_URL = legacy.cninfo.STOCK_LIST_URLS[0]
if not hasattr(legacy.cninfo, "QUERY_URL"):
    legacy.cninfo.QUERY_URL = legacy.cninfo.QUERY_URLS[0]

# Re-export the stable crawler API used by tests and downstream tools.
for _name in dir(legacy):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(legacy, _name))

_legacy_validate_snapshot = legacy.validate_snapshot


def extract_institutional_investors(
    pages: list[legacy.PdfPage],
    company_name: str,
    *,
    max_investors: int,
) -> list[dict[str, Any]]:
    return prospectus_parser.extract_institutional_investors(
        pages,
        company_name,
        max_investors=max_investors,
    )


def extract_issuer_contact(
    pages: list[legacy.PdfPage],
    company_name: str,
) -> dict[str, Any]:
    # Issuer IR contact is not an institutional-shareholder contact and is not
    # needed by this directory. Keeping the fields empty avoids scope confusion.
    return {}


def validate_snapshot(
    snapshot: dict[str, Any],
    *,
    require_companies: bool = False,
) -> list[str]:
    errors = list(
        _legacy_validate_snapshot(snapshot, require_companies=require_companies)
    )
    companies = snapshot.get("companies")
    if not isinstance(companies, dict):
        return errors

    for slug, company in companies.items():
        if not isinstance(company, dict):
            continue
        prospectus = (
            company.get("prospectus")
            if isinstance(company.get("prospectus"), dict)
            else {}
        )
        if re.search(r"<[^>]+>", str(prospectus.get("title", ""))):
            errors.append(f"{slug}: prospectus title contains HTML markup")

        company_name = prospectus_parser.clean_text(company.get("name"), 120)
        company_key = prospectus_parser.normalize_name(company_name)
        investors = company.get("investors")
        if not isinstance(investors, list):
            continue
        for investor in investors:
            if not isinstance(investor, dict):
                continue
            name = prospectus_parser.clean_text(investor.get("name"), 240)
            evidence = prospectus_parser.clean_text(
                investor.get("evidence"), 500
            )
            if not evidence:
                errors.append(f"{slug}: investor {name} missing table-row evidence")
            try:
                shares = float(investor.get("preIpoShares", 0))
                ownership = float(investor.get("preIpoOwnershipPct", 0))
            except (TypeError, ValueError):
                shares = 0
                ownership = 0
            if shares <= 0 or not (0 < ownership <= 100):
                errors.append(
                    f"{slug}: investor {name} missing valid same-row holding facts"
                )
            if investor.get("nameResolution") not in {
                "definitions",
                "basic-information",
            }:
                errors.append(
                    f"{slug}: investor {name} lacks prospectus name resolution"
                )
            if any(
                fragment in name
                for fragment in prospectus_parser.NARRATIVE_NAME_FRAGMENTS
            ):
                errors.append(
                    f"{slug}: narrative phrase published as investor: {name}"
                )
            if name in prospectus_parser.GENERIC_NAMES:
                errors.append(f"{slug}: generic institution name published: {name}")
            name_key = prospectus_parser.normalize_name(name)
            if company_key and company_key in name_key:
                errors.append(f"{slug}: issuer published as its own investor: {name}")
    return list(dict.fromkeys(errors))


# The legacy implementation resolves these names from module globals at runtime.
legacy.clean_text = prospectus_parser.clean_text
legacy.normalized_name = prospectus_parser.normalize_name
legacy.extract_institutional_investors = extract_institutional_investors
legacy.extract_issuer_contact = extract_issuer_contact
legacy.validate_snapshot = validate_snapshot


def main() -> int:
    return legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())
