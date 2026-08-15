#!/usr/bin/env python3
"""Run the standard crawler with verified WeChat and source-portfolio routing."""

from __future__ import annotations

import json

try:  # Imported by tests as tools.crawl_with_wechat_registry.
    from . import article_publication_gate
    from . import core_official_adapters
    from . import crawl_with_source_categories as base
    from . import financing_details
    from . import http_policy_bridge
    from . import professional_media_progress
    from . import professional_media_sources
    from . import search_index_feed_redirects
    from . import source_evidence
    from . import source_health_runtime
    from . import source_performance
    from . import source_portfolio
    from . import toutiao_public_feed
    from . import wechat_fetch_compat
    from . import wechat_index_context_guard
    from . import wechat_index_record_fallback
    from . import wechat_original_redirect_bridge
    from . import wechat_public_aggregator
    from . import wechat_public_sources
    from . import wechat_registry_bridge
    from . import wechat_sogou_bridge
    from . import wechat_sogou_index
    from . import wechat_sogou_link_compat
    from . import wechat_sogou_redirect_compat
    from . import wechat_snapshot_quality
except ImportError:  # Executed directly with python tools/...
    import article_publication_gate
    import core_official_adapters
    import crawl_with_source_categories as base
    import financing_details
    import http_policy_bridge
    import professional_media_progress
    import professional_media_sources
    import search_index_feed_redirects
    import source_evidence
    import source_health_runtime
    import source_performance
    import source_portfolio
    import toutiao_public_feed
    import wechat_fetch_compat
    import wechat_index_context_guard
    import wechat_index_record_fallback
    import wechat_original_redirect_bridge
    import wechat_public_aggregator
    import wechat_public_sources
    import wechat_registry_bridge
    import wechat_sogou_bridge
    import wechat_sogou_index
    import wechat_sogou_link_compat
    import wechat_sogou_redirect_compat
    import wechat_snapshot_quality


def _publishable_article(article) -> bool:
    source = article.get("source") if isinstance(article, dict) else None
    source = source if isinstance(source, dict) else {}
    platform = str(source.get("platform", ""))
    source_id = str(article.get("sourceId", "")) if isinstance(article, dict) else ""
    is_wechat = (
        source_id.startswith("user-track-wechat-")
        or platform.startswith("微信")
        or bool(article.get("wechatAccount"))
    )
    if not is_wechat:
        return True
    return (
        platform == "微信"
        and article.get("wechatContentMode") != "index-only"
        and wechat_original_redirect_bridge.is_direct_wechat_url(
            str(source.get("url", ""))
        )
    )


def _install_snapshot_quality() -> None:
    original = base.tracking.crawler.replace_source_batches
    if getattr(original, "_wechat_snapshot_quality", False):
        return

    def replace_source_batches(existing, incoming, statuses):
        clean_existing = [article for article in existing if _publishable_article(article)]
        clean_incoming = [article for article in incoming if _publishable_article(article)]
        wechat_rows = [
            article
            for article in clean_incoming
            if article.get("source", {}).get("platform") == "微信"
        ]
        other_rows = [
            article
            for article in clean_incoming
            if article.get("source", {}).get("platform") != "微信"
        ]
        resolved = wechat_snapshot_quality.resolve_cross_sector_articles(
            wechat_rows,
            base.tracking.load_tracking(),
        )
        return original(clean_existing, [*other_rows, *resolved], statuses)

    setattr(replace_source_batches, "_wechat_snapshot_quality", True)
    base.tracking.crawler.replace_source_batches = replace_source_batches


