#!/usr/bin/env python3
"""Drive all deterministic venture publication gates to one shared fixed point."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Callable

try:
    from . import enforce_venture_entity_semantics as entity_semantics
    from . import finalize_venture_profiles as structural_finalization
    from . import guard_venture_cross_field_noise as cross_field_noise_guard
    from . import normalize_venture_profiles as base_normalization
    from . import refine_venture_research_evidence as research_evidence
    from . import sanitize_venture_profiles as low_level_sanitization
    from .normalize_venture_publication import normalize_publication_payload
    from .stabilize_venture_profiles import stabilize_snapshot as stabilize_terminal_snapshot
    from .stabilize_venture_research_evidence import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        stabilize_evidence_snapshot,
    )
except ImportError:
    import enforce_venture_entity_semantics as entity_semantics
    import finalize_venture_profiles as structural_finalization
    import guard_venture_cross_field_noise as cross_field_noise_guard
    import normalize_venture_profiles as base_normalization
    import refine_venture_research_evidence as research_evidence
    import sanitize_venture_profiles as low_level_sanitization
    from normalize_venture_publication import normalize_publication_payload
    from stabilize_venture_profiles import stabilize_snapshot as stabilize_terminal_snapshot
    from stabilize_venture_research_evidence import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        stabilize_evidence_snapshot,
    )


EvidenceStabilizer = Callable[..., tuple[dict[str, Any], dict[str, Any]]]
Normalizer = Callable[[dict[str, Any], str], tuple[dict[str, Any], dict[str, Any]]]
TerminalStabilizer = Callable[..., tuple[dict[str, Any], dict[str, Any]]]

# All publication gates must use the same explicit transaction-action vocabulary.
# Exchange names, ticker labels, earnings announcements, investor conferences,
# and internal team reorganizations are context, not capital-market events.
CROSS_GATE_FINANCING_ACTION_RE = re.compile(
    r"(?:"
    r"\brais(?:e|ed|es|ing)\b(?!\s+(?:full[- ]year\s+)?guidance\b)|"
    r"\bfunding round\b|\bfinancing round\b|\binvestment round\b|"
    r"\bseries\s+(?:[a-z]\d*|\d+)(?:\s+(?:funding|financing|round))?\b|"
    r"\bseed round\b|\bpre-seed\b|"
    r"\bfirst close.{0,80}(?:funding|financing)\b|"
    r"\bcomplet(?:e|ed|es|ing).{0,80}(?:funding|financing)\b|"
    r"\bsecured .{0,40} funding\b|\bcloses? .{0,40} round\b|"
    r"\bbacked by\b|\bled by\b|\binvestment from\b|"
    r"\binvest(?:ed|s|ing)?\s+(?:in|into)\b|\bvaluation\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"融资|募资|领投|跟投|战略投资|估值"
    r")",
    re.IGNORECASE,
)
CROSS_GATE_CAPITAL_ACTION_RE = re.compile(
    r"(?:"
    r"\binitial public offering\b|"
    r"\b(?:files?|filed|plans?|planned|launch(?:es|ed)?|prices?|priced|"
    r"completes?|completed|pursues?|pursued|seeks?|sought)\s+(?:an?\s+)?ipo\b|"
    r"\bwent public\b|\bgo(?:es|ing)? public\b|"
    r"\bbecom(?:e|es|ing) (?:a )?public company\b|"
    r"\b(?:list(?:ed|ing)|debut(?:ed|s)?) on\b|"
    r"\bacquir(?:e|es|ed)\b|\bacquired by\b|\bacquisition\b|"
    r"\bmerger\b|\bmerg(?:e|ed|ing)\s+(?:with|into)\b|"
    r"\bbusiness combination\b|\bdelist(?:ed|ing)?\b|"
    r"完成上市|正式上市|申请上市|拟上市|启动上市|成为上市公司|已上市公司|"
    r"借壳上市|合并上市|登陆.{0,16}交易所|赴.{0,16}上市|挂牌|"
    r"并购|收购|完成退出|退市"
    r")",
    re.IGNORECASE,
)


def align_capital_event_patterns() -> None:
    """Install shared capital-event and summary contracts across mutable gates."""

    research_evidence.FINANCING_RE = CROSS_GATE_FINANCING_ACTION_RE
    base_normalization.FINANCING_ACTION_PATTERN = CROSS_GATE_FINANCING_ACTION_RE
    low_level_sanitization.FINANCING_ACTION_RE = CROSS_GATE_FINANCING_ACTION_RE
    structural_finalization.STRONG_FINANCING_RE = CROSS_GATE_FINANCING_ACTION_RE
    entity_semantics.FINANCING_ACTION_RE = CROSS_GATE_FINANCING_ACTION_RE

    research_evidence.CAPITAL_MARKET_RE = CROSS_GATE_CAPITAL_ACTION_RE
    base_normalization.CAPITAL_MARKET_ACTION_PATTERN = CROSS_GATE_CAPITAL_ACTION_RE
    low_level_sanitization.CAPITAL_ACTION_RE = CROSS_GATE_CAPITAL_ACTION_RE
    structural_finalization.CAPITAL_EVIDENCE_RE = CROSS_GATE_CAPITAL_ACTION_RE
    entity_semantics.CAPITAL_ACTION_RE = CROSS_GATE_CAPITAL_ACTION_RE

    # Capital summaries are derived fields. The structural finalizer owns their
    # canonical representation because it de-duplicates semantically equivalent
    # amount/round/investor labels via normalized keys. The semantic and
    # cross-field guards must reuse that exact builder instead of re-creating
    # summaries with raw-string de-duplication (for example treating
    # ``15.5 Billion`` and ``$15.5 Billion`` as two different amounts).
    entity_semantics._capital_summary = structural_finalization._capital_summary
    cross_field_noise_guard._capital_summary = structural_finalization._capital_summary


def _state_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _preview(value: Any, limit: int = 180) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return rendered if len(rendered) <= limit else rendered[: limit - 1] + "…"


def _diff_paths(
    left: Any,
    right: Any,
    *,
    prefix: str = "$",
    limit: int = 30,
) -> list[dict[str, str]]:
    """Return a bounded set of JSON-style paths changed by one gate."""
    differences: list[dict[str, str]] = []

    def visit(before: Any, after: Any, path: str) -> None:
        if len(differences) >= limit or before == after:
            return
        if isinstance(before, dict) and isinstance(after, dict):
            keys = sorted(set(before) | set(after), key=str)
            for key in keys:
                if len(differences) >= limit:
                    break
                child_path = f"{path}.{key}"
                if key not in before:
                    differences.append(
                        {"path": child_path, "before": "<missing>", "after": _preview(after[key])}
                    )
                elif key not in after:
                    differences.append(
                        {"path": child_path, "before": _preview(before[key]), "after": "<missing>"}
                    )
                else:
                    visit(before[key], after[key], child_path)
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


def stabilize_publication_snapshot(
    snapshot: dict[str, Any],
    articles: dict[str, Any],
    catalog_text: str,
    *,
    max_passes: int = 8,
    evidence_stabilizer: EvidenceStabilizer = stabilize_evidence_snapshot,
    normalizer: Normalizer = normalize_publication_payload,
    terminal_stabilizer: TerminalStabilizer = stabilize_terminal_snapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the conservative shared fixed point of all publication gates.

    Evidence alignment can propose a raw representation that downstream
    normalization rewrites without rejecting the underlying fact. Therefore an
    evidence proposal is considered stable after it passes through the same
    normalization and terminal gates used for publication. A repeated state is
    still rejected when the complete ordered pipeline itself is not idempotent.
    """
    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    align_capital_event_patterns()
    current = copy.deepcopy(snapshot)
    seen: dict[str, int] = {_state_key(current): 0}
    history: list[dict[str, Any]] = []

    for pass_index in range(1, max_passes + 1):
        evidence, evidence_diagnostics = evidence_stabilizer(
            current,
            articles,
            catalog_text,
            max_passes=max_passes,
        )
        normalized, normalization_diagnostics = normalizer(
            copy.deepcopy(evidence), catalog_text
        )
        candidate, terminal_diagnostics = terminal_stabilizer(
            normalized,
            catalog_text,
            max_passes=max_passes,
        )

        evidence_check, evidence_check_diagnostics = evidence_stabilizer(
            candidate,
            articles,
            catalog_text,
            max_passes=max_passes,
        )
        evidence_check_normalized, evidence_check_normalization_diagnostics = normalizer(
            copy.deepcopy(evidence_check), catalog_text
        )
        evidence_check_terminal, evidence_check_terminal_diagnostics = terminal_stabilizer(
            evidence_check_normalized,
            catalog_text,
            max_passes=max_passes,
        )
        normalized_check, normalization_check_diagnostics = normalizer(
            copy.deepcopy(candidate), catalog_text
        )
        terminal_check, terminal_check_diagnostics = terminal_stabilizer(
            candidate,
            catalog_text,
            max_passes=max_passes,
        )

        raw_evidence_stable = evidence_check == candidate
        evidence_stable = evidence_check_terminal == candidate
        normalization_stable = normalized_check == candidate
        terminal_stable = terminal_check == candidate
        changed = candidate != current
        gate_diffs = {
            "evidence": _diff_paths(candidate, evidence_check_terminal),
            "evidenceRaw": _diff_paths(candidate, evidence_check),
            "normalization": _diff_paths(candidate, normalized_check),
            "terminal": _diff_paths(candidate, terminal_check),
        }
        history.append(
            {
                "pass": pass_index,
                "changed": changed,
                "rawEvidenceStable": raw_evidence_stable,
                "evidenceStable": evidence_stable,
                "normalizationStable": normalization_stable,
                "terminalStable": terminal_stable,
                "evidence": evidence_diagnostics,
                "normalization": normalization_diagnostics,
                "terminal": terminal_diagnostics,
                "evidenceCheck": evidence_check_diagnostics,
                "evidenceCheckNormalization": evidence_check_normalization_diagnostics,
                "evidenceCheckTerminal": evidence_check_terminal_diagnostics,
                "normalizationCheck": normalization_check_diagnostics,
                "terminalCheck": terminal_check_diagnostics,
                "gateDiffs": gate_diffs,
            }
        )

        if evidence_stable and normalization_stable and terminal_stable:
            return candidate, {
                "passes": pass_index,
                "changedPasses": sum(bool(item["changed"]) for item in history),
                "converged": True,
                "history": history,
            }

        state_key = _state_key(candidate)
        if state_key in seen:
            cycle = {
                "repeatedFromPass": seen[state_key],
                "repeatedAtPass": pass_index,
                "rawEvidenceStable": raw_evidence_stable,
                "evidenceStable": evidence_stable,
                "normalizationStable": normalization_stable,
                "terminalStable": terminal_stable,
                "gateDiffs": gate_diffs,
            }
            raise RuntimeError(
                "venture publication gates entered a cycle before reaching a shared fixed point: "
                + json.dumps(cycle, ensure_ascii=False, sort_keys=True)
            )
        seen[state_key] = pass_index
        current = candidate

    last = history[-1] if history else {}
    raise RuntimeError(
        f"venture publication gates did not converge within {max_passes} passes: "
        + json.dumps(last.get("gateDiffs", {}), ensure_ascii=False, sort_keys=True)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--articles", type=Path, default=ARTICLE_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--max-passes", type=int, default=8)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    articles = json.loads(args.articles.read_text(encoding="utf-8"))
    stabilized, diagnostics = stabilize_publication_snapshot(
        snapshot,
        articles,
        args.catalog.read_text(encoding="utf-8"),
        max_passes=args.max_passes,
    )
    rendered = json.dumps(stabilized, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot has not reached the shared publication fixed point.")
            return 1
        print("Venture profile snapshot passed the shared publication fixed-point check.")
        return 0

    if rendered == current:
        print("No venture publication fixed-point changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
