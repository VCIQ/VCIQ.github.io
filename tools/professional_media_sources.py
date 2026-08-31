"""Load and route the owner-curated professional technology media catalog.

Every enabled outlet becomes an independent, bounded discovery source. This
prevents large publications from consuming a shared result page and makes the
formal snapshot expose one execution status per registered media outlet. Every
returned URL is checked against the original media host and, when a source uses
a section path, against that path as well.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "professional_technology_media_sources.json"
VALID_REGIONS = {"中国", "美国", "全球"}
DIRECT_TIMEOUT_SECONDS = 8
DIRECT_ATTEMPTS = 1
DIRECT_FEED_LIMIT = 2
DIRECT_CANDIDATE_LIMIT = 8


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _unique(values: Iterable[Any], limit: int = 160) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, 160)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _host(value: str) -> str:
    return (urlsplit(str(value or "")).hostname or "").casefold().removeprefix("www.")


def _path(value: str) -> str:
    return urlsplit(str(value or "")).path.rstrip("/")


def _slug(value: Any) -> str:
    text = _clean(value, 80).casefold()
    result = []
    previous_dash = False
    for character in text:
        if character.isascii() and character.isalnum():
            result.append(character)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True
    return "".join(result).strip("-")[:60] or "media"


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or int(payload.get("schemaVersion", 0)) != 1:
        raise ValueError("unsupported professional media registry schema")
    settings = payload.get("settings")
    sources = payload.get("sources")
    if not isinstance(settings, dict) or not isinstance(sources, list):
        raise ValueError("professional media registry requires settings and sources")

    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for raw in sources:
        if not isinstance(raw, dict):
            raise ValueError("professional media source rows must be objects")
        source_id = _clean(raw.get("id"), 80)
        name = _clean(raw.get("name"), 120)
        url = _clean(raw.get("url"), 500)
        host = _clean(raw.get("host"), 200).casefold().removeprefix("www.")
        scope = _clean(raw.get("searchScope"), 300).casefold().removeprefix("www.")
        sector = _clean(raw.get("primarySector"), 60)
        order = int(raw.get("order", 0) or 0)
        if not source_id or not name or not url or not host or not scope or not sector:
            raise ValueError(f"incomplete professional media source: {source_id or name}")
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"invalid professional media URL: {source_id}")
        if _host(url) != host:
            raise ValueError(f"professional media host mismatch: {source_id}")
        if source_id in seen_ids or order in seen_orders:
            raise ValueError(f"duplicate professional media identity: {source_id}")
        seen_ids.add(source_id)
        seen_orders.add(order)
        region = _clean(raw.get("region"), 20)
        normalized.append(
            {
                **raw,
                "id": source_id,
                "name": name,
                "url": url,
                "host": host,
                "searchScope": scope,
                "primarySector": sector,
                "region": region if region in VALID_REGIONS else "全球",
                "priority": max(1, min(int(raw.get("priority", 3) or 3), 3)),
                "focus": _unique(raw.get("focus", []), 20),
                "enabled": raw.get("enabled", True) is not False,
            }
        )
    return {**payload, "sources": normalized}


def enabled_sources(path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    return [source for source in load_registry(path)["sources"] if source["enabled"]]


def grouped_specs(
    tracks: Sequence[dict[str, Any]],
    tracking: Any,
    path: Path = REGISTRY_PATH,
) -> list[dict[str, Any]]:
    """Build one independently executable, allowlisted source per media outlet."""

    payload = load_registry(path)
    settings = payload["settings"]
    max_items = max(
        2,
        min(
            int(
                settings.get(
                    "maxItemsPerSource",
                    min(int(settings.get("maxItemsPerGroup", 4) or 4), 4),
                )
                or 4
            ),
            6,
        ),
    )
    event_terms = _unique(settings.get("eventTerms", []), 18)
    track_by_name = {
        _clean(track.get("name"), 60).casefold(): track
        for track in tracks
        if isinstance(track, dict)
    }

    specs: list[dict[str, Any]] = []
    sources = sorted(
        (source for source in payload["sources"] if source["enabled"]),
        key=lambda source: (source["priority"], int(source.get("order", 0))),
    )
    for source in sources:
        sector = source["primarySector"]
        track = track_by_name.get(sector.casefold())
        track_terms = tracking._track_terms(track) if track else [sector]
        relevance_terms = tracking._unique(
            [sector, *track_terms, *source.get("focus", [])],
            20,
        )
        discovery_terms = tracking._unique(
            [*relevance_terms, *event_terms],
            28,
        )
        query = (
            f"site:{source['searchScope']} "
            f"({tracking._quoted_or_query(discovery_terms, 28)})"
        )
        source_id = f"professional-media-{_slug(source['id'])}"
        media_row = {
            "id": source["id"],
            "name": source["name"],
            "url": source["url"],
            "host": source["host"],
            "pathPrefix": _path(source["url"]),
            "region": source["region"],
            "focus": source.get("focus", []),
            "priority": source["priority"],
        }
        specs.append(
            {
                "id": source_id,
                "name": source["name"],
                "url": tracking._bing_rss(query),
                "sourceUrl": source["url"],
                "adapter": "professional_media",
                "platform": source["name"],
                "sourceCategory": "media",
                "sourceLevel": "媒体报道",
                "region": source["region"],
                "sector": sector,
                "maxItems": max_items,
                "keywords": relevance_terms,
                "strictTitleKeywords": False,
                "allowedHosts": [source["host"]],
                "professionalMedia": [media_row],
                "directRequestBudget": {
                    "timeoutSeconds": DIRECT_TIMEOUT_SECONDS,
                    "attempts": DIRECT_ATTEMPTS,
                    "feedLimit": DIRECT_FEED_LIMIT,
                    "candidateLimit": DIRECT_CANDIDATE_LIMIT,
                },
                "enabled": True,
            }
        )
    return specs


def match_media(url: str, rows: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    candidate_host = _host(url)
    candidate_path = _path(url)
    matches: list[dict[str, Any]] = []
    for row in rows:
        host = _clean(row.get("host"), 200).casefold().removeprefix("www.")
        if not host or not (
            candidate_host == host or candidate_host.endswith(f".{host}")
        ):
            continue
        prefix = _clean(row.get("pathPrefix"), 300).rstrip("/")
        if prefix and prefix != "/" and not (
            candidate_path == prefix or candidate_path.startswith(f"{prefix}/")
        ):
            continue
        matches.append(row)
    if not matches:
        return None
    return max(matches, key=lambda row: len(_clean(row.get("pathPrefix"), 300)))


def attribute_article(
    article: dict[str, Any],
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    source = article.get("source")
    if not isinstance(source, dict):
        return None
    matched = match_media(str(source.get("url", "")), rows)
    if not matched:
        return None
    result = copy.deepcopy(article)
    next_source = dict(source)
    next_source["name"] = matched["name"]
    next_source["platform"] = matched["name"]
    result["source"] = next_source
    result["professionalMediaId"] = matched["id"]
    result["professionalMediaUrl"] = matched["url"]
    result["professionalMediaFocus"] = list(matched.get("focus", []))[:12]
    if result.get("region") == "全球" and matched.get("region") in VALID_REGIONS:
        result["region"] = matched["region"]
    return result


def _article_url(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("url") or "").strip()


def _dedupe_attributed(
    articles: Iterable[dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    crawler: Any,
    limit: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for article in articles:
        attributed = attribute_article(article, rows)
        if not attributed:
            continue
        url = crawler.normalize_url(_article_url(attributed))
        if not url or url in seen:
            continue
        result.append(attributed)
        seen.add(url)
        if len(result) >= limit:
            break
    return result


def crawl_professional_source(
    spec: dict[str, Any],
    user_agent: str,
    crawler: Any,
    generic: Any,
    primary_crawl: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Try public-search RSS, then directly inspect the registered media site."""

    rows = spec.get("professionalMedia")
    if not isinstance(rows, list) or not rows:
        raise ValueError("professional media source is missing registry metadata")

    max_items = max(1, int(spec.get("maxItems", 4) or 4))
    budget = spec.get("directRequestBudget")
    budget = budget if isinstance(budget, dict) else {}
    timeout = max(3, min(int(budget.get("timeoutSeconds", DIRECT_TIMEOUT_SECONDS)), 12))
    attempts = max(1, min(int(budget.get("attempts", DIRECT_ATTEMPTS)), 2))
    feed_limit = max(0, min(int(budget.get("feedLimit", DIRECT_FEED_LIMIT)), 4))
    candidate_limit = max(
        1,
        min(int(budget.get("candidateLimit", DIRECT_CANDIDATE_LIMIT)), 12),
    )

    scanned = 0
    failures = 0
    errors: list[str] = []
    strategies: list[str] = []
    collected: list[dict[str, Any]] = []

    discovery_spec = {**spec, "adapter": "rss", "url": spec["url"]}
    strategies.append("public-search-rss")
    try:
        primary_items, primary_status = primary_crawl(discovery_spec, user_agent)
        collected.extend(primary_items)
        scanned += max(1, int(primary_status.get("scanned", 0) or 0))
        failures += int(primary_status.get("failed", 0) or 0)
        if primary_status.get("error"):
            errors.append(f"search {primary_status['error']}")
    except Exception as exc:
        scanned += 1
        failures += 1
        errors.append(f"search {type(exc).__name__}: {exc}")

    attributed = _dedupe_attributed(collected, rows, crawler, max_items)
    source_url = str(spec.get("sourceUrl") or "").strip()
    body = ""
    if len(attributed) < max_items:
        strategies.append("original-site")
        try:
            body = crawler.fetch_text(
                source_url,
                user_agent,
                timeout=timeout,
                attempts=attempts,
            )
            scanned += 1
        except Exception as exc:
            failures += 1
            errors.append(f"site {type(exc).__name__}: {exc}")

    if body and len(attributed) < max_items:
        language = generic.detect_language(
            source_url,
            body,
            str(spec.get("sourceLanguage") or ""),
        )
        keywords = generic.localize_keywords(spec.get("keywords", []), language)
        runtime_spec = {
            **spec,
            "adapter": "generic_web",
            "url": source_url,
            "sourceUrl": source_url,
            "sourceLanguage": language,
            "keywords": keywords,
            "platform": spec["name"],
        }

        feeds = generic.discover_feeds(source_url, body)[:feed_limit]
        if feeds:
            strategies.append("original-feed")
        for feed in feeds:
            if len(attributed) >= max_items:
                break
            try:
                feed_spec = {
                    **runtime_spec,
                    "url": feed,
                    "allowedHosts": list(spec.get("allowedHosts", [])),
                }
                feed_items = crawler.parse_feed_items(
                    crawler.fetch_text(
                        feed,
                        user_agent,
                        timeout=timeout,
                        attempts=attempts,
                    ),
                    feed_spec,
                )
                scanned += 1
                collected.extend(feed_items)
                attributed = _dedupe_attributed(collected, rows, crawler, max_items)
            except Exception as exc:
                failures += 1
                errors.append(f"feed {type(exc).__name__}: {exc}")

        candidates = generic.discover_candidates(
            source_url,
            body,
            keywords,
            limit=candidate_limit,
        )
        if candidates:
            strategies.append("original-articles")
        for candidate in candidates:
            if len(attributed) >= max_items:
                break
            try:
                article = generic.parse_article(
                    runtime_spec,
                    candidate,
                    crawler.fetch_text(
                        candidate,
                        user_agent,
                        timeout=timeout,
                        attempts=attempts,
                    ),
                    crawler,
                    keywords,
                )
                scanned += 1
                if article:
                    collected.append(article)
                    attributed = _dedupe_attributed(collected, rows, crawler, max_items)
            except Exception as exc:
                failures += 1
                errors.append(f"article {type(exc).__name__}: {exc}")

    rejected = max(0, len(collected) - len(attributed))
    if attributed and failures == 0:
        status_name = "ok"
    elif attributed:
        status_name = "partial"
    elif failures:
        status_name = "error"
    else:
        status_name = "empty"

    transport_requests = scanned
    record_scanned = max(len(collected), len(attributed))
    status = crawler._status(
        spec["id"],
        spec["name"],
        status_name,
        record_scanned,
        len(attributed),
        failed=failures,
        platform=spec["name"],
        error="; ".join(errors[:4]) if errors and not attributed else None,
    )
    status.update(
        {
            "attempted": True,
            "adapter": "professional-media-v1",
            "canonicalSourceUrl": source_url,
            "discoveryUrl": str(spec.get("url") or ""),
            "strategies": strategies,
            "candidateArticles": len(collected),
            "transportRequests": transport_requests,
            "rejectedOutsideRegistry": rejected,
            "requestBudget": {
                "timeoutSeconds": timeout,
                "attempts": attempts,
                "feedLimit": feed_limit,
                "candidateLimit": candidate_limit,
                "stopAfterAccepted": max_items,
            },
        }
    )
    return attributed, status


def install(crawler: Any, generic: Any | None = None) -> None:
    """Enforce original-domain attribution and direct execution for media sources."""

    original_parse = crawler.parse_feed_items
    if not getattr(original_parse, "_professional_media_attribution", False):
        def parse_feed_items(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
            articles = original_parse(body, spec)
            rows = spec.get("professionalMedia")
            if not isinstance(rows, list):
                return articles
            return [
                attributed
                for article in articles
                if (attributed := attribute_article(article, rows)) is not None
            ]

        setattr(parse_feed_items, "_professional_media_attribution", True)
        crawler.parse_feed_items = parse_feed_items

    if generic is None:
        return
    original_crawl = crawler._crawl_config_source
    if getattr(original_crawl, "_professional_media_direct", False):
        return

    def crawl_source(
        spec: dict[str, Any], user_agent: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if spec.get("adapter") != "professional_media":
            return original_crawl(spec, user_agent)
        return crawl_professional_source(
            spec,
            user_agent,
            crawler,
            generic,
            original_crawl,
        )

    setattr(crawl_source, "_professional_media_direct", True)
    crawler._crawl_config_source = crawl_source