def _install_professional_media() -> None:
    original = base._custom_sources
    if getattr(original, "_professional_media_catalog", False):
        return

    source_portfolio.install_professional_media(professional_media_sources)

    def custom_sources(tracking_config, tracks):
        runtime_specs, sec_specs = original(tracking_config, tracks)
        professional_specs = professional_media_sources.grouped_specs(
            tracks,
            base.tracking,
        )
        professional_specs = source_portfolio.classify_professional_media_specs(
            professional_specs
        )
        return [*runtime_specs, *professional_specs], sec_specs

    setattr(custom_sources, "_professional_media_catalog", True)
    base._custom_sources = custom_sources
    professional_media_sources.install(
        base.tracking.crawler,
        base.generic_web_sources,
    )
    professional_media_progress.install(base.tracking.crawler)
    prefixes = tuple(base.tracking.USER_SOURCE_PREFIXES)
    if "professional-media-" not in prefixes:
        base.tracking.USER_SOURCE_PREFIXES = (*prefixes, "professional-media-")


def _install_source_governance() -> None:
    crawler = base.tracking.crawler
    if getattr(crawler, "_source_governance_installed", False):
        return

    original_source = crawler._source
    original_repair = crawler.repair_media_company_attribution
    original_install_runtime = base.tracking._install_runtime_overrides

    def source(name, url, level, platform):
        return source_evidence.enrich_source_evidence(
            original_source(name, url, level, platform)
        )

    def repair_media_company_attribution(articles):
        # Add evidence grade/role before tracking-quality scoring so downstream
        # ranking can inspect authority. Financing envelopes are deterministic
        # metadata extracted only from the published title/summary and do not
        # alter publication eligibility.
        repaired = original_repair(articles)
        repaired = financing_details.enrich_financing_articles(repaired)
        return source_evidence.enrich_article_sources(repaired)

    def install_runtime(merged, sec_specs, active_ids):
        original_install_runtime(merged, sec_specs, active_ids)

        runtime_repair = crawler.repair_media_company_attribution
        if not getattr(runtime_repair, "_article_publication_gate", False):
            def repair_with_publication_gate(articles):
                scored = runtime_repair(articles)
                enriched = source_evidence.enrich_article_sources(scored)
                publishable, report = article_publication_gate.filter_publishable_articles(
                    enriched
                )
                print(
                    "Article publication gate: "
                    + json.dumps(report, ensure_ascii=False)
                )
                # Re-run deterministic enrichment after publication filtering so
                # the committed batch always carries the envelope contract even
                # when a runtime scoring wrapper reconstructed article dicts.
                return financing_details.enrich_financing_articles(publishable)

            setattr(repair_with_publication_gate, "_article_publication_gate", True)
            crawler.repair_media_company_attribution = repair_with_publication_gate

        original_replace = crawler.replace_source_batches
        if getattr(original_replace, "_source_publication_quarantine", False):
            return
        quarantined_ids = source_health_runtime.load_publication_quarantine()

        def replace_source_batches(existing, incoming, statuses):
            publishable, replacement_statuses = (
                source_health_runtime.withhold_quarantined_publication(
                    incoming,
                    statuses,
                    quarantined_ids,
                )
            )
            if quarantined_ids:
                print(
                    "Source publication quarantine: "
                    + json.dumps(sorted(quarantined_ids), ensure_ascii=False)
                )
            # replacement_statuses intentionally excludes quarantined sources so
            # their previously verified article batches remain published. The
            # caller-owned statuses list is retained and already carries probe
            # metadata such as publicationWithheld/collectionState.
            published = original_replace(existing, publishable, replacement_statuses)
            source_performance.annotate_publication_metrics(
                incoming,
                published,
                statuses,
                withheld_source_ids=quarantined_ids,
            )
            return published

        setattr(replace_source_batches, "_source_publication_quarantine", True)
        crawler.replace_source_batches = replace_source_batches

    crawler._source = source
    crawler.repair_media_company_attribution = repair_media_company_attribution
    base.tracking._install_runtime_overrides = install_runtime
    setattr(crawler, "_source_governance_installed", True)


def main() -> int:
    core_official_adapters.install(base.tracking.crawler)
    http_policy_bridge.install(base.tracking.crawler)
    search_index_feed_redirects.install(base.tracking.crawler)
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
    wechat_public_aggregator.install(wechat_sogou_index)
    wechat_sogou_bridge.install(wechat_public_sources)
    toutiao_public_feed.install(base.tracking)
    _install_professional_media()
    _install_source_governance()
    _install_snapshot_quality()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
