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


def fetch_public(url: str, max_bytes: int, timeout: int = 24) -> bytes:
    """Use system-CA-verified curl: no cookies, redirects restricted to HTTPS."""
    if urlsplit(url).scheme != "https":
        raise ValueError("HTTPS-only transport")
    response = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location",
         "--proto", "=https", "--proto-redir", "=https", "--compressed",
         "--max-time", str(timeout), "--max-filesize", str(max_bytes), url],
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


def feed_entries(raw: bytes, *, max_items: int = MAX_FEED_ITEMS) -> tuple[str, list[dict]]:
    root = ET.fromstring(raw)
    if root.tag.lower() not in ("rss", "{http://www.w3.org/2005/Atom}feed"):
        raise ValueError("unexpected RSS/Atom root")
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel missing")
    name = channel.findtext("title", "").strip()
    rows: list[dict] = []
    seen: set[str] = set()
    for node in channel.findall("item")[:max_items]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        date_value = pub_date(node.findtext("pubDate") or "")
        key = wechat_key(link)
        if not title or not key or not date_value or key in seen:
            continue
        seen.add(key)
        rows.append({"title": title[:220], "url": link, "wechatKey": key,
                     "publishedDate": date_value.isoformat()})
    return name, rows


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
) -> dict:
    if window_days < 1 or window_days > 14:
        raise ValueError("window_days must be between 1 and 14")
    end = observed_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
    start = end - timedelta(days=window_days - 1)
    title_index = _title_index(snapshot)
    existing = snapshot.get("articles", [])
    previous_rows = {r.get("id"): r for r in (previous or {}).get("rows", [])}
    result_rows: list[dict] = []
    per_source = []
    for spec in specs:
        source_id = spec["id"]
        if source_id not in feeds:
            per_source.append({"sourceId": source_id, "status": "fetch-error", "observed": 0})
            continue
        try:
            published_name, items = feed_entries(feeds[source_id])
            if published_name != spec["name"]:
                per_source.append({"sourceId": source_id, "status": "title-mismatch",
                                   "reportedTitle": published_name, "observed": 0})
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
                old = previous_rows.get(row_id, {})
                result_rows.append({"id": row_id, "sourceId": source_id,
                                    "sourceName": spec["name"], **item,
                                    "firstSeenAt": old.get("firstSeenAt", observed_at.isoformat()),
                                    "lastSeenAt": observed_at.isoformat(),
                                    "exactTitleSources": sorted({e.get("sourceId", "") for e in exact}),
                                    "possibleSameEvent": similar,
                                    "status": "manual-review", "published": False})
            per_source.append({"sourceId": source_id, "status": "ok",
                               "feedItems": len(items), "windowItems": sampled})
        except (ET.ParseError, ValueError) as exc:
            per_source.append({"sourceId": source_id, "status": "parse-error",
                               "error": str(exc)[:120], "observed": 0})
    return {"schemaVersion": 1, "mode": "read-only-shadow", "asOf": observed_at.isoformat(),
            "windowStart": start.isoformat(), "windowEnd": end.isoformat(),
            "snapshotGeneratedAt": snapshot.get("generatedAt", ""),
            "snapshotArticles": len(existing), "sources": per_source,
            "rows": sorted(result_rows, key=lambda r: (r["sourceId"], r["publishedDate"], r["id"])),
            "summary": {"observed": len(result_rows),
                        "exactTitle": sum(bool(r["exactTitleSources"]) for r in result_rows),
                        "possibleSameEvent": sum(bool(r["possibleSameEvent"]) for r in result_rows),
                        "needsManualReview": len(result_rows)},
            "limitations": ["A feed response is not proof of complete publication history",
                            "No event-level matches are automatically approved",
                            "No production publication or state change"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PILOT_CONFIG)
    parser.add_argument("--snapshot", type=Path, help="read local snapshot instead of network")
    parser.add_argument("--previous-ledger", type=Path, help="existing JSON report for stable firstSeenAt")
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
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else json.loads(
        fetch_public("https://vciq.github.io/data/articles.json", MAX_SNAPSHOT_BYTES)
    )
    feeds = {}
    fetch_errors = {}
    for spec in specs:
        try:
            feeds[spec["id"]] = fetch_public(spec["url"], MAX_FEED_BYTES)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            fetch_errors[spec["id"]] = str(exc)[:160]
    report = observe(specs, feeds, snapshot, previous, observed_at, args.window_days)
    for spec in report["sources"]:
        if spec["sourceId"] in fetch_errors:
            spec["error"] = fetch_errors[spec["sourceId"]]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(s["status"] == "ok" for s in report["sources"]) else 2


if __name__ == "__main__":
    sys.exit(main())
