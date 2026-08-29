"""Compatibility for Sogou WeChat's public result-link signature.

Sogou result pages expose ``/link?url=...`` entries plus a small client-side
``k``/``h`` calculation. This module reproduces that public-page calculation
before following the result. CAPTCHA pages remain terminal failures.

Search-result timestamps are not trusted as final publication dates. They are
used only as a conservative request-budget filter: rows that are *explicitly*
older than the configured freshness window do not consume a Sogou redirect
request. Missing or apparently recent timestamps still resolve normally and
must pass the original WeChat page's own date/account/content validation later.
"""

from __future__ import annotations

import random
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PAD_PATTERN = re.compile(
    r"href\.substr\(a\+(\d+)\+parseInt\(['\"](\d+)['\"]\)\+b,1\)",
    flags=re.IGNORECASE,
)


def guarded_result_url(
    result_url: str,
    search_body: str,
    *,
    nonce: int | None = None,
) -> str:
    """Append the public ``k`` and ``h`` values required by Sogou result links."""

    parts = urlsplit(str(result_url or ""))
    if not parts.path.startswith("/link") or "url=" not in parts.query:
        return result_url
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    if any(key == "k" for key, _value in query_pairs):
        return result_url
    pads = PAD_PATTERN.findall(search_body or "")
    pair = pads[0] if pads else ()
    marker_position = result_url.find("url=")
    value = int(nonce if nonce is not None else random.randint(1, 100))
    offset = marker_position + value + sum(int(item) for item in pair)
    if marker_position < 0 or offset < 0 or offset >= len(result_url):
        return result_url
    query_pairs.extend([("k", str(value)), ("h", result_url[offset])])
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), "")
    )


def _reported_row_may_be_fresh(row: dict[str, Any], spec: dict[str, Any]) -> bool:
    """Keep unknown/recent rows; prune only rows explicitly outside the window.

    The Sogou timestamp is discovery metadata rather than publication evidence.
    A false-recent value therefore still proceeds to the original WeChat page,
    where the canonical publication date is checked again. This function only
    prevents obviously old rows from spending redirect-resolution requests.
    """

    value = str(row.get("publishedAt") or "").strip()
    if not value:
        return True
    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            published = datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return True
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    max_age_days = max(1, int(spec.get("maxArticleAgeDays", 45) or 45))
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    return published >= cutoff


def install(index: Any) -> None:
    """Patch Sogou discovery while retaining its session and CAPTCHA circuit breaker."""

    current = index.discover
    if getattr(current, "_sogou_link_signature_compat", False):
        return

    def discover(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        search_url = index.build_search_url(spec)
        search_body = index._request(search_url)
        rows = index.parse_search_results(search_body, search_url)
        candidates = [row for row in rows if _reported_row_may_be_fresh(row, spec)]
        resolved = 0
        failures = 0
        for row in candidates:
            try:
                result_url = guarded_result_url(row["url"], search_body)
                body = index._request(
                    index._normalized_url(result_url),
                    referer=search_url,
                )
                direct = index.resolve_script_url(body)
            except Exception:
                direct = ""
                failures += 1
            if direct:
                row["directUrl"] = direct
                resolved += 1
        return rows, {
            "provider": "sogou-weixin",
            "query": index._query_term(spec),
            "scanned": len(rows),
            "eligibleForResolution": len(candidates),
            "stalePruned": len(rows) - len(candidates),
            "resolved": resolved,
            "failed": failures,
        }

    setattr(discover, "_sogou_link_signature_compat", True)
    index.discover = discover
