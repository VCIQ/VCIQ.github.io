"""Print the deterministic reader projection, or check its committed copy.

The full review manifest remains authoritative; prose and audit links stay there
instead of being shipped with every homepage script. No eligibility rule changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIELDS = (
    "id", "articleId", "sourceId", "sourceUrl", "expectedTitle",
    "expectedSummaryContains", "removeCompanySlugs", "removeMentionedCompanies",
    "fields", "removeTrackSlugs", "addTrackSlugs",
)


def project(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("reviews"), list):
        raise ValueError("Unsupported review manifest")
    return {"schemaVersion": 1, "reviews": [
        {field: row[field] for field in FIELDS if field in row}
        for row in payload["reviews"]
    ]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "config/article_metadata_reviews.json").read_text(encoding="utf-8"))
    expected = project(manifest)
    if args.check:
        actual = json.loads((ROOT / "config/article_metadata_runtime.json").read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError("Runtime projection is stale; regenerate from the full review manifest")
        print("Article review runtime projection matches the full manifest")
    else:
        print(json.dumps(expected, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
