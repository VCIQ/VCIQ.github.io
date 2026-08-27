#!/usr/bin/env python3
"""Validate and apply authenticated company-candidate review decisions.

Human review answers one narrow question: is this candidate a company, not a
company, or an alias of an existing company? Review decisions are intentionally
separate from publication. Accepted/merged candidates still pass the existing
official-source, profile and publication quality gates.

Batch review uses a candidate-specific SHA-256 evidence fingerprint instead of a
repository-wide main SHA. Unrelated repository writes therefore do not invalidate
a human decision, while any change to the reviewed candidate evidence still does.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "config" / "company_candidate_review_queue.json"
DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"
REGISTRY_PATH = ROOT / "config" / "company_registry.json"

VALID_ACTIONS = {"accepted", "rejected", "merged"}
FINAL_STATUSES = {"accepted", "rejected", "merged", "published"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_BATCH = 20


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


def _string_list(value: Any, limit: int = 40) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({clean(item, 2_000) for item in value if clean(item, 2_000)})[:limit]


def candidate_review_fingerprint(candidate: Mapping[str, Any]) -> str:
    """Fingerprint only evidence that can change the human identity decision."""
    payload = {
        "decisionKey": normalize_identity(candidate.get("decisionKey") or candidate.get("name")),
        "score": max(0, min(100, int(candidate.get("score", 0) or 0))),
        "articleCount": max(0, int(candidate.get("articleCount", 0) or 0)),
        "sourceCount": max(0, int(candidate.get("sourceCount", 0) or 0)),
        "sourceArticleIds": _string_list(candidate.get("sourceArticleIds")),
        "sourceUrls": _string_list(candidate.get("sourceUrls")),
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_homepage(value: Any) -> str:
    url = clean(value, 2_000)
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return url


def default_note(action: str) -> str:
    if action == "accepted":
        return "人工确认该候选为独立公司实体；正式发布仍须通过自动建档、官方来源和质量门。"
    if action == "rejected":
        return "人工确认该候选不是应进入公司目录的独立公司实体。"
    return "人工确认该候选应合并到现有公司实体；别名关系仍须通过后续校验。"


def validate_review_request(
    *,
    candidate_key: Any,
    action: Any,
    note: Any = "",
    merged_slug: Any = "",
    reviewed_by: Any,
    candidate_fingerprint: Any = "",
    homepage_hint: Any = "",
) -> dict[str, str]:
    key = normalize_identity(candidate_key)
    if len(key) < 2 or len(key) > 200:
        raise ReviewDecisionError("candidate key is invalid")

    decision = clean(action, 30).casefold()
    if decision not in VALID_ACTIONS:
        raise ReviewDecisionError("decision must be accepted, rejected, or merged")

    public_note = clean(note, 500) or default_note(decision)

    merge_target = clean(merged_slug, 120).casefold()
    if decision == "merged":
        if not SLUG_RE.fullmatch(merge_target):
            raise ReviewDecisionError("merged decisions require a valid existing company slug")
    elif merge_target:
        raise ReviewDecisionError("mergedSlug is only valid for merged decisions")

    actor = clean(reviewed_by, 120)
    if not actor or "@" in actor:
        raise ReviewDecisionError("reviewedBy must be a public audit actor label, not an email address")

    fingerprint = clean(candidate_fingerprint, 64).casefold()
    if fingerprint and not FINGERPRINT_RE.fullmatch(fingerprint):
        raise ReviewDecisionError("candidate fingerprint must be a SHA-256 hex digest")

    homepage = _safe_homepage(homepage_hint)
    if clean(homepage_hint, 2_000) and not homepage:
        raise ReviewDecisionError("homepage hint must be a public http(s) URL")
    if decision != "accepted" and homepage:
        raise ReviewDecisionError("homepage hint is only valid for accepted decisions")

    return {
        "candidateKey": key,
        "decision": decision,
        "note": public_note,
        "mergedSlug": merge_target,
        "reviewedBy": actor,
        "candidateFingerprint": fingerprint,
        "homepageHint": homepage,
    }


def validate_review_requests(raw: Any, *, reviewed_by: str) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ReviewDecisionError("decisions batch must be a non-empty JSON array")
    if len(raw) > MAX_BATCH:
        raise ReviewDecisionError(f"at most {MAX_BATCH} candidate decisions may be submitted at once")
    requests: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ReviewDecisionError("every batch decision must be a JSON object")
        request = validate_review_request(
            candidate_key=item.get("candidateKey"),
            action=item.get("decision"),
            note=item.get("note", ""),
            merged_slug=item.get("mergedSlug", ""),
            reviewed_by=reviewed_by,
            candidate_fingerprint=item.get("candidateFingerprint", ""),
            homepage_hint=item.get("homepageHint", ""),
        )
        if request["candidateKey"] in seen:
            raise ReviewDecisionError("the same candidate cannot appear twice in one batch")
        seen.add(request["candidateKey"])
        requests.append(request)
    return requests


def _preflight_requests(
    candidates_payload: Mapping[str, Any],
    registry_payload: Mapping[str, Any],
    requests: list[Mapping[str, str]],
) -> None:
    candidates = candidate_index(candidates_payload)
    slugs = registry_slugs(registry_payload)
    for request in requests:
        candidate = candidates.get(request["candidateKey"])
        if candidate is None:
            raise ReviewDecisionError(
                f"candidate {request['candidateKey']} is no longer present in the review queue"
            )
        if clean(candidate.get("status"), 30) != "pending":
            raise ReviewDecisionError(
                f"candidate {request['candidateKey']} is no longer pending review"
            )
        expected = request.get("candidateFingerprint", "")
        if expected and candidate_review_fingerprint(candidate) != expected:
            raise ReviewDecisionError(
                f"candidate {request['candidateKey']} evidence changed; refresh the review queue"
            )
        if request["decision"] == "merged" and request["mergedSlug"] not in slugs:
            raise ReviewDecisionError(
                f"merge target {request['mergedSlug']} does not exist in the company registry"
            )


def _apply_one(
    candidates_payload: Mapping[str, Any],
    decisions_payload: Mapping[str, Any],
    request: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = candidate_index(candidates_payload)[request["candidateKey"]]
    action = request["decision"]
    merge_target = request["mergedSlug"]

    root = copy.deepcopy(decisions_payload) if isinstance(decisions_payload, Mapping) else {}
    if not isinstance(root, dict):
        root = {}
    root["schemaVersion"] = max(1, int(root.get("schemaVersion", 1) or 1))
    raw_decisions = root.get("decisions")
    if not isinstance(raw_decisions, dict):
        raw_decisions = {}
        root["decisions"] = raw_decisions

    existing_index = decision_index(root)
    existing = existing_index.get(request["candidateKey"])
    if existing:
        existing_status = clean(existing[1].get("status"), 30)
        if existing_status in FINAL_STATUSES:
            same_target = clean(existing[1].get("mergedSlug"), 120) == merge_target
            if existing_status == action and same_target:
                return root, {
                    "ok": True,
                    "changed": False,
                    "candidateKey": request["candidateKey"],
                    "name": clean(candidate.get("name"), 240),
                    "decision": existing_status,
                    "mergedSlug": merge_target,
                    "message": "candidate already has the requested final review decision",
                    "requiresOnboarding": action in {"accepted", "merged"},
                }
            raise ReviewDecisionError(
                f"candidate {request['candidateKey']} already has final decision {existing_status}"
            )

    raw_key = existing[0] if existing else clean(candidate.get("decisionKey"), 200) or request["candidateKey"]
    previous = copy.deepcopy(existing[1]) if existing else {}
    previous.update(
        {
            "status": action,
            "note": request["note"],
            "mergedSlug": merge_target,
            "homepageHint": request.get("homepageHint", "") if action == "accepted" else "",
            "decidedAt": now_iso(now),
            "reviewedBy": request["reviewedBy"],
        }
    )
    raw_decisions[raw_key] = previous

    return root, {
        "ok": True,
        "changed": True,
        "candidateKey": request["candidateKey"],
        "name": clean(candidate.get("name"), 240),
        "decision": action,
        "mergedSlug": merge_target,
        "homepageHint": request.get("homepageHint", ""),
        "message": "review decision validated",
        "requiresOnboarding": action in {"accepted", "merged"},
    }


def apply_review_decisions(
    candidates_payload: Mapping[str, Any],
    decisions_payload: Mapping[str, Any],
    registry_payload: Mapping[str, Any],
    requests: list[Mapping[str, str]],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _preflight_requests(candidates_payload, registry_payload, requests)
    updated: Mapping[str, Any] = decisions_payload
    reports: list[dict[str, Any]] = []
    timestamp = now or datetime.now(UTC)
    for request in requests:
        updated, report = _apply_one(
            candidates_payload,
            updated,
            request,
            now=timestamp,
        )
        reports.append(report)
    changed_count = sum(1 for report in reports if report.get("changed"))
    return dict(updated), {
        "ok": True,
        "changed": changed_count > 0,
        "changedCount": changed_count,
        "decisionCount": len(reports),
        "requiresOnboarding": any(report.get("requiresOnboarding") for report in reports),
        "reports": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["validate", "apply"], required=True)
    parser.add_argument("--batch-json", default="")
    parser.add_argument("--candidate-key", default="")
    parser.add_argument("--decision", default="")
    parser.add_argument("--candidate-fingerprint", default="")
    parser.add_argument("--merged-slug", default="")
    parser.add_argument("--homepage-hint", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--candidates", default=str(CANDIDATES_PATH))
    parser.add_argument("--decisions", default=str(DECISIONS_PATH))
    parser.add_argument("--registry", default=str(REGISTRY_PATH))
    args = parser.parse_args()

    if args.batch_json:
        try:
            raw_batch = json.loads(args.batch_json)
        except json.JSONDecodeError as exc:
            raise ReviewDecisionError("batch JSON is invalid") from exc
        requests = validate_review_requests(raw_batch, reviewed_by=args.reviewed_by)
    else:
        requests = [
            validate_review_request(
                candidate_key=args.candidate_key,
                action=args.decision,
                note=args.note,
                merged_slug=args.merged_slug,
                reviewed_by=args.reviewed_by,
                candidate_fingerprint=args.candidate_fingerprint,
                homepage_hint=args.homepage_hint,
            )
        ]

    candidates_path = Path(args.candidates)
    decisions_path = Path(args.decisions)
    registry_path = Path(args.registry)
    updated, report = apply_review_decisions(
        load_json(candidates_path),
        load_json(decisions_path),
        load_json(registry_path),
        requests,
    )
    if args.mode == "apply" and report["changed"]:
        write_json(decisions_path, updated)
    report["mode"] = args.mode
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
