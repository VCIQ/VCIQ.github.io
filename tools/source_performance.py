"""Rolling source-performance metrics and publication deduplication accounting.

The public crawler already records whether a source succeeded and how many rows
it scanned/accepted. This module turns those per-run observations into bounded,
auditable rolling metrics without deleting a source automatically.

Metrics are deliberately separated:

* availabilityRate -- the source endpoint was reachable and parsable;
* productiveRate -- the run produced at least one accepted record;
* validYieldRate -- explicit qualified records divided by scanned candidates, falling back to accepted for legacy runs;
* duplicateRate -- current candidates removed by URL/fingerprint deduplication;
* dropRate -- unique current candidates omitted for non-duplicate reasons;
* averageDiscoveryLagDays -- calendar-day lag from publication to first sighting.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_PERFORMANCE_POLICY = {
    "performanceWindowRuns": 30,
    "performanceMinimumRuns": 5,
    "performanceMinimumScanned": 20,
    "minimumAvailabilityRate": 0.60,
    "minimumProductiveRate": 0.15,
    "minimumValidYieldRate": 0.08,
    "maximumDuplicateRate": 0.80,
    "maximumAverageDiscoveryLagDays": 7.0,
    "retirementMinimumRuns": 10,
    "retirementMaximumAvailabilityRate": 0.20,
    "retirementMaximumProductiveRate": 0.05,
}

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

REVIEW_REASON_LABELS = {
    "low-availability": "抓取成功率低于阈值",
    "low-productivity": "有效产出频率低于阈值",
    "low-valid-yield": "扫描候选转化率低于阈值",
    "high-duplicate-rate": "已接收候选重复率过高",
    "slow-discovery": "新记录发现延迟高于阈值",
    "quarantined": "来源处于发布隔离或恢复观察",
    "low-priority": "来源已因长期无有效产出降为低优先级",
    "manual-misattribution": "人工抽查误归属率超过阈值",
}


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


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
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/") or "/",
            query,
            "",
        )
    )


def _source_id(record: dict[str, Any]) -> str:
    return str(record.get("sourceId") or record.get("id") or "").strip()


def _title_fingerprint(article: dict[str, Any]) -> str:
    title = re.sub(
        r"[^\w\u4e00-\u9fff]+",
        "",
        str(article.get("title") or "").casefold(),
    )
    if not title:
        return ""
    company = str(article.get("companySlug") or article.get("company") or "")
    published_at = str(article.get("publishedAt") or "")
    return "|".join((company, published_at, title))


def _article_keys(article: dict[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    url = _normalized_url(source.get("url"))
    fingerprint = _title_fingerprint(article)
    if url:
        keys.append(f"url:{url}")
    if fingerprint:
        keys.append(f"fingerprint:{fingerprint}")
    article_id = str(article.get("id") or "").strip()
    if not keys and article_id:
        keys.append(f"id:{article_id}")
    return tuple(keys)


def _current_candidate_groups(
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in incoming:
        if not isinstance(article, dict):
            continue
        source_id = _source_id(article)
        if source_id:
            grouped[source_id].append(article)

    status_by_id = {
        _source_id(status): status
        for status in statuses
        if isinstance(status, dict) and _source_id(status)
    }
    selected: dict[str, list[dict[str, Any]]] = {}
    estimated_ids: set[str] = set()
    for source_id, group in grouped.items():
        status = status_by_id.get(source_id, {})
        if status.get("newAccepted") is None:
            selected[source_id] = group
            continue
        expected = _integer(status.get("newAccepted"))
        if expected <= 0:
            selected[source_id] = []
            continue

        verified_values = [
            str(article.get("lastVerifiedAt") or "")
            for article in group
            if str(article.get("lastVerifiedAt") or "")
        ]
        latest_verified = max(verified_values) if verified_values else ""
        current = [
            article
            for article in group
            if latest_verified
            and str(article.get("lastVerifiedAt") or "") == latest_verified
        ]
        if len(current) >= expected:
            selected[source_id] = current[:expected]
        else:
            # Legacy rows should already have observation metadata. If they do
            # not, use the bounded expected count and explicitly mark the metric
            # as estimated rather than treating all retained history as current.
            selected[source_id] = group[:expected]
            estimated_ids.add(source_id)
    return selected, estimated_ids


def annotate_publication_metrics(
    incoming: list[dict[str, Any]],
    published: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    *,
    withheld_source_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Annotate current-run candidate, publication and deduplication counts.

    Adaptive sources may carry bounded historical rows in ``incoming``. Their
    ``newAccepted`` count and current ``lastVerifiedAt`` values isolate the
    current crawl batch. A candidate is a duplicate only when it repeats a URL
    or crawler title fingerprint, or loses to the same identity from another
    source. Other unpublished candidates are recorded separately as dropped.
    """

    withheld_ids = {str(value) for value in withheld_source_ids if str(value)}
    current_groups, estimated_ids = _current_candidate_groups(incoming, statuses)

    published_by_source: dict[str, set[str]] = defaultdict(set)
    published_global: set[str] = set()
    for article in published:
        if not isinstance(article, dict):
            continue
        source_id = _source_id(article)
        keys = _article_keys(article)
        if source_id:
            published_by_source[source_id].update(keys)
        published_global.update(keys)

    for status in statuses:
        if not isinstance(status, dict):
            continue
        source_id = _source_id(status)
        if not source_id:
            continue
        candidates = current_groups.get(source_id, [])
        candidate_count = len(candidates)
        seen_keys: set[str] = set()
        unique_candidates: list[tuple[str, ...]] = []
        intrinsic_duplicates = 0
        for article in candidates:
            keys = _article_keys(article)
            if keys and any(key in seen_keys for key in keys):
                intrinsic_duplicates += 1
                continue
            unique_candidates.append(keys)
            seen_keys.update(keys)

        if source_id in withheld_ids:
            published_count = 0
            duplicate_count = 0
            dropped_count = 0
            withheld_count = candidate_count
        else:
            published_count = 0
            cross_source_duplicates = 0
            dropped_count = 0
            same_source_keys = published_by_source.get(source_id, set())
            for keys in unique_candidates:
                if keys and any(key in same_source_keys for key in keys):
                    published_count += 1
                elif keys and any(key in published_global for key in keys):
                    cross_source_duplicates += 1
                else:
                    dropped_count += 1
            duplicate_count = intrinsic_duplicates + cross_source_duplicates
            withheld_count = 0

        denominator = candidate_count - withheld_count
        status["candidateCount"] = candidate_count
        status["uniqueCandidateCount"] = len(unique_candidates)
        status["publishedCount"] = published_count
        status["duplicateCount"] = duplicate_count
        status["droppedCount"] = dropped_count
        status["withheldCount"] = withheld_count
        status["publicationRate"] = _ratio(published_count, denominator)
        status["duplicateRate"] = _ratio(duplicate_count, denominator)
        status["dropRate"] = _ratio(dropped_count, denominator)
        if source_id in estimated_ids:
            status["candidateMetricEstimated"] = True
        else:
            status.pop("candidateMetricEstimated", None)
    return statuses


