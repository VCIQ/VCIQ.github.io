#!/usr/bin/env python3
"""Workflow entrypoint for native event reports; never rewrites the daily brief."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

try:
    from .native_event_research import EVENT_RE, REQUEST_RE, atomic_json, generate, load, merge_result, record, rows
except ImportError:
    from native_event_research import EVENT_RE, REQUEST_RE, atomic_json, generate, load, merge_result, record, rows


def main() -> int:
    root = Path.cwd()
    event_id = os.environ.get("NATIVE_RESEARCH_EVENT_ID", "").strip()
    request_id = os.environ.get("NATIVE_RESEARCH_REQUEST_ID", "").strip() or str(uuid4())
    if not EVENT_RE.fullmatch(event_id) or not REQUEST_RE.fullmatch(request_id):
        raise ValueError("Invalid native research identity; no model request sent.")
    path = root / "public/data/native_research_reports.json"
    existing = load(path, {"results": []})
    complete = next((row for row in rows(record(existing).get("results"))
                     if row.get("requestId") == request_id and row.get("status") == "completed-draft"), None)
    if complete:
        if complete.get("eventId") != event_id:
            raise ValueError("Request identity conflict; refusing event substitution.")
        print("Native research already completed; retained result without another model call.")
        return 0
    result = generate(root, event_id, request_id)
    atomic_json(path, merge_result(existing, result))
    print(json.dumps({"eventId": event_id, "requestId": request_id, "status": result["status"]}, ensure_ascii=False))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(f"Native research: **{result['status']}**. Unreviewed, snapshot-grounded analysis, not independent fact verification.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
