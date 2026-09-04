"""Build institution-level regulatory source observations from disclosure crawls.

Listed-company disclosure crawlers emit company/listing-level status rows.  The
public source directory, however, exposes institution-level regulatory entities
such as CNINFO, HKEX and SEC.  This module bridges only observations whose
provider attribution is unambiguous; it deliberately does not infer exchange
performance from mixed CNINFO/exchange rows or treat company IR mirrors as SEC
availability.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "listed_company_disclosure_sources.json"
DISCLOSURE_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"

REGULATORY_PREFIX = "regulatory:"
DIRECT_SEC_PREFIX = "sec-disclosure-"
US_IR_PREFIX = "us-ir-disclosure-"


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _errors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _state(*, accepted: int, errors: list[str], fallback: str = "empty") -> str:
    if accepted > 0:
        return "partial" if errors else "ok"
    return "error" if errors else fallback


def _aggregate_state(states: Iterable[str]) -> str:
    values = [str(value or "unknown").casefold() for value in states]
    if not values:
        return "unknown"
    successful = {"ok", "partial", "empty"}
    has_success = any(value in successful for value in values)
    has_error = any(value in {"error", "failed"} for value in values)
    if has_success and has_error:
        return "partial"
    if "partial" in values:
        return "partial"
    if "ok" in values:
        return "ok"
    if "empty" in values:
        return "empty"
    if has_error:
        return "error"
    return "unknown"


def _load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_disclosure_snapshot(path: Path = DISCLOSURE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _observation(
    source_key: str,
    *,
    state: str,
    scanned: Any,
    accepted: Any,
    errors: Any,
) -> tuple[str, dict[str, Any]]:
    error_rows = _errors(errors)
    return source_key, {
        "status": state,
        "scanned": _integer(scanned),
        "accepted": _integer(accepted),
        "failed": len(error_rows),
        "errors": error_rows,
    }


def _collect_observations(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    statuses = payload.get("sourceStatus", [])
    statuses = statuses if isinstance(statuses, list) else []

    for raw in statuses:
        if not isinstance(raw, dict):
            continue
        source_id = str(raw.get("id") or "")

        # SSE/SZSE observations come only from dedicated official endpoint
        # instrumentation. Never infer exchange performance from the mixed base
        # crawler counters or from CNINFO/Eastmoney content.
        if (
            source_id.startswith("exchange-disclosure-")
            and str(raw.get("market") or "") == "A股"
            and raw.get("exchangeDirectAttempted") is True
        ):
            exchange_name = str(raw.get("exchange") or "")
            expected_institution = {
                "上海证券交易所": "sse",
                "深圳证券交易所": "szse",
            }.get(exchange_name, "")
            observed_institution = str(raw.get("exchangeDirectInstitution") or "")
            if expected_institution and observed_institution == expected_institution:
                exchange_errors = _errors(raw.get("exchangeDirectErrors"))
                key, row = _observation(
                    expected_institution,
                    state=str(raw.get("exchangeDirectStatus") or "unknown").casefold(),
                    scanned=raw.get("exchangeDirectScanned"),
                    accepted=raw.get("exchangeDirectAccepted"),
                    errors=exchange_errors,
                )
                grouped[key].append(row)

        # CNINFO structured metrics are explicitly separated from the base
        # A-share exchange status by cninfo_structured_disclosures.py.
        if raw.get("structuredAttempted") is True:
            structured_errors = _errors(raw.get("structuredErrors"))
            structured_accepted = _integer(raw.get("structuredAccepted"))
            key, row = _observation(
                "cninfo",
                state=_state(
                    accepted=structured_accepted,
                    errors=structured_errors,
                ),
                scanned=raw.get("structuredScanned"),
                accepted=structured_accepted,
                errors=structured_errors,
            )
            grouped[key].append(row)

        # HKEX listing rows are direct and are not rewritten by the CNINFO
        # enrichment.  If Eastmoney fallback supplied the accepted records,
        # keep the HKEX observation as a failed direct attempt instead of
        # attributing the fallback rows to HKEX.
        if (
            source_id.startswith("exchange-disclosure-")
            and str(raw.get("market") or "") == "港股"
        ):
            fallback_used = raw.get("fallbackUsed") is True
            direct_errors = _errors(raw.get("errors"))
            direct_accepted = 0 if fallback_used else _integer(raw.get("accepted"))
            direct_state = (
                "error"
                if fallback_used
                else str(raw.get("status") or "unknown").casefold()
            )
            key, row = _observation(
                "hkex",
                state=direct_state,
                scanned=raw.get("scanned"),
                accepted=direct_accepted,
                errors=direct_errors,
            )
            grouped[key].append(row)

        # Direct SEC rows are safe to aggregate.  Current production normally
        # replaces them with company-IR mirror rows because shared CI addresses
        # are blocked by SEC; those us-ir rows are intentionally ignored here.
        if source_id.startswith(DIRECT_SEC_PREFIX):
            sec_errors = _errors(raw.get("errors"))
            key, row = _observation(
                "sec",
                state=str(raw.get("status") or "unknown").casefold(),
                scanned=raw.get("scanned"),
                accepted=raw.get("accepted"),
                errors=sec_errors,
            )
            grouped[key].append(row)

        # Do not bridge the following:
        # - Legacy SSE/SZSE rows without exchangeDirect* evidence: aggregate
        #   counters can mix CNINFO and exchange-origin candidates.
        # - Eastmoney fallback: it is a database fallback, not a regulator.
        # - us-ir-disclosure-* rows: they prove issuer IR availability, not SEC.
        if source_id.startswith(US_IR_PREFIX):
            continue

    return dict(grouped)


def regulatory_source_statuses(
    payload: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return auditable institution-level statuses for this disclosure run."""

    config = config or _load_config()
    official_sources = config.get("officialSources", {})
    official_sources = official_sources if isinstance(official_sources, dict) else {}
    observations = _collect_observations(payload)
    result: list[dict[str, Any]] = []

    for source_key in sorted(observations):
        rows = observations[source_key]
        source = official_sources.get(source_key, {})
        source = source if isinstance(source, dict) else {}
        errors = [error for row in rows for error in _errors(row.get("errors"))]
        result.append(
            {
                "id": f"{REGULATORY_PREFIX}{source_key}",
                "name": str(source.get("name") or source_key),
                "platform": str(source.get("name") or "监管机构"),
                "sourceLevel": "监管文件",
                "sourceRole": "primary",
                "url": str(source.get("homepage") or ""),
                "status": _aggregate_state(str(row.get("status") or "") for row in rows),
                "scanned": sum(_integer(row.get("scanned")) for row in rows),
                "accepted": sum(_integer(row.get("accepted")) for row in rows),
                "failed": sum(_integer(row.get("failed")) for row in rows),
                "errors": errors,
                "evidenceAggregation": "institution-from-disclosure-channels",
                "observationCount": len(rows),
            }
        )
    return result


def merge_regulatory_statuses(
    article_payload: dict[str, Any],
    disclosure_payload: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge regulatory statuses into the full-refresh source-status ledger."""

    existing = article_payload.get("sourceStatus", [])
    existing = existing if isinstance(existing, list) else []
    retained = [
        row
        for row in existing
        if isinstance(row, dict)
        and not str(row.get("id") or "").startswith(REGULATORY_PREFIX)
    ]
    article_payload["sourceStatus"] = [
        *retained,
        *regulatory_source_statuses(disclosure_payload, config=config),
    ]
    return article_payload
