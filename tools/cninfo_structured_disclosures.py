#!/usr/bin/env python3
"""Enrich the listed-company snapshot through CNINFO's structured announcement data.

CNINFO remains the preferred A-share disclosure enrichment source. The transport is
intentionally resilient because public CI egress can be throttled independently from
normal browser traffic:

* prefer HTTPS, then retry the documented public HTTP endpoint;
* warm a browser-like cookie session before structured requests;
* seed orgId values for the small tracked A-share universe from reviewed config;
* merge a live registry over those seeds when the registry is available;
* retain previously verified CNINFO documents when a live endpoint is temporarily
  unavailable;
* always continue to direct SSE/SZSE observations so the company channel keeps an
  independent official-exchange health path.

Only metadata and short factual snippets are retained; document links continue to
point at CNINFO's original static document host.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

try:
    from . import crawl_listed_company_disclosures as base
except ImportError:
    import crawl_listed_company_disclosures as base

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"

CNINFO_HOME_URLS = (
    "https://www.cninfo.com.cn/new/index.jsp",
    "http://www.cninfo.com.cn/new/index.jsp",
)
STOCK_LIST_URLS = (
    "https://www.cninfo.com.cn/new/data/szse_stock.json",
    "http://www.cninfo.com.cn/new/data/szse_stock.json",
)
QUERY_URLS = (
    "https://www.cninfo.com.cn/new/hisAnnouncement/query",
    "http://www.cninfo.com.cn/new/hisAnnouncement/query",
)
STATIC_DOCUMENT_ROOT = "https://static.cninfo.com.cn/"
PROVIDER = "cninfo-structured-api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def _referer_for(url: str) -> str:
    scheme = urlsplit(url).scheme or "https"
    return (
        f"{scheme}://www.cninfo.com.cn/new/commonUrl/pageOfSearch?"
        "url=disclosure/list/search&lastPage=index"
    )


def _decode_json(payload: bytes, charset: str | None = None) -> dict[str, Any]:
    encodings = [charset] if charset else []
    encodings.extend(["utf-8", "gb18030"])
    for encoding in encodings:
        if not encoding:
            continue
        try:
            value = json.loads(payload.decode(encoding))
            return value if isinstance(value, dict) else {}
        except (LookupError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {}


def _request_headers(url: str, *, form: bool) -> dict[str, str]:
    scheme = urlsplit(url).scheme or "https"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Accept-Encoding": "identity",
        "Referer": _referer_for(url),
        "Origin": f"{scheme}://www.cninfo.com.cn",
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "close",
    }
    if form:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    return headers


def build_session(timeout: int = 18) -> tuple[Any, list[str]]:
    """Warm a browser-like cookie jar, but never make warm-up itself fatal."""
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    errors: list[str] = []
    for url in CNINFO_HOME_URLS:
        scheme = urlsplit(url).scheme or "https"
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                    "Accept-Encoding": "identity",
                    "Referer": f"{scheme}://www.cninfo.com.cn/",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Connection": "close",
                },
            )
            with opener.open(request, timeout=timeout) as response:
                response.read(64_000)
            return opener, errors
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append(f"preflight:{url}:{type(exc).__name__}:{exc}")
    return opener, errors


def fetch_json(
    url: str,
    *,
    form: dict[str, Any] | None = None,
    timeout: int = 18,
    attempts: int = 2,
    opener: Any | None = None,
) -> dict[str, Any]:
    """Fetch one CNINFO JSON endpoint with bounded retries."""
    last_error: Exception | None = None
    data = urlencode(form).encode("utf-8") if form is not None else None
    client = opener
    for attempt in range(max(1, min(attempts, 3))):
        request = Request(
            url,
            data=data,
            headers=_request_headers(url, form=form is not None),
            method="POST" if form is not None else "GET",
        )
        try:
            if client is None:
                response_context = urlopen(request, timeout=timeout)
            else:
                response_context = client.open(request, timeout=timeout)
            with response_context as response:
                result = _decode_json(
                    response.read(4_000_000),
                    response.headers.get_content_charset(),
                )
                if result:
                    return result
                raise RuntimeError("CNINFO returned a non-JSON or empty response")
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"CNINFO request failed for {url}: {last_error}")


def fetch_first_json(
    urls: Iterable[str],
    *,
    form: dict[str, Any] | None = None,
    timeout: int = 18,
    attempts: int = 2,
    opener: Any | None = None,
) -> tuple[dict[str, Any], str, list[str]]:
    """Try the preferred endpoint followed by protocol-compatible fallbacks."""
    errors: list[str] = []
    for url in urls:
        try:
            return (
                fetch_json(
                    url,
                    form=form,
                    timeout=timeout,
                    attempts=attempts,
                    opener=opener,
                ),
                url,
                errors,
            )
        except Exception as exc:  # noqa: BLE001 - preserve transport evidence.
            errors.append(f"{url}:{type(exc).__name__}:{exc}")
    raise RuntimeError(" | ".join(errors) or "CNINFO endpoint list is empty")


def parse_org_ids(payload: dict[str, Any]) -> dict[str, str]:
    rows = payload.get("stockList", [])
    if not isinstance(rows, list):
        return {}
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = base.normalize_ticker("A股", row.get("code"))
        org_id = base.clean_text(row.get("orgId"), 100)
        if code and org_id:
            result[code] = org_id
    return result


def configured_org_ids(config: dict[str, Any]) -> dict[str, str]:
    raw = config.get("cninfoOrgIds", {})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for ticker, org_id in raw.items():
        code = base.normalize_ticker("A股", ticker)
        value = base.clean_text(org_id, 100)
        if code and value:
            result[code] = value
    return result


def resolve_org_ids(
    config: dict[str, Any],
    settings: dict[str, Any],
    *,
    fetcher: Callable[..., tuple[dict[str, Any], str, list[str]]] = fetch_first_json,
    session_builder: Callable[[int], tuple[Any, list[str]]] = build_session,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Resolve orgIds without letting a registry outage erase reviewed identities."""
    seeded = configured_org_ids(config)
    merged = dict(seeded)
    timeout = int(settings.get("requestTimeout", 18))
    attempts = int(settings.get("requestAttempts", 2))
    opener, warmup_errors = session_builder(timeout)
    diagnostics: dict[str, Any] = {
        "status": "seeded" if seeded else "unavailable",
        "endpoint": "",
        "seededOrgIdCount": len(seeded),
        "liveOrgIdCount": 0,
        "errors": list(warmup_errors),
    }
    try:
        payload, endpoint, transport_errors = fetcher(
            STOCK_LIST_URLS,
            timeout=timeout,
            attempts=attempts,
            opener=opener,
        )
        live = parse_org_ids(payload)
        if live:
            merged.update(live)
            diagnostics["status"] = "live"
            diagnostics["endpoint"] = endpoint
            diagnostics["liveOrgIdCount"] = len(live)
        elif seeded:
            diagnostics["status"] = "seeded"
            diagnostics["errors"].append("registry returned no usable orgId rows")
        else:
            diagnostics["errors"].append("registry returned no usable orgId rows")
        diagnostics["errors"].extend(transport_errors)
    except Exception as exc:  # noqa: BLE001 - seed cache is the intended fallback.
        diagnostics["status"] = "seeded" if seeded else "unavailable"
        diagnostics["errors"].append(f"registry:{type(exc).__name__}:{exc}")
    diagnostics["_opener"] = opener
    return merged, diagnostics


