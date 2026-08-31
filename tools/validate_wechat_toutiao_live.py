#!/usr/bin/env python3
"""Run bounded live acceptance checks for WeChat cross-platform routes and Toutiao.

The WeChat portion is intentionally strict: every enabled configured publisher
must produce at least one recent article from an explicitly whitelisted
publisher-owned or certified cross-platform endpoint. A WeChat original may
still be accepted by the production crawler, but it does not satisfy this
cross-platform endpoint validation.
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
    entry.wechat_official_index_bridge.install(entry.wechat_registry_bridge)
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
        "sourceKind": article.get("sourceKind") or source.get("sourceKind"),
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
            "error": status.get("error") if not verified else None,
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
        "keywords": keywords,
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


def _is_verified_crossplatform_copy(
    article: dict[str, Any], allowed_hosts: set[str]
) -> bool:
    host = _original_host(article).removeprefix("www.")
    source = article.get("source")
    source = source if isinstance(source, dict) else {}
    source_kind = str(article.get("sourceKind") or source.get("sourceKind") or "")
    return (
        source_kind in {"official-website", "official-crosspost"}
        and host in allowed_hosts
    )


def _wechat_probe(crawler: Any) -> dict[str, Any]:
    registry = wechat_source_registry.load_registry()
    accounts = [
        account
        for account in registry.get("accounts", [])
        if isinstance(account, dict) and account.get("enabled", True) is not False
    ]
    attempts: list[dict[str, Any]] = []
    accepted_articles: list[dict[str, Any]] = []

    for account in accounts:
        spec = _wechat_spec(account)
        allowed_hosts = {
            str(host).casefold().removeprefix("www.")
            for host in spec.get("officialCrosspostHosts", [])
        }
        try:
            articles, status = entry.wechat_public_sources.crawl_wechat_source(
                spec,
                crawler.DEFAULT_USER_AGENT,
                crawler,
            )
            verified = [
                article
                for article in articles
                if _is_verified_crossplatform_copy(article, allowed_hosts)
            ]
            attempts.append(
                {
                    "accountId": account.get("id"),
                    "account": account.get("name"),
                    "ok": bool(verified),
                    "status": status.get("status"),
                    "accepted": len(verified),
                    "scanned": status.get("scanned", 0),
                    "allowedHosts": sorted(allowed_hosts),
                    "acceptedSourceKinds": spec.get("acceptedSourceKinds", []),
                    "provider": status.get("discoveryProvider"),
                    "error": status.get("error") if not verified else None,
                    "articles": [_article_summary(article) for article in verified[:2]],
                }
            )
            accepted_articles.extend(verified)
        except Exception as exc:  # noqa: BLE001 - continue through all entities.
            attempts.append(
                {
                    "accountId": account.get("id"),
                    "account": account.get("name"),
                    "ok": False,
                    "status": "error",
                    "accepted": 0,
                    "scanned": 0,
                    "allowedHosts": sorted(allowed_hosts),
                    "acceptedSourceKinds": spec.get("acceptedSourceKinds", []),
                    "provider": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "articles": [],
                }
            )

    failed_accounts = [
        str(attempt.get("account")) for attempt in attempts if not attempt.get("ok")
    ]
    return {
        "ok": len(accounts) == 13 and not failed_accounts,
        "configuredAccounts": len(accounts),
        "passedAccounts": sum(bool(attempt.get("ok")) for attempt in attempts),
        "failedAccounts": failed_accounts,
        "accepted": len(accepted_articles),
        "attempts": attempts,
        "articles": [_article_summary(article) for article in accepted_articles[:13]],
        "error": (
            None
            if not failed_accounts and len(accounts) == 13
            else (
                "Cross-platform endpoint validation failed for: "
                + ", ".join(failed_accounts or [f"configured={len(accounts)}"])
            )
        ),
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
            "Focused live validation failed: all 13 configured WeChat publishers must produce a verified whitelisted cross-platform article and Toutiao must remain healthy",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
