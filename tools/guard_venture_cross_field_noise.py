#!/usr/bin/env python3
"""Remove high-confidence cross-field noise from venture company profiles.

This terminal guard handles failure modes that are hard to prevent during broad
web discovery but are unsafe to render as structured facts:

* role/business labels parsed as people;
* executive/management headings parsed as products;
* executive biographies parsed as company financing because they mention money;
* company summaries truncated after honorific abbreviations such as ``Dr.``.

The transform is deterministic and information-reducing.  It does not invent
replacement facts: when an incomplete background is detected, it falls back to
the curated catalog summary.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .venture_profile_extraction import (
        clean_text,
        evidence_score,
        parse_catalog,
    )
except ImportError:
    from venture_profile_extraction import clean_text, evidence_score, parse_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"

PERSONNEL_NAME_TOKENS = {
    "class",
    "executive",
    "general",
    "global",
    "governor",
    "leadership",
    "management",
    "manager",
    "president",
    "sales",
    "specialty",
    "team",
}
PERSONNEL_PRODUCT_RE = re.compile(
    r"\b(?:chief(?:\s+\w+){0,3}\s+officer|ceo|cto|cfo|coo|"
    r"president|vice president|general manager|managing director|"
    r"executive management|management team|board of directors|head of)\b",
    re.IGNORECASE,
)
PERSONNEL_PAGE_RE = re.compile(
    r"\b(?:executive management|management team|leadership|board of directors|"
    r"our team|team|biography|bio|profile)\b",
    re.IGNORECASE,
)
BIOGRAPHY_RE = re.compile(
    r"^\s*(?:he|she|they)\b|\b(?:has helped|has led|previously|prior to|"
    r"before joining|career|served as|worked at|was responsible for)\b",
    re.IGNORECASE,
)
HONORIFIC_TRUNCATION_RE = re.compile(
    r"\b(?:Dr|Mr|Mrs|Ms|Prof)\.$",
    re.IGNORECASE,
)


def _compact(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\u3400-\u9fff]+",
        "",
        clean_text(value, 500).casefold(),
    )


def _aliases(values: Iterable[Any]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean_text(raw, 160)
        key = value.casefold()
        if len(_compact(value)) < 2 or key in seen:
            continue
        result.append(value)
        seen.add(key)
    return tuple(result)


def _contains_alias(value: Any, aliases: Sequence[str]) -> bool:
    lowered = clean_text(value, 1600).casefold()
    return any(alias.casefold() in lowered for alias in aliases if len(_compact(alias)) >= 2)


def _personnel_name_noise(value: Any) -> bool:
    name = clean_text(value, 160).strip(" ,，:：;；-|｜")
    if not name or re.search(r"[&/]", name):
        return True
    if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
        return False
    tokens = {
        token.casefold().strip(".,:;()[]{}")
        for token in re.findall(r"[A-Za-z][A-Za-z'.-]*", name)
    }
    return bool(tokens & PERSONNEL_NAME_TOKENS)


def _sanitize_team(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            continue
        name = clean_text(raw.get("name"), 160)
        if _personnel_name_noise(name):
            continue
        key = name.casefold()
        if not key or key in seen:
            continue
        result.append(copy.deepcopy(raw))
        seen.add(key)
    return result


def _sanitize_products(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = clean_text(raw, 200).strip(" >›→-|｜")
        key = _compact(item)
        if not item or not key or key in seen:
            continue
        if PERSONNEL_PRODUCT_RE.search(item):
            continue
        result.append(item)
        seen.add(key)
    return result


def _sanitize_technology_products(values: Any, products: Sequence[str]) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    allowed = {_compact(item) for item in products}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            continue
        name = clean_text(raw.get("name"), 200)
        key = _compact(name)
        if (
            not key
            or key not in allowed
            or key in seen
            or PERSONNEL_PRODUCT_RE.search(name)
        ):
            continue
        result.append(copy.deepcopy(raw))
        seen.add(key)
    return result


def _sanitize_financing(values: Any, aliases: Sequence[str]) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in values:
        if not isinstance(raw, dict):
            continue
        title = clean_text(raw.get("title"), 300)
        summary = clean_text(raw.get("summary"), 1200)
        if PERSONNEL_PAGE_RE.search(title) and (
            BIOGRAPHY_RE.search(summary) or not _contains_alias(summary, aliases)
        ):
            continue
        result.append(copy.deepcopy(raw))
    return result


def _capital_summary(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    latest = sorted(
        events,
        key=lambda row: clean_text(row.get("date"), 20),
        reverse=True,
    )[0] if events else {}
    amounts = list(
        dict.fromkeys(
            clean_text(row.get("amount"), 80)
            for row in events
            if clean_text(row.get("amount"), 80)
        )
    )[:12]
    rounds = list(
        dict.fromkeys(
            clean_text(row.get("round"), 80)
            for row in events
            if clean_text(row.get("round"), 80)
        )
    )[:12]
    investors = list(
        dict.fromkeys(
            clean_text(item, 120)
            for row in events
            for item in (
                row.get("investors", [])
                if isinstance(row.get("investors"), list)
                else []
            )
            if clean_text(item, 120)
        )
    )[:20]
    if events:
        summary = (
            f"共识别到{len(events)}条可追溯融资记录；"
            f"最新记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
            f"{clean_text(latest.get('title'), 180)}。"
        )
    else:
        summary = "当前公开来源未提供可核对的融资轮次、金额和投资方记录。"
    return {
        "eventCount": len(events),
        "disclosedAmounts": amounts,
        "rounds": rounds,
        "majorInvestors": investors,
        "latestDate": clean_text(latest.get("date"), 20),
        "latestRound": clean_text(latest.get("round"), 80),
        "summary": summary,
    }


def guard_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    companies, _ = parse_catalog(catalog_text)
    specs = {item.slug: item for item in companies}
    cleaned = copy.deepcopy(payload)
    diagnostics = {
        "changedCompanies": 0,
        "removedTeamMembers": 0,
        "removedProducts": 0,
        "removedFinancing": 0,
        "repairedBackgrounds": 0,
    }

    profiles = cleaned.get("companies", {})
    if not isinstance(profiles, dict):
        return cleaned, diagnostics

    for slug, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        before = copy.deepcopy(profile)
        spec = specs.get(slug)
        aliases = _aliases(
            (
                profile.get("name", ""),
                slug,
                *(spec.aliases if spec else ()),
            )
        )

        team_before = profile.get("team", [])
        profile["team"] = _sanitize_team(team_before)
        diagnostics["removedTeamMembers"] += max(
            0,
            (len(team_before) if isinstance(team_before, list) else 0)
            - len(profile["team"]),
        )

        products_before = profile.get("products", [])
        profile["products"] = _sanitize_products(products_before)
        diagnostics["removedProducts"] += max(
            0,
            (len(products_before) if isinstance(products_before, list) else 0)
            - len(profile["products"]),
        )
        profile["technologyProducts"] = _sanitize_technology_products(
            profile.get("technologyProducts", []), profile["products"]
        )

        financing_before = profile.get("financing", [])
        profile["financing"] = _sanitize_financing(financing_before, aliases)
        diagnostics["removedFinancing"] += max(
            0,
            (len(financing_before) if isinstance(financing_before, list) else 0)
            - len(profile["financing"]),
        )
        profile["capitalSummary"] = _capital_summary(profile["financing"])

        background = clean_text(profile.get("background"), 1000)
        if HONORIFIC_TRUNCATION_RE.search(background) and spec:
            replacement = clean_text(spec.summary, 900)
            if replacement:
                profile["background"] = replacement
                project = profile.get("projectBackground")
                if isinstance(project, dict):
                    project["summary"] = replacement
                diagnostics["repairedBackgrounds"] += 1

        profile["evidenceScore"] = evidence_score(profile, "company")
        if profile != before:
            diagnostics["changedCompanies"] += 1

    quality = cleaned.setdefault("qualityGate", {})
    checks = quality.setdefault("checks", {})
    checks["crossFieldNoiseGuard"] = {
        "actual": 0,
        "required": 0,
        "passed": True,
    }
    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    return cleaned, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    cleaned, diagnostics = guard_snapshot(
        payload,
        args.catalog.read_text(encoding="utf-8"),
    )
    rendered = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot still contains cross-field noise.")
            return 1
        print("Venture profile snapshot passed cross-field noise guard.")
        return 0

    if rendered == current:
        print("No venture cross-field noise changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
