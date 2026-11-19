"""Read-only, bounded WeChat RSS observation; emits JSON evidence to stdout.

No writes, article publication, production crawler invocation, or config changes.
Only approved source names from the staged intelligence source manifest are read.
Use --previous-ledger to preserve first-seen evidence across daily invocations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PILOT_CONFIG = ROOT / "config/wechat_rss_shadow_pilots.json"
PILOT_IDS = ("wechat-rss-qbitai", "wechat-rss-deepseek", "wechat-rss-kimi")
MAX_FEED_BYTES = 5_000_000
MAX_SNAPSHOT_BYTES = 7_000_000
MAX_FEED_ITEMS = 50


APPROVED_PUBLIC_HOSTS = frozenset({"wechat2rss.xlab.app", "wechat2rss.bestblogs.dev", "vciq.github.io"})


def fetch_public(url: str, max_bytes: int, timeout: int = 24) -> bytes:
    """Fetch one allowlisted HTTPS URL, rejecting *all* HTTP redirects.

    Rejecting redirects entirely is deliberately stricter than validating the
    final curl URL: the latter would permit a request to an unapproved host.
    """
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in APPROVED_PUBLIC_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("public HTTPS URL host/credentials/port not allowlisted")
    response = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location",
         "--max-redirs", "0", "--proto", "=https", "--proto-redir", "=https",
         "--compressed", "--max-time", str(timeout), "--max-filesize", str(max_bytes), url],
        capture_output=True, timeout=timeout + 4, check=False,
    )
    if response.returncode:
        raise RuntimeError(response.stderr.decode("utf-8", "replace")[-240:])
    if len(response.stdout) > max_bytes:
        raise ValueError("response exceeded size cap")
    return response.stdout


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", title.casefold())


def wechat_key(link: str) -> str | None:
    parsed = urlsplit(link)
    if parsed.scheme != "https" or parsed.hostname != "mp.weixin.qq.com":
        return None
    args = parse_qs(parsed.query)
    fields = [args.get(field, [""])[0] for field in ("__biz", "mid", "idx")]
    if not all(fields):
        return None
    return "|".join(fields)


def pub_date(text: str) -> date | None:
    try:
        return parsedate_to_datetime(text).astimezone(
            ZoneInfo("Asia/Shanghai")
        ).date()
    except (TypeError, ValueError, IndexError):
        return None


def feed_entries_with_stats(raw: bytes, *, max_items: int = MAX_FEED_ITEMS) -> tuple[str, list[dict], dict]:
    """Return name, valid unique RSS items and explicit raw/filtered counts.

    Only RSS 2.0 channel/item is supported; do not silently pretend to parse Atom.
    """
    if max_items < 1:
        raise ValueError("max_items must be positive")
    root = ET.fromstring(raw)
    if root.tag.lower() != "rss":
        raise ValueError("unsupported feed root: only RSS channel/item is supported")
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel missing")
    name = channel.findtext("title", "").strip()
    raw_nodes = channel.findall("item")
    rows: list[dict] = []
    seen: set[str] = set()
    invalid = 0
    repeated = 0
    for node in raw_nodes[:max_items]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        date_value = pub_date(node.findtext("pubDate") or "")
        key = wechat_key(link)
        if not title or not key or not date_value:
            invalid += 1
            continue
        if key in seen:
            repeated += 1
            continue
        seen.add(key)
        rows.append({"title": title[:220], "url": link, "wechatKey": key,
                     "publishedDate": date_value.isoformat()})
    stats = {"rawFeedItems": len(raw_nodes), "processedFeedItems": min(len(raw_nodes), max_items),
             "validParsedItems": len(rows), "invalidItems": invalid,
             "sameWeChatKeyItems": repeated, "truncatedItems": max(0, len(raw_nodes) - max_items)}
    return name, rows, stats


def feed_entries(raw: bytes, *, max_items: int = MAX_FEED_ITEMS) -> tuple[str, list[dict]]:
    """Backwards-compatible two-value view for existing callers/tests."""
    name, rows, _ = feed_entries_with_stats(raw, max_items=max_items)
    return name, rows


def _bigrams(title: str) -> set[str]:
    chars = normalized_title(title)
    return {chars[i:i + 2] for i in range(len(chars) - 1)}


def _mark_feed_review_candidates(rows: list[dict]) -> dict:
    """Pairwise *review leads*, never proven duplicate events or auto-deletes."""
    counts = {"sameWeChatKeyPairs": 0, "sameFeedExactTitlePairs": 0,
              "sameFeedNearTitlePairs": 0, "crossFeedExactTitlePairs": 0,
              "crossFeedNearTitlePairs": 0}
    for row in rows:
        row["feedReviewCandidates"] = []
    for i, left in enumerate(rows):
        left_date = date.fromisoformat(left["publishedDate"])
        left_title = normalized_title(left["title"])
        for right in rows[i + 1:]:
            right_date = date.fromisoformat(right["publishedDate"])
            same_feed = left["sourceId"] == right["sourceId"]
            if left["wechatKey"] == right["wechatKey"]:
                # This is the same article even if a feed republishes its URL
                # later; the three-day heuristic only applies to title matches.
                reason, score, count_field = "same-wechat-key", 1.0, "sameWeChatKeyPairs"
            else:
                if abs((left_date - right_date).days) > 3:
                    continue
                if left_title == normalized_title(right["title"]):
                    reason, score = "same-title", 1.0
                    count_field = "sameFeedExactTitlePairs" if same_feed else "crossFeedExactTitlePairs"
                else:
                    one, two = _bigrams(left["title"]), _bigrams(right["title"])
                    score = len(one & two) / len(one | two) if one and two else 0
                    if len(one) < 5 or len(two) < 5 or score < 0.48:
                        continue
                    reason = "similar-title"
                    count_field = "sameFeedNearTitlePairs" if same_feed else "crossFeedNearTitlePairs"
            counts[count_field] += 1
            for row, other in ((left, right), (right, left)):
                row["feedReviewCandidates"].append({
                    "id": other["id"], "sourceId": other["sourceId"],
                    "wechatKey": other["wechatKey"], "title": other["title"],
                    "reason": reason, "similarity": round(score, 3)})
    for row in rows:
        row["feedReviewCandidates"] = sorted(
            row["feedReviewCandidates"],
            key=lambda c: (-c["similarity"], c["id"]))[:5]
    counts["feedReviewRows"] = sum(bool(r["feedReviewCandidates"]) for r in rows)
    return counts


def _title_index(snapshot: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for item in snapshot.get("articles", []):
        key = normalized_title(str(item.get("title", "")))
        if key:
            result.setdefault(key, []).append(item)
    return result


def _event_candidates(title: str, published: date, articles: list[dict]) -> list[dict]:
    """Conservative review leads only, never automatic event equivalence."""
    chars = normalized_title(title)
    grams = {chars[i:i + 2] for i in range(len(chars) - 1)}
    if len(grams) < 5:
        return []
    matches: list[dict] = []
    for article in articles:
        try:
            other_date = date.fromisoformat(str(article.get("publishedAt", ""))[:10])
        except ValueError:
            continue
        if abs((published - other_date).days) > 3:
            continue
        value = normalized_title(str(article.get("title", "")))
        other = {value[i:i + 2] for i in range(len(value) - 1)}
        score = len(grams & other) / len(grams | other) if other else 0
        if score >= 0.48:
            matches.append({"sourceId": article.get("sourceId", ""),
                            "title": str(article.get("title", ""))[:220],
                            "similarity": round(score, 3)})
    return sorted(matches, key=lambda x: -x["similarity"])[:3]


def observe(
    specs: list[dict], feeds: dict[str, bytes], snapshot: dict,
    previous: dict | None, observed_at: datetime, window_days: int = 7,
    *, snapshot_status: str = "ok",
) -> dict:
    if window_days < 1 or window_days > 14:
        raise ValueError("window_days must be between 1 and 14")
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone aware")
    if snapshot_status not in ("ok", "fetch-error"):
        raise ValueError("snapshot_status must be ok or fetch-error")
    end = observed_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
    start = end - timedelta(days=window_days - 1)
    title_index = _title_index(snapshot) if snapshot_status == "ok" else {}
    existing = snapshot.get("articles", []) if snapshot_status == "ok" else []

    # Preserve first-seen records even if an entire source failed yesterday or
    # an article fell out of the rolling window. Migration from v1 rows is best
    # effort only; a legacy failed-day report cannot recover older entries.
    history = {}
    if previous is not None:
        for key, value in previous.get("seenHistory", {}).items():
            if isinstance(value, dict) and isinstance(value.get("firstSeenAt"), str):
                history[key] = {"firstSeenAt": value["firstSeenAt"],
                                "lastSeenAt": value.get("lastSeenAt", value["firstSeenAt"])}
        for r in previous.get("rows", []):
            if r.get("id") and r.get("firstSeenAt"):
                history.setdefault(r["id"], {"firstSeenAt": r["firstSeenAt"],
                                                  "lastSeenAt": r.get("lastSeenAt", r["firstSeenAt"])})

    result_rows: list[dict] = []
    per_source: list[dict] = []
    now = observed_at.isoformat()
    for spec in specs:
        source_id = spec["id"]
        if source_id not in feeds:
            per_source.append({"sourceId": source_id, "status": "fetch-error", "observed": 0})
            continue
        try:
            published_name, items, stats = feed_entries_with_stats(feeds[source_id])
            if published_name != spec["name"]:
                per_source.append({"sourceId": source_id, "status": "title-mismatch",
                                   "reportedTitle": published_name, "observed": 0, **stats})
                continue
            sampled = 0
            for item in items:
                d = date.fromisoformat(item["publishedDate"])
                if not start <= d <= end:
                    continue
                sampled += 1
                row_id = hashlib.sha256((source_id + "|" + item["wechatKey"]).encode()).hexdigest()[:20]
                exact = title_index.get(normalized_title(item["title"]), [])
                similar = [] if exact else _event_candidates(item["title"], d, existing)
                old = history.get(row_id)
                first_seen = old["firstSeenAt"] if old else now
                history[row_id] = {"firstSeenAt": first_seen, "lastSeenAt": now}
                result_rows.append({"id": row_id, "sourceId": source_id,
                                    "sourceName": spec["name"], **item,
                                    "firstSeenAt": first_seen,
                                    "lastSeenAt": now,
                                    "newSincePrevious": None if previous is None else old is None,
                                    "exactTitleSources": (sorted({e.get("sourceId", "") for e in exact})
                                                          if snapshot_status == "ok" else None),
                                    "possibleSameEvent": similar if snapshot_status == "ok" else None,
                                    "status": "manual-review", "published": False})
            per_source.append({"sourceId": source_id, "status": "ok",
                               "feedItems": len(items), "windowItems": sampled, **stats})
        except (ET.ParseError, ValueError) as exc:
            per_source.append({"sourceId": source_id, "status": "parse-error",
                               "error": str(exc)[:120], "observed": 0})
    candidate_counts = _mark_feed_review_candidates(result_rows)
    report = {"schemaVersion": 2, "mode": "read-only-shadow", "asOf": now,
              "windowStart": start.isoformat(), "windowEnd": end.isoformat(),
              "snapshotStatus": snapshot_status,
              "snapshotGeneratedAt": snapshot.get("generatedAt", "") if snapshot_status == "ok" else None,
              "snapshotArticles": len(existing) if snapshot_status == "ok" else None,
              "previousLedgerProvided": previous is not None,
              "historyEntries": len(history),
              "seenHistory": dict(sorted(history.items())),
              "sources": per_source,
              "rows": sorted(result_rows, key=lambda r: (r["sourceId"], r["publishedDate"], r["id"])),
              "summary": {"observed": len(result_rows),
                          "exactTitle": (sum(bool(r["exactTitleSources"]) for r in result_rows)
                                         if snapshot_status == "ok" else None),
                          "possibleSameEvent": (sum(bool(r["possibleSameEvent"]) for r in result_rows)
                                                if snapshot_status == "ok" else None),
                          "needsManualReview": len(result_rows),
                          "newSincePrevious": (sum(r["newSincePrevious"] for r in result_rows)
                                               if previous is not None else None),
                          **candidate_counts},
              "limitations": ["A feed response is not proof of complete publication history",
                              "No event-level matches are automatically approved",
                              "If previousLedgerProvided=false, firstSeenAt is only a new observation baseline",
                              "No production publication or state change"]}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PILOT_CONFIG)
    parser.add_argument("--snapshot", type=Path, help="read local snapshot instead of network")
    parser.add_argument("--previous-ledger", type=Path, help="previous JSON report, including seenHistory")
    parser.add_argument("--as-of", help="ISO datetime, defaults to current UTC")
    parser.add_argument("--window-days", type=int, default=7)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    candidates = {s["id"]: s for s in config.get("feeds", [])}
    if any(s not in candidates for s in PILOT_IDS):
        parser.error("pilot RSS sources missing from explicit shadow-only config")
    specs = [candidates[source_id] for source_id in PILOT_IDS]
    if any(s.get("enabled") is not False or s.get("allowedHosts") != ["mp.weixin.qq.com"] for s in specs):
        parser.error("pilot feeds must be explicitly disabled and WeChat-link restricted")
    approved_feed_hosts = {"wechat2rss.xlab.app", "wechat2rss.bestblogs.dev"}
    if any(urlsplit(spec["url"]).hostname not in approved_feed_hosts for spec in specs):
        parser.error("pilot feed transport host is not approved")
    previous = json.loads(args.previous_ledger.read_text(encoding="utf-8")) if args.previous_ledger else None
    observed_at = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else datetime.now(UTC)
    if observed_at.tzinfo is None:
        parser.error("--as-of must contain a timezone")
    snapshot_status = "ok"
    snapshot_error = None
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else json.loads(
            fetch_public("https://vciq.github.io/data/articles.json", MAX_SNAPSHOT_BYTES)
        )
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("articles"), list):
            raise ValueError("snapshot must be an object with an articles list")
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        snapshot_status, snapshot_error = "fetch-error", str(exc)[:160]
        snapshot = {"articles": []}
    feeds: dict[str, bytes] = {}
    fetch_errors: dict[str, str] = {}
    for spec in specs:
        try:
            feeds[spec["id"]] = fetch_public(spec["url"], MAX_FEED_BYTES)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            fetch_errors[spec["id"]] = str(exc)[:160]
    report = observe(specs, feeds, snapshot, previous, observed_at, args.window_days,
                     snapshot_status=snapshot_status)
    if snapshot_error:
        report["snapshotError"] = snapshot_error
    for spec in report["sources"]:
        if spec["sourceId"] in fetch_errors:
            spec["error"] = fetch_errors[spec["sourceId"]]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if snapshot_status == "ok" and all(s["status"] == "ok" for s in report["sources"]) else 2


if __name__ == "__main__":
    sys.exit(main())
