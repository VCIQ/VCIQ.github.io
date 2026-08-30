"""Use Sogou discovery only when no account-scoped public index is configured.

Configured public indexes follow their own bounded route: detail resolver first,
then at most two title lookups.  Running broad Sogou discovery ahead of that
route used to spend up to ten redirect requests and could trip the shared CAPTCHA
circuit breaker before the bounded compatibility layer was reached.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

try:
    from . import wechat_sogou_index
    from . import wechat_source_registry
except ImportError:
    import wechat_sogou_index
    import wechat_source_registry


def _is_recent(value: Any, max_age_days: int, crawler: Any) -> bool:
    normalized = crawler.normalize_date(value)
    if not normalized:
        return True
    try:
        published = datetime.fromisoformat(normalized).date()
    except ValueError:
        return True
    return published >= datetime.now(UTC).date() - timedelta(days=max_age_days)


def _status(
    spec: dict[str, Any],
    status: str,
    scanned: int,
    accepted: int,
    failed: int,
    *,
    error: str | None = None,
    provider: str = "sogou-weixin",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": spec["id"],
        "name": spec["name"],
        "status": status,
        "scanned": scanned,
        "accepted": accepted,
        "failed": failed,
        "platform": "微信",
        "discoveryProvider": provider,
    }
    if error:
        result["error"] = error
    return result


def install(wechat: Any) -> None:
    original_crawl = wechat.crawl_wechat_source
    if getattr(original_crawl, "_wechat_sogou_primary", False):
        return

    def crawl_wechat_source(
        spec: dict[str, Any], user_agent: str, crawler: Any
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if spec.get("publicIndexUrls"):
            try:
                articles, original_status = original_crawl(
                    spec,
                    user_agent,
                    crawler,
                )
            except Exception as exc:  # noqa: BLE001 - retain branch diagnostics.
                articles = []
                original_status = _status(
                    spec,
                    "error",
                    0,
                    0,
                    1,
                    error=f"{type(exc).__name__}: {exc}",
                    provider="bing-or-public-index",
                )
            result = dict(original_status)
            result.setdefault("discoveryProvider", "bing-or-public-index")
            result["sogouPrimarySkipped"] = True
            result["publicIndexTitleQueries"] = int(
                spec.get("_publicIndexTitleSearchQueries", 0) or 0
            )
            result["publicIndexTitleRedirects"] = int(
                spec.get("_publicIndexTitleRedirectAttempts", 0) or 0
            )
            result["publicIndexTitleFailureKinds"] = list(
                spec.get("_publicIndexTitleFailureKinds", [])
            )
            if not articles:
                result["status"] = "error"
                result["accepted"] = 0
                result["failed"] = max(1, int(result.get("failed", 0) or 0))
                result["retainedPrevious"] = True
                result.setdefault(
                    "error",
                    "No current-run public-index article passed original-page "
                    "verification; previous snapshot retained",
                )
            return articles, result

        del user_agent
        accepted: list[dict[str, Any]] = []
        seen: set[str] = set()
        failures = 0
        meta: dict[str, Any] = {"scanned": 0, "resolved": 0, "failed": 0}
        sogou_error = ""
        max_items = int(spec.get("maxItems", 6))
        max_age_days = int(spec.get("maxArticleAgeDays", 45))

        try:
            rows, meta = wechat_sogou_index.discover(spec)
            failures += int(meta.get("failed", 0) or 0)
            provider = str(meta.get("provider") or "sogou-weixin")
            for row in rows:
                direct_url = str(row.get("directUrl") or "")
                if not direct_url or direct_url in seen:
                    continue
                observed_account = str(row.get("account") or "")
                if (
                    observed_account
                    and spec.get("expectedAccounts")
                    and not wechat_source_registry.account_matches(
                        spec, observed_account
                    )
                ):
                    continue
                if not _is_recent(
                    row.get("publishedAt"), max_age_days, crawler
                ):
                    continue
                try:
                    body = wechat.fetch_public_wechat_page(direct_url)
                    article = wechat.parse_wechat_article(
                        spec,
                        direct_url,
                        body,
                        crawler,
                        fallback_title=str(row.get("title") or ""),
                        fallback_summary=str(row.get("summary") or ""),
                        fallback_date=(
                            str(row.get("publishedAt"))
                            if row.get("publishedAt")
                            else None
                        ),
                    )
                except Exception:  # noqa: BLE001 - fallback chain handles failure.
                    failures += 1
                    continue
                if not article or not _is_recent(
                    article.get("publishedAt"), max_age_days, crawler
                ):
                    continue
                article["wechatDiscoveryProvider"] = provider
                accepted.append(article)
                seen.add(direct_url)
                if len(accepted) >= max_items:
                    break
        except Exception as exc:  # CAPTCHA/network errors are not bypassed.
            sogou_error = f"{type(exc).__name__}: {exc}"
            failures += 1

        if accepted:
            return accepted, _status(
                spec,
                "partial" if failures else "ok",
                int(meta.get("scanned", 0) or 0),
                len(accepted),
                failures,
                error=sogou_error or None,
                provider=str(meta.get("provider") or "sogou-weixin"),
            )

        # Existing Bing/public-index logic remains the conservative fallback.
        try:
            fallback_articles, fallback_status = original_crawl(
                spec, crawler.DEFAULT_USER_AGENT, crawler
            )
        except Exception as exc:  # noqa: BLE001 - return a retained snapshot status.
            fallback_articles = []
            fallback_status = _status(
                spec,
                "error",
                int(meta.get("scanned", 0) or 0),
                0,
                max(1, failures),
                error=f"Sogou: {sogou_error or 'no verified result'}; fallback: {type(exc).__name__}: {exc}",
                provider=str(meta.get("provider") or "sogou-weixin"),
            )

        if fallback_articles:
            result = dict(fallback_status)
            result["discoveryProvider"] = result.get(
                "discoveryProvider", "bing-or-public-index"
            )
            result["sogouScanned"] = int(meta.get("scanned", 0) or 0)
            result["sogouResolved"] = int(meta.get("resolved", 0) or 0)
            return fallback_articles, result

        result = dict(fallback_status)
        result["status"] = "error"
        result["failed"] = max(1, int(result.get("failed", 0) or 0), failures)
        result["retainedPrevious"] = True
        result["discoveryProvider"] = (
            f"{meta.get('provider', 'sogou-weixin')}+fallback"
        )
        result["sogouScanned"] = int(meta.get("scanned", 0) or 0)
        result["sogouResolved"] = int(meta.get("resolved", 0) or 0)
        result["error"] = (
            "No verified public WeChat article passed account and entity checks; "
            "previous snapshot retained"
        )
        return [], result

    setattr(crawl_wechat_source, "_wechat_sogou_primary", True)
    wechat.crawl_wechat_source = crawl_wechat_source
