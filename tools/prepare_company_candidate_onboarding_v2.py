#!/usr/bin/env python3
"""Run automatic company onboarding with evidence-linked official-site discovery.

Resolution order stays authority-first:

1. existing formal official-source registry (handled by the core preparer);
2. exact Wikidata identity with one official website;
3. evidence-linked outbound site or exact brand-domain probe, with deterministic
   homepage identity + sector checks;
4. hold for exception handling.

Only already-verified metadata is passed into the existing onboarding preparer.
Both successful and failed pre-resolution outcomes are cached for the bounded
batch so the core preparer never repeats the same external identity lookup.

Persistent identity/source holds are written back as ``awaiting_profile`` states
with the candidate evidence fingerprint. Subsequent runs skip unchanged holds so
one unresolved candidate cannot permanently consume the bounded batch. A changed
evidence fingerprint, an exact registry match, or a newly registered official
source makes the candidate eligible again.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import company_official_source_discovery as discovery
    from . import onboard_company_candidates as onboarding
    from . import prepare_company_candidate_onboarding as preparation
except ImportError:  # pragma: no cover - direct execution
    import company_official_source_discovery as discovery  # type: ignore
    import onboard_company_candidates as onboarding  # type: ignore
    import prepare_company_candidate_onboarding as preparation  # type: ignore


PERSISTENT_HOLD_MARKERS = (
    "investment institution",
    "wikidata exact identity is a person",
    "wikidata identity is ambiguous",
    "wikidata has no exact identity",
    "wikidata exact identity has no official website",
    "wikidata returned no candidate",
    "no verified evidence-linked official site",
    "no verified official homepage",
    "official homepage does not name the resolved candidate",
    "official homepage does not support the candidate sector",
    "already belongs to another company",
)


def _persistent_hold_reason(reason: str) -> bool:
    text = str(reason or "").casefold()
    return any(marker in text for marker in PERSISTENT_HOLD_MARKERS)


def _current_persistent_hold(
    decision: dict[str, Any], candidate: dict[str, Any]
) -> bool:
    state = (
        decision.get("onboarding")
        if isinstance(decision.get("onboarding"), dict)
        else {}
    )
    if state.get("status") != "awaiting_profile":
        return False
    reason = str(state.get("error") or "")
    if not reason or not _persistent_hold_reason(reason):
        return False
    return str(state.get("evidenceFingerprint") or "") == onboarding.evidence_fingerprint(
        candidate
    )


def _can_bypass_persistent_hold(
    candidate: dict[str, Any],
    official_sources_payload: dict[str, Any],
    registry_payload: dict[str, Any],
) -> bool:
    if preparation.candidate_is_institution_like(candidate):
        return False
    if preparation._registry_match(registry_payload, candidate):
        return True
    return preparation._official_source_match(official_sources_payload, candidate) is not None


def _should_skip_persistent_hold(
    decision: dict[str, Any],
    candidate: dict[str, Any],
    official_sources_payload: dict[str, Any],
    registry_payload: dict[str, Any],
) -> bool:
    return _current_persistent_hold(decision, candidate) and not _can_bypass_persistent_hold(
        candidate, official_sources_payload, registry_payload
    )


def _working_decisions(
    decisions_payload: dict[str, Any],
    candidates_payload: dict[str, Any],
    official_sources_payload: dict[str, Any],
    registry_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    normalized = onboarding.normalize_decisions(decisions_payload)
    candidates = onboarding.candidate_index(candidates_payload)
    working: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []

    for key, decision in normalized["decisions"].items():
        candidate = candidates.get(key)
        if candidate and _should_skip_persistent_hold(
            decision, candidate, official_sources_payload, registry_payload
        ):
            skipped.append(key)
            continue

        row = dict(decision)
        state = row.get("onboarding") if isinstance(row.get("onboarding"), dict) else {}
        if state.get("status") == "awaiting_profile":
            # The candidate is being retried because evidence changed or a formal
            # registry/source now exists. Do not carry the stale hold into the
            # fresh attempt; a new persistent failure will be recorded below.
            row.pop("onboarding", None)
        working[key] = row

    return {
        "schemaVersion": normalized["schemaVersion"],
        "decisions": working,
    }, sorted(skipped)


def _persist_holds(
    decisions_payload: dict[str, Any],
    candidates_payload: dict[str, Any],
    holds: list[dict[str, str]],
) -> list[str]:
    candidates = onboarding.candidate_index(candidates_payload)
    persisted: list[str] = []

    for hold in holds:
        key = onboarding.decision_key(hold.get("candidateKey"))
        reason = str(hold.get("reason") or "")
        candidate = candidates.get(key)
        decision = decisions_payload.get("decisions", {}).get(key)
        if (
            not key
            or not candidate
            or not isinstance(decision, dict)
            or decision.get("status") != "accepted"
            or not _persistent_hold_reason(reason)
        ):
            continue

        decision["onboarding"] = {
            "status": "awaiting_profile",
            "mode": "create",
            "profile": {},
            "evidenceFingerprint": onboarding.evidence_fingerprint(candidate),
            "requestedAt": "",
            "requestedBy": "VCIQ/auto-profile-hold",
            "publishedAt": "",
            "publishedSlug": "",
            "error": reason,
        }
        persisted.append(key)

    return sorted(set(persisted))


def discover_candidate_identities(
    candidates_payload: dict[str, Any],
    decisions_payload: dict[str, Any],
    official_sources_payload: dict[str, Any],
    registry_payload: dict[str, Any],
    *,
    limit: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    candidates = onboarding.candidate_index(candidates_payload)
    decisions = onboarding.normalize_decisions(decisions_payload)
    verified: dict[str, dict[str, Any]] = {}
    verified_sources: dict[str, str] = {}
    attempted_reasons: dict[str, str] = {}
    holds: list[dict[str, str]] = []
    checked = 0

    for key, decision in decisions["decisions"].items():
        if checked >= max(1, limit):
            break
        if decision.get("status") != "accepted":
            continue
        state = (
            decision.get("onboarding")
            if isinstance(decision.get("onboarding"), dict)
            else {}
        )
        if state.get("status") in {"requested", "published", "failed", "merged"}:
            continue
        candidate = candidates.get(key)
        if not candidate:
            continue
        if preparation.candidate_is_institution_like(candidate):
            continue
        if preparation._registry_match(registry_payload, candidate):
            continue
        if preparation._official_source_match(official_sources_payload, candidate) is not None:
            continue
        if _should_skip_persistent_hold(
            decision, candidate, official_sources_payload, registry_payload
        ):
            continue

        checked += 1
        name = preparation.clean(candidate.get("name"), 240)
        name_key = preparation.identity_key(name)
        if not name_key:
            continue

        metadata, wikidata_reason = preparation.resolve_wikidata_company(name)
        if metadata is not None:
            verified[name_key] = metadata
            verified_sources[name_key] = "wikidata"
            continue

        metadata, discovery_reason = discovery.discover_verified_official_site(
            candidate,
            page_fetcher=preparation.fetch_official_page,
            identity_checker=preparation.page_supports_identity,
            sector_checker=preparation.page_supports_sector,
        )
        if metadata is not None:
            verified[name_key] = metadata
            verified_sources[name_key] = str(metadata.get("source") or "evidence-linked")
            continue

        reason = (
            f"{wikidata_reason or 'Wikidata unresolved'}; "
            f"{discovery_reason or 'no verified evidence-linked official site'}"
        )
        attempted_reasons[name_key] = reason
        holds.append({"candidateKey": key, "reason": reason})

    return verified, {
        "checkedCount": checked,
        "verifiedCount": len(verified),
        "verifiedKeys": sorted(verified),
        "verifiedSources": {
            key: verified_sources[key] for key in sorted(verified_sources)
        },
        "attemptedFailureCount": len(attempted_reasons),
        "attemptedReasons": {
            key: attempted_reasons[key] for key in sorted(attempted_reasons)
        },
        "holdCount": len(holds),
        "holds": sorted(holds, key=lambda row: row["candidateKey"]),
    }


def run(
    *,
    candidates_payload: dict[str, Any],
    decisions_payload: dict[str, Any],
    official_sources_payload: dict[str, Any],
    registry_payload: dict[str, Any],
    captures_payload: dict[str, Any],
    limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = onboarding.normalize_decisions(decisions_payload)
    working_decisions, skipped_holds = _working_decisions(
        normalized,
        candidates_payload,
        official_sources_payload,
        registry_payload,
    )
    discovered, discovery_report = discover_candidate_identities(
        candidates_payload,
        working_decisions,
        official_sources_payload,
        registry_payload,
        limit=limit,
    )
    attempted_reasons = discovery_report.get("attemptedReasons", {})
    attempted_reasons = attempted_reasons if isinstance(attempted_reasons, dict) else {}

    def resolver(name: str):
        key = preparation.identity_key(name)
        if key in discovered:
            return discovered[key], ""
        if key in attempted_reasons:
            # The bounded pre-resolution pass already exhausted exact Wikidata and
            # deterministic evidence-linked discovery for this identity. Reusing
            # the cached negative result avoids duplicate network traffic and makes
            # one run internally deterministic even if upstream sources change.
            return None, str(attempted_reasons[key])
        # Candidates beyond the bounded pre-discovery window retain the core
        # exact-Wikidata fallback instead of being silently disabled.
        return preparation.resolve_wikidata_company(name)

    prepared_decisions, onboarding_report = preparation.prepare_automatic_onboarding(
        candidates_payload,
        working_decisions,
        official_sources_payload,
        registry_payload,
        captures_payload,
        resolver=resolver,
        limit=limit,
    )
    normalized["decisions"].update(prepared_decisions.get("decisions", {}))
    holds = onboarding_report.get("holds", [])
    holds = holds if isinstance(holds, list) else []
    persisted_holds = _persist_holds(normalized, candidates_payload, holds)

    return normalized, {
        **onboarding_report,
        "persistedHoldCount": len(persisted_holds),
        "persistedHoldKeys": persisted_holds,
        "skippedPersistedHoldCount": len(skipped_holds),
        "skippedPersistedHoldKeys": skipped_holds,
        "sourceDiscovery": discovery_report,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=preparation.CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=preparation.DECISIONS_PATH)
    parser.add_argument(
        "--official-sources", type=Path, default=preparation.OFFICIAL_SOURCES_PATH
    )
    parser.add_argument("--registry", type=Path, default=preparation.REGISTRY_PATH)
    parser.add_argument("--captures", type=Path, default=preparation.CAPTURES_PATH)
    parser.add_argument("--limit", type=int, default=preparation.MAX_AUTO_REQUESTS)
    args = parser.parse_args()

    current = onboarding.load_json(
        args.decisions, {"schemaVersion": 1, "decisions": {}}
    )
    next_decisions, report = run(
        candidates_payload=onboarding.load_json(args.candidates, {"candidates": []}),
        decisions_payload=current,
        official_sources_payload=onboarding.load_json(
            args.official_sources, {"companies": []}
        ),
        registry_payload=onboarding.load_json(args.registry, {"companies": []}),
        captures_payload=onboarding.load_json(args.captures, {"records": []}),
        limit=max(1, args.limit),
    )
    changed = onboarding.normalize_decisions(current) != next_decisions
    if changed:
        write_json(args.decisions, next_decisions)
    print(json.dumps({"changed": changed, **report}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
