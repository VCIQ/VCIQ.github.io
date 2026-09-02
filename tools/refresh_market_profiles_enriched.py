#!/usr/bin/env python3
"""Production entrypoint for enriched three-market company profiles."""

from __future__ import annotations

import math
import re
from typing import Any

try:
    from . import market_profile_enrichment as enrichment
    from . import market_quote_news_sources as quote_news
    from . import refresh_market_profiles as runner
except ImportError:
    import market_profile_enrichment as enrichment
    import market_quote_news_sources as quote_news
    import refresh_market_profiles as runner

_original_crawl_item = runner.crawl_item
_original_parse_tonghuashun = runner.market.parse_tonghuashun_html

_NAVIGATION_LABELS = (
    "所属地域",
    "所属地区",
    "经营分析",
    "财务分析",
    "公司资料",
    "公司概况",
    "主营业务",
    "营业收入构成",
    "总市值",
    "行情走势",
    "新闻公告",
)


def navigation_noise(value: object) -> bool:
    compact = re.sub(r"[\s，。；;:：|\-—_/]+", "", str(value or ""))
    if not compact:
        return True
    hits = sum(label in compact for label in _NAVIGATION_LABELS)
    if hits >= 2 and len(compact) < 80:
        return True
    if hits >= 1 and len(compact) < 18:
        return True
    return bool(re.fullmatch(r"(?:--?|暂无|待同步|亿|万|元|股)+", compact))


def parse_tonghuashun_html(raw_html, identity, configured_name):
    parsed = _original_parse_tonghuashun(raw_html, identity, configured_name)
    parser = runner.market.TextCollector()
    parser.feed(raw_html)
    text = parser.text()
    region = runner.robust_labeled_value(
        text,
        ["所属地域", "所属地区", "所在地区", "国家/地区", "注册地区"],
        40,
    )
    if region and not navigation_noise(region):
        parsed.setdefault("company", {})["region"] = region
    return parsed


def preserve_company_copy(profile, previous):
    company = profile.setdefault("company", {})
    previous_company = previous.get("company", {}) if isinstance(previous, dict) else {}
    for field in ("description", "mainBusiness", "industry"):
        value = company.get(field)
        if navigation_noise(value):
            previous_value = previous_company.get(field)
            if previous_value and not navigation_noise(previous_value):
                company[field] = previous_value
            else:
                company.pop(field, None)
    profile["company"] = company
    return profile


def valid_ohlc_point(point: object) -> bool:
    """Apply the same strict OHLC invariant enforced by the product validator."""

    if not isinstance(point, dict):
        return False
    try:
        open_ = float(point["open"])
        close = float(point["close"])
        high = float(point["high"])
        low = float(point["low"])
    except (KeyError, TypeError, ValueError):
        return False
    values = (open_, close, high, low)
    if not all(math.isfinite(value) and value >= 0 for value in values):
        return False
    return high >= max(values) and low <= min(values)


def filter_inconsistent_price_history(profile: dict[str, Any]) -> dict[str, Any]:
    """Drop malformed provider rows rather than fabricating corrected prices.

    Public daily endpoints can expose an incomplete current-session row whose
    close has advanced beyond the simultaneously returned high/low.  The
    committed snapshot must remain internally valid, so the row is rejected,
    the prior completed history is retained, and the profile is made partial
    with an explicit warning.  The downstream validator remains strict.
    """

    raw_points = profile.get("priceHistory")
    if not isinstance(raw_points, list):
        return profile
    accepted = [point for point in raw_points if valid_ohlc_point(point)]
    rejected = len(raw_points) - len(accepted)
    if rejected <= 0:
        return profile

    profile["priceHistory"] = runner.market.dedupe_price_points(accepted)
    warnings = profile.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    warning = (
        f"行情走势质量门：已过滤{rejected}条 OHLC 不一致或非数值日线；"
        "未改写任何价格字段"
    )
    if warning not in warnings:
        warnings.append(warning)
    profile["warnings"] = warnings[-8:]
    if profile.get("status") == "ok":
        profile["status"] = "partial"
    return profile


def crawl_item(item, previous):
    profile, status = _original_crawl_item(item, previous)
    profile = preserve_company_copy(profile, previous)
    profile = enrichment.enrich_profile(
        item["identity"],
        profile,
        runner.neutral_fetch_text,
    )
    profile = preserve_company_copy(profile, previous)
    profile = quote_news.enrich_quote_and_news(item["identity"], profile, previous)
    profile = filter_inconsistent_price_history(profile)
    status["status"] = profile.get("status", status.get("status", "partial"))
    status["pricePoints"] = len(profile.get("priceHistory", []))
    status["marketCapAccepted"] = any(
        metric.get("id") == "marketCap"
        for metric in profile.get("metrics", [])
        if isinstance(metric, dict)
    )
    status["quoteAccepted"] = isinstance(profile.get("quote"), dict) and bool(
        profile.get("quote", {}).get("price")
    )
    status["newsCount"] = len(profile.get("news") or [])
    return profile, status


def main() -> int:
    runner.market.parse_tonghuashun_html = parse_tonghuashun_html
    runner.crawl_item = crawl_item
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
