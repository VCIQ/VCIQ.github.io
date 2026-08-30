"""Resolve public-index article titles through bounded Sogou reverse lookup.

Public indexes remain discovery-only hints. This fallback returns only a direct
``mp.weixin.qq.com`` candidate. The existing registry/original-page pipeline
still verifies the public-account identity, original publication date, and
entity relevance before an article can be published.
"""

from __future__ import annotations

import difflib
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

try:
    from . import wechat_sogou_link_compat, wechat_source_registry
except ImportError:
    import wechat_sogou_link_compat
    import wechat_source_registry

MAX_QUERY_LENGTH = 38
MAX_SEARCH_QUERIES_PER_SOURCE = 2
MAX_REDIRECT_ATTEMPTS_PER_SOURCE = 2
MIN_TITLE_SCORE = 0.62
_GENERIC_SEGMENTS = {
    "独家",
    "重磅",
    "快讯",
    "最新",
    "观察",
    "市场观察",
    "行业观察",
    "盘点",
    "关注",
    "突发",
    "原创",
}
_SPLIT_PATTERN = re.compile(r"[|｜丨:：;；,，。.!！?？【】\[\]()（）/、“”\"'‘’]+")


def _clean(value: Any, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _normalize_title(value: Any) -> str:
    return re.sub(
        r"[^0-9a-z\u3400-\u9fff]+",
        "",
        _clean(value, 500).casefold(),
        flags=re.IGNORECASE,
    )


def _query_variants(title: str) -> list[str]:
    """Return at most two bounded queries: broad title then unique fragments."""

    cleaned = _clean(_SPLIT_PATTERN.sub(" ", title), 500)
    result: list[str] = []
    if cleaned:
        result.append(cleaned[:MAX_QUERY_LENGTH].strip())

    pieces = [
        _clean(piece, 80)
        for piece in _SPLIT_PATTERN.split(title)
        if _clean(piece, 80)
    ]
    informative = [
        piece
        for piece in pieces
        if piece.casefold() not in _GENERIC_SEGMENTS
        and len(_normalize_title(piece)) >= 4
    ]
    distinctive_tokens = re.findall(
        r"[A-Za-z][A-Za-z0-9.-]{1,}|\d{2,}",
        title,
    )
    token_fragment = " ".join(distinctive_tokens[:5])
    # Preserve a short publisher/entity phrase when an acronym-heavy title
    # would otherwise degrade into a broad query such as ``60 DDR5 RCD``.
    # This still keeps the compact acronym-only form for WAIC-style headlines.
    lead = informative[0] if informative else ""
    companion = (
        max(informative[1:], key=lambda value: len(_normalize_title(value)))
        if len(informative) > 1
        else ""
    )
    if (
        lead
        and companion
        and 4 <= len(_normalize_title(lead)) <= 12
        and re.search(r"[\u3400-\u9fff]", lead)
    ):
        result.append(f"{lead} {companion}"[:32].strip())
    elif len(distinctive_tokens) >= 2 and token_fragment:
        result.append(token_fragment[:24].strip())

    if informative:
        fragment = max(
            informative,
            key=lambda value: len(_normalize_title(value)),
        )[:32]
        if result and _normalize_title(fragment) == _normalize_title(result[0]):
            fragment = max(
                informative,
                key=lambda value: len(_normalize_title(value)),
            )[:32]
        if fragment and fragment not in result:
            result.append(fragment)

    deduped: list[str] = []
    seen: set[str] = set()
    for query in result:
        query = _clean(query, MAX_QUERY_LENGTH)
        key = _normalize_title(query)
        if not query or not key or key in seen:
            continue
        seen.add(key)
        deduped.append(query)
        if len(deduped) >= 2:
            break
    return deduped


def _title_score(expected: str, candidate: str, query: str = "") -> float:
    wanted = _normalize_title(expected)
    observed = _normalize_title(candidate)
    query_key = _normalize_title(query)
    if not wanted or not observed:
        return 0.0
    if wanted == observed:
        return 1.0

    scores = [difflib.SequenceMatcher(None, wanted, observed).ratio()]
    if len(query_key) >= 8:
        scores.append(difflib.SequenceMatcher(None, query_key, observed).ratio())
    for left, right in ((wanted, observed), (query_key, observed)):
        if not left or not right:
            continue
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        if len(shorter) >= 8 and shorter in longer:
            scores.append(min(0.98, 0.76 + 0.22 * len(shorter) / len(longer)))
        match = difflib.SequenceMatcher(None, left, right).find_longest_match()
        if match.size >= 10:
            scores.append(
                min(0.96, 0.58 + 0.38 * match.size / min(len(left), len(right)))
            )
    return max(scores)


def _is_direct_wechat(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    path = parts.path.rstrip("/")
    return (
        parts.scheme.casefold() == "https"
        and (parts.hostname or "").casefold() == "mp.weixin.qq.com"
        and (path == "/s" or path.startswith("/s/"))
    )


def _date_is_recent(value: Any, spec: dict[str, Any], crawler: Any) -> bool:
    normalized = crawler.normalize_date(value)
    if not normalized:
        return True
    try:
        published = datetime.fromisoformat(normalized).date()
    except ValueError:
        return True
    max_age_days = max(1, int(spec.get("maxArticleAgeDays", 45)))
    return published >= datetime.now(UTC).date() - timedelta(days=max_age_days)


def _sogou_row_may_be_fresh(row: dict[str, Any], spec: dict[str, Any]) -> bool:
    """Reuse the link adapter's conservative request-budget guard when present."""

    guard = getattr(wechat_sogou_link_compat, "_reported_row_may_be_fresh", None)
    if guard is None:
        return True
    return bool(guard(row, spec))


def _source_budget(spec: dict[str, Any], key: str, limit: int) -> bool:
    """Consume a per-generated-spec budget without persisting cross-run state."""

    current = int(spec.get(key, 0) or 0)
    if current >= limit:
        return False
    spec[key] = current + 1
    return True


def _record_lookup_failure(spec: dict[str, Any], exc: Exception) -> None:
    message = str(exc).casefold()
    if "cooldown" in message:
        kind = "sogou-circuit-open"
    elif "anti-spider" in message or "captcha" in message:
        kind = "sogou-captcha"
    else:
        kind = type(exc).__name__
    failures = spec.setdefault("_publicIndexTitleFailureKinds", [])
    if kind not in failures:
        failures.append(kind)


def _ranked_rows(
    rows: list[dict[str, Any]],
    expected_title: str,
    query: str,
    spec: dict[str, Any],
    crawler: Any,
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        if not _sogou_row_may_be_fresh(row, spec):
            continue
        if not _date_is_recent(row.get("publishedAt"), spec, crawler):
            continue
        score = _title_score(expected_title, str(row.get("title") or ""), query)
        if score < MIN_TITLE_SCORE:
            continue
        # A copied or syndicated headline can rank ahead of the configured
        # publisher even when both titles are identical.  Sogou already exposes
        # the public-account name, so reject an explicit mismatch before
        # spending the redirect budget.  Empty account fields remain eligible
        # because the original mp.weixin page is still the acceptance authority.
        observed_account = _clean(row.get("account"), 100)
        if (
            spec.get("expectedAccounts")
            and observed_account
            and not wechat_source_registry.account_matches(spec, observed_account)
        ):
            spec["_publicIndexTitleAccountMismatches"] = int(
                spec.get("_publicIndexTitleAccountMismatches", 0) or 0
            ) + 1
            continue
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in ranked]


def _resolve_by_title(
    row: dict[str, str],
    spec: dict[str, Any],
    crawler: Any,
    index: Any,
) -> list[dict[str, str]]:
    if spec.get("_publicIndexTitleDirectResolved"):
        return []
    title = _clean(row.get("title"), 260)
    if not title or len(_normalize_title(title)) < 8:
        return []
    if not _date_is_recent(row.get("date"), spec, crawler):
        return []

    variants = _query_variants(title)
    if not variants:
        return []
    prefer_short = spec.pop("_publicIndexPreferShortTitleQuery", False)
    query = variants[-1] if prefer_short and len(variants) > 1 else variants[0]
    title_key = _normalize_title(title)
    lookup_keys = spec.setdefault("_publicIndexTitleLookupKeys", [])
    lookup_query_keys = spec.setdefault("_publicIndexTitleLookupQueryKeys", [])
    if title_key in lookup_keys:
        return []
    if int(spec.get("_publicIndexTitleSearchQueries", 0) or 0) >= (
        MAX_SEARCH_QUERIES_PER_SOURCE
    ):
        return []
    lookup_keys.append(title_key)
    spec.setdefault("_publicIndexTitleLookupTitles", []).append(title)

    # Spend at most one query per discovered title: the first title receives a
    # bounded exact query, and after a miss the next distinct title receives its
    # short fragment. This preserves recency diversity while keeping the total
    # source budget at two searches and one redirect candidate per search.
    for query in [query]:
        query_key = _normalize_title(query)
        if not query_key or query_key in lookup_query_keys:
            continue
        if not _source_budget(
            spec,
            "_publicIndexTitleSearchQueries",
            MAX_SEARCH_QUERIES_PER_SOURCE,
        ):
            break
        lookup_query_keys.append(query_key)
        try:
            search_url = index.build_search_url(spec, query=query)
            search_body = index._request(search_url)
            search_rows = index.parse_search_results(search_body, search_url)
        except Exception as exc:  # noqa: BLE001 - CAPTCHA/network errors stay terminal.
            _record_lookup_failure(spec, exc)
            spec["_publicIndexPreferShortTitleQuery"] = True
            return []

        ranked_rows = _ranked_rows(
            search_rows,
            title,
            query,
            spec,
            crawler,
        )
        if not ranked_rows:
            matching_rows = [
                candidate
                for candidate in search_rows
                if _title_score(title, str(candidate.get("title") or ""), query)
                >= MIN_TITLE_SCORE
            ]
            if matching_rows and not any(
                _sogou_row_may_be_fresh(candidate, spec)
                and _date_is_recent(candidate.get("publishedAt"), spec, crawler)
                for candidate in matching_rows
            ):
                # The public index can retain an old headline after Sogou's
                # original timestamp has aged out. Preserve the remaining query
                # for the next discovered title and prefer that title's short,
                # distinctive fragment instead of retrying this stale one.
                spec["_publicIndexPreferShortTitleQuery"] = True
                return []
            spec["_publicIndexPreferShortTitleQuery"] = True
            return []

        for rank, candidate in enumerate(ranked_rows[:1], 1):
            if not _source_budget(
                spec,
                "_publicIndexTitleRedirectAttempts",
                MAX_REDIRECT_ATTEMPTS_PER_SOURCE,
            ):
                return []
            try:
                result_url = wechat_sogou_link_compat.guarded_result_url(
                    str(candidate.get("url") or ""),
                    search_body,
                )
                jump_body = index._request(
                    index._normalized_url(result_url),
                    referer=search_url,
                )
                direct = index.resolve_script_url(jump_body)
            except Exception as exc:  # noqa: BLE001 - never bypass Sogou/WeChat guards.
                _record_lookup_failure(spec, exc)
                spec["_publicIndexPreferShortTitleQuery"] = True
                return []
            if not _is_direct_wechat(direct):
                spec["_publicIndexPreferShortTitleQuery"] = True
                return []
            account = _clean(candidate.get("account"), 100)
            if account:
                accounts = spec.setdefault("_publicIndexTitleCandidateAccounts", [])
                if account not in accounts and len(accounts) < 4:
                    accounts.append(account)
            spec["_publicIndexTitleDirectResolved"] = True
            return [
                {
                    **row,
                    "url": direct,
                    "kind": "wechat",
                    # Never use public-index or Sogou dates as final evidence.
                    # The downstream original-page parser must recover the date
                    # directly from mp.weixin.qq.com.
                    "date": "",
                    "discoveryUrl": str(row.get("url") or ""),
                    "titleLookupQuery": query,
                    "titleLookupRank": str(rank),
                    "sogouDiscoveryTitle": _clean(candidate.get("title"), 260),
                    "sogouDiscoveryDate": _clean(candidate.get("publishedAt"), 40),
                    "sogouDiscoveryAccount": account,
                }
            ]
        spec["_publicIndexPreferShortTitleQuery"] = True
        return []
    return []


def install(bridge: Any, index: Any) -> None:
    """Try the public-index detail first, then use bounded title lookup."""

    original = bridge._resolve_detail_row
    if getattr(original, "_wechat_public_index_title_fallback", False):
        return

    def resolve_detail_row(
        row: dict[str, str],
        spec: dict[str, Any],
        user_agent: str,
        crawler: Any,
    ) -> list[dict[str, str]]:
        if row.get("kind") == "title":
            return _resolve_by_title(row, spec, crawler, index)

        # A public index remains a discovery surface. Preserve its direct-detail
        # resolver as the primary path and invoke Sogou only after that path has
        # actually failed for a detail row.
        resolved = original(row, spec, user_agent, crawler)
        if resolved or row.get("kind") != "detail":
            return resolved

        # The source-local counter inside _resolve_by_title caps all title
        # searches across all detail rows at MAX_SEARCH_QUERIES_PER_SOURCE.
        return _resolve_by_title(row, spec, crawler, index)

    setattr(resolve_detail_row, "_wechat_public_index_title_fallback", True)
    bridge._resolve_detail_row = resolve_detail_row
