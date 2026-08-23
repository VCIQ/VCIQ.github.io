#!/usr/bin/env python3
"""Drive structural and entity-semantic venture gates to one shared fixed point."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

try:
    from .enforce_venture_entity_semantics import enforce_snapshot
    from .finalize_venture_profiles import finalize_snapshot
    from .venture_profile_extraction import parse_catalog
except ImportError:
    from enforce_venture_entity_semantics import enforce_snapshot
    from finalize_venture_profiles import finalize_snapshot
    from venture_profile_extraction import parse_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"


def _state_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _preview(value: Any, limit: int = 180) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return rendered if len(rendered) <= limit else rendered[: limit - 1] + "…"


def _diff_paths(
    left: Any,
    right: Any,
    *,
    prefix: str = "$",
    limit: int = 30,
) -> list[dict[str, str]]:
    """Return a bounded set of JSON-style paths changed by one terminal gate."""
    differences: list[dict[str, str]] = []

    def visit(before: Any, after: Any, path: str) -> None:
        if len(differences) >= limit or before == after:
            return
        if isinstance(before, dict) and isinstance(after, dict):
            for key in sorted(set(before) | set(after), key=str):
                if len(differences) >= limit:
                    break
                child = f"{path}.{key}"
                if key not in before:
                    differences.append(
                        {"path": child, "before": "<missing>", "after": _preview(after[key])}
                    )
                elif key not in after:
                    differences.append(
                        {"path": child, "before": _preview(before[key]), "after": "<missing>"}
                    )
                else:
                    visit(before[key], after[key], child)
            return
        if isinstance(before, list) and isinstance(after, list):
            shared = min(len(before), len(after))
            for index in range(shared):
                if len(differences) >= limit:
                    break
                visit(before[index], after[index], f"{path}[{index}]")
            for index in range(shared, max(len(before), len(after))):
                if len(differences) >= limit:
                    break
                if index >= len(before):
                    differences.append(
                        {
                            "path": f"{path}[{index}]",
                            "before": "<missing>",
                            "after": _preview(after[index]),
                        }
                    )
                else:
                    differences.append(
                        {
                            "path": f"{path}[{index}]",
                            "before": _preview(before[index]),
                            "after": "<missing>",
                        }
                    )
            return
        differences.append(
            {"path": path, "before": _preview(before), "after": _preview(after)}
        )

    visit(left, right, prefix)
    return differences


def _anchor_catalog_backgrounds(
    payload: dict[str, Any], catalog_text: str
) -> dict[str, Any]:
    """Keep company identity summaries stable across live crawler refreshes.

    The crawler may discover a valid-looking About sentence in a different
    language or wording on every run. Company ``background`` and the summary
    inside ``projectBackground`` are identity fields, so when the catalog has a
    reviewed summary it is the canonical value for both. More detailed live
    evidence remains available in technology, products, sources, and other
    research fields.
    """
    anchored = copy.deepcopy(payload)
    company_specs, _ = parse_catalog(catalog_text)
    summaries = {
        spec.slug: spec.summary.strip()
        for spec in company_specs
        if spec.summary and spec.summary.strip()
    }
    companies = anchored.get("companies", {})
    if not isinstance(companies, dict):
        return anchored

    for slug, profile in companies.items():
        if not isinstance(profile, dict):
            continue
        summary = summaries.get(slug)
        if not summary:
            continue
        profile["background"] = summary
        project = profile.get("projectBackground")
        if isinstance(project, dict):
            project["summary"] = summary
    return anchored


def stabilize_snapshot(
    payload: dict[str, Any],
    catalog_text: str,
    *,
    max_passes: int = 8,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a snapshot accepted unchanged by both terminal quality gates.

    The structural finalizer and entity-semantic gate are individually
    deterministic, but one can expose a field that the other still normalizes.
    Alternate them until both are no-ops. Repeated states are treated as a real
    contract cycle rather than silently choosing one gate's output.
    """
    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    current = _anchor_catalog_backgrounds(payload, catalog_text)
    seen: dict[str, int] = {_state_key(current): 0}
    history: list[dict[str, Any]] = []

    for pass_index in range(1, max_passes + 1):
        structural, structural_diagnostics = finalize_snapshot(current, catalog_text)
        semantic, semantic_diagnostics = enforce_snapshot(structural, catalog_text)

        structural_check, structural_check_diagnostics = finalize_snapshot(
            semantic, catalog_text
        )
        semantic_check, semantic_check_diagnostics = enforce_snapshot(
            semantic, catalog_text
        )

        structural_stable = structural_check == semantic
        semantic_stable = semantic_check == semantic
        structural_diff = _diff_paths(semantic, structural_check)
        semantic_diff = _diff_paths(semantic, semantic_check)
        history.append(
            {
                "pass": pass_index,
                "structuralStable": structural_stable,
                "semanticStable": semantic_stable,
                "structural": structural_diagnostics,
                "semantic": semantic_diagnostics,
                "structuralCheck": structural_check_diagnostics,
                "semanticCheck": semantic_check_diagnostics,
                "structuralDiff": structural_diff,
                "semanticDiff": semantic_diff,
            }
        )
        if structural_stable and semantic_stable:
            return semantic, {
                "passes": pass_index,
                "converged": True,
                "history": history,
            }

        state_key = _state_key(semantic)
        if state_key in seen:
            raise RuntimeError(
                "venture terminal gates entered a cycle before reaching a shared fixed point: "
                + json.dumps(
                    {
                        "repeatedFromPass": seen[state_key],
                        "repeatedAtPass": pass_index,
                        "structuralStable": structural_stable,
                        "semanticStable": semantic_stable,
                        "structuralDiff": structural_diff,
                        "semanticDiff": semantic_diff,
                        "finalizeStepDiff": _diff_paths(current, structural),
                        "semanticStepDiff": _diff_paths(structural, semantic),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        seen[state_key] = pass_index
        current = semantic

    last = history[-1] if history else {}
    raise RuntimeError(
        f"venture terminal gates did not converge within {max_passes} passes: "
        + json.dumps(
            {
                "structuralStable": last.get("structuralStable"),
                "semanticStable": last.get("semanticStable"),
                "structuralDiff": last.get("structuralDiff", []),
                "semanticDiff": last.get("semanticDiff", []),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--max-passes", type=int, default=8)
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    stabilized, diagnostics = stabilize_snapshot(
        payload,
        args.catalog.read_text(encoding="utf-8"),
        max_passes=args.max_passes,
    )
    rendered = json.dumps(stabilized, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot has not reached the shared terminal fixed point.")
            return 1
        print("Venture profile snapshot passed the shared terminal fixed-point check.")
        return 0

    if rendered == current:
        print("No venture profile stabilization changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
