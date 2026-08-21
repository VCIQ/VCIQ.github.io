#!/usr/bin/env python3
"""Raw tracking person/company compound-entity integrity checks.

This Python companion intentionally mirrors the conservative TypeScript production
splitter used by the protected capture path. It is used by Python-only repository
writers that can mutate ``tracks[].people`` or ``tracks[].sampleCompanies``.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "user_tracking.json"
ENTITY_CONTENT_RE = re.compile(r"[A-Za-z0-9\u3400-\u9fff]")
COMPOUND_SEPARATOR_RE = re.compile(
    r"(?:[\n\r、，；;|｜]+|\s+[\/／]\s+|\s+(?:和|与|及)\s+)"
)


def split_compound_tracking_entity_name(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    raw = value.strip()
    if not raw:
        return []
    parts = [
        re.sub(r"\s+", " ", unicodedata.normalize("NFKC", part)).strip()
        for part in COMPOUND_SEPARATOR_RE.split(raw)
    ]
    parts = [part for part in parts if ENTITY_CONTENT_RE.search(part)]
    return parts if len(parts) > 1 else []


def find_compound_tracking_entities(config: Any) -> list[dict[str, Any]]:
    if not isinstance(config, dict) or not isinstance(config.get("tracks"), list):
        raise ValueError("raw tracking config must contain a tracks array")

    issues: list[dict[str, Any]] = []
    for index, track in enumerate(config["tracks"]):
        if not isinstance(track, dict):
            raise ValueError(f"raw tracking config track {index + 1} is not an object")
        slug = track.get("slug")
        name = track.get("name")
        if not isinstance(slug, str) or not isinstance(name, str):
            raise ValueError(f"raw tracking config track {index + 1} lacks string slug/name")
        for field, entity_type in (("people", "person"), ("sampleCompanies", "company")):
            values = track.get(field)
            if not isinstance(values, list):
                raise ValueError(f"{slug}/{field} must be an array")
            for value_index, value in enumerate(values):
                if not isinstance(value, str):
                    raise ValueError(
                        f"{slug}/{field} item {value_index + 1} is not a string"
                    )
                parts = split_compound_tracking_entity_name(value)
                if len(parts) < 2:
                    continue
                issues.append(
                    {
                        "trackSlug": slug,
                        "trackName": name,
                        "entityType": entity_type,
                        "value": value,
                        "parts": parts,
                    }
                )
    return issues


def assert_no_compound_tracking_entities(config: Any) -> None:
    issues = find_compound_tracking_entities(config)
    if not issues:
        return
    preview = []
    for issue in issues[:5]:
        label = "人物" if issue["entityType"] == "person" else "公司"
        preview.append(
            f'{issue["trackName"]}/{label}“{issue["value"]}” → '
            + "、".join(issue["parts"])
        )
    suffix = f"；另有 {len(issues) - 5} 项" if len(issues) > 5 else ""
    raise ValueError(
        "检测到复合追踪实体，user_tracking.json 必须保持零复合状态："
        + "；".join(preview)
        + suffix
        + "。"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.config.read_text(encoding="utf-8"))
        assert_no_compound_tracking_entities(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc))
        return 1

    print("Tracking entity clean state valid: zero compound people/companies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
