#!/usr/bin/env python3
"""Refresh only verified WeChat originals while preserving other snapshot data."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

try:  # Imported by tests as tools.refresh_wechat_snapshot.
    from . import crawl_articles as crawler
    from . import crawl_with_tracking as tracking
    from . import wechat_fetch_compat
    from . import wechat_index_context_guard
    from . import wechat_index_record_fallback
    from . import wechat_original_redirect_bridge
    from . import wechat_public_aggregator
    from . import wechat_public_index_title_fallback
    from . import wechat_public_sources
    from . import wechat_registry_bridge
    from . import wechat_sogou_bridge
    from . import wechat_sogou_index
    from . import wechat_sogou_link_compat
    from . import wechat_sogou_redirect_compat
    from . import wechat_snapshot_quality
except ImportError:  # Executed directly with python tools/...
    import crawl_articles as crawler
    import crawl_with_tracking as tracking
    import wechat_fetch_compat
    import wechat_index_context_guard
    import wechat_index_record_fallback
    import wechat_original_redirect_bridge
    import wechat_public_aggregator
    import wechat_public_index_title_fallback
    import wechat_public_sources
    import wechat_registry_bridge
    import wechat_sogou_bridge
    import wechat_sogou_index
    import wechat_sogou_link_compat
    import wechat_sogou_redirect_compat
    import wechat_snapshot_quality

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "articles.json"


def install_wechat_pipeline() -> None:
    wechat_fetch_compat.install(wechat_public_sources)
    wechat_registry_bridge.install(wechat_public_sources)
    wechat_original_redirect_bridge.install(
        wechat_public_sources,
        wechat_registry_bridge,
    )
    wechat_index_context_guard.install(wechat_registry_bridge)
    wechat_index_record_fallback.install(
        wechat_public_sources,
        wechat_registry_bridge,
    )
    wechat_sogou_redirect_compat.install(wechat_sogou_index)
    wechat_sogou_link_compat.install(wechat_sogou_index)
    wechat_public_index_title_fallback.install(
        wechat_registry_bridge,
        wechat_sogou_index,
    )
    wechat_public_aggregator.install(wechat_sogou_index)
    wechat_sogou_bridge.install(wechat_public_sources)


def configured_sources(account_ids: set[str] | None = None) -> list[dict[str, Any]]:
    install_wechat_pipeline()
    payload = tracking.load_tracking()
    tracks = tracking._enabled_tracks(payload)
    sources = wechat_public_sources.generated_wechat_sources(tracks, tracking)
    if account_ids:
        sources = [
            source
            for source in sources
            if str(source.get("accountConfigId") or source.get("id")) in account_ids
        ]
    return sources


def _is_wechat_record(article: dict[str, Any]) -> bool:
    source = article.get("source")
    source = source if isinstance(source, dict) else {}
    source_id = str(article.get("sourceId", ""))
    platform = str(source.get("platform", ""))
    url = str(source.get("url", ""))
    return (
        source_id.startswith("user-track-wechat-")
        or platform.startswith("微信")
        or bool(article.get("wechatAccount"))
        or wechat_original_redirect_bridge.is_direct_wechat_url(url)
        or wechat_original_redirect_bridge.is_public_index_proxy_url(url)
    )


def _publishable_article(article: dict[str, Any]) -> bool:
    if not _is_wechat_record(article):
        return True
    source = article.get("source")
    source = source if isinstance(source, dict) else {}
    return (
        str(source.get("platform", "")) == "微信"
        and article.get("wechatContentMode") != "index-only"
        and wechat_original_redirect_bridge.is_direct_wechat_url(
            str(source.get("url", ""))
        )
    )


def _normalize_statuses(
    statuses: Sequence[dict[str, Any]],
    incoming: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    accepted_by_source = Counter(str(article.get("sourceId", "")) for article in incoming)
    result: list[dict[str, Any]] = []
    for raw in statuses:
        status = dict(raw)
        source_id = str(status.get("id", ""))
        if source_id.startswith("user-track-wechat-"):
            accepted = accepted_by_source.get(source_id, 0)
            status["accepted"] = accepted
            if accepted == 0 and status.get("status") in {"ok", "partial"}:
                status["status"] = "error"
                status["failed"] = max(1, int(status.get("failed", 0) or 0))
                status["retainedPrevious"] = True
                status["error"] = (
                    "Discovery returned only proxy/index pages; no original "
                    "mp.weixin.qq.com article was published"
                )
        result.append(status)
    return result


def crawl_sources(
    sources: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incoming: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or crawler.DEFAULT_USER_AGENT
    for source in sources:
        try:
            articles, status = wechat_public_sources.crawl_wechat_source(
                source,
                user_agent,
                crawler,
            )
        except Exception as exc:  # noqa: BLE001 - retain the previous source batch.
            articles = []
            status = crawler._status(
                source["id"],
                source["name"],
                "error",
                0,
                0,
                failed=1,
                platform="微信",
                error=f"{type(exc).__name__}: {exc}",
            )
            status["retainedPrevious"] = True
        incoming.extend(articles)
        statuses.append(status)
        print(
            "wechat={id} sector={sector} status={status} scanned={scanned} "
            "accepted={accepted}".format(
                id=source.get("id"),
                sector=source.get("sector"),
                status=status.get("status"),
                scanned=status.get("scanned", 0),
                accepted=status.get("accepted", 0),
            )
        )
    incoming = wechat_snapshot_quality.resolve_cross_sector_articles(
        incoming,
        tracking.load_tracking(),
    )
    incoming = [article for article in incoming if _publishable_article(article)]
    return incoming, _normalize_statuses(statuses, incoming)


def merge_wechat_snapshot(
    payload: dict[str, Any],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_existing = [
        article for article in payload.get("articles", []) if isinstance(article, dict)
    ]
    existing_articles = [article for article in raw_existing if _publishable_article(article)]
    removed_proxy_records = len(raw_existing) - len(existing_articles)
    raw_incoming = [article for article in incoming if isinstance(article, dict)]
    incoming = [article for article in raw_incoming if _publishable_article(article)]
    rejected_incoming = len(raw_incoming) - len(incoming)
    statuses = _normalize_statuses(statuses, incoming)

    merged_articles = crawler.replace_source_batches(
        existing_articles,
        incoming,
        statuses,
    )
    invalid = [
        {"id": article.get("id", "unknown"), "errors": crawler.validate_article(article)}
        for article in merged_articles
        if crawler.validate_article(article)
    ]
    if invalid:
        raise ValueError(f"invalid WeChat snapshot articles: {invalid[:5]}")

    merged_status = crawler.merge_source_status(
        [item for item in payload.get("sourceStatus", []) if isinstance(item, dict)],
        statuses,
    )
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    next_payload = dict(payload)
    next_payload.update(
        {
            "schemaVersion": 3,
            "generatedAt": generated_at,
            "articleCount": len(merged_articles),
            "articles": merged_articles,
            "sourceStatus": merged_status,
            "wechatIngestion": {
                "generatedAt": generated_at,
                "configuredSources": len(statuses),
                "successfulSources": sum(
                    1
                    for status in statuses
                    if status.get("status") in {"ok", "partial"}
                    and int(status.get("accepted", 0) or 0) > 0
                ),
                "acceptedArticles": len(incoming),
                "fullTextArticles": len(incoming),
                "indexOnlyArticles": 0,
                "removedProxyRecords": removed_proxy_records + rejected_incoming,
                "retainedSources": sum(
                    1
                    for status in statuses
                    if status.get("retainedPrevious")
                    or int(status.get("accepted", 0) or 0) == 0
                ),
                "mentionedCompanyLinks": sum(
                    len(article.get("mentionedCompanies", [])) for article in incoming
                ),
                "mentionedPeopleLinks": sum(
                    len(article.get("mentionedPeople", [])) for article in incoming
                ),
            },
        }
    )
    return next_payload


def write_snapshot(next_payload: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    previous = {}
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
    comparable_previous = dict(previous)
    comparable_next = dict(next_payload)
    comparable_previous.pop("generatedAt", None)
    comparable_next.pop("generatedAt", None)
    previous_ingestion = comparable_previous.get("wechatIngestion")
    next_ingestion = comparable_next.get("wechatIngestion")
    if isinstance(previous_ingestion, dict):
        previous_ingestion = dict(previous_ingestion)
        previous_ingestion.pop("generatedAt", None)
        comparable_previous["wechatIngestion"] = previous_ingestion
    if isinstance(next_ingestion, dict):
        next_ingestion = dict(next_ingestion)
        next_ingestion.pop("generatedAt", None)
        comparable_next["wechatIngestion"] = next_ingestion
    if comparable_previous == comparable_next:
        print("No WeChat snapshot changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            next_payload.get("wechatIngestion", {}),
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account",
        action="append",
        default=[],
        help="Refresh only one configured account id; repeat to select several.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    account_ids = {value.strip() for value in args.account if value.strip()} or None
    sources = configured_sources(account_ids)
    if not sources:
        raise SystemExit("No configured WeChat sources matched the request")
    incoming, statuses = crawl_sources(sources)
    payload = crawler.load_existing_payload()
    next_payload = merge_wechat_snapshot(payload, incoming, statuses)
    if args.dry_run:
        print(json.dumps(next_payload.get("wechatIngestion", {}), ensure_ascii=False))
        return 0
    write_snapshot(next_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