def new_article_metrics(
    article_payload: dict[str, Any],
    *,
    previous_generated_at: Any,
    now: datetime,
) -> dict[str, dict[str, int]]:
    """Measure exact first sightings since the previous health snapshot."""

    lower_bound = _parse_time(previous_generated_at)
    current_time = now.astimezone(UTC)
    metrics: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "newArticleCount": 0,
            "discoveryLagDayTotal": 0,
            "discoveryLagSampleCount": 0,
        }
    )
    articles = article_payload.get("articles", [])
    if not isinstance(articles, list):
        return {}

    for article in articles:
        if not isinstance(article, dict) or article.get("firstSeenEstimated") is True:
            continue
        first_seen = _parse_time(article.get("firstSeenAt"))
        source_id = _source_id(article)
        if not first_seen or not source_id or first_seen > current_time:
            continue
        if lower_bound is not None and first_seen <= lower_bound:
            continue
        # With no previous state, avoid treating the whole current snapshot as a
        # new ingestion batch. Exact first sightings become measurable next run.
        if lower_bound is None:
            continue

        row = metrics[source_id]
        row["newArticleCount"] += 1
        published_date = _parse_date(article.get("publishedAt"))
        if published_date is not None:
            lag_days = max(0, (first_seen.date() - published_date).days)
            row["discoveryLagDayTotal"] += lag_days
            row["discoveryLagSampleCount"] += 1
    return dict(metrics)


