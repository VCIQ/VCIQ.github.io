#!/usr/bin/env python3
"""Record strict institution-level observations from SSE and SZSE official endpoints.

The existing listed-company crawler intentionally mixes several discovery paths so it
can maximize document coverage. Those aggregate counters are useful for the content
pipeline but cannot be attributed to one exchange after CNINFO enrichment. This
module is deliberately narrower: it queries only official SSE/SZSE structured
endpoints and stores the resulting observation in separate ``exchangeDirect*`` fields
on each A-share listing status. It does not publish documents and does not mutate the
existing aggregate status counters.
"""

from __future__ import annotations

import argparse
import json
import time
from http.cookiejar import CookieJar
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

try:
    from . import crawl_listed_company_disclosures as base
except ImportError:
    import crawl_listed_company_disclosures as base

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
CONFIG_PATH = ROOT / "config" / "listed_company_disclosure_sources.json"
SSE_ENDPOINT = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"
SZSE_HOME = "https://www.szse.cn/disclosure/listed/notice/index.html"
SZSE_ENDPOINT = "https://www.szse.cn/api/disc/announcement/annList"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_snapshot(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_settings(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = _load_json(path)
    settings = payload.get("settings", {})
    return settings if isinstance(settings, dict) else {}


def _decode_json(payload: bytes | str) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload)
    stripped = text.strip()
    if not stripped:
        return {}
    candidates = [stripped]
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        candidates.append(stripped[first : last + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _sse_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    page_help = payload.get("pageHelp", {})
    if isinstance(page_help, dict) and isinstance(page_help.get("data"), list):
        return [row for row in page_help["data"] if isinstance(row, dict)]
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _szse_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _title(row: dict[str, Any]) -> str:
    for key in (
        "TITLE",
        "title",
        "bulletinTitle",
        "BULLETIN_TITLE",
        "announcementTitle",
    ):
        value = base.clean_text(row.get(key), 800)
        if value:
            return value
    return ""


def _classify_rows(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    material = list(rows)
    accepted = sum(1 for row in material if base.classify_document(_title(row)))
    return len(material), accepted


def fetch_sse(listing: base.Listing, settings: dict[str, Any]) -> dict[str, Any]:
    max_age_days = max(30, int(settings.get("maxAgeDays", 1095)))
    end = date.today()
    begin = end - timedelta(days=max_age_days)
    params = {
        "isPagination": "true",
        "productId": listing.ticker,
        "keyWord": "",
        "securityType": "0101,120100,020100,020200,120200",
        "reportType2": "",
        "reportType": "ALL",
        "beginDate": begin.isoformat(),
        "endDate": end.isoformat(),
        "pageHelp.pageSize": "30",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
    }
    request = Request(
        SSE_ENDPOINT + "?" + urlencode(params),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/javascript,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Accept-Encoding": "identity",
            "Connection": "close",
            "Referer": (
                "https://www.sse.com.cn/assortment/stock/list/info/announcement/"
                f"index.shtml?productId={listing.ticker}"
            ),
        },
    )
    timeout = int(settings.get("requestTimeout", 18))
    with urlopen(request, timeout=timeout) as response:
        return _decode_json(response.read(4_000_000))


def fetch_szse(listing: base.Listing, settings: dict[str, Any]) -> dict[str, Any]:
    """Query SZSE in a short browser-like session with bounded retries.

    SZSE sometimes resets stateless CI connections before returning an HTTP status.
    Its public notice page and API are therefore opened through one CookieJar session;
    every connection is explicitly closed and retries stay within the existing source
    request-attempt budget. No alternate host or third-party fallback is used.
    """

    body = json.dumps(
        {
            "seDate": ["", ""],
            "channelCode": ["listedNotice_disc"],
            "pageSize": 30,
            "pageNum": 1,
            "stock": [listing.ticker],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    timeout = int(settings.get("requestTimeout", 18))
    attempts = max(1, min(int(settings.get("requestAttempts", 2)), 3))
    last_error: Exception | None = None

    for attempt in range(attempts):
        cookies = CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookies))
        common_headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        try:
            preflight = Request(
                SZSE_HOME,
                headers={
                    **common_headers,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with opener.open(preflight, timeout=timeout) as response:
                response.read(64_000)

            request = Request(
                f"{SZSE_ENDPOINT}?random={time.time():.6f}",
                data=body,
                method="POST",
                headers={
                    **common_headers,
                    "Accept": "application/json,text/javascript,*/*;q=0.8",
                    "Content-Type": "application/json",
                    "Origin": "https://www.szse.cn",
                    "Referer": SZSE_HOME,
                    "X-Request-Type": "ajax",
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with opener.open(request, timeout=timeout) as response:
                payload = _decode_json(response.read(4_000_000))
            if payload:
                return payload
            raise RuntimeError("SZSE returned an empty or non-JSON response")
        except Exception as exc:  # noqa: BLE001 - preserve exact official-endpoint failure.
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.2 * (attempt + 1))

    raise RuntimeError(f"SZSE request failed after {attempts} attempts: {last_error}")


def observe_listing(
    listing: base.Listing,
    settings: dict[str, Any],
    *,
    sse_fetcher: Callable[[base.Listing, dict[str, Any]], dict[str, Any]] = fetch_sse,
    szse_fetcher: Callable[[base.Listing, dict[str, Any]], dict[str, Any]] = fetch_szse,
) -> dict[str, Any]:
    institution = base.a_share_exchange(listing.ticker)
    provider = "sse-company-bulletin-api" if institution == "sse" else "szse-announcement-api"
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        payload = (
            sse_fetcher(listing, settings)
            if institution == "sse"
            else szse_fetcher(listing, settings)
        )
        rows = _sse_rows(payload) if institution == "sse" else _szse_rows(payload)
        if not payload:
            errors.append("official endpoint returned empty or non-JSON response")
    except Exception as exc:  # noqa: BLE001 - the failure itself is availability evidence.
        errors.append(f"{type(exc).__name__}:{exc}")
    scanned, accepted = _classify_rows(rows)
    status = "error" if errors else ("ok" if scanned else "empty")
    return {
        "institution": institution,
        "provider": provider,
        "status": status,
        "scanned": scanned,
        "accepted": accepted,
        "errors": errors,
    }


def enrich_snapshot(
    snapshot: dict[str, Any],
    listings: Iterable[base.Listing],
    settings: dict[str, Any],
    *,
    observer: Callable[[base.Listing, dict[str, Any]], dict[str, Any]] = observe_listing,
) -> dict[str, Any]:
    result = json.loads(json.dumps(snapshot, ensure_ascii=False))
    statuses = [row for row in result.get("sourceStatus", []) if isinstance(row, dict)]
    status_by_id = {str(row.get("id") or ""): row for row in statuses}
    attempted = 0

    for listing in listings:
        if listing.market != "A股":
            continue
        attempted += 1
        observation = observer(listing, settings)
        expected = base.a_share_exchange(listing.ticker)
        institution = str(observation.get("institution") or "")
        if institution != expected:
            raise ValueError(
                f"exchange observation mismatch for {listing.ticker}: {institution} != {expected}"
            )
        status = status_by_id.get(listing.source_id)
        if status is None:
            status = {
                "id": listing.source_id,
                "companySlug": listing.catalog_slug,
                "name": listing.name,
                "market": listing.market,
                "ticker": listing.ticker,
                "exchange": listing.exchange,
            }
            statuses.append(status)
            status_by_id[listing.source_id] = status
        status["exchangeDirectAttempted"] = True
        status["exchangeDirectInstitution"] = institution
        status["exchangeDirectProvider"] = str(observation.get("provider") or "")
        status["exchangeDirectStatus"] = str(observation.get("status") or "unknown")
        status["exchangeDirectScanned"] = max(0, int(observation.get("scanned", 0) or 0))
        status["exchangeDirectAccepted"] = max(0, int(observation.get("accepted", 0) or 0))
        status["exchangeDirectErrors"] = [
            str(value).strip()
            for value in observation.get("errors", [])
            if str(value).strip()
        ]

    result["sourceStatus"] = statuses
    result["exchangeDirect"] = {
        "schemaVersion": 1,
        "attemptedListingCount": attempted,
        "providers": ["sse-company-bulletin-api", "szse-announcement-api"],
    }
    return result


def validate_snapshot(
    snapshot: dict[str, Any],
    listings: Iterable[base.Listing],
    *,
    require_attempts: bool = False,
) -> list[str]:
    statuses = {
        str(row.get("id") or ""): row
        for row in snapshot.get("sourceStatus", [])
        if isinstance(row, dict)
    }
    errors: list[str] = []
    for listing in listings:
        if listing.market != "A股":
            continue
        row = statuses.get(listing.source_id)
        if row is None:
            errors.append(f"missing listing status: {listing.source_id}")
            continue
        if require_attempts and row.get("exchangeDirectAttempted") is not True:
            errors.append(f"missing direct exchange observation: {listing.source_id}")
            continue
        if row.get("exchangeDirectAttempted") is not True:
            continue
        expected = base.a_share_exchange(listing.ticker)
        if str(row.get("exchangeDirectInstitution") or "") != expected:
            errors.append(f"wrong direct exchange institution: {listing.source_id}")
        scanned = int(row.get("exchangeDirectScanned", 0) or 0)
        accepted = int(row.get("exchangeDirectAccepted", 0) or 0)
        if scanned < 0 or accepted < 0 or accepted > scanned:
            errors.append(f"invalid direct exchange counters: {listing.source_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-attempts", action="store_true")
    args = parser.parse_args()

    listings = base.load_listings()
    snapshot = load_snapshot()
    if args.check:
        errors = validate_snapshot(snapshot, listings, require_attempts=args.require_attempts)
        print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False))
        return 1 if errors else 0

    enriched = enrich_snapshot(snapshot, listings, load_settings())
    errors = validate_snapshot(enriched, listings, require_attempts=True)
    if errors:
        print(json.dumps({"passed": False, "errors": errors}, ensure_ascii=False))
        return 1
    OUTPUT_PATH.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    observed = [
        row
        for row in enriched.get("sourceStatus", [])
        if isinstance(row, dict) and row.get("exchangeDirectAttempted") is True
    ]
    print(
        json.dumps(
            {
                "passed": True,
                "attempted": len(observed),
                "sse": sum(row.get("exchangeDirectInstitution") == "sse" for row in observed),
                "szse": sum(row.get("exchangeDirectInstitution") == "szse" for row in observed),
                "errors": sum(bool(row.get("exchangeDirectErrors")) for row in observed),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
