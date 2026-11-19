"""Offline, read-only historical WeChat article link repair queue validator.

Never writes articles.json, never promotes a temporary signed URL.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

try:
    from .wechat_link_policy import classify_wechat_article_url
except ImportError:  # python tools/wechat_historical_link_review.py
    from wechat_link_policy import classify_wechat_article_url

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/articles.json"
QUEUE = ROOT / "diagnostics/wechat-historical-link-repair-20261119.json"
PRIORITIES = {"P0", "P1", "P2"}


def historical_temporary_rows(snapshot: dict) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for item in snapshot.get("articles", []):
        if not isinstance(item, dict):
            continue
        src = item.get("source")
        if not isinstance(src, dict) or src.get("platform") != "微信":
            continue
        if classify_wechat_article_url(str(src.get("url", ""))) != "temporary":
            continue
        aid = item.get("id")
        if not isinstance(aid, str) or not aid:
            raise ValueError("historical WeChat article is missing a stable ID")
        if aid in rows:
            raise ValueError("duplicate historical article ID")
        rows[aid] = item
    return rows


def validate(snapshot: dict, queue: dict) -> dict:
    errors: list[str] = []
    baseline = queue.get("snapshot", {})
    review_rows = queue.get("articles", [])
    if queue.get("schemaVersion") != 1 or queue.get("mode") != "review-only":
        errors.append("not the review-only schema")
    if not isinstance(review_rows, list):
        raise ValueError("articles must be a list")
    if baseline.get("generatedAt") != snapshot.get("generatedAt"):
        errors.append("generatedAt mismatch: review snapshot drift")
    if baseline.get("articleCount") != len(snapshot.get("articles", [])):
        errors.append("article count mismatch: review snapshot drift")
    expected = historical_temporary_rows(snapshot)
    by_id: dict[str, dict] = {}
    for row in review_rows:
        if not isinstance(row, dict):
            errors.append("non-object review item")
            continue
        key = row.get("articleId")
        if key in by_id:
            errors.append("duplicate review ID")
        by_id[key] = row
    if set(by_id) != set(expected):
        errors.append("review IDs differ from the frozen snapshot")
    if len(review_rows) != baseline.get("temporaryWechatArticles"):
        errors.append("declared baseline count differs from review count")
    candidates = 0
    original_candidates = 0
    seen_original_urls: set[str] = set()
    for aid, row in by_id.items():
        if aid not in expected:
            continue
        original = expected[aid]
        for key, old_key in (("title", "title"), ("sourceId", "sourceId"),
                             ("wechatAccount", "wechatAccount"), ("publishedAt", "publishedAt")):
            if row.get(key) != original.get(old_key):
                errors.append(f"snapshot provenance mismatch: {aid}")
                break
        if (row.get("originalLinkStatus") != "temporary-signed" or
                row.get("reviewStatus") != "pending-original-verification" or
                row.get("reviewDecision") != "pending"):
            errors.append(f"incorrect review status: {aid}")
        if (row.get("verifiedOriginalWechatUrl") is not None
                or row.get("approvedReplacementUrl") is not None
                or row.get("appliedToProduction") is not False):
            errors.append(f"unapproved replacement: {aid}")
        if row.get("priority") not in PRIORITIES:
            errors.append(f"invalid priority: {aid}")
        wechat_candidates = row.get("originalWechatCandidates", [])
        if not isinstance(wechat_candidates, list) or len(wechat_candidates) > 3:
            errors.append(f"invalid original-candidate list: {aid}")
            wechat_candidates = []
        for candidate in wechat_candidates:
            original_candidates += 1
            if not isinstance(candidate, dict):
                errors.append(f"malformed original candidate: {aid}")
                continue
            candidate_url = str(candidate.get("url", "")).strip()
            if classify_wechat_article_url(candidate_url) != "durable":
                errors.append(f"invalid/temporary WeChat original candidate: {aid}")
            if candidate_url in seen_original_urls:
                errors.append(f"original candidate reused across articles: {aid}")
            seen_original_urls.add(candidate_url)
            if (candidate.get("accessStatus") != "not-verified"
                    or candidate.get("humanReviewStatus") != "pending"
                    or candidate.get("publisherIdentityConfirmedFromWeChat") is not False
                    or candidate.get("approvedForReplacement") is not False):
                errors.append(f"candidate prematurely treated as approved: {aid}")
            evidence = candidate.get("independentEvidenceUrls")
            hosts: set[str] = set()
            if not isinstance(evidence, list):
                errors.append(f"missing original-candidate provenance: {aid}")
                continue
            for eurl in evidence:
                try:
                    p = urlsplit(str(eurl))
                    if (p.scheme != "https" or not p.hostname or p.username
                            or p.password or p.hostname.casefold() == "mp.weixin.qq.com"):
                        errors.append(f"unsafe provenance URL: {aid}")
                    elif p.hostname:
                        hosts.add(p.hostname.casefold())
                except ValueError:
                    errors.append(f"malformed provenance URL: {aid}")
            if len(hosts) < 2:
                errors.append(f"needs two separately hosted references: {aid}")
        for candidate in row.get("alternativeCandidates", []):
            candidates += 1
            if not isinstance(candidate, dict):
                errors.append(f"invalid candidate: {aid}")
                continue
            url = str(candidate.get("url", ""))
            try:
                p = urlsplit(url)
                params = {key.casefold() for key, _ in parse_qsl(p.query)}
            except ValueError:
                errors.append(f"malformed candidate URL: {aid}")
                continue
            if (p.scheme != "https" or not p.hostname or p.username or p.password
                    or p.fragment or p.hostname.casefold() == "mp.weixin.qq.com"
                    or bool(params & {"signature", "timestamp"})):
                errors.append(f"unsafe candidate URL: {aid}")
            if (candidate.get("kind") != "non-wechat-alternative"
                    or candidate.get("reviewStatus") != "pending"
                    or candidate.get("verifiedAsOriginalWechat") is not False
                    or candidate.get("approvedForReplacement") is not False
                    or not candidate.get("publisher")
                    or not candidate.get("relationship")):
                errors.append(f"candidate incorrectly promoted: {aid}")
    safe_dump = json.dumps(queue, ensure_ascii=False)
    if "signature=" in safe_dump or "timestamp=" in safe_dump:
        errors.append("review queue contains a temporary signed query")
    return {
        "status": "ok" if not errors else "invalid",
        "trackedHistorical": len(expected),
        "reviewRows": len(review_rows),
        "alternativeCandidates": candidates,
        "originalWechatCandidates": original_candidates,
        "priorityCounts": dict(Counter(row.get("priority") for row in review_rows if isinstance(row, dict))),
        "verifiedOriginalWechat": 0,
        "appliedToProduction": 0,
        "errors": errors,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    p.add_argument("--queue", type=Path, default=QUEUE)
    p.add_argument("--expected-count", type=int, default=22)
    args = p.parse_args()
    report = validate(json.loads(args.snapshot.read_text(encoding="utf-8")),
                      json.loads(args.queue.read_text(encoding="utf-8")))
    if report["trackedHistorical"] != args.expected_count:
        report["status"] = "invalid"
        report["errors"].append("frozen historical scope has drifted")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