def _run_sample(
    status: dict[str, Any],
    article_metric: dict[str, int] | None,
    *,
    timestamp: str,
) -> dict[str, Any] | None:
    state = str(status.get("status") or "unknown").casefold()
    if state == "disabled":
        return None
    attempted = state not in {"not-run", "skipped"}
    if not attempted:
        return None
    retained = bool(status.get("retainedPrevious"))
    successful = state in {"ok", "partial", "empty"} and not retained
    accepted = _integer(
        status.get("newAccepted")
        if status.get("newAccepted") is not None
        else status.get("accepted")
    )
    productive = accepted > 0 and state in {"ok", "partial"} and not retained
    article_metric = article_metric or {}
    sample = {
        "at": timestamp,
        "status": state,
        "successful": bool(successful),
        "productive": bool(productive),
        "scanned": _integer(status.get("scanned")),
        "accepted": accepted,
        "failed": _integer(status.get("failed")),
        "candidates": _integer(status.get("candidateCount")),
        "published": _integer(status.get("publishedCount")),
        "duplicates": _integer(status.get("duplicateCount")),
        "withheld": _integer(status.get("withheldCount")),
        "dropped": _integer(status.get("droppedCount")),
        "newArticles": _integer(article_metric.get("newArticleCount")),
        "lagDayTotal": _integer(article_metric.get("discoveryLagDayTotal")),
        "lagSamples": _integer(article_metric.get("discoveryLagSampleCount")),
    }
    if status.get("qualified") is not None:
        sample["qualified"] = _integer(status.get("qualified"))
    return sample


def _aggregate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "runs": len(samples),
        "successfulRuns": sum(bool(item.get("successful")) for item in samples),
        "productiveRuns": sum(bool(item.get("productive")) for item in samples),
        "scanned": sum(_integer(item.get("scanned")) for item in samples),
        "accepted": sum(_integer(item.get("accepted")) for item in samples),
        "failed": sum(_integer(item.get("failed")) for item in samples),
        "candidates": sum(_integer(item.get("candidates")) for item in samples),
        "published": sum(_integer(item.get("published")) for item in samples),
        "duplicates": sum(_integer(item.get("duplicates")) for item in samples),
        "withheld": sum(_integer(item.get("withheld")) for item in samples),
        "dropped": sum(_integer(item.get("dropped")) for item in samples),
        "newArticles": sum(_integer(item.get("newArticles")) for item in samples),
        "lagDayTotal": sum(_integer(item.get("lagDayTotal")) for item in samples),
        "lagSamples": sum(_integer(item.get("lagSamples")) for item in samples),
    }
    duplicate_denominator = totals["candidates"] - totals["withheld"]
    has_explicit_qualified = any("qualified" in item for item in samples)
    explicit_qualified_total = sum(
        _integer(item.get("qualified")) for item in samples if "qualified" in item
    )
    valid_yield_numerator = sum(
        _integer(item.get("qualified"))
        if "qualified" in item
        else _integer(item.get("accepted"))
        for item in samples
    )
    return {
        **totals,
        **({"qualified": explicit_qualified_total} if has_explicit_qualified else {}),
        "availabilityRate": _ratio(totals["successfulRuns"], totals["runs"]),
        "productiveRate": _ratio(totals["productiveRuns"], totals["runs"]),
        "validYieldRate": _ratio(valid_yield_numerator, totals["scanned"]),
        "publicationRate": _ratio(totals["published"], duplicate_denominator),
        "duplicateRate": _ratio(totals["duplicates"], duplicate_denominator),
        "dropRate": _ratio(totals["dropped"], duplicate_denominator),
        "averageDiscoveryLagDays": _ratio(
            totals["lagDayTotal"], totals["lagSamples"]
        ),
    }


def _threshold(policy: dict[str, Any], key: str) -> float:
    return _number(
        policy.get(key),
        float(DEFAULT_PERFORMANCE_POLICY[key]),
    )


