"""Read-only selected-company crawl receipt contract.

A zero process exit code and a passing global quality gate are insufficient
evidence that each selected company had a successful *new* crawl: the
underlying crawler can retain previous profiles or fall back when pages fail.
This gate must be applied to the per-company snapshot immediately after the
crawl step, before --mark-processed. It does not itself authenticate a CI
runner, source website, process exit code, or input provenance.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

MAX_RUN_DURATION = timedelta(minutes=90)
MAX_SELECTED = 10
MAX_PAGES = 10
MAX_RECEIPT_SECONDS = 3900
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}\Z")


class CrawlReceiptError(ValueError):
    """Fixed error code; no source URLs, user data or secrets in exceptions."""


def _time(value):
    if not isinstance(value, str) or len(value) > 64:
        raise CrawlReceiptError("CRAWL_RECEIPT_TIME_INVALID")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CrawlReceiptError("CRAWL_RECEIPT_TIME_INVALID") from None
    if timestamp.tzinfo is None:
        raise CrawlReceiptError("CRAWL_RECEIPT_TIME_INVALID")
    return timestamp.astimezone(UTC)


def stable_sha256(payload):
    """Stable, strict digest for separately captured status/profile JSON."""
    try:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        raise CrawlReceiptError("CRAWL_RECEIPT_JSON_INVALID") from None
    if len(raw) > 8 * 1024 * 1024:
        raise CrawlReceiptError("CRAWL_RECEIPT_JSON_TOO_LARGE")
    return hashlib.sha256(raw).hexdigest()


def _host(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise CrawlReceiptError("CRAWL_RECEIPT_SOURCE_INVALID")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise CrawlReceiptError("CRAWL_RECEIPT_SOURCE_INVALID")
    return parts.hostname.lower().removeprefix("www.")


def _matches_official(url, official_host):
    candidate_host = _host(url)
    return candidate_host == official_host or candidate_host.endswith("." + official_host)


def check_selected_crawl_receipts(
    selected_slugs,
    pinned_official_urls,
    crawl_snapshot,
    per_company_receipts,
    *,
    run_started_at,
    run_completed_at,
):
    """Validate immediate post-crawl evidence for every selected company.

    The caller must independently supply an immutable selection verified
    against a pinned article/catalog Git commit, and capture a receipt for
    each crawler process from the orchestration step. The receipts contain
    exitCode, capturedAt, statusSha256 and profileSha256. Hashes bind a
    capture to the snapshot but do not cryptographically attest its origin.
    This result never authorizes processing/merging/publishing by itself.
    """
    started = _time(run_started_at)
    ended = _time(run_completed_at)
    if ended < started or ended - started > MAX_RUN_DURATION:
        raise CrawlReceiptError("CRAWL_RECEIPT_RUN_WINDOW_INVALID")
    if (not isinstance(selected_slugs, list)
        or len(selected_slugs) > MAX_SELECTED
        or any(not isinstance(slug, str) or not SLUG.fullmatch(slug)
               for slug in selected_slugs)
        or len(selected_slugs) != len(set(selected_slugs))):
        raise CrawlReceiptError("CRAWL_RECEIPT_SELECTION_INVALID")
    if (not isinstance(pinned_official_urls, dict)
        or set(pinned_official_urls) != set(selected_slugs)
        or not isinstance(crawl_snapshot, dict)
        or not isinstance(crawl_snapshot.get("companies"), dict)
        or not isinstance(crawl_snapshot.get("sourceStatus"), list)
        or not isinstance(crawl_snapshot.get("qualityGate"), dict)
        or crawl_snapshot["qualityGate"].get("passed") is not True
        or not isinstance(per_company_receipts, list)
        or len(per_company_receipts) != len(selected_slugs)):
        raise CrawlReceiptError("CRAWL_RECEIPT_INPUT_INVALID")

    statuses = {}
    for row in crawl_snapshot["sourceStatus"]:
        if not isinstance(row, dict):
            raise CrawlReceiptError("CRAWL_RECEIPT_STATUS_INVALID")
        if row.get("kind") == "company" and row.get("slug") in selected_slugs:
            slug = row["slug"]
            if slug in statuses:
                raise CrawlReceiptError("CRAWL_RECEIPT_STATUS_DUPLICATE")
            statuses[slug] = row
    captures = {}
    for item in per_company_receipts:
        if not isinstance(item, dict) or set(item) != {
            "slug", "exitCode", "capturedAt", "statusSha256", "profileSha256",
        }:
            raise CrawlReceiptError("CRAWL_RECEIPT_CAPTURE_INVALID")
        slug = item["slug"]
        if not isinstance(slug, str) or slug not in selected_slugs or slug in captures:
            raise CrawlReceiptError("CRAWL_RECEIPT_CAPTURE_INVALID")
        if type(item["exitCode"]) is not int or item["exitCode"] != 0:
            raise CrawlReceiptError("CRAWL_RECEIPT_NONZERO_EXIT")
        if (not isinstance(item["statusSha256"], str)
            or not SHA256.fullmatch(item["statusSha256"])
            or not isinstance(item["profileSha256"], str)
            or not SHA256.fullmatch(item["profileSha256"])):
            raise CrawlReceiptError("CRAWL_RECEIPT_DIGEST_INVALID")
        timestamp = _time(item["capturedAt"])
        if not started <= timestamp <= ended:
            raise CrawlReceiptError("CRAWL_RECEIPT_CAPTURE_TIME_INVALID")
        captures[slug] = item
    if set(statuses) != set(selected_slugs) or set(captures) != set(selected_slugs):
        raise CrawlReceiptError("CRAWL_RECEIPT_MISSING_EVIDENCE")

    for slug in selected_slugs:
        status = statuses[slug]
        profile = crawl_snapshot["companies"].get(slug)
        capture = captures[slug]
        if not isinstance(profile, dict):
            raise CrawlReceiptError("CRAWL_RECEIPT_PROFILE_MISSING")
        if (stable_sha256(status) != capture["statusSha256"]
            or stable_sha256(profile) != capture["profileSha256"]):
            raise CrawlReceiptError("CRAWL_RECEIPT_DIGEST_MISMATCH")
        state = status.get("status")
        if (state not in ("ok", "partial")
            or profile.get("status") != state
            or profile.get("slug") != slug
            or status.get("slug") != slug
            or status.get("kind") != "company"
            or status.get("retainedPrevious") is not False
            or status.get("error")
            or profile.get("warnings")):
            raise CrawlReceiptError("CRAWL_RECEIPT_NOT_FRESH")
        pages = status.get("fetchedPages")
        sections = status.get("acceptedSections")
        elapsed = status.get("elapsedSeconds")
        if (type(pages) is not int or not 2 <= pages <= MAX_PAGES
            or type(sections) is not int
            or sections < (5 if state == "ok" else 4)
            or isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
            or not math.isfinite(elapsed) or not 0 <= elapsed <= MAX_RECEIPT_SECONDS):
            raise CrawlReceiptError("CRAWL_RECEIPT_INSUFFICIENT_CRAWL")
        updated = _time(profile.get("updatedAt"))
        if not started <= updated <= _time(capture["capturedAt"]):
            raise CrawlReceiptError("CRAWL_RECEIPT_PROFILE_TIME_INVALID")
        official_host = _host(pinned_official_urls[slug])
        sources = profile.get("sources")
        if not isinstance(sources, list):
            raise CrawlReceiptError("CRAWL_RECEIPT_SOURCE_INVALID")
        matched = set()
        for source in sources:
            if not isinstance(source, dict):
                raise CrawlReceiptError("CRAWL_RECEIPT_SOURCE_INVALID")
            url = source.get("url")
            if _matches_official(url, official_host):
                matched.add(url)
        if not matched:
            raise CrawlReceiptError("CRAWL_RECEIPT_OFFICIAL_SOURCE_MISSING")
        if state == "partial":
            score = profile.get("evidenceScore")
            if (type(score) not in (int, float) or not math.isfinite(score)
                or score < 70 or len(matched) < 2
                or not all(profile.get(k) for k in ("background", "technology", "products"))):
                raise CrawlReceiptError("CRAWL_RECEIPT_PARTIAL_TOO_WEAK")
    return {
        "ok": True,
        "verifiedCompanyCount": len(selected_slugs),
        "selectedSlugs": list(selected_slugs),
        "markProcessedAuthorized": False,
        "mergeAuthorized": False,
        "publicationAuthorized": False,
        "sourceFetchCryptographicallyAttested": False,
    }
