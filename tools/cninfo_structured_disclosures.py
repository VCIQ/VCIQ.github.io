#!/usr/bin/env python3
"""Enrich the listed-company snapshot through CNINFO's structured announcement data.

The browser-facing CNINFO search page does not expose final document URLs in its
server-rendered HTML. This module uses the same structured announcement endpoint
behind that page, resolves each ``adjunctUrl`` to the original CNINFO document,
and merges only classified capital-market disclosures into the formal snapshot.

The module is deliberately narrow:
* A-share listings only;
* metadata and short factual snippets only;
* original ``static.cninfo.com.cn`` document URLs only;
* bounded pages, article count and request retries;
* previous verified events are retained when the endpoint is temporarily down.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from . import crawl_listed_company_disclosures as base
except ImportError:
    import crawl_listed_company_disclosures as base

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
STOCK_LIST_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
STATIC_DOCUMENT_ROOT = "https://static.cninfo.com.cn/"
REFERER = (
    "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?"
    "url=disclosure/list/search&lastPage=index"
)
PROVIDER = "cninfo-structured-api"


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


def fetch_json(
    url: str,
    *,
    form: dict[str, Any] | None = None,
    timeout: int = 18,
    attempts: int = 2,
) -> dict[str, Any]:
    last_error: Exception | None = None
    data = urlencode(form).encode("utf-8") if form is not None else None
    for attempt in range(max(1, min(attempts, 3))):
        request = Request(
            url,
            data=data,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "Accept-Encoding": "identity",
                "Referer": REFERER,
                "Origin": "https://www.cninfo.com.cn",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            method="POST" if form is not None else "GET",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
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

    for page_num in range(1, max_pages + 1):
        try:
            payload = fetch_json(
                QUERY_URL,
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
            )
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
        "scanned": scanned,
        "accepted": len(events),
        "errors": errors,
    }


def _event_url(event: dict[str, Any]) -> str:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    return base.clean_text(source.get("url"), 1200)


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
) -> dict[str, Any]:
    result = json.loads(json.dumps(snapshot, ensure_ascii=False))
    companies = result.setdefault("companies", {})
    statuses = [
        status for status in result.get("sourceStatus", []) if isinstance(status, dict)
    ]
    status_by_id = {str(status.get("id", "")): status for status in statuses}
    per_listing_limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    company_limit = max(1, min(per_listing_limit * 2, 48))
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    for listing in listings:
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
                "scanned": 0,
                "accepted": 0,
                "errors": ["CNINFO orgId not found"],
            }
            events: list[dict[str, Any]] = []
        else:
            try:
                events, structured = query_fn(listing, org_id, settings)
            except Exception as exc:  # noqa: BLE001 - retain prior company events.
                events = []
                structured = {
                    "attempted": True,
                    "provider": PROVIDER,
                    "orgIdResolved": True,
                    "scanned": 0,
                    "accepted": 0,
                    "errors": [f"{type(exc).__name__}:{exc}"],
                }

        status["structuredProvider"] = structured["provider"]
        status["structuredAttempted"] = structured["attempted"]
        status["structuredOrgIdResolved"] = structured["orgIdResolved"]
        status["structuredScanned"] = structured["scanned"]
        status["structuredAccepted"] = structured["accepted"]
        status["structuredErrors"] = structured["errors"]
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
    result["cninfoStructured"] = {
        "schemaVersion": 1,
        "provider": PROVIDER,
        "attemptedListingCount": sum(
            1 for listing in listings if listing.market == "A股"
        ),
        "acceptedEventCount": sum(
            int(status.get("structuredAccepted", 0) or 0) for status in statuses
        ),
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
    accepted = int(
        snapshot.get("cninfoStructured", {}).get("acceptedEventCount", 0)
        if isinstance(snapshot.get("cninfoStructured"), dict)
        else 0
    )
    if require_events and accepted <= 0:
        errors.append("CNINFO structured query produced no A-share disclosure events")
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
    print(
        json.dumps(
            {
                "companyCount": snapshot.get("companyCount", 0),
                "eventCount": snapshot.get("eventCount", 0),
                "cninfoAccepted": snapshot.get("cninfoStructured", {}).get(
                    "acceptedEventCount", 0
                ),
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
        print(
            json.dumps(
                {
                    "passed": True,
                    "acceptedEventCount": snapshot.get("cninfoStructured", {}).get(
                        "acceptedEventCount", 0
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0

    config = base.load_config()
    settings = config["settings"]
    stock_payload = fetch_json(
        STOCK_LIST_URL,
        timeout=int(settings.get("requestTimeout", 18)),
        attempts=int(settings.get("requestAttempts", 2)),
    )
    org_ids = parse_org_ids(stock_payload)
    snapshot = enrich_snapshot(
        base.load_previous(OUTPUT_PATH),
        listings,
        org_ids,
        settings,
    )
    errors = validate_enrichment(snapshot, listings, require_events=args.require_events)
    if errors:
        raise SystemExit("; ".join(errors))

    # The content pipeline may mix CNINFO and exchange discovery, so collect
    # exchange health separately through the exchanges' own structured endpoints.
    # This augments sourceStatus only; it does not replace CNINFO events or mutate
    # the aggregate listing counters above.
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