def performance_recommendation(
    metrics: dict[str, Any],
    *,
    evidence_grade: str,
    collection_state: str,
    priority: str,
    manual_quality: dict[str, Any] | None,
    policy: dict[str, Any],
) -> tuple[str, list[str]]:
    minimum_runs = max(
        1,
        _integer(
            policy.get(
                "performanceMinimumRuns",
                DEFAULT_PERFORMANCE_POLICY["performanceMinimumRuns"],
            )
        ),
    )
    runs = _integer(metrics.get("runs"))
    reasons: list[str] = []
    if runs < minimum_runs:
        return "insufficient-data", reasons

    availability = metrics.get("availabilityRate")
    productive = metrics.get("productiveRate")
    valid_yield = metrics.get("validYieldRate")
    duplicate_rate = metrics.get("duplicateRate")
    discovery_lag = metrics.get("averageDiscoveryLagDays")

    if availability is not None and availability < _threshold(
        policy, "minimumAvailabilityRate"
    ):
        reasons.append("low-availability")
    if productive is not None and productive < _threshold(
        policy, "minimumProductiveRate"
    ):
        reasons.append("low-productivity")
    minimum_scanned = max(
        1,
        _integer(
            policy.get(
                "performanceMinimumScanned",
                DEFAULT_PERFORMANCE_POLICY["performanceMinimumScanned"],
            )
        ),
    )
    if (
        _integer(metrics.get("scanned")) >= minimum_scanned
        and valid_yield is not None
        and valid_yield < _threshold(policy, "minimumValidYieldRate")
    ):
        reasons.append("low-valid-yield")
    if (
        _integer(metrics.get("candidates")) >= 10
        and duplicate_rate is not None
        and duplicate_rate > _threshold(policy, "maximumDuplicateRate")
    ):
        reasons.append("high-duplicate-rate")
    if (
        _integer(metrics.get("lagSamples")) >= 3
        and discovery_lag is not None
        and discovery_lag > _threshold(policy, "maximumAverageDiscoveryLagDays")
    ):
        reasons.append("slow-discovery")
    if collection_state in {"quarantined", "probation"}:
        reasons.append("quarantined")
    if priority == "low":
        reasons.append("low-priority")

    manual_quality = manual_quality or {}
    manual_rate = manual_quality.get("misattributionRate")
    maximum_manual_rate = _number(policy.get("maximumMisattributionRate"), 0.05)
    if (
        _integer(manual_quality.get("reviewedRecords")) >= 20
        and manual_rate is not None
        and float(manual_rate) > maximum_manual_rate
    ):
        reasons.append("manual-misattribution")

    reasons = list(dict.fromkeys(reasons))
    if not reasons:
        return "retain", reasons
    if evidence_grade in {"A", "B"}:
        return "monitor", reasons

    retirement_minimum_runs = max(
        minimum_runs,
        _integer(
            policy.get(
                "retirementMinimumRuns",
                DEFAULT_PERFORMANCE_POLICY["retirementMinimumRuns"],
            )
        ),
    )
    retire = (
        runs >= retirement_minimum_runs
        and availability is not None
        and productive is not None
        and availability
        <= _threshold(policy, "retirementMaximumAvailabilityRate")
        and productive <= _threshold(policy, "retirementMaximumProductiveRate")
    ) or (
        runs >= retirement_minimum_runs
        and collection_state == "quarantined"
        and _integer(metrics.get("productiveRuns")) == 0
    )
    if retire:
        return "retire-candidate", reasons
    if len(reasons) >= 2 or collection_state in {"quarantined", "probation"}:
        return "downgrade-candidate", reasons
    return "monitor", reasons


def _observed_dates(
    previous: dict[str, Any],
    samples: list[dict[str, Any]],
) -> list[str]:
    """Persist cross-day lifecycle evidence independently from the run window.

    Existing snapshots are bootstrapped from the still-retained samples. Once
    ``observedDates`` exists, future runs keep extending that date set even as
    old performance samples roll out of ``performanceWindowRuns``.
    """

    observed: set[str] = set()
    persisted = previous.get("observedDates", [])
    if isinstance(persisted, list):
        for value in persisted:
            parsed = _parse_date(value)
            if parsed is not None:
                observed.add(parsed.isoformat())

    for item in samples:
        parsed = _parse_date(item.get("at"))
        if parsed is not None:
            observed.add(parsed.isoformat())
    return sorted(observed)


def update_source_performance(
    previous: dict[str, Any] | None,
    status: dict[str, Any],
    article_metric: dict[str, int] | None,
    *,
    evidence_grade: str,
    collection_state: str,
    priority: str,
    manual_quality: dict[str, Any] | None,
    policy: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    previous = previous if isinstance(previous, dict) else {}
    samples = previous.get("samples", [])
    samples = [item for item in samples if isinstance(item, dict)]
    timestamp = now.astimezone(UTC).replace(microsecond=0).isoformat()
    sample = _run_sample(status, article_metric, timestamp=timestamp)
    if sample is not None:
        samples.append(sample)

    observed_dates = _observed_dates(previous, samples)
    window_size = max(
        1,
        _integer(
            policy.get(
                "performanceWindowRuns",
                DEFAULT_PERFORMANCE_POLICY["performanceWindowRuns"],
            )
        ),
    )
    samples = samples[-window_size:]
    metrics = _aggregate(samples)
    state, reasons = performance_recommendation(
        metrics,
        evidence_grade=evidence_grade,
        collection_state=collection_state,
        priority=priority,
        manual_quality=manual_quality,
        policy=policy,
    )
    return {
        "windowRuns": window_size,
        "samples": samples,
        "observedDates": observed_dates,
        **metrics,
        "reviewState": state,
        "reviewRequired": state not in {"retain", "insufficient-data"},
        "reviewReasons": reasons,
        "reviewReasonLabels": [
            REVIEW_REASON_LABELS.get(reason, reason) for reason in reasons
        ],
        "manualQuality": manual_quality or {
            "reviewedRecords": 0,
            "misattributedRecords": 0,
            "confirmedDuplicateRecords": 0,
            "misattributionRate": None,
            "lastReviewedAt": None,
        },
    }