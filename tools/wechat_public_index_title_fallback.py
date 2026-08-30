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
    from . import wechat_sogou_link_compat
except ImportError:
    import wechat_sogou_link_compat

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
    if informative:
        combined: list[str] = []
        for piece in informative:
            candidate = " ".join([*combined, piece]).strip()
            if len(candidate) > 32:
                continue
            combined.append(piece)
        fragment = " ".join(combined).strip()
        if not fragment:
            fragment = max(informative, key=lambda value: len(_normalize_title(value)))[:32]
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
    if query_key:
        scores.append(difflib.SequenceMatcher(None, query_key, observed).ratio())
    for left, right in ((wanted, observed), (query_key, observed)):
        if not left or not right:
            continue
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        if len(shorter) >= 8 and shorter in longer:
            scores.append(min(0.98, 0.76 + 0.22 * len(shorter) / len(longer)))
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
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in ranked]


def _resolve_by_title(
    row: dict[str, str],
    spec: dict[str, Any],
    crawler: Any,
    index: Any,
) -> list[dict[str, str]]:
    title = _clean(row.get("title"), 260)
    if not title or len(_normalize_title(title)) < 8:
        return []
    if not _date_is_recent(row.get("date"), spec, crawler):
        return []

    # Treat the budget as two distinct title lookups, not two variants spent on
    # the first row.  Public indexes often publish faster than Sogou indexes;
    # giving a second discovered title one bounded chance is materially more
    # useful than retrying the newest title immediately with near-identical
    # terms.  The broad first variant has also been the stable exact-title route
    # on the public Sogou result page.
    variants = _query_variants(title)
    if not variants:
        return []
    title_key = _normalize_title(title)
    query = variants[0]
    query_key = _normalize_title(query)
    lookup_keys = spec.setdefault("_publicIndexTitleLookupKeys", [])
    lookup_query_keys = spec.setdefault("_publicIndexTitleLookupQueryKeys", [])
    if title_key in lookup_keys or query_key in lookup_query_keys:
        return []
    if not _source_budget(
        spec,
        "_publicIndexTitleSearchQueries",
        MAX_SEARCH_QUERIES_PER_SOURCE,
    ):
        return []
    lookup_keys.append(title_key)
    lookup_query_keys.append(query_key)
    spec.setdefault("_publicIndexTitleLookupTitles", []).append(title)
    try:
        search_url = index.build_search_url(spec, query=query)
        search_body = index._request(search_url)
        search_rows = index.parse_search_results(search_body, search_url)
    except Exception as exc:  # noqa: BLE001 - CAPTCHA/network errors stay terminal.
        _record_lookup_failure(spec, exc)
        return []

    # One redirect attempt per looked-up title keeps the two-title budget fair;
    # downstream original-page verification is authoritative for the selected
    # top-scoring candidate.
    for candidate in _ranked_rows(
        search_rows,
        title,
        query,
        spec,
        crawler,
    )[:1]:
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
            continue
        if not _is_direct_wechat(direct):
            continue
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
                "sogouDiscoveryTitle": _clean(candidate.get("title"), 260),
                "sogouDiscoveryDate": _clean(candidate.get("publishedAt"), 40),
            }
        ]
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
