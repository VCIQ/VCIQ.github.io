#!/usr/bin/env python3
"""Run a bounded live acceptance check for media and ByteDance/Toutiao.

This validator is intentionally separate from the full-source refresh. It proves
that each route can reach a verified publisher-owned URL and produce a normal
article record, while preserving destination-host and identity safeguards.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from . import crawl_with_wechat_registry as entry
    from . import wechat_source_registry
except ImportError:
    import crawl_with_wechat_registry as entry
    import wechat_source_registry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "wechat-toutiao-live-report.json"
BYTE_TERMS = ["字节跳动", "豆包", "ByteDance", "Doubao", "火山引擎"]


def _install_adapters() -> Any:
    crawler = entry.base.tracking.crawler
    entry.search_index_feed_redirects.install(crawler)
    entry.wechat_fetch_compat.install(entry.wechat_public_sources)
    entry.wechat_registry_bridge.install(entry.wechat_public_sources)
    entry.wechat_original_redirect_bridge.install(
        entry.wechat_public_sources,
        entry.wechat_registry_bridge,
    )
    entry.wechat_index_context_guard.install(entry.wechat_registry_bridge)
    entry.wechat_index_record_fallback.install(
        entry.wechat_public_sources,
        entry.wechat_registry_bridge,
    )
    entry.wechat_sogou_redirect_compat.install(entry.wechat_sogou_index)
    entry.wechat_sogou_link_compat.install(entry.wechat_sogou_index)
    entry.wechat_public_aggregator.install(entry.wechat_sogou_index)
    entry.wechat_sogou_bridge.install(entry.wechat_public_sources)
    return crawler


def _original_host(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return (urlsplit(str(source.get("url", ""))).hostname or "").casefold()


def _article_summary(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return {
        "title": article.get("title"),
        "publishedAt": article.get("publishedAt"),
        "sourceId": article.get("sourceId"),
        "platform": source.get("platform"),
        "sourceName": source.get("name"),
        "url": source.get("url"),
        "company": article.get("company"),
        "wechatAccount": article.get("wechatAccount"),
        "wechatDiscoveryProvider": article.get("wechatDiscoveryProvider"),
    }


def _contains_byte_term(article: dict[str, Any]) -> bool:
    text = f"{article.get('title', '')} {article.get('summary', '')}".casefold()
    return any(term.casefold() in text for term in BYTE_TERMS)


def _toutiao_probe(crawler: Any) -> dict[str, Any]:
    spec = {
        "id": "live-byte-toutiao",
        "name": "今日头条 · 科技",
        "url": entry.toutiao_public_feed.FEED_ENDPOINT,
        "adapter": "toutiao_feed",
        "platform": "今日头条",
        "sourceLevel": "媒体报道",
        "region": "中国",
        "sector": "AI / AGI",
        "maxItems": 6,
        "categories": ["news_tech", "__all__"],
        # Route validation must not depend on whether a ByteDance-specific story
        # happens to be in the current hot-feed window.
        "keywords": [],
        "allowedHosts": ["toutiao.com"],
        "enabled": True,
    }
    try:
        articles, status = entry.toutiao_public_feed.crawl_toutiao_source(
            spec,
            crawler.DEFAULT_USER_AGENT,
            crawler,
        )
        verified = [
            article
            for article in articles
            if _original_host(article) == "toutiao.com"
            or _original_host(article).endswith(".toutiao.com")
        ]
        return {
            "ok": bool(verified),
            "accepted": len(verified),
            "scanned": status.get("scanned", 0),
            "status": status.get("status"),
            "byteDanceMatches": sum(_contains_byte_term(article) for article in verified),
            "articles": [_article_summary(article) for article in verified[:6]],
            "error": status.get("error")
            if not verified
            else None,
        }
    except Exception as exc:  # noqa: BLE001 - serialized for CI diagnostics.
        return {
            "ok": False,
            "accepted": 0,
            "scanned": 0,
            "status": "error",
            "byteDanceMatches": 0,
            "articles": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def _wechat_spec(account: dict[str, Any]) -> dict[str, Any]:
    sector = str(account.get("defaultSector") or "AI / AGI")
    keywords = list(account.get("sectorKeywords", {}).get(sector, []))
    expected = [account.get("name"), account.get("accountId")]
    public_indexes = entry.wechat_registry_bridge._load_public_indexes()
    return {
        "id": f"live-wechat-{account['id']}",
        "name": account["name"],
        "url": "https://weixin.sogou.com/",
        "adapter": "wechat_search",
        "platform": "微信",
        "sourceLevel": account.get("sourceLevel", "媒体报道"),
        "region": account.get("region", "中国"),
        "sector": sector,
        "maxItems": 2,
        "maxArticleAgeDays": 180,
        "keywords": [*keywords, *BYTE_TERMS],
        "trackedCompanies": list(account.get("companies", [])),
        "trackedPeople": list(account.get("people", [])),
        "strictTitleKeywords": False,
        "expectedAccounts": [value for value in expected if value],
        "accountConfigId": account.get("id"),
        "publisherEntity": account.get("publisherEntity") or account.get("name"),
        "acceptedSourceKinds": list(account.get("acceptedSourceKinds", [])),
        "officialCrosspostHosts": list(account.get("officialCrosspostHosts", [])),
        "publicIndexUrls": list(public_indexes.get(str(account.get("id")), [])),
        "queryIdentity": account.get("name"),
        "discoveryScope": "account",
        "genericDiscovery": False,
        "enabled": True,
    }


def _wechat_probe(crawler: Any) -> dict[str, Any]:
    registry = wechat_source_registry.load_registry()
    configured = {
        str(account.get("id")): account
        for account in registry.get("accounts", [])
        if isinstance(account, dict) and account.get("enabled", True)
    }
    preferred = ["zhidx", "chipmaster", "icsmart", "qbitai", "icbank"]
    accounts = [configured[account_id] for account_id in preferred if account_id in configured]
    attempts: list[dict[str, Any]] = []
    accepted_articles: list[dict[str, Any]] = []
    for account in accounts:
        spec = _wechat_spec(account)
        try:
            articles, status = entry.wechat_public_sources.crawl_wechat_source(
                spec,
                crawler.DEFAULT_USER_AGENT,
                crawler,
            )
            allowed_hosts = {
                str(host).casefold().removeprefix("www.")
                for host in spec.get("officialCrosspostHosts", [])
            }
            verified = []
            for article in articles:
                host = _original_host(article).removeprefix("www.")
                source = article.get("source")
                source = source if isinstance(source, dict) else {}
                source_kind = str(
                    article.get("sourceKind") or source.get("sourceKind") or ""
                )
                is_wechat_original = (
                    host == "mp.weixin.qq.com"
                    and article.get("wechatContentMode") != "index-only"
                )
                is_publisher_copy = (
                    source_kind in {"official-website", "official-crosspost"}
                    and host in allowed_hosts
                )
                if is_wechat_original or is_publisher_copy:
                    verified.append(article)
            attempts.append(
                {
                    "account": account.get("name"),
                    "status": status.get("status"),
                    "accepted": len(verified),
                    "scanned": status.get("scanned", 0),
                    "provider": status.get("discoveryProvider"),
                    "error": status.get("error"),
                }
            )
            accepted_articles.extend(verified)
            if verified:
                break
        except Exception as exc:  # noqa: BLE001 - continue across bounded fallbacks.
            attempts.append(
                {
                    "account": account.get("name"),
                    "status": "error",
                    "accepted": 0,
                    "scanned": 0,
                    "provider": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "ok": bool(accepted_articles),
        "accepted": len(accepted_articles),
        "attempts": attempts,
        "articles": [
            _article_summary(article) for article in accepted_articles[:4]
        ],
        "error": None
        if accepted_articles
        else "No verified WeChat original or publisher-owned copy passed checks",
    }


def run(output: Path) -> dict[str, Any]:
    crawler = _install_adapters()
    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "wechat": _wechat_probe(crawler),
        "toutiao": _toutiao_probe(crawler),
    }
    report["ok"] = bool(report["wechat"]["ok"] and report["toutiao"]["ok"])
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        print(
            "Focused live validation failed: media and Toutiao must produce verified publisher-domain articles",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
