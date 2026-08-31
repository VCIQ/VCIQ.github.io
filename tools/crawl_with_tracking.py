#!/usr/bin/env python3
"""Run the public crawler with browser-managed tracking configuration.

The website writes ``config/user_tracking.json`` through GitHub's Contents API.
This adapter turns that safe, small schema into the crawler's native source
configuration without duplicating the main crawler implementation.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus, urlsplit

try:  # Imported by tests as tools.crawl_with_tracking.
    from . import crawl_articles as crawler
    from . import tracking_quality
    from . import tracking_taxonomy
except ImportError:  # Executed directly with ``python tools/...``.
    import crawl_articles as crawler
    import tracking_quality
    import tracking_taxonomy


TRACKING_PATH = crawler.ROOT / "config" / "user_tracking.json"
USER_SOURCE_PREFIXES = ("user-source-", "user-track-", "user-x-")
COMPANY_SOURCE_EVENT_TERMS = (
    "IPO OR listing OR filing OR earnings OR 上市 OR 公告 OR 财报 OR 融资"
)
MEDIA_SOURCE_EVENT_TERMS = (
    "技术 OR technology OR 投资 OR investment OR 融资 OR funding OR "
    "政策 OR policy OR 监管 OR regulation OR regulatory OR 法规 OR "
    "产品 OR product OR 发布 OR launch OR 科研 OR research OR 论文 OR paper OR "
    "专利 OR patent OR 突破 OR breakthrough OR 并购 OR acquisition OR "
    "合作 OR partnership OR 市场 OR market"
)
GENERIC_PERSON_LABELS = {
    "人物",
    "专家",
    "研究员",
    "科学家",
    "创始人",
    "创业者",
    "投资人",
    "ceo",
    "cto",
    "founder",
    "researcher",
    "scientist",
}
PERSON_SEPARATOR_PATTERN = r"[\s|｜·•:：,，;；/\\\-—–()（）\[\]【】]+"


def _clean(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _slug(value: Any) -> str:
    text = _clean(value, 80).casefold()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return text[:60] or "item"


def _unique(values: Iterable[Any], limit: int = 120) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _trim_person_separators(value: str) -> str:
    value = re.sub(rf"^{PERSON_SEPARATOR_PATTERN}", "", value)
    value = re.sub(rf"{PERSON_SEPARATOR_PATTERN}$", "", value)
    return _clean(value, 80)


def _parse_person_label(raw: Any) -> dict[str, Any] | None:
    """Validate and split a browser-managed person/account label.

    Organization and project accounts are intentionally accepted. A label with
    a valid X handle produces three independent search terms: display name,
    bare handle, and @handle. A concrete name without a handle remains useful
    for public search but does not generate an X timeline source.
    """

    value = _clean(raw, 100).replace("＠", "@")
    if not value:
        return None
    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        return None
    if re.search(r"(?:x|twitter)\.com/", value, flags=re.IGNORECASE):
        return None
    if value.count("@") > 1:
        return None

    match = re.search(r"@([A-Za-z0-9_]{1,15})(?![A-Za-z0-9_])", value)
    if "@" in value and not match:
        return None

    if match:
        handle = match.group(1)
        display_name = _trim_person_separators(
            f"{value[:match.start()]} {value[match.end():]}"
        )
        if display_name and not re.search(r"[A-Za-z0-9\u3400-\u9fff]", display_name):
            return None
        normalized = f"{display_name} @{handle}" if display_name else f"@{handle}"
        return {
            "normalized": normalized,
            "displayName": display_name,
            "handle": handle,
            "searchTerms": _unique([display_name, handle, f"@{handle}"], 3),
        }

    display_name = _trim_person_separators(value)
    if (
        len(display_name) < 2
        or not re.search(r"[A-Za-z0-9\u3400-\u9fff]", display_name)
        or display_name.casefold() in GENERIC_PERSON_LABELS
    ):
        return None
    return {
        "normalized": display_name,
        "displayName": display_name,
        "handle": "",
        "searchTerms": [display_name],
    }


def _normalize_people(values: Any, limit: int = 40) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        parsed = _parse_person_label(raw)
        if not parsed:
            continue
        normalized = str(parsed["normalized"])
        key = normalized.casefold()
        if key in seen:
            continue
        result.append(normalized)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def load_tracking(path: Path = TRACKING_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": 1, "tracks": [], "sources": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("user tracking configuration must be a JSON object")
    if int(payload.get("schemaVersion", 1)) != 1:
        raise ValueError("unsupported user tracking schema version")
    tracks = payload.get("tracks", [])
    sources = payload.get("sources", [])
    if not isinstance(tracks, list) or not isinstance(sources, list):
        raise ValueError("user tracking tracks and sources must be arrays")
    return payload


def _enabled_tracks(tracking: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in tracking.get("tracks", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        name = _clean(raw.get("name"), 60)
        if not name:
            continue
        result.append(
            {
                "slug": _slug(raw.get("slug") or name),
                "name": name,
                "keywords": _unique(raw.get("keywords", []), 60),
                "people": _normalize_people(raw.get("people", []), 40),
                "sampleCompanies": _unique(raw.get("sampleCompanies", []), 40),
            }
        )
    return result[:30]


def _person_search_terms(values: Iterable[Any]) -> list[str]:
    terms: list[str] = []
    for raw in values:
        parsed = _parse_person_label(raw)
        if parsed:
            terms.extend(parsed.get("searchTerms", []))
    return _unique(terms, 80)


def _track_terms(track: dict[str, Any]) -> list[str]:
    return _unique(
        [
            track["name"],
            *track.get("keywords", []),
            *_person_search_terms(track.get("people", [])),
            *track.get("sampleCompanies", []),
        ],
        80,
    )


def _bing_rss(query: str) -> str:
    return f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"


def _quoted_or_query(terms: list[str], limit: int = 16) -> str:
    quoted = [f'"{term.replace(chr(34), "")}"' for term in terms[:limit] if term]
    return " OR ".join(quoted)


def _generated_track_sources(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    event_terms = "融资 OR 投资 OR IPO OR 上市 OR 发布 OR 突破 OR 研究 OR funding OR launch"
    for track in tracks:
        terms = _track_terms(track)
        if not terms:
            continue
        query = f"({_quoted_or_query(terms)}) ({event_terms})"
        sources.append(
            {
                "id": f"user-track-{track['slug']}",
                "name": f"{track['name']} · 用户追踪",
                "url": _bing_rss(query),
                "adapter": "rss",
                "platform": "用户追踪",
                "sourceLevel": "待交叉验证",
                "region": "全球",
                "sector": track["name"],
                "maxItems": 8,
                "keywords": terms,
                "strictTitleKeywords": False,
                "enabled": True,
            }
        )
        sources.append(
            tracking_taxonomy.toutiao_source_spec(
                track["slug"],
                track["name"],
                _bing_rss(f"site:{tracking_taxonomy.TOUTIAO_HOST} {query}"),
                terms,
            )
        )
    return sources


def _person_profile(raw: str, track: dict[str, Any]) -> dict[str, Any] | None:
    parsed = _parse_person_label(raw)
    if not parsed or not parsed.get("handle"):
        return None
    handle = str(parsed["handle"])
    name = str(parsed.get("displayName") or handle)
    return {
        "id": f"user-x-{_slug(handle)}",
        "name": name,
        "handle": handle,
        "kind": "person",
        "region": "全球",
        "sector": track["name"],
        "platform": "X",
        "maxItems": 5,
        "enabled": True,
    }


def _generated_x_profiles(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for track in tracks:
        for raw in track.get("people", []):
            profile = _person_profile(raw, track)
            if profile and profile["id"] not in seen:
                profiles.append(profile)
                seen.add(profile["id"])
    return profiles


def _source_keywords(raw: dict[str, Any], track_by_name: dict[str, dict[str, Any]]) -> list[str]:
    linked = track_by_name.get(_clean(raw.get("sector"), 60).casefold())
    return _unique(
        [
            raw.get("company"),
            raw.get("ticker"),
            *raw.get("keywords", []),
            *(_track_terms(linked) if linked else []),
        ],
        80,
    )


def _custom_sources(
    tracking: dict[str, Any], tracks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str, str, str]]]:
    feed_specs: list[dict[str, Any]] = []
    sec_specs: dict[str, tuple[str, str, str, str]] = {}
    track_by_name = {track["name"].casefold(): track for track in tracks}
    for index, raw in enumerate(tracking.get("sources", [])):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        name = _clean(raw.get("name"), 80)
        source_type = _clean(raw.get("sourceType"), 30) or "listing-search"
        source_category = _clean(raw.get("sourceCategory"), 30).casefold()
        if source_category not in {"media", "company", "person"}:
            source_category = "company"
        is_media_source = source_category == "media"
        company = _clean(raw.get("company"), 80) or name
        ticker = _clean(raw.get("ticker"), 30).upper()
        region = _clean(raw.get("region"), 20)
        if region not in {"中国", "美国", "全球"}:
            region = "全球"
        sector = _clean(raw.get("sector"), 60) or "AI / AGI"
        url = _clean(raw.get("url"), 500)
        source_id = f"user-source-{_slug(raw.get('id') or name or index)}"
        if not name:
            continue
        if source_type == "sec":
            if ticker:
                sec_specs[ticker] = (company, _slug(company), sector, region)
            continue
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            continue
        keywords = _source_keywords(raw, track_by_name)
        if source_type == "rss":
            feed_url = url
            platform = "用户媒体来源" if is_media_source else "用户 RSS"
            allowed_hosts: list[str] = []
        else:
            host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
            if not host:
                continue
            if is_media_source:
                discovery_terms = keywords or [sector]
                query = (
                    f"site:{host} ({_quoted_or_query(discovery_terms)}) "
                    f"({MEDIA_SOURCE_EVENT_TERMS})"
                )
                platform = "用户媒体来源"
            else:
                identity_terms = _unique([company, ticker, *keywords], 16)
                query = (
                    f"site:{host} ({_quoted_or_query(identity_terms)}) "
                    f"({COMPANY_SOURCE_EVENT_TERMS})"
                )
                platform = "用户公司来源"
            feed_url = _bing_rss(query)
            allowed_hosts = [host]
        spec: dict[str, Any] = {
            "id": source_id,
            "name": name,
            "url": feed_url,
            "adapter": "rss",
            "platform": platform,
            "sourceLevel": "待交叉验证",
            "sourceCategory": source_category,
            "region": region,
            "sector": sector,
            "maxItems": 10,
            "keywords": keywords,
            "strictTitleKeywords": False,
            "enabled": True,
        }
        if not is_media_source:
            spec["company"] = company
            spec["companySlug"] = _slug(company)
        if allowed_hosts:
            spec["allowedHosts"] = allowed_hosts
        feed_specs.append(spec)
    return feed_specs[:60], sec_specs


def build_merged_config(
    base: dict[str, Any], tracking: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, tuple[str, str, str, str]], set[str]]:
    config = copy.deepcopy(base)
    tracks = _enabled_tracks(tracking)
    global_terms = _unique(
        term for track in tracks for term in _track_terms(track)
    )
    terms_by_sector = {
        track["name"].casefold(): _track_terms(track) for track in tracks
    }

    for group in ("feeds", "publicDiscovery", "papers"):
        specs = config.setdefault(group, [])
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            sector_terms = terms_by_sector.get(_clean(spec.get("sector"), 60).casefold())
            extra_terms = sector_terms or global_terms
            spec["keywords"] = _unique(
                [*spec.get("keywords", []), *extra_terms],
                120,
            )

    generated_track_sources = _generated_track_sources(tracks)
    custom_sources, sec_specs = _custom_sources(tracking, tracks)
    generated_x = _generated_x_profiles(tracks)
    config.setdefault("publicDiscovery", []).extend(generated_track_sources)
    config.setdefault("feeds", []).extend(custom_sources)
    config.setdefault("xProfiles", []).extend(generated_x)

    active_ids = {
        spec["id"]
        for spec in [*generated_track_sources, *custom_sources, *generated_x]
    }
    return config, sec_specs, active_ids


def _install_runtime_overrides(
    merged: dict[str, Any],
    sec_specs: dict[str, tuple[str, str, str, str]],
    active_ids: set[str],
) -> None:
    original_load_config = crawler.load_config
    original_load_payload = crawler.load_existing_payload
    original_external_article = crawler._external_article
    original_repair_attribution = crawler.repair_media_company_attribution
    original_evaluate_quality = crawler.evaluate_quality
    tracking_report: dict[str, Any] = {}

    def load_config(path: Path = crawler.CONFIG_PATH) -> dict[str, Any]:
        if Path(path) == crawler.CONFIG_PATH:
            return copy.deepcopy(merged)
        return original_load_config(path)

    def load_payload(path: Path = crawler.OUTPUT_PATH) -> dict[str, Any]:
        payload = original_load_payload(path)
        payload["articles"] = [
            article
            for article in payload.get("articles", [])
            if not str(article.get("sourceId", "")).startswith(USER_SOURCE_PREFIXES)
            or str(article.get("sourceId", "")) in active_ids
        ]
        payload["sourceStatus"] = [
            status
            for status in payload.get("sourceStatus", [])
            if not str(status.get("id", "")).startswith(USER_SOURCE_PREFIXES)
            or str(status.get("id", "")) in active_ids
        ]
        return payload

    def external_article(spec: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("company", spec.get("company") or None)
        kwargs.setdefault("company_slug", spec.get("companySlug") or None)
        return original_external_article(spec, **kwargs)

    def repair_media_company_attribution(
        articles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        repaired = original_repair_attribution(articles)
        filtered, report = tracking_quality.apply_tracking_quality(repaired, merged)
        tracking_report.clear()
        tracking_report.update(report)
        print(f"Tracking quality: {json.dumps(report, ensure_ascii=False)}")
        return filtered

    def evaluate_quality(
        articles: list[dict[str, Any]],
        source_status: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        quality = original_evaluate_quality(articles, source_status, settings)
        quality["trackingQuality"] = dict(tracking_report)
        return quality

    crawler.load_config = load_config
    crawler.load_existing_payload = load_payload
    crawler._external_article = external_article
    crawler.repair_media_company_attribution = repair_media_company_attribution
    crawler.evaluate_quality = evaluate_quality
    crawler.SEC_TRACKED.update(sec_specs)


def main() -> int:
    base = crawler.load_config()
    tracking = load_tracking()
    merged, sec_specs, active_ids = build_merged_config(base, tracking)
    _install_runtime_overrides(merged, sec_specs, active_ids)
    return crawler.main()


if __name__ == "__main__":
    raise SystemExit(main())
