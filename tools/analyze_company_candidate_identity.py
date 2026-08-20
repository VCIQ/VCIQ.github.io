#!/usr/bin/env python3
"""Read-only identity analysis for pending company candidates.

This tool never writes the review queue. It atomizes compound candidate names,
compares each atom with the two existing company registries, and reports what can
be resolved safely versus what still needs human review.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "config" / "company_candidate_review_queue.json"
COMPANY_REGISTRY_PATH = ROOT / "config" / "company_registry.json"
OFFICIAL_SOURCES_PATH = ROOT / "config" / "official_company_sources.json"

LEGAL_SUFFIXES = (
    "incorporated", "corporation", "company", "limited", "holdings", "holding",
    "group", "corp", "inc", "ltd", "llc", "plc", "co",
    "股份有限公司", "有限责任公司", "有限公司", "集团",
)
STRUCTURAL_NOISE = {
    "benchmarks", "benchmark", "leaderboards", "leaderboard",
}


def clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean(value).casefold())


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean(raw, 240)
        key = normalize_identity(value)
        if not value or not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def atomize_name(value: Any) -> list[str]:
    name = clean(value, 240).strip(" ,，:：;；|｜-—")
    if not name:
        return []
    hard_parts = unique(re.split(r"[、；;|｜\n\r]+", name))
    first_pass = hard_parts if len(hard_parts) > 1 else [name]
    result: list[str] = []
    for part in first_pass:
        comma_parts = unique(re.split(r"[,，]+", part))
        if len(comma_parts) == 2 and normalize_identity(comma_parts[1]) in {
            "inc", "incorporated", "corp", "corporation", "co", "company",
            "ltd", "limited", "llc", "plc",
        }:
            result.append(part)
        elif len(comma_parts) > 1:
            result.extend(comma_parts)
        else:
            result.append(part)
    return unique(result)[:20]


def legal_core(value: Any) -> str:
    text = clean(value, 240).normalize("NFKC") if hasattr(str, "normalize") else clean(value, 240)
    # Python str has no normalize method; NFKC-like punctuation differences are
    # already removed by normalize_identity, so suffix stripping can stay textual.
    text = clean(value, 240).casefold().strip()
    changed = True
    while changed and text:
        changed = False
        for suffix in LEGAL_SUFFIXES:
            suffix_folded = suffix.casefold()
            if re.search(r"[\u3400-\u9fff]", suffix):
                if text.endswith(suffix_folded):
                    base = text[: -len(suffix_folded)].strip(" .,-_()（）")
                    if len(normalize_identity(base)) >= 2:
                        text = base
                        changed = True
                        break
            elif re.search(rf"(?:^|\s|[,.]){re.escape(suffix_folded)}\.?$", text):
                text = re.sub(rf"(?:^|\s|[,.]){re.escape(suffix_folded)}\.?$", "", text).strip(" .,-_")
                changed = True
                break
    return normalize_identity(text)


def registry_entities(company_registry: dict[str, Any], official_sources: dict[str, Any]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    def add(slug: str, name: str, aliases: list[str], provenance: str) -> None:
        canonical_key = slug or normalize_identity(name)
        if not canonical_key or not name:
            return
        row = merged.setdefault(canonical_key, {"slug": slug, "name": name, "aliases": [], "provenance": []})
        if not row["slug"] and slug:
            row["slug"] = slug
        if not row["name"] and name:
            row["name"] = name
        row["aliases"] = unique([*row["aliases"], name, *aliases])
        if provenance not in row["provenance"]:
            row["provenance"].append(provenance)

    for raw in company_registry.get("companies", []):
        if not isinstance(raw, dict):
            continue
        aliases = [clean(raw.get("englishName"), 240)]
        if isinstance(raw.get("aliases"), list):
            aliases.extend(clean(item, 240) for item in raw["aliases"])
        add(clean(raw.get("slug"), 120), clean(raw.get("name"), 240), aliases, "company_registry")

    for raw in official_sources.get("companies", []):
        if not isinstance(raw, dict):
            continue
        aliases = [clean(item, 240) for item in raw.get("aliases", [])] if isinstance(raw.get("aliases"), list) else []
        add(clean(raw.get("slug"), 120), clean(raw.get("name"), 240), aliases, "official_company_sources")

    return list(merged.values())


def build_indexes(entities: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    exact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cores: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        seen_exact: set[str] = set()
        seen_core: set[str] = set()
        for alias in entity["aliases"]:
            key = normalize_identity(alias)
            core = legal_core(alias)
            if key and key not in seen_exact:
                exact[key].append(entity)
                seen_exact.add(key)
            if core and len(core) >= 4 and core not in seen_core:
                cores[core].append(entity)
                seen_core.add(core)
    return exact, cores


def one_unique(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    unique_rows: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row.get("slug") or normalize_identity(row.get("name"))
        unique_rows[key] = row
    return next(iter(unique_rows.values())) if len(unique_rows) == 1 else None


def possible_core_match(name: str, cores: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    candidate_core = legal_core(name)
    if len(candidate_core) < 4:
        return None
    direct = one_unique(cores.get(candidate_core, []))
    if direct:
        return direct
    matches: list[dict[str, Any]] = []
    for core, rows in cores.items():
        shorter, longer = sorted((candidate_core, core), key=len)
        if len(shorter) < 4 or len(shorter) * 2 < len(longer):
            continue
        if shorter not in longer:
            continue
        matches.extend(rows)
    return one_unique(matches)


def classify_atom(name: str, exact: dict[str, list[dict[str, Any]]], cores: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    key = normalize_identity(name)
    if key in STRUCTURAL_NOISE:
        return {"category": "structural_noise", "reason": "known non-company content label", "match": None}
    exact_match = one_unique(exact.get(key, []))
    if exact_match:
        return {"category": "resolved_existing", "reason": "unique exact name/englishName/alias match", "match": exact_match}
    possible = possible_core_match(name, cores)
    if possible:
        return {"category": "possible_existing", "reason": "unique conservative legal/core-name match", "match": possible}
    return {"category": "ambiguous_review", "reason": "no unique existing-company identity match", "match": None}


def analyze(queue: dict[str, Any], company_registry: dict[str, Any], official_sources: dict[str, Any]) -> dict[str, Any]:
    entities = registry_entities(company_registry, official_sources)
    exact, cores = build_indexes(entities)
    pending = [row for row in queue.get("candidates", []) if isinstance(row, dict) and clean(row.get("status"), 30) == "pending"]
    counts: Counter[str] = Counter()
    details: list[dict[str, Any]] = []
    compound_rows = 0
    atom_count = 0

    for row in pending:
        parent_name = clean(row.get("name"), 240)
        atoms = atomize_name(parent_name) or [parent_name]
        if len(atoms) > 1:
            compound_rows += 1
        atom_count += len(atoms)
        results = []
        for atom in atoms:
            classified = classify_atom(atom, exact, cores)
            counts[classified["category"]] += 1
            match = classified["match"]
            results.append({
                "name": atom,
                "category": classified["category"],
                "reason": classified["reason"],
                "match": None if not match else {
                    "slug": match.get("slug", ""),
                    "name": match.get("name", ""),
                    "provenance": match.get("provenance", []),
                },
            })
        details.append({
            "candidateId": clean(row.get("id"), 200),
            "parentName": parent_name,
            "score": int(row.get("score") or 0),
            "compound": len(atoms) > 1,
            "atoms": results,
        })

    summary = {
        "pendingBefore": len(pending),
        "compoundCandidateRows": compound_rows,
        "atomizedEntities": atom_count,
        "registryResolved": counts["resolved_existing"],
        "possibleExisting": counts["possible_existing"],
        "structuralNoise": counts["structural_noise"],
        "ambiguousStillNeedsReview": counts["ambiguous_review"],
        "identityRegistryEntities": len(entities),
    }
    if sum(summary[key] for key in ("registryResolved", "possibleExisting", "structuralNoise", "ambiguousStillNeedsReview")) != atom_count:
        raise AssertionError("dry-run category accounting mismatch")

    def examples(category: str, limit: int = 12) -> list[dict[str, Any]]:
        result = []
        for row in details:
            for atom in row["atoms"]:
                if atom["category"] != category:
                    continue
                result.append({"parentName": row["parentName"], **atom})
                if len(result) >= limit:
                    return result
        return result

    return {
        "schemaVersion": 1,
        "mode": "read-only-dry-run",
        "summary": summary,
        "examples": {
            "compound": [row for row in details if row["compound"]][:12],
            "resolvedExisting": examples("resolved_existing"),
            "possibleExisting": examples("possible_existing"),
            "structuralNoise": examples("structural_noise"),
            "ambiguousReview": examples("ambiguous_review"),
        },
        "details": details,
        "safety": {
            "writesQueue": False,
            "changesCandidateStatus": False,
            "automaticReject": False,
            "automaticMerge": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--company-registry", type=Path, default=COMPANY_REGISTRY_PATH)
    parser.add_argument("--official-sources", type=Path, default=OFFICIAL_SOURCES_PATH)
    parser.add_argument("--json", action="store_true", help="print the complete JSON report")
    args = parser.parse_args()

    report = analyze(load_json(args.queue), load_json(args.company_registry), load_json(args.official_sources))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
