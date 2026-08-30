"""Build strict, sector-aware WeChat discovery sources from configuration.

Every enabled tracking sector always receives a generic sector discovery source.
Configured public accounts are additive precision sources rather than replacements,
so a failed or missing account registry can never disable WeChat coverage for a
newly added sector.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "wechat_sources.json"
MAX_QUERY_TERMS = 16
MAX_CONFIGURED_ACCOUNTS_PER_TRACK = 12
EVENT_TERMS = (
    "发布",
    "推出",
    "融资",
    "投资",
    "上市",
    "IPO",
    "研究",
    "突破",
    "合作",
    "签署",
    "报告",
    "论文",
    "访谈",
    "演讲",
    "观点",
    "表示",
    "量产",
    "投产",
)


def _clean(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\u3400-\u9fff]+", "", _clean(value, 160).casefold()
    )


def _slug(value: Any) -> str:
    text = _clean(value, 80).casefold()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return text[:60] or "wechat"


def _unique(values: Iterable[Any], limit: int = 120) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, 120)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _person_name(value: Any) -> str:
    text = _clean(value, 100).replace("＠", "@")
    text = re.sub(r"\s*@[A-Za-z0-9_]{1,15}\s*$", "", text)
    return text.strip(" ·•|｜-—–()（）[]【】")


def _quoted_terms(values: Sequence[str], limit: int = MAX_QUERY_TERMS) -> str:
    return " OR ".join(
        f'"{value.replace(chr(34), "")}"' for value in values[:limit] if value
    )


def load_registry(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or int(payload.get("schemaVersion", 0)) != 1:
        raise ValueError("unsupported WeChat source registry schema")
    accounts = payload.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("WeChat source registry accounts must be an array")
    return payload


def account_matches(spec: dict[str, Any], observed: str) -> bool:
    expected = spec.get("expectedAccounts", [])
    if not expected:
        return True
    observed_key = _key(observed)
    if not observed_key:
        return False
    for value in expected:
        expected_key = _key(value)
        if expected_key and (
            expected_key == observed_key
            or expected_key in observed_key
        ):
            return True
    return False


def _track_index(tracks: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _clean(track.get("name"), 60).casefold(): track
        for track in tracks
        if _clean(track.get("name"), 60)
    }


def _configured_for_sector(
    registry: dict[str, Any], sector: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in registry.get("accounts", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        sector_keywords = raw.get("sectorKeywords", {})
        if isinstance(sector_keywords, dict) and sector in sector_keywords:
            result.append(raw)
    return result[:MAX_CONFIGURED_ACCOUNTS_PER_TRACK]


def _sector_name_terms(value: Any) -> list[str]:
    sector = _clean(value, 80)
    if not sector:
        return []
    parts = [
        part.strip()
        for part in re.split(r"[/／|｜、,，]+", sector)
        if part.strip()
    ]
    return _unique([sector, *parts], 6)


def _tracked_entities(track: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    companies = _unique(track.get("sampleCompanies", []), 30)
    people = _unique(
        (_person_name(value) for value in track.get("people", [])), 30
    )
    keywords = _unique(
        [*_sector_name_terms(track.get("name")), *track.get("keywords", [])],
        60,
    )
    return companies, people, keywords


def _query_url(identity: Sequence[str], terms: Sequence[str]) -> str:
    identity_query = _quoted_terms(_unique(identity, 3), 3)
    topic_query = _quoted_terms(_unique(terms, MAX_QUERY_TERMS), MAX_QUERY_TERMS)
    event_query = _quoted_terms(list(EVENT_TERMS), 12)
    query = "site:mp.weixin.qq.com/s "
    if identity_query:
        query += f"({identity_query}) "
    query += f"({topic_query}) ({event_query})"
    return f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"


def _configured_spec(
    account: dict[str, Any],
    sector: str,
    track: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    track_companies, track_people, track_keywords = _tracked_entities(track)
    configured_keywords = account.get("sectorKeywords", {}).get(sector, [])
    companies = _unique([*account.get("companies", []), *track_companies], 50)
    people = _unique([*account.get("people", []), *track_people], 50)
    keywords = _unique([*configured_keywords, *track_keywords], 80)
    identity = [account.get("name", ""), account.get("accountId", "")]
    query_terms = [*keywords[:8], *companies[:5], *people[:3]]
    source_id = (
        f"user-track-wechat-{_slug(account.get('id') or account.get('name'))}-"
        f"{_slug(track.get('slug') or sector)}"
    )
    return {
        "id": source_id,
        "name": account["name"],
        "url": _query_url(identity, query_terms),
        "adapter": "wechat_search",
        "platform": "微信",
        "sourceLevel": account.get("sourceLevel", "媒体报道"),
        "region": account.get("region", "中国"),
        "sector": sector,
        "maxItems": int(settings.get("maxItemsPerAccount", 6)),
        "maxArticleAgeDays": int(settings.get("maxArticleAgeDays", 45)),
        "keywords": keywords,
        "trackedCompanies": companies,
        "trackedPeople": people,
        "strictTitleKeywords": False,
        "expectedAccounts": _unique(identity, 3),
        "accountConfigId": account.get("id"),
        "publisherEntity": account.get("publisherEntity") or account.get("name"),
        "acceptedSourceKinds": _unique(
            account.get("acceptedSourceKinds", []), 4
        ),
        "officialCrosspostHosts": _unique(
            account.get("officialCrosspostHosts", []), 6
        ),
        "queryIdentity": account.get("name") or sector,
        "discoveryScope": "account",
        "genericDiscovery": False,
        "enabled": True,
    }


def _generic_spec(
    track: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any]:
    companies, people, keywords = _tracked_entities(track)
    sector = _clean(track.get("name"), 60)
    discovery_terms = _unique(
        [*keywords[:10], *companies[:6], *people[:5], sector],
        MAX_QUERY_TERMS,
    )
    source_id = f"user-track-wechat-{_slug(track.get('slug') or sector)}"
    return {
        "id": source_id,
        "name": f"微信公众号 · {sector}",
        "url": _query_url([], discovery_terms),
        "adapter": "wechat_search",
        "platform": "微信",
        "sourceLevel": "媒体报道",
        "region": "中国",
        "sector": sector,
        "maxItems": int(settings.get("maxItemsPerTrack", 6)),
        "maxArticleAgeDays": int(settings.get("maxArticleAgeDays", 45)),
        "keywords": keywords,
        "trackedCompanies": companies,
        "trackedPeople": people,
        "strictTitleKeywords": False,
        "queryIdentity": sector,
        "discoveryScope": "track",
        "genericDiscovery": True,
        "enabled": True,
    }


def generated_wechat_sources(
    tracks: Sequence[dict[str, Any]], tracking: Any
) -> list[dict[str, Any]]:
    """Generate complete WeChat coverage for every enabled tracking sector.

    Each sector receives one account-agnostic source unconditionally. Any
    configured public-account sources are appended as stricter, higher-precision
    probes. No global slicing is applied, so later custom sectors cannot be
    silently dropped when the source registry grows.
    """

    del tracking
    registry = load_registry()
    settings = registry.get("settings", {}) if isinstance(registry, dict) else {}
    indexed = _track_index(tracks)
    sources: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for track in tracks:
        sector = _clean(track.get("name"), 60)
        if not sector:
            continue

        # This invariant guarantees that every built-in or user-created track
        # remains crawlable even if no account is configured or all account
        # probes fail.
        generic = _generic_spec(indexed[sector.casefold()], settings)
        sources.append(generic)
        seen_ids.add(generic["id"])

        for account in _configured_for_sector(registry, sector):
            spec = _configured_spec(
                account,
                sector,
                indexed[sector.casefold()],
                settings,
            )
            if spec["id"] in seen_ids:
                continue
            sources.append(spec)
            seen_ids.add(spec["id"])

    return sources
