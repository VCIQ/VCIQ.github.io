#!/usr/bin/env python3
"""Bounded official-source observation; never publish or modify the article snapshot."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

try:
    from .crawl_official_companies import ROOT, DEFAULT_USER_AGENT, load_registry, crawl_all_companies
except ImportError:
    from crawl_official_companies import ROOT, DEFAULT_USER_AGENT, load_registry, crawl_all_companies


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-empty", action="store_true", help="Observe zero-yield companies in the previous dated receipt")
    args = parser.parse_args()
    approved = json.loads((ROOT / "config/listed_innovation_companies.json").read_text())
    rows = approved.get("companies", [])
    allowed = {row["companySlug"] for row in rows}
    if len(allowed) != 40:
        raise ValueError("Expected exactly 40 owner-approved research identities")
    selected = allowed
    if args.only_empty:
        previous = json.loads((ROOT / "public/data/listed_innovation_source_health.json").read_text())
        selected = allowed & {row["companySlug"] for row in previous["sources"] if not row.get("accepted")}
    started = datetime.now(UTC).isoformat()
    articles, statuses = crawl_all_companies([spec for spec in load_registry() if spec.slug in selected], DEFAULT_USER_AGENT)
    receipt = {
        "schemaVersion": 1,
        "scope": "owner-approved-listed-p1-empty-followup" if args.only_empty else "owner-approved-listed-p1",
        "startedAt": started,
        "completedAt": datetime.now(UTC).isoformat(),
        "approvedCompanyCount": len(allowed),
        "attemptedCompanyCount": len(statuses),
        "companiesWithAcceptedArticles": sum(bool(row.get("accepted")) for row in statuses),
        "acceptedCandidateCount": len(articles),
        "snapshotPublished": False,
        "note": "Read-only observation; accepted means parser candidates, not net-new or published articles, complete filing coverage, or deployment.",
        "sources": statuses,
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
