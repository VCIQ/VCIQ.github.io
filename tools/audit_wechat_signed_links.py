#!/usr/bin/env python3
"""Read-only audit of non-durable WeChat links in public JSON snapshots.

The report never prints article URLs, signature values, article text or
identifiers. It does not rewrite any existing JSON or change release status.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .wechat_link_policy import classify_wechat_article_url
except ImportError:
    from wechat_link_policy import classify_wechat_article_url

ROOT = Path(__file__).resolve().parents[1]


def _urls(value: Any):
    if isinstance(value, str):
        if value.startswith(("https://", "http://")):
            yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _urls(child)
    elif isinstance(value, list):
        for child in value:
            yield from _urls(child)


def audit(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    unique: set[str] = set()
    counts = {"temporary": 0, "unverified": 0, "durable": 0}
    unreadable = 0
    for path in sorted(root.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unreadable += 1
            continue
        file_counts = {"temporary": 0, "unverified": 0, "durable": 0}
        for value in _urls(document):
            category = classify_wechat_article_url(value)
            if category not in file_counts:
                continue
            file_counts[category] += 1
            counts[category] += 1
            if category in {"temporary", "unverified"}:
                unique.add(value)
        if sum(file_counts.values()):
            files.append({"file": path.name, **file_counts})
    return {
        "scannedJsonFiles": len(list(root.glob("*.json"))),
        "unreadableJsonFiles": unreadable,
        "nonDurableUniqueUrls": len(unique),
        "linkReferences": counts,
        "files": files,
        "scope": "local public/data JSON; read-only reference count, not online availability",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "public" / "data")
    args = parser.parse_args()
    print(json.dumps(audit(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
