"""Public-only, bounded catch-up with resumable publisher-ID checkpoints.

MITTR: always inspect the head, then at most two catch-up pages. The frozen
checkpoint is advanced only after overlap with the previous successful window.
RSS: inspect the available feed, but report history gaps rather than invent a
paging endpoint. No HTTP request in this module receives application credentials.
"""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import hashlib
import json
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit

from tools.crawl_articles import parse_feed_items, parse_mittrchina_items, normalize_date
from tools.priority_entity_linking import link_priority_entities

MAX_PAGES = 3
PAGE_SIZE = 20
MAX_SOURCE_ITEMS = 60


def _cursor(value):
    value = value if isinstance(value, dict) else {}
    def ids(key):
        values = value.get(key, [])
        if not isinstance(values, list) or len(values) > PAGE_SIZE:
            raise ValueError("invalid public source cursor")
        if any(not isinstance(x, str) or len(x) > 100 for x in values):
            raise ValueError("invalid public cursor identity")
        return values
    resume = value.get("resumePage", 2)
    if isinstance(resume, bool) or not isinstance(resume, int) or not 2 <= resume <= 10000:
        raise ValueError("invalid public cursor page")
    return {"anchorIds": ids("anchorIds"), "pendingHeadIds": ids("pendingHeadIds"), "resumePage": resume}


def _time(raw, fallback):
    try:
        if isinstance(raw, (int, float)) or str(raw).isdigit():
            value = float(raw); value = value / 1000 if value > 10_000_000_000 else value
            date = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            date = parsedate_to_datetime(raw)
        if date.tzinfo is None: return fallback, "day"
        # Midnight feeds often supply only day precision; do not pretend otherwise.
        if date.hour == date.minute == date.second == 0: return fallback, "day"
        return date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "second"
    except (ValueError, TypeError, OverflowError, OSError):
        return fallback, "day"


def _mit_url(base, page):
    parsed = urlsplit(base)
    if parsed.scheme != "https" or parsed.hostname != "apii.web.mittrchina.com" or parsed.path != "/information/index":
        raise ValueError("unapproved paged source")
    params = parse_qs(parsed.query); params.update(page=[str(page)], limit=[str(PAGE_SIZE)])
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(params, doseq=True), ""))


def collect_source(spec, now, fetcher, previous_cursor=None):
    cursor = _cursor(previous_cursor)
    source_id = spec["id"]; items = {}; trace = []; pages = []; observed = 0
    head_ids = []; complete = False; partial = False; gap = False; last_page = 1
    is_mit = spec["adapter"] == "mittrchina_json"
    requested = [1, cursor["resumePage"], cursor["resumePage"] + 1] if is_mit else [1]
    for page in requested[:MAX_PAGES]:
        try:
            body = fetcher(_mit_url(spec["url"], page) if is_mit else spec["url"])
            if is_mit:
                payload = json.loads(body)
                if not isinstance(payload, dict) or payload.get("code") != 10000 or not isinstance(payload.get("data"), dict) or not isinstance(payload["data"].get("items"), list):
                    raise ValueError("invalid MITTR list")
                raw_rows = payload["data"]["items"]
                if len(raw_rows) > PAGE_SIZE: raise ValueError("publisher page exceeded requested budget")
                entries = []
                for row in raw_rows:
                    if not isinstance(row, dict): raise ValueError("invalid publisher row")
                    raw_id = row.get("id")
                    valid_id = not isinstance(raw_id, bool) and str(raw_id).isdigit()
                    identity = str(raw_id) if valid_id else "invalid-" + hashlib.sha256(str(row).encode()).hexdigest()[:12]
                    single = json.dumps({"code": 10000, "data": {"items": [row]}})
                    entries.append((identity, row.get("name", ""), row.get("start_time"),
                                    f"https://www.mittrchina.com/news/detail/{raw_id}" if valid_id else "",
                                    single))
            else:
                root = ET.fromstring(body)
                nodes = [x for x in root.iter() if x.tag.split("}")[-1] in ("item", "entry")]
                entries = []
                # A long archive tail is not a missed recent window. Do not
                # claim completeness if skipped dates are absent or recent.
                cutoff = (now - timedelta(days=7)).date().isoformat()
                def skipped_is_recent(node):
                    dates = [x.text for x in node if x.tag.split("}")[-1].lower() in ("pubdate", "published", "updated", "date")]
                    normalized = normalize_date(dates[0]) if dates else None
                    return normalized is None or normalized >= cutoff
                gap = any(skipped_is_recent(node) for node in nodes[MAX_SOURCE_ITEMS:])
                for node in nodes[:MAX_SOURCE_ITEMS]:
                    values = {x.tag.split("}")[-1].lower(): x.text or x.attrib.get("href", "") for x in node}
                    url = values.get("link", ""); identity = hashlib.sha256(url.encode()).hexdigest()[:24]
                    single = ET.tostring(node, encoding="unicode")
                    entries.append((identity, values.get("title", ""), values.get("pubdate", values.get("published", "")), url, single))
            pages.append(page); last_page = page; observed += len(entries)
            if page == 1: head_ids = [x[0] for x in entries[:PAGE_SIZE]]
            for identity, title, original_time, url, single in entries:
                parsed = (parse_mittrchina_items if is_mit else parse_feed_items)(single, {**spec, "maxItems": 1})
                reason = "accepted" if parsed else (
                    "invalid-publication-date" if not normalize_date(original_time) else
                    "missing-title-or-url" if not title or not url else "source-filter-or-invalid-record")
                if parsed:
                    row = parsed[0]
                    row["publishedAt"], row["publicationTimePrecision"] = _time(original_time, row["publishedAt"])
                    items[row["id"]] = link_priority_entities(row)
                    identity = row["id"]
                trace.append({"id": identity, "sourceId": source_id, "title": str(title)[:240],
                              "url": url if urlsplit(url).hostname in spec.get("allowedHosts", []) else "",
                              "reason": reason})
            hit_anchor = bool(set(x[0] for x in entries) & set(cursor["anchorIds"]))
            old_window = bool(entries) and all((normalize_date(x[2]) or "9999") < (now - timedelta(days=7)).date().isoformat() for x in entries)
            if not is_mit:
                gap = gap or bool(cursor["anchorIds"] and not hit_anchor)
                complete = not gap
                break
            if hit_anchor or len(entries) < PAGE_SIZE or old_window:
                complete = True
                break
        except (OSError, ValueError, TypeError, KeyError, ET.ParseError):
            if not pages: raise
            partial = True; break
    next_cursor = cursor
    if complete and not partial:
        next_cursor = {"anchorIds": cursor["pendingHeadIds"] or head_ids or cursor["anchorIds"], "pendingHeadIds": [], "resumePage": 2}
    elif is_mit and not partial:
        next_cursor = {"anchorIds": cursor["anchorIds"], "pendingHeadIds": cursor["pendingHeadIds"] or head_ids,
                       "resumePage": max(2, last_page)}  # one page overlap absorbs offset shifts
    elif not is_mit and not partial:
        next_cursor = {"anchorIds": head_ids, "pendingHeadIds": [], "resumePage": 2}
    return {"sourceId": source_id, "status": "partial" if partial or gap else "ok" if items else "empty",
            "items": list(items.values()), "cursor": next_cursor, "pagesFetched": pages,
            "pending": bool(is_mit and not complete), "historyGap": gap,
            "scanned": observed, "filtered": sum(x["reason"] != "accepted" for x in trace),
            "trace": trace[:MAX_SOURCE_ITEMS]}
