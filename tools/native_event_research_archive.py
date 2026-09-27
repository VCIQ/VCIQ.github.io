"""Read a reviewed, repository-local event retention record; never fetch arbitrary history."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def archived_event(root: Path, event_id: str) -> dict[str, Any] | None:
    path = root / "config/native_research_event_archives.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise ValueError("Invalid retained research event schema")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("Invalid retained research event records")
    for row in records:
        if not isinstance(row, dict) or row.get("eventId") != event_id:
            continue
        event = row.get("event")
        if not isinstance(event, dict) or event.get("id") != event_id:
            raise ValueError("Retained event identity mismatch")
        if row.get("sourcePath") != "public/data/articles.json" or any(
            not isinstance(row.get(key), str) or not re.fullmatch(r"[a-f0-9]{40}", row[key])
            for key in ("sourceCommit", "sourceBlob")
        ):
            raise ValueError("Retained event provenance invalid")
        return {**event, "archiveProvenance": {
            "sourceCommit": row["sourceCommit"], "sourcePath": row["sourcePath"],
            "sourceBlob": row["sourceBlob"],
        }}
    return None
