#!/usr/bin/env python3
"""Validate and apply authenticated company-candidate review decisions.

This module is intentionally narrow. It writes only the private candidate decision
ledger consumed by the existing company onboarding workflow. A decision never
creates a company profile directly: accepted/merged candidates still pass the
existing onboarding, official-source and profile quality gates.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "config" / "company_candidate_review_queue.json"
DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"
REGISTRY_PATH = ROOT / "config" / "company_registry.json"

VALID_ACTIONS = {"accepted", "rejected", "merged"}
FINAL_STATUSES = {"accepted", "rejected", "merged", "published"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReviewDecisionError(ValueError):
    pass


def clean(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def normalize_identity(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean(value, 240)).casefold()
    return "".join(
        character
        for character in text
        if character.isascii() and character.isalnum()
        or "\u3400" <= character <= "\u9fff"
    )


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReviewDecisionError(f"{path.name} must contain a JSON object")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat()


def candidate_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("candidates", [])
    if not isinstance(raw, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        key = normalize_identity(row.get("decisionKey") or row.get("name"))
        if key:
            result[key] = row
    return result


def decision_index(payload: Mapping[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    raw = payload.get("decisions", {})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for raw_key, row in raw.items():
        if not isinstance(row, dict):
            continue
        key = normalize_identity(raw_key)
        if key:
            result[key] = (str(raw_key), row)
    return result


def registry_slugs(payload: Mapping[str, Any]) -> set[str]:
    rows = payload.get("companies", [])
    if not isinstance(rows, list):
        return set()
    return {
        clean(row.get("slug"), 120)
        for row in rows
        if isinstance(row, dict) and clean(row.get("slug"), 120)
    }


def validate_review_request(
    *,
    candidate_key: Any,
    action: Any,
    note: Any,
    merged_slug: Any,
    reviewed_by: Any,
    expected_revision: Any,
) -> dict[str, str]:
    key = normalize_identity(candidate_key)
    if len(key) < 2 or len(key) > 200:
        raise ReviewDecisionError("candidate key is invalid")

    decision = clean(action, 30).casefold()
    if decision not in VALID_ACTIONS:
        raise ReviewDecisionError("decision must be accepted, rejected, or merged")

    public_note = clean(note, 500)
    if len(public_note) < 2:
        raise ReviewDecisionError("a public review note is required")

    merge_target = clean(merged_slug, 120).casefold()
    if decision == "merged":
        if not SLUG_RE.fullmatch(merge_target):
            raise ReviewDecisionError("merged decisions require a valid existing company slug")
    elif merge_target:
        raise ReviewDecisionError("mergedSlug is only valid for merged decisions")

    actor = clean(reviewed_by, 120)
    if not actor or "@" in actor:
        raise ReviewDecisionError("reviewedBy must be a public audit actor label, not an email address")

    revision = clean(expected_revision, 40).casefold()
    if not SHA_RE.fullmatch(revision):
        raise ReviewDecisionError("expected revision must be a full git SHA")

    return {
        "candidateKey": key,
        "decision": decision,
        "note": public_note,
        "mergedSlug": merge_target,
        "reviewedBy": actor,
        "expectedRevision": revision,
    }


def apply_review_decision(
    candidates_payload: Mapping[str, Any],
    decisions_payload: Mapping[str, Any],
    registry_payload: Mapping[str, Any],
    request: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = candidate_index(candidates_payload)
    key = request["candidateKey"]
    candidate = candidates.get(key)
    if candidate is None:
        raise ReviewDecisionError("candidate is no longer present in the review queue")
    if clean(candidate.get("status"), 30) != "pending":
        raise ReviewDecisionError("candidate is no longer pending review")

    action = request["decision"]
    merge_target = request["mergedSlug"]
    if action == "merged" and merge_target not in registry_slugs(registry_payload):
        raise ReviewDecisionError("merge target does not exist in the company registry")

    root = copy.deepcopy(decisions_payload) if isinstance(decisions_payload, Mapping) else {}
    if not isinstance(root, dict):
        root = {}
    root["schemaVersion"] = max(1, int(root.get("schemaVersion", 1) or 1))
    raw_decisions = root.get("decisions")
    if not isinstance(raw_decisions, dict):
        raw_decisions = {}
        root["decisions"] = raw_decisions

    existing_index = decision_index(root)
    existing = existing_index.get(key)
    if existing:
        existing_status = clean(existing[1].get("status"), 30)
        if existing_status in FINAL_STATUSES:
            same_target = clean(existing[1].get("mergedSlug"), 120) == merge_target
            if existing_status == action and same_target:
                return root, {
                    "ok": True,
                    "changed": False,
                    "candidateKey": key,
                    "name": clean(candidate.get("name"), 240),
                    "decision": existing_status,
                    "mergedSlug": merge_target,
                    "message": "candidate already has the requested final review decision",
                    "requiresOnboarding": action in {"accepted", "merged"},
                }
            raise ReviewDecisionError(
                f"candidate already has final decision {existing_status}; final review decisions are immutable"
            )

    raw_key = existing[0] if existing else clean(candidate.get("decisionKey"), 200) or key
    previous = copy.deepcopy(existing[1]) if existing else {}
    previous.update(
        {
            "status": action,
            "note": request["note"],
            "mergedSlug": merge_target,
            "decidedAt": now_iso(now),
            "reviewedBy": request["reviewedBy"],
        }
    )
    raw_decisions[raw_key] = previous

    report = {
        "ok": True,
        "changed": True,
        "candidateKey": key,
        "name": clean(candidate.get("name"), 240),
        "decision": action,
        "mergedSlug": merge_target,
        "message": "review decision validated" if action != "merged" else "merge decision validated against existing registry slug",
        "requiresOnboarding": action in {"accepted", "merged"},
    }
    return root, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["validate", "apply"], required=True)
    parser.add_argument("--candidate-key", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--merged-slug", default="")
    parser.add_argument("--note", required=True)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--candidates", default=str(CANDIDATES_PATH))
    parser.add_argument("--decisions", default=str(DECISIONS_PATH))
    parser.add_argument("--registry", default=str(REGISTRY_PATH))
    args = parser.parse_args()

    request = validate_review_request(
        candidate_key=args.candidate_key,
        action=args.decision,
        note=args.note,
        merged_slug=args.merged_slug,
        reviewed_by=args.reviewed_by,
        expected_revision=args.expected_revision,
    )
    candidates_path = Path(args.candidates)
    decisions_path = Path(args.decisions)
    registry_path = Path(args.registry)
    updated, report = apply_review_decision(
        load_json(candidates_path),
        load_json(decisions_path),
        load_json(registry_path),
        request,
    )
    if args.mode == "apply" and report["changed"]:
        write_json(decisions_path, updated)
    report["mode"] = args.mode
    report["expectedRevision"] = request["expectedRevision"]
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
