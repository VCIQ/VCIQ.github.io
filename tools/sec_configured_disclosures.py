#!/usr/bin/env python3
"""Run SEC EDGAR enrichment with a verified configured-CIK registry first.

The SEC company-ticker index may reject shared CI runners. Current tracked US
companies therefore use CIKs verified from their SEC entity pages and stored in
``listed_company_disclosure_sources.json``. Dynamic ticker lookup remains a
fallback only for newly added companies that do not yet have a configured CIK.

The ``--observation-only`` mode performs the same direct SEC submissions
requests against an empty US content seed and writes only current-run
``sec-disclosure-*`` status evidence plus ``secStructured`` metadata back into
the real snapshot. This keeps direct SEC availability evidence independent from
company-IR fallback content.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Callable

try:
    from . import crawl_listed_company_disclosures as base
    from . import sec_structured_disclosures as sec
except ImportError:
    import crawl_listed_company_disclosures as base
    import sec_structured_disclosures as sec


DIRECT_SEC_PREFIX = "sec-disclosure-"


def normalize_cik(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    try:
        numeric = int(digits)
    except ValueError:
        return ""
    return f"{numeric:010d}" if numeric > 0 else ""


def configured_ticker_ciks(
    listings: list[sec.USListing],
    config: dict[str, Any],
) -> tuple[dict[str, str], list[sec.USListing]]:
    registry = config.get("secCiks", {})
    registry = registry if isinstance(registry, dict) else {}
    resolved: dict[str, str] = {}
    missing: list[sec.USListing] = []
    for listing in listings:
        cik = normalize_cik(registry.get(listing.catalog_slug))
        if cik:
            resolved[listing.ticker.upper()] = cik
        else:
            missing.append(listing)
    return resolved, missing


def resolve_ticker_ciks(
    listings: list[sec.USListing],
    config: dict[str, Any],
    *,
    index_fetcher: Callable[..., dict[str, Any]] = sec.fetch_json,
) -> tuple[dict[str, str], dict[str, Any]]:
    resolved, missing = configured_ticker_ciks(listings, config)
    configured_tickers = sorted(resolved)
    metadata: dict[str, Any] = {
        "configuredListingCount": len(listings) - len(missing),
        "configuredTickers": configured_tickers,
        "dynamicLookupAttempted": bool(missing),
        "dynamicResolvedCount": 0,
        "dynamicResolvedTickers": [],
        "dynamicLookupErrors": [],
    }
    if not missing:
        return resolved, metadata

    settings = config.get("settings", {})
    try:
        index_payload = index_fetcher(
            sec.TICKER_INDEX_URL,
            timeout=int(settings.get("requestTimeout", 18)),
            attempts=int(settings.get("requestAttempts", 2)),
        )
        dynamic = sec.parse_ticker_index(index_payload)
    except Exception as exc:  # noqa: BLE001 - unresolved listings remain explicit.
        dynamic = {}
        metadata["dynamicLookupErrors"] = [f"{type(exc).__name__}:{exc}"]

    for listing in missing:
        ticker = listing.ticker.upper()
        cik = normalize_cik(dynamic.get(ticker))
        if cik:
            resolved[ticker] = cik
            metadata["dynamicResolvedCount"] += 1
            metadata["dynamicResolvedTickers"].append(ticker)
    return resolved, metadata


def verify_submission_identity(
    payload: dict[str, Any],
    *,
    expected_ticker: str,
    expected_cik: str,
) -> None:
    actual_cik = normalize_cik(payload.get("cik"))
    if actual_cik and actual_cik != normalize_cik(expected_cik):
        raise RuntimeError(
            f"SEC submission CIK mismatch: expected {expected_cik}, got {actual_cik}"
        )
    tickers = payload.get("tickers", [])
    actual_tickers = {
        str(value or "").upper().strip()
        for value in tickers
        if str(value or "").strip()
    } if isinstance(tickers, list) else set()
    if actual_tickers and expected_ticker.upper() not in actual_tickers:
        raise RuntimeError(
            "SEC submission ticker mismatch: "
            f"expected {expected_ticker}, got {sorted(actual_tickers)}"
        )


def verified_submissions_fetcher(
    ticker_ciks: dict[str, str],
    *,
    fetcher: Callable[..., dict[str, Any]] = sec.fetch_json,
) -> Callable[..., dict[str, Any]]:
    expected_by_cik = {
        normalize_cik(cik): ticker.upper()
        for ticker, cik in ticker_ciks.items()
        if normalize_cik(cik)
    }

    def fetch(url: str, *, timeout: int, attempts: int) -> dict[str, Any]:
        payload = fetcher(url, timeout=timeout, attempts=attempts)
        match = re.search(r"CIK(\d{1,10})\.json", url, flags=re.IGNORECASE)
        if not match:
            raise RuntimeError(f"unrecognized SEC submissions URL: {url}")
        cik = normalize_cik(match.group(1))
        expected_ticker = expected_by_cik.get(cik)
        if not expected_ticker:
            raise RuntimeError(f"SEC CIK is not registered for this run: {cik}")
        verify_submission_identity(
            payload,
            expected_ticker=expected_ticker,
            expected_cik=cik,
        )
        return payload

    return fetch


def apply_registry_metadata(
    snapshot: dict[str, Any],
    listings: list[sec.USListing],
    registry_metadata: dict[str, Any],
) -> dict[str, Any]:
    result = json.loads(json.dumps(snapshot, ensure_ascii=False))
    configured_tickers = {
        str(value).upper()
        for value in registry_metadata.get("configuredTickers", [])
    }
    statuses = [
        status
        for status in result.get("sourceStatus", [])
        if isinstance(status, dict)
    ]
    listing_by_id = {listing.source_id: listing for listing in listings}
    for status in statuses:
        listing = listing_by_id.get(str(status.get("id", "")))
        if not listing:
            continue
        status["cikSource"] = (
            "configured-official-registry"
            if listing.ticker.upper() in configured_tickers
            else "dynamic-sec-ticker-index"
        )
    result["sourceStatus"] = statuses
    metadata = result.get("secStructured")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    metadata["cikRegistry"] = registry_metadata
    result["secStructured"] = metadata
    return result


def build_observation_snapshot(
    previous: dict[str, Any],
    listings: list[sec.USListing] | None = None,
    config: dict[str, Any] | None = None,
    *,
    index_fetcher: Callable[..., dict[str, Any]] = sec.fetch_json,
    submissions_fetcher: Callable[..., dict[str, Any]] = sec.fetch_json,
) -> dict[str, Any]:
    """Merge only current-run direct SEC status evidence into ``previous``.

    Direct EDGAR requests run against an empty US content seed. This prevents
    previously retained company-IR events from changing a failed direct SEC
    attempt into a misleading ``retained`` status and prevents direct SEC
    content events from leaking into the IR fallback content path.
    """

    rows = list(listings or sec.load_us_listings())
    config = config or base.load_config()
    settings = config.get("settings", {})
    ticker_ciks, registry_metadata = resolve_ticker_ciks(
        rows,
        config,
        index_fetcher=index_fetcher,
    )

    seed: dict[str, Any] = {"companies": {}, "sourceStatus": []}
    observed = sec.enrich_snapshot(
        seed,
        rows,
        ticker_ciks,
        settings,
        submissions_fetcher=verified_submissions_fetcher(
            ticker_ciks,
            fetcher=submissions_fetcher,
        ),
    )
    observed = apply_registry_metadata(observed, rows, registry_metadata)
    observed_at = str(observed.get("generatedAt", ""))
    current_ids = {listing.source_id for listing in rows}

    direct_statuses: list[dict[str, Any]] = []
    for status in observed.get("sourceStatus", []):
        if not isinstance(status, dict):
            continue
        if str(status.get("id", "")) not in current_ids:
            continue
        row = dict(status)
        row["observedAt"] = observed_at
        direct_statuses.append(row)

    result = json.loads(json.dumps(previous, ensure_ascii=False))
    existing_statuses = [
        status
        for status in result.get("sourceStatus", [])
        if isinstance(status, dict)
        and not str(status.get("id", "")).startswith(DIRECT_SEC_PREFIX)
    ]
    result["sourceStatus"] = [*existing_statuses, *direct_statuses]

    metadata = observed.get("secStructured")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    metadata["observationOnly"] = True
    metadata["observedAt"] = observed_at
    result["secStructured"] = metadata
    result["generatedAt"] = observed_at
    return result


def validate_observation_snapshot(
    snapshot: dict[str, Any],
    listings: list[sec.USListing] | None = None,
) -> list[str]:
    rows = list(listings or sec.load_us_listings())
    errors: list[str] = []
    statuses = {
        str(status.get("id", "")): status
        for status in snapshot.get("sourceStatus", [])
        if isinstance(status, dict)
        and str(status.get("id", "")).startswith(DIRECT_SEC_PREFIX)
    }
    metadata = snapshot.get("secStructured", {})
    observed_at = str(metadata.get("observedAt", "")) if isinstance(metadata, dict) else ""

    for listing in rows:
        status = statuses.get(listing.source_id)
        if not status:
            errors.append(f"missing direct SEC observation: {listing.source_id}")
            continue
        if status.get("provider") != sec.PROVIDER:
            errors.append(f"direct SEC provider mismatch: {listing.source_id}")
        if status.get("attempted") is not True:
            errors.append(f"direct SEC source not attempted: {listing.source_id}")
        if status.get("cikResolved") is not True:
            errors.append(f"direct SEC CIK unresolved: {listing.source_id}")
        if not status.get("cikSource"):
            errors.append(f"direct SEC CIK source missing: {listing.source_id}")
        if not status.get("observedAt") or status.get("observedAt") != observed_at:
            errors.append(f"direct SEC observation timestamp mismatch: {listing.source_id}")
        scanned = int(status.get("scanned", 0) or 0)
        accepted = int(status.get("accepted", 0) or 0)
        if scanned < 0 or accepted < 0 or accepted > scanned:
            errors.append(f"invalid direct SEC counters: {listing.source_id}")

    if not isinstance(metadata, dict):
        errors.append("secStructured observation metadata missing")
    else:
        if metadata.get("provider") != sec.PROVIDER:
            errors.append("secStructured observation provider mismatch")
        if metadata.get("observationOnly") is not True:
            errors.append("secStructured observation-only marker missing")
        if not observed_at:
            errors.append("secStructured observation timestamp missing")
        if int(metadata.get("attemptedListingCount", -1)) != len(rows):
            errors.append("secStructured observation listing count mismatch")
    return errors


def validate_registry_coverage(
    snapshot: dict[str, Any],
    listings: list[sec.USListing],
) -> list[str]:
    errors = sec.validate_enrichment(snapshot, listings, require_events=True)
    statuses = {
        str(status.get("id", "")): status
        for status in snapshot.get("sourceStatus", [])
        if isinstance(status, dict)
    }
    for listing in listings:
        status = statuses.get(listing.source_id, {})
        if not status.get("cikSource"):
            errors.append(f"SEC CIK source missing: {listing.source_id}")
        if int(status.get("accepted", 0) or 0) <= 0:
            errors.append(f"SEC source accepted no filings: {listing.source_id}")
    metadata = snapshot.get("secStructured", {})
    registry = metadata.get("cikRegistry", {}) if isinstance(metadata, dict) else {}
    if not isinstance(registry, dict):
        errors.append("SEC CIK registry metadata missing")
    elif int(registry.get("configuredListingCount", -1)) < len(listings):
        unresolved = [
            listing.source_id
            for listing in listings
            if not statuses.get(listing.source_id, {}).get("cikResolved")
        ]
        if unresolved:
            errors.append("unresolved SEC listings: " + ", ".join(unresolved))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-events", action="store_true")
    parser.add_argument("--observation-only", action="store_true")
    args = parser.parse_args()

    listings = sec.load_us_listings()
    if args.check:
        snapshot = base.load_previous(sec.OUTPUT_PATH)
        errors = (
            validate_observation_snapshot(snapshot, listings)
            if args.observation_only
            else validate_registry_coverage(snapshot, listings)
        )
        if errors:
            raise SystemExit("; ".join(errors))
        print(
            json.dumps(
                {
                    "passed": True,
                    "listedCompanyCount": len(listings),
                    "acceptedEventCount": snapshot.get("secStructured", {}).get(
                        "acceptedEventCount", 0
                    ),
                    "observationOnly": args.observation_only,
                },
                ensure_ascii=False,
            )
        )
        return 0

    config = base.load_config()
    if args.observation_only:
        snapshot = build_observation_snapshot(
            base.load_previous(sec.OUTPUT_PATH),
            listings,
            config,
        )
        errors = validate_observation_snapshot(snapshot, listings)
        if errors:
            raise SystemExit("; ".join(errors))
        sec.write_snapshot(snapshot, sec.OUTPUT_PATH)
        return 0

    settings = config["settings"]
    ticker_ciks, registry_metadata = resolve_ticker_ciks(listings, config)
    snapshot = base.load_previous(sec.OUTPUT_PATH)
    enriched = sec.enrich_snapshot(
        snapshot,
        listings,
        ticker_ciks,
        settings,
        submissions_fetcher=verified_submissions_fetcher(ticker_ciks),
    )
    enriched = apply_registry_metadata(
        enriched,
        listings,
        registry_metadata,
    )
    errors = (
        validate_registry_coverage(enriched, listings)
        if args.require_events
        else sec.validate_enrichment(enriched, listings)
    )
    if errors:
        raise SystemExit("; ".join(errors))
    sec.write_snapshot(enriched, sec.OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
