#!/usr/bin/env python3
"""Second-pass per-company discovery for the PR #692 pre-listing universe.

Read-only: queries each company independently through the production RSS parser,
writes a JSON artifact, and does not commit or publish fetched articles.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from urllib.request import Request, urlopen
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import crawl_with_source_categories as base  # noqa: E402
from tools import crawl_with_wechat_registry as registry  # noqa: E402
from tools.google_news_url_resolver import resolve_google_news_url  # noqa: E402
from tools.prelisting_event_dedupe import cluster_candidates, extract_investors  # noqa: E402
from tools.prelisting_article_evidence import extract_article_evidence, is_safe_public_http_url  # noqa: E402

TARGETS = ("track-jq5v2n", "track-6l9y0y")
EVENTS = (
    "融资 OR 投资 OR 战略合作 OR 产品发布 OR 量产 OR 商业化 OR "
    "订单 OR IPO OR 上市辅导 OR 招股 OR 研发进展"
)


def install_adapters() -> None:
    crawler = base.tracking.crawler
    registry.core_official_adapters.install(crawler)
    registry.http_policy_bridge.install(crawler)
    registry.search_index_feed_redirects.install(crawler)
    registry.wechat_fetch_compat.install(registry.wechat_public_sources)
    registry.wechat_registry_bridge.install(registry.wechat_public_sources)
    registry.wechat_original_redirect_bridge.install(
        registry.wechat_public_sources, registry.wechat_registry_bridge
    )
    registry.wechat_index_context_guard.install(registry.wechat_registry_bridge)
    registry.wechat_index_record_fallback.install(
        registry.wechat_public_sources, registry.wechat_registry_bridge
    )
    registry.wechat_sogou_redirect_compat.install(registry.wechat_sogou_index)
    registry.wechat_sogou_link_compat.install(registry.wechat_sogou_index)
    registry.wechat_public_index_title_fallback.install(
        registry.wechat_registry_bridge, registry.wechat_sogou_index
    )
    registry.wechat_public_aggregator.install(registry.wechat_sogou_index)
    registry.wechat_sogou_bridge.install(registry.wechat_public_sources)
    registry.toutiao_public_feed.install(base.tracking)
    registry._install_professional_media()
    registry._install_source_governance()
    registry._install_snapshot_quality()
    base._install_strict_tracking_validation()
    base.tracking_taxonomy.install(base.tracking)
    base.x_rate_limit.install(crawler)
    base.wechat_public_sources.install(base.tracking)
    base.tracking._custom_sources = base._custom_sources
    base._install_generic_adapter()


def normalize(value: Any) -> str:
    import re
    import unicodedata
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s._:：\-—–/／|｜,，;；、&＆+＋()（）\[\]【】]+", "", text)


def article_text(row: dict[str, Any]) -> str:
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    return " ".join(str(x or "") for x in (
        row.get("title"), row.get("summary"), row.get("company"),
        row.get("sector"), source.get("name")
    ))


def classify_subject_role(title: str, company: str) -> str:
    """Conservative title-only role heuristic; never upgrades to verified entity."""
    import re
    title = str(title or "").strip()
    name = re.escape(str(company or "").strip())
    if not name or not title:
        return "unknown"
    # Target company is the recipient/investee in "A invests in B".
    if re.search(rf"(?:投资|入股|收购|并购|增资|战略投资).{{0,18}}{name}", title):
        return "investee"
    # Target company is the investor in "A invests in B".
    if re.search(rf"{name}.{{0,12}}(?:投资|入股|收购|并购|增资|战略投资)", title):
        return "investor"
    # The company is the grammatical subject raising capital.
    if re.search(rf"{name}.{{0,18}}(?:完成|获得|获|融资|募资|新一轮|Pre-[A-Z]|[A-F][轮＋+])", title, re.I):
        return "funding_subject"
    # The company is named as a collaborator/partner, not necessarily event owner.
    if re.search(rf"{name}.{{0,18}}(?:合作|联合|携手|签约|战略伙伴)", title):
        return "partner"
    if name in title:
        return "mentioned"
    return "unknown"


def classify_date_window(value: Any) -> str:
    from datetime import date
    import re
    raw = str(value or "").strip()
    match = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})?", raw)
    if not match:
        return "date_missing"
    try:
        event_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3) or 1))
    except ValueError:
        return "date_missing"
    age_days = (date.today() - event_date).days
    if age_days < 0:
        return "future_or_invalid"
    return "last_12_months" if age_days <= 365 else "historical"


def fetch_public_article(url: str) -> dict[str, Any]:
    if not is_safe_public_http_url(url):
        return {"fetchStatus": "skipped_unsafe_url"}
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; VCIQResearchAudit/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                return {"fetchStatus": "skipped_non_html", "contentType": content_type[:120]}
            payload = response.read(1_000_001)
            if len(payload) > 1_000_000:
                return {"fetchStatus": "skipped_too_large"}
            charset = response.headers.get_content_charset() or "utf-8"
            parsed = extract_article_evidence(payload.decode(charset, errors="replace"))
            parsed["fetchStatus"] = "fetched"
            parsed["contentType"] = content_type[:120]
            parsed["investorsExtractedFromBody"] = extract_investors(parsed.get("articleBody", ""))
            parsed["investorBodyExtractionMethod"] = parsed.get("bodyExtractionMethod")
            return parsed
    except Exception as exc:
        return {"fetchStatus": "fetch_error", "fetchError": f"{type(exc).__name__}: {exc}"[:200]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/prelisting-targeted-audit.json")
    args = parser.parse_args()

    tracking = base.tracking.load_tracking()
    tracks = {
        str(row.get("slug")): row for row in tracking.get("tracks", [])
        if isinstance(row, dict) and row.get("enabled", True) is not False
    }
    companies = []
    for slug in TARGETS:
        row = tracks.get(slug)
        if not row:
            raise SystemExit(f"missing target track {slug}")
        companies.extend((slug, row["name"], name) for name in row.get("sampleCompanies", []))
    if len(companies) != 42 or len({normalize(x[2]) for x in companies}) != 42:
        raise SystemExit("expected exactly 42 unique target companies")

    install_adapters()
    crawler = base.tracking.crawler
    base_config = crawler.load_config()
    merged, sec_specs, active_ids = base.tracking.build_merged_config(base_config, tracking)
    base.tracking._install_runtime_overrides(merged, sec_specs, active_ids)

    specs = []
    for slug, track_name, company in companies:
        query = f'("{company}") ({EVENTS})'
        specs.append({
            "id": f"prelisting-targeted-{slug}-{normalize(company)[:36]}",
            "name": f"{track_name} · {company} · 精准发现",
            "url": base.tracking_taxonomy._google_news_url(query, chinese=True),
            "adapter": "rss",
            "platform": "Google News 中文精准检索",
            "sourceLevel": "待交叉验证",
            "region": "中国",
            "sector": track_name,
            "company": company,
            "keywords": [company],
            "maxItems": 12,
            "strictTitleKeywords": False,
            "enabled": True,
        })

    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or crawler.DEFAULT_USER_AGENT
    articles, statuses, errors = crawler._crawl_config_group(specs, user_agent)
    status_map = {str(x.get("id")): x for x in statuses}

    # Resolve a bounded sample per company to publisher URLs. Keep the Google
    # wrapper URL regardless of resolution outcome; resolution is best-effort.
    resolved_cache = {}
    results = []
    for slug, track_name, company in companies:
        source_id = f"prelisting-targeted-{slug}-{normalize(company)[:36]}"
        status = status_map.get(source_id, {})
        key = normalize(company)
        matches = []
        for row in articles:
            title_key = normalize(row.get("title"))
            company_key = normalize(row.get("company"))
            # Avoid false positives caused by a company name appearing only in
            # a summary, sector label, or publisher name.
            if not key or (key not in title_key and key not in company_key):
                continue
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            wrapper_url = str(source.get("url") or "")
            resolution = resolved_cache.get(wrapper_url)
            should_resolve = len(matches) < 12
            if wrapper_url and resolution is None and should_resolve:
                try:
                    resolution = resolve_google_news_url(wrapper_url)
                except Exception as exc:  # resolver is best-effort and audited
                    resolution = {
                        "resolved": False,
                        "url": wrapper_url,
                        "method": "resolver-error",
                        "error": f"{type(exc).__name__}: {exc}"[:240],
                    }
                resolved_cache[wrapper_url] = resolution
            if resolution is None:
                resolution = {
                    "resolved": False,
                    "url": wrapper_url,
                    "method": "not-attempted-beyond-export-limit",
                }
            matches.append({
                "title": row.get("title"),
                "publishedAt": row.get("publishedAt"),
                "googleNewsUrl": wrapper_url,
                "publisherUrl": (resolution or {}).get("url", wrapper_url),
                "publisherUrlResolved": bool((resolution or {}).get("resolved")),
                "publisherDomain": (resolution or {}).get("publisherDomain"),
                "urlResolutionMethod": (resolution or {}).get("method", "not-attempted"),
                "platform": source.get("platform"),
                "sourceLevel": source.get("sourceLevel"),
                "entityMatchBasis": "title-or-company-field",
                "subjectRole": classify_subject_role(str(row.get("title") or ""), company),
                "dateWindow": classify_date_window(row.get("publishedAt")),
                "urlResolutionError": (resolution or {}).get("error"),
            })
        # Fetch at most two publisher pages per company. This is best-effort,
        # bounded, and read-only; RSS discovery remains successful if a publisher
        # blocks automated access.
        fetched_pages = 0
        for candidate in matches:
            publisher_url = candidate.get("publisherUrl") or ""
            if fetched_pages >= 2:
                candidate["articleEvidence"] = {"fetchStatus": "not_attempted_company_limit"}
                continue
            if candidate.get("publisherUrlResolved") and publisher_url:
                candidate["articleEvidence"] = fetch_public_article(publisher_url)
                fetched_pages += 1
                time.sleep(0.2)
            else:
                candidate["articleEvidence"] = {"fetchStatus": "not_attempted_unresolved_url"}

        results.append({
            "track": track_name,
            "slug": slug,
            "company": company,
            "routeStatus": status.get("status", "missing"),
            "scanned": int(status.get("scanned", 0) or 0),
            "accepted": int(status.get("accepted", 0) or 0),
            "error": status.get("error"),
            "candidateCount": len(matches),
            "exportedCandidateCount": min(len(matches), 12),
            "truncated": len(matches) > 12,
            "candidates": matches[:12],
        })

    event_candidates = []
    for company_row in results:
        for candidate in company_row["candidates"]:
            event_candidates.append({
                "company": company_row["company"],
                "title": candidate["title"],
                "publishedAt": candidate["publishedAt"],
                "publisherUrl": candidate["publisherUrl"],
                "googleNewsUrl": candidate["googleNewsUrl"],
                "publisherDomain": candidate["publisherDomain"],
                "publisherUrlResolved": candidate["publisherUrlResolved"],
                "subjectRole": candidate["subjectRole"],
                "eventType": {
                    "funding_subject": "financing",
                    "investor": "investment",
                    "investee": "investment_received",
                    "partner": "partnership",
                    "mentioned": "mention",
                }.get(candidate["subjectRole"], "unclassified"),
            })
    event_groups = cluster_candidates(event_candidates)

    report = {
        "schemaVersion": 1,
        "mode": "read-only-per-company-google-news-zh-discovery",
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "gitSha": os.environ.get("GITHUB_SHA", ""),
        "companyCount": len(results),
        "matchedCompanyCount": sum(x["candidateCount"] > 0 for x in results),
        "emptyCompanyCount": sum(x["candidateCount"] == 0 for x in results),
        "routeErrorCount": sum(x["routeStatus"] == "error" for x in results),
        "publisherUrlResolvedCount": sum(
            candidate["publisherUrlResolved"]
            for company in results for candidate in company["candidates"]
        ),
        "publisherUrlUnresolvedCount": sum(
            not candidate["publisherUrlResolved"]
            for company in results for candidate in company["candidates"]
        ),
        "truncatedCompanyCount": sum(x["truncated"] for x in results),
        "dateWindowCounts": {
            bucket: sum(
                candidate["dateWindow"] == bucket
                for company in results for candidate in company["candidates"]
            )
            for bucket in ("last_12_months", "historical", "date_missing", "future_or_invalid")
        },
        "subjectRoleCounts": {
            role: sum(
                candidate["subjectRole"] == role
                for company in results for candidate in company["candidates"]
            )
            for role in ("funding_subject", "investor", "investee", "partner", "mentioned", "unknown")
        },
        "entityMatchBasis": "title-or-company-field-only; subjectRole is heuristic, not verified entity resolution",
        "sourceErrors": errors,
        "companies": results,
        "eventCandidateCount": len(event_candidates),
        "eventEvidenceCount": sum(group["candidateCount"] for group in event_groups),
        "duplicateCandidateRowsRemoved": len(event_candidates) - sum(group["candidateCount"] for group in event_groups),
        "proposedEventGroupCount": len(event_groups),
        "eventGroups": event_groups,
        "eventGroupingPolicy": "conservative heuristic; DISCOVERED only; never official confirmation",
        "discoveryOnly": True,
        "officialDisclosureClaimed": False,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "companyCount": report["companyCount"],
        "matchedCompanyCount": report["matchedCompanyCount"],
        "emptyCompanyCount": report["emptyCompanyCount"],
        "routeErrorCount": report["routeErrorCount"],
        "articleCount": len(articles),
        "report": str(out),
    }, ensure_ascii=False))
    return 1 if errors or len(statuses) != 42 else 0


if __name__ == "__main__":
    raise SystemExit(main())
