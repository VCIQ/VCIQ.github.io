#!/usr/bin/env python3
"""Audit approved P1 sources through the scheduled production adapter chain.

Only the terminal snapshot-writing main() is replaced. The actual scheduled
entrypoint installs its normal transport, structured-source, public-region and
tracking adapters. Article data, historic receipts and private interests are
never written. Emit an observation, not a production/publication success claim.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import UTC, datetime
import hashlib
import json
import sys
from unittest.mock import patch

try:
    from . import crawl_official_companies as official
    from . import eastmoney_transport as entrypoint
except ImportError:
    import crawl_official_companies as official
    import eastmoney_transport as entrypoint


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", action="append", default=[])
    args = parser.parse_args()
    approval = json.loads(official.LISTED_INNOVATION_PATH.read_text(encoding="utf-8"))
    approved = {row["companySlug"] for row in approval["companies"]}
    if len(approved) != 40 or len(approval["companies"]) != 40:
        raise ValueError("Expected exactly 40 owner-approved P1 identities")
    selected = set(args.company) if args.company else approved
    if not selected or selected - approved:
        raise ValueError("Only approved P1 company slugs may be audited")
    code_paths = (
        "tools/crawl_official_companies.py", "tools/crawl_official_with_tracking.py",
        "tools/crawl_official_with_source_categories.py", "tools/eastmoney_transport.py",
        "tools/bytedance_official_sources.py", "tools/crawl_articles.py",
        "config/official_company_sources.json", "config/listed_innovation_companies.json",
    )
    hashes = {p: hashlib.sha256((official.ROOT / p).read_bytes()).hexdigest() for p in code_paths}
    receipt = {}

    def observe_instead_of_publish(*_args, **_kwargs) -> int:
        specs = [s for s in official.load_registry() if s.slug in selected]
        if len(specs) != len(selected) or {s.slug for s in specs} != selected:
            raise ValueError("Production registry does not exactly cover the audit selection")
        started = datetime.now(UTC).isoformat()
        articles, statuses = official.crawl_all_companies(specs, official.DEFAULT_USER_AGENT)
        receipt.update({
            "schemaVersion": 1,
            "scope": "owner-approved-listed-p1-production-adapter-audit",
            "entrypoint": "tools/eastmoney_transport.py",
            "startedAt": started, "completedAt": datetime.now(UTC).isoformat(),
            "approvedCompanyCount": len(approved), "attemptedCompanyCount": len(statuses),
            "selectedCompanySlugs": sorted(selected),
            "companiesWithAcceptedArticles": sum(bool(s.get("accepted")) for s in statuses),
            "acceptedCandidateCount": len(articles), "snapshotPublished": False,
            "inputSha256": hashes,
            "note": "Production adapters, read-only observation. Parser candidates are not net-new or published articles, full regulatory coverage, or a deployed snapshot.",
            "sources": statuses,
        })
        return 0

    # The patch is intentionally at the writer boundary, not at the parser:
    # bypassing adapters was precisely what missed the production TypeError.
    with patch.object(official, "main", side_effect=observe_instead_of_publish) as terminal:
        with redirect_stdout(sys.stderr):
            result = entrypoint.main()
        if result != 0 or terminal.call_count != 1 or not receipt:
            raise RuntimeError("Scheduled entrypoint did not execute the audit boundary exactly once")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