def query_payload(
    listing: base.Listing,
    org_id: str,
    *,
    page_num: int,
    page_size: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    return {
        "pageNum": max(1, page_num),
        "pageSize": max(1, min(page_size, 30)),
        "column": "sse" if base.a_share_exchange(listing.ticker) == "sse" else "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": f"{listing.ticker},{org_id}",
        "searchkey": "",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
        "sortName": "time",
        "sortType": "desc",
        "isHLtitle": "true",
    }


def _announcement_date(row: dict[str, Any]) -> str:
    timestamp = row.get("announcementTime")
    try:
        numeric = float(timestamp)
        if numeric > 10_000_000_000:
            numeric /= 1000
        if numeric > 0:
            return datetime.fromtimestamp(numeric, UTC).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        pass
    return base.normalize_date(str(row.get("adjunctUrl", "")))


def parse_announcements(
    payload: dict[str, Any],
    listing: base.Listing,
) -> list[base.Candidate]:
    rows = payload.get("announcements", [])
    if not isinstance(rows, list):
        return []
    candidates: list[base.Candidate] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        sec_code = base.normalize_ticker("A股", row.get("secCode"))
        if sec_code and sec_code != listing.ticker:
            continue
        adjunct = base.clean_text(row.get("adjunctUrl"), 1200).lstrip("/")
        title = base.clean_text(row.get("announcementTitle"), 600)
        published_at = _announcement_date(row)
        if not adjunct or not title or not published_at:
            continue
        url = STATIC_DOCUMENT_ROOT + adjunct
        if url in seen:
            continue
        adjunct_type = base.clean_text(row.get("adjunctType"), 30)
        announcement_id = base.clean_text(row.get("announcementId"), 100)
        sec_name = base.clean_text(row.get("secName"), 120)
        summary = " · ".join(
            value
            for value in (
                f"证券代码 {listing.ticker}",
                sec_name,
                f"文件类型 {adjunct_type}" if adjunct_type else "",
                f"公告编号 {announcement_id}" if announcement_id else "",
            )
            if value
        )
        candidates.append(base.Candidate(title, url, summary, published_at, PROVIDER))
        seen.add(url)
    return candidates


def query_listing(
    listing: base.Listing,
    org_id: str,
    settings: dict[str, Any],
    *,
    opener: Any | None = None,
    fetcher: Callable[..., tuple[dict[str, Any], str, list[str]]] = fetch_first_json,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timeout = int(settings.get("requestTimeout", 18))
    attempts = int(settings.get("requestAttempts", 2))
    max_age_days = int(settings.get("maxAgeDays", 1095))
    limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=max_age_days)
    page_size = 30
    max_pages = max(1, min(int(settings.get("cninfoMaxPages", 4)), 8))
    candidates: list[base.Candidate] = []
    errors: list[str] = []
    scanned = 0
    endpoint = ""

    for page_num in range(1, max_pages + 1):
        try:
            payload, used_endpoint, transport_errors = fetcher(
                QUERY_URLS,
                form=query_payload(
                    listing,
                    org_id,
                    page_num=page_num,
                    page_size=page_size,
                    start_date=start_date,
                    end_date=end_date,
                ),
                timeout=timeout,
                attempts=attempts,
                opener=opener,
            )
            endpoint = used_endpoint or endpoint
            errors.extend(transport_errors)
        except Exception as exc:  # noqa: BLE001 - retain previous verified data.
            errors.append(f"page-{page_num}:{type(exc).__name__}:{exc}")
            break
        page_rows = payload.get("announcements", [])
        scanned += len(page_rows) if isinstance(page_rows, list) else 0
        candidates.extend(parse_announcements(payload, listing))
        if payload.get("hasMore") is not True:
            break

    accepted: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if not base.allowed_url(listing, candidate.url, fallback=False):
            continue
        event = base.to_event(listing, candidate, fallback=False)
        if event:
            accepted[event["source"]["url"]] = event
    events = sorted(
        accepted.values(),
        key=lambda event: (str(event.get("publishedAt", "")), str(event.get("id", ""))),
        reverse=True,
    )[:limit]
    return events, {
        "attempted": True,
        "provider": PROVIDER,
        "orgIdResolved": True,
        "endpoint": endpoint,
        "scanned": scanned,
        "qualified": len(accepted),
        "accepted": len(events),
        "errors": errors,
    }


def _event_url(event: dict[str, Any]) -> str:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    return base.clean_text(source.get("url"), 1200)


def _is_cninfo_a_share_event(event: dict[str, Any]) -> bool:
    if str(event.get("market") or "") != "A股":
        return False
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    source_name = base.clean_text(source.get("name"), 80)
    source_url = base.clean_text(source.get("url"), 1200)
    return (
        str(event.get("discoveredVia") or "") == PROVIDER
        or source_name == "巨潮资讯"
        or base.normalized_host(source_url).endswith("cninfo.com.cn")
    )


def count_available_cninfo_events(
    snapshot: dict[str, Any],
    listings: Iterable[base.Listing] | None = None,
) -> int:
    allowed_slugs = {
        listing.catalog_slug
        for listing in (list(listings) if listings is not None else base.load_listings())
        if listing.market == "A股"
    }
    urls: set[str] = set()
    companies = snapshot.get("companies", {})
    if not isinstance(companies, dict):
        return 0
    for slug, company in companies.items():
        if slug not in allowed_slugs or not isinstance(company, dict):
            continue
        for event in company.get("events", []):
            if not isinstance(event, dict) or not _is_cninfo_a_share_event(event):
                continue
            url = _event_url(event)
            if url:
                urls.add(url)
    return len(urls)


def _merge_events(
    existing: Iterable[dict[str, Any]],
    incoming: Iterable[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for event in existing:
        url = _event_url(event)
        if url:
            by_url[url] = event
    for event in incoming:
        url = _event_url(event)
        if url:
            by_url[url] = event
    return sorted(
        by_url.values(),
        key=lambda event: (str(event.get("publishedAt", "")), str(event.get("id", ""))),
        reverse=True,
    )[: max(1, limit)]


def enrich_snapshot(
    snapshot: dict[str, Any],
    listings: Iterable[base.Listing],
    org_ids: dict[str, str],
    settings: dict[str, Any],
    *,
    query_fn=query_listing,
    registry_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = list(listings)
    result = json.loads(json.dumps(snapshot, ensure_ascii=False))
    companies = result.setdefault("companies", {})
    statuses = [
        status for status in result.get("sourceStatus", []) if isinstance(status, dict)
    ]
    status_by_id = {str(status.get("id", "")): status for status in statuses}
    per_listing_limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    company_limit = max(1, min(per_listing_limit * 2, 48))
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    diagnostics = dict(registry_diagnostics or {})
    opener = diagnostics.pop("_opener", None)
    live_accepted = 0

    for listing in rows:
        if listing.market != "A股":
            continue
        status = status_by_id.get(listing.source_id)
        if status is None:
            status = {
                "id": listing.source_id,
                "companySlug": listing.catalog_slug,
                "name": listing.name,
                "market": listing.market,
                "ticker": listing.ticker,
                "exchange": listing.exchange,
                "provider": "official",
                "status": "error",
                "scanned": 0,
                "accepted": 0,
                "fallback": False,
                "errors": [],
            }
            statuses.append(status)
            status_by_id[listing.source_id] = status

        org_id = org_ids.get(listing.ticker, "")
        if not org_id:
            structured = {
                "attempted": True,
                "provider": PROVIDER,
                "orgIdResolved": False,
                "endpoint": "",
                "scanned": 0,
                "qualified": 0,
                "accepted": 0,
                "errors": ["CNINFO orgId not found in live registry or reviewed seed cache"],
            }
            events: list[dict[str, Any]] = []
        else:
            try:
                try:
                    events, structured = query_fn(
                        listing,
                        org_id,
                        settings,
                        opener=opener,
                    )
                except TypeError as exc:
                    if "opener" not in str(exc):
                        raise
                    events, structured = query_fn(listing, org_id, settings)
            except Exception as exc:  # noqa: BLE001 - retain prior company events.
                events = []
                structured = {
                    "attempted": True,
                    "provider": PROVIDER,
                    "orgIdResolved": True,
                    "endpoint": "",
                    "scanned": 0,
                    "qualified": 0,
                    "accepted": 0,
                    "errors": [f"{type(exc).__name__}:{exc}"],
                }

        status["structuredProvider"] = structured["provider"]
        status["structuredAttempted"] = structured["attempted"]
        status["structuredOrgIdResolved"] = structured["orgIdResolved"]
        status["structuredEndpoint"] = structured.get("endpoint", "")
        status["structuredScanned"] = structured["scanned"]
        status["structuredQualified"] = structured.get("qualified", structured["accepted"])
        status["structuredAccepted"] = structured["accepted"]
        status["structuredErrors"] = structured["errors"]
        live_accepted += int(structured["accepted"] or 0)
        if events:
            status["provider"] = "official+cninfo-structured"
            status["status"] = "ok"
            status["accepted"] = max(int(status.get("accepted", 0) or 0), len(events))

        company = companies.setdefault(
            listing.catalog_slug,
            {
                "slug": listing.catalog_slug,
                "name": listing.name,
                "updatedAt": generated_at,
                "status": "partial",
                "listings": [],
                "events": [],
            },
        )
        if not isinstance(company, dict):
            continue
        listing_rows = company.setdefault("listings", [])
        listing_marker = {
            "market": listing.market,
            "ticker": listing.ticker,
            "exchange": listing.exchange,
            "listingRole": listing.listing_role,
        }
        if isinstance(listing_rows, list) and listing_marker not in listing_rows:
            listing_rows.append(listing_marker)
        existing_events = [
            event for event in company.get("events", []) if isinstance(event, dict)
        ]
        merged = _merge_events(existing_events, events, company_limit)
        company["events"] = merged
        company["updatedAt"] = generated_at
        if events:
            company["status"] = "ok"
        company["officialEventCount"] = sum(
            not bool(event.get("fallback")) for event in merged
        )
        company["fallbackEventCount"] = sum(
            bool(event.get("fallback")) for event in merged
        )

    result["generatedAt"] = generated_at
    result["companies"] = companies
    result["sourceStatus"] = statuses
    result["companyCount"] = len(companies)
    result["eventCount"] = sum(
        len(company.get("events", []))
        for company in companies.values()
        if isinstance(company, dict)
    )
    available = count_available_cninfo_events(result, rows)
    result["cninfoStructured"] = {
        "schemaVersion": 2,
        "provider": PROVIDER,
        "attemptedListingCount": sum(1 for listing in rows if listing.market == "A股"),
        "qualifiedEventCount": sum(
            int(status.get("structuredQualified", 0) or 0) for status in statuses
        ),
        "acceptedEventCount": live_accepted,
        "liveAcceptedEventCount": live_accepted,
        "availableEventCount": available,
        "registryStatus": str(diagnostics.get("status") or "unknown"),
        "registryEndpoint": str(diagnostics.get("endpoint") or ""),
        "seededOrgIdCount": int(diagnostics.get("seededOrgIdCount", 0) or 0),
        "liveOrgIdCount": int(diagnostics.get("liveOrgIdCount", 0) or 0),
        "registryErrors": [
            str(value)
            for value in diagnostics.get("errors", [])
            if str(value).strip()
        ],
    }
    return result


def validate_enrichment(
    snapshot: dict[str, Any],
    listings: Iterable[base.Listing] | None = None,
    *,
    require_events: bool = False,
) -> list[str]:
    rows = list(listings or base.load_listings())
    errors = base.validate_snapshot(snapshot, rows)
    statuses = {
        str(status.get("id", "")): status
        for status in snapshot.get("sourceStatus", [])
        if isinstance(status, dict)
    }
    for listing in rows:
        if listing.market != "A股":
            continue
        status = statuses.get(listing.source_id, {})
        if status.get("structuredAttempted") is not True:
            errors.append(f"CNINFO structured source not attempted: {listing.source_id}")
        if not status.get("structuredProvider"):
            errors.append(f"CNINFO structured provider missing: {listing.source_id}")

    cninfo_summary = (
        snapshot.get("cninfoStructured", {})
        if isinstance(snapshot.get("cninfoStructured"), dict)
        else {}
    )
    available = int(
        cninfo_summary.get(
            "availableEventCount",
            count_available_cninfo_events(snapshot, rows),
        )
        or 0
    )
    if require_events and available <= 0:
        errors.append(
            "no verified CNINFO A-share disclosure events are available after live/retained fallback"
        )
    return errors


def write_snapshot(snapshot: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    previous = base.load_previous(path)
    comparable_previous = json.loads(json.dumps(previous, ensure_ascii=False))
    comparable_next = json.loads(json.dumps(snapshot, ensure_ascii=False))
    comparable_previous.pop("generatedAt", None)
    comparable_next.pop("generatedAt", None)
    for payload in (comparable_previous, comparable_next):
        companies = payload.get("companies", {})
        if isinstance(companies, dict):
            for company in companies.values():
                if isinstance(company, dict):
                    company.pop("updatedAt", None)
    if comparable_previous == comparable_next and path.exists():
        print("No CNINFO structured disclosure changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = snapshot.get("cninfoStructured", {})
    print(
        json.dumps(
            {
                "companyCount": snapshot.get("companyCount", 0),
                "eventCount": snapshot.get("eventCount", 0),
                "cninfoLiveAccepted": summary.get("liveAcceptedEventCount", 0),
                "cninfoAvailable": summary.get("availableEventCount", 0),
                "cninfoRegistryStatus": summary.get("registryStatus", "unknown"),
            },
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-events", action="store_true")
    args = parser.parse_args()
    listings = base.load_listings()
    if args.check:
        snapshot = base.load_previous(OUTPUT_PATH)
        errors = validate_enrichment(
            snapshot,
            listings,
            require_events=args.require_events,
        )
        if errors:
            raise SystemExit("; ".join(errors))
        summary = snapshot.get("cninfoStructured", {})
        print(
            json.dumps(
                {
                    "passed": True,
                    "liveAcceptedEventCount": summary.get(
                        "liveAcceptedEventCount",
                        summary.get("acceptedEventCount", 0),
                    ),
                    "availableEventCount": summary.get(
                        "availableEventCount",
                        count_available_cninfo_events(snapshot, listings),
                    ),
                    "registryStatus": summary.get("registryStatus", "legacy"),
                },
                ensure_ascii=False,
            )
        )
        return 0

    config = base.load_config()
    settings = config["settings"]
    org_ids, registry_diagnostics = resolve_org_ids(config, settings)
    snapshot = enrich_snapshot(
        base.load_previous(OUTPUT_PATH),
        listings,
        org_ids,
        settings,
        registry_diagnostics=registry_diagnostics,
    )
    errors = validate_enrichment(snapshot, listings, require_events=args.require_events)
    if errors:
        raise SystemExit("; ".join(errors))

    try:
        from . import exchange_direct_observations as exchange_direct
    except ImportError:
        import exchange_direct_observations as exchange_direct
    snapshot = exchange_direct.enrich_snapshot(snapshot, listings, settings)
    exchange_errors = exchange_direct.validate_snapshot(
        snapshot, listings, require_attempts=True
    )
    if exchange_errors:
        raise SystemExit("; ".join(exchange_errors))

    write_snapshot(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
