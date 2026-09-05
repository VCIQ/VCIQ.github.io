"""Preserve first-seen and last-verified timestamps for intelligence records.

The crawler replaces successful source batches on every run. This module keeps
observation metadata stable across those replacements without changing event
publication dates:

* ``firstSeenAt`` records when the site first observed a stable article ID/URL;
* ``lastVerifiedAt`` records the latest crawl that returned that article;
* legacy rows receive a conservative snapshot-time upper bound and are marked
  estimated so they are never counted as newly discovered records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from .financing_details import validate_financing_details
except ImportError:
    from financing_details import validate_financing_details  # type: ignore

TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "spm",
}


def normalize_observation_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat()


def _normalized_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return text.casefold()
    if not parts.scheme or not parts.netloc:
        return text.casefold()
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_PARAMETERS
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path,
            query,
            "",
        )
    )


def _article_keys(article: dict[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    article_id = str(article.get("id", "")).strip()
    if article_id:
        keys.append(f"id:{article_id}")
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    source_url = _normalized_url(source.get("url"))
    if source_url:
        keys.append(f"url:{source_url}")
    return tuple(keys)


def _legacy_fallback(article: dict[str, Any], snapshot_generated_at: Any) -> str:
    snapshot = normalize_observation_timestamp(snapshot_generated_at)
    if snapshot:
        return snapshot
    published = str(article.get("publishedAt", "")).strip()
    if published:
        return normalize_observation_timestamp(f"{published}T00:00:00+00:00")
    return "1970-01-01T00:00:00+00:00"


def prepare_existing_articles(
    articles: list[dict[str, Any]],
    snapshot_generated_at: Any,
) -> list[dict[str, Any]]:
    """Backfill conservative observation metadata for existing snapshots."""

    prepared: list[dict[str, Any]] = []
    for raw in articles:
        article = dict(raw)
        fallback = _legacy_fallback(article, snapshot_generated_at)

        first_seen = normalize_observation_timestamp(article.get("firstSeenAt"))
        if not first_seen:
            article["firstSeenAt"] = fallback
            article["firstSeenEstimated"] = True
        else:
            article["firstSeenAt"] = first_seen
            article["firstSeenEstimated"] = bool(
                article.get("firstSeenEstimated", False)
            )

        last_verified = normalize_observation_timestamp(article.get("lastVerifiedAt"))
        if not last_verified:
            article["lastVerifiedAt"] = fallback
            article["lastVerifiedEstimated"] = True
        else:
            article["lastVerifiedAt"] = last_verified
            article["lastVerifiedEstimated"] = bool(
                article.get("lastVerifiedEstimated", False)
            )
        prepared.append(article)
    return prepared


def apply_incoming_observations(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    observed_at: Any,
) -> list[dict[str, Any]]:
    """Stamp incoming rows while preserving the earliest known observation."""

    observed = normalize_observation_timestamp(observed_at)
    if not observed:
        raise ValueError("observed_at must be an ISO-8601 timestamp")

    previous_by_key: dict[str, dict[str, Any]] = {}
    for article in existing:
        for key in _article_keys(article):
            previous_by_key.setdefault(key, article)

    stamped: list[dict[str, Any]] = []
    for raw in incoming:
        article = dict(raw)
        previous = next(
            (
                previous_by_key[key]
                for key in _article_keys(article)
                if key in previous_by_key
            ),
            None,
        )

        if previous:
            first_seen = normalize_observation_timestamp(previous.get("firstSeenAt"))
            article["firstSeenAt"] = first_seen or observed
            article["firstSeenEstimated"] = bool(
                previous.get("firstSeenEstimated", False)
            ) if first_seen else False
        else:
            article["firstSeenAt"] = observed
            article["firstSeenEstimated"] = False

        article["lastVerifiedAt"] = observed
        article["lastVerifiedEstimated"] = False
        stamped.append(article)
    return stamped


def validate_observation_metadata(article: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    first_seen = normalize_observation_timestamp(article.get("firstSeenAt"))
    last_verified = normalize_observation_timestamp(article.get("lastVerifiedAt"))
    if article.get("firstSeenAt") and not first_seen:
        errors.append("invalid:firstSeenAt")
    if article.get("lastVerifiedAt") and not last_verified:
        errors.append("invalid:lastVerifiedAt")
    if first_seen and last_verified and first_seen > last_verified:
        errors.append("invalid:observation-order")
    # Financing is optional, but if present it is part of the public article
    # metadata contract and must remain evidence-constrained in every validation
    # path, including standalone ``crawl_articles.py --validate-only`` calls.
    errors.extend(validate_financing_details(article))
    return errors
