#!/usr/bin/env python3
"""Validate the independent native research report artifact before publication."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .native_event_research import EVENT_RE, REQUEST_RE, MAX_INDEX_BYTES, public_url, validate_analysis
except ImportError:
    from native_event_research import EVENT_RE, REQUEST_RE, MAX_INDEX_BYTES, public_url, validate_analysis


def validate(payload: object) -> None:
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 2:
        raise ValueError("invalid report index version")
    entries = payload.get("results")
    if not isinstance(entries, list) or len(entries) > 40:
        raise ValueError("invalid result list")
    seen: set[str] = set()
    for row in entries:
        if not isinstance(row, dict) or row.get("schemaVersion") != 2:
            raise ValueError("invalid report record")
        event_id, request_id = row.get("eventId"), row.get("requestId")
        if not isinstance(event_id, str) or not EVENT_RE.fullmatch(event_id):
            raise ValueError("invalid event identity")
        if not isinstance(request_id, str) or not REQUEST_RE.fullmatch(request_id) or request_id in seen:
            raise ValueError("invalid or duplicate request identity")
        seen.add(request_id)
        if row.get("reviewStatus") != "automated_unreviewed":
            raise ValueError("automatic reports cannot self-approve")
        if row.get("sourceScope") != "published-vciq-snapshots-only":
            raise ValueError("unrecognized evidence scope")
        if row.get("status") not in {"completed-draft", "evidence-insufficient", "model-unavailable", "event-unavailable"}:
            raise ValueError("invalid report status")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or len(evidence) > 16:
            raise ValueError("invalid evidence count")
        ids: set[str] = set()
        for source in evidence:
            if not isinstance(source, dict) or not isinstance(source.get("id"), str) or source["id"] in ids or not public_url(source.get("url")):
                raise ValueError("invalid evidence record")
            if source.get("verificationStatus") != "source-statement-unverified":
                raise ValueError("source material cannot self-verify")
            ids.add(source["id"])
        if row["status"] == "completed-draft":
            if row.get("modelUsed") is not True:
                raise ValueError("completed report missing model receipt")
            validate_analysis(row.get("analysis"), evidence)
        elif row.get("analysis") is not None or row.get("modelUsed") is not False:
            raise ValueError("non-completed report must not contain research conclusions")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=Path("public/data/native_research_reports.json"))
    args = parser.parse_args()
    if args.path.stat().st_size > MAX_INDEX_BYTES:
        raise ValueError("report index exceeds byte budget")
    validate(json.loads(args.path.read_text(encoding="utf-8")))
    print("Native research reports: identity, status and evidence gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
