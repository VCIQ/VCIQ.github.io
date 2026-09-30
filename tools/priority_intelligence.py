"""Bounded public-publisher updates; no private preferences and no Pages build.

The collection job has no write token. A separate serialized publisher validates
its artifact against the current source config and uses a dedicated data branch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from tools.crawl_articles import parse_feed_items, parse_mittrchina_items

ROOT = Path(__file__).resolve().parents[1]
POLICY = "priority-publisher-v1"
REPO = "VCIQ/VCIQ.github.io"
BRANCH = "intelligence-live"
DATA_PATH = "public/data/priority_intelligence.json"
LIMIT = 300_000
SOURCES = {
    "amd-newsroom": ("newsroom.amd.com", "newsroom.amd.com", "官方披露"),
    "mittrchina-public-news": ("apii.web.mittrchina.com", "www.mittrchina.com", "媒体报道"),
}
TYPES = {"融资", "产业投资", "产品发布", "技术突破", "商业进展", "公司动态", "并购", "财报", "政策", "监管文件", "IPO", "论文", "人物观点"}


def timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_specs(root: Path = ROOT) -> list[dict]:
    config = json.loads((root / "config/intelligence_sources.json").read_text())
    specs = [x for x in config["feeds"] if x.get("id") in SOURCES and x.get("enabled", True)]
    if len(specs) != len(SOURCES) or {x["id"] for x in specs} != set(SOURCES):
        raise ValueError("priority source config is incomplete; do not fabricate coverage")
    for spec in specs:
        url = urlsplit(spec["url"])
        if url.scheme != "https" or url.hostname != SOURCES[spec["id"]][0] or url.username or url.password:
            raise ValueError("unexpected priority source endpoint")
        if spec.get("adapter") not in {"rss", "mittrchina_json"}:
            raise ValueError("unexpected priority source adapter")
    return specs


def config_hash(specs: list[dict]) -> str:
    return hashlib.sha256(compact(specs).encode()).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public(url: str) -> str:
    request = Request(url, headers={"User-Agent": "VCIQPriorityCollector/1.0", "Accept": "application/json, application/rss+xml, application/xml"})
    with build_opener(NoRedirect()).open(request, timeout=10) as response:
        body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError("priority publisher response exceeds budget")
        return body.decode("utf-8-sig")


def wire_item(raw: dict, source_id: str) -> dict:
    if not isinstance(raw, dict) or source_id not in SOURCES:
        raise ValueError("invalid priority item")
    def string(value, length):
        if not isinstance(value, str) or len(value) > length:
            raise ValueError("invalid priority text")
        return value
    source = raw.get("source", {})
    url = string(source.get("url"), 1600)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != SOURCES[source_id][1] or parsed.username or parsed.password:
        raise ValueError("priority article is outside its publisher")
    item_id = string(raw.get("id"), 180)
    if not item_id.startswith(source_id + "-") or raw.get("sourceId") != source_id:
        raise ValueError("priority item identity mismatch")
    published = string(raw.get("publishedAt"), 40)
    datetime.fromisoformat(published.replace("Z", "+00:00"))
    importance = raw.get("importance")
    if isinstance(importance, bool) or not isinstance(importance, (int, float)) or not 0 <= importance <= 100:
        raise ValueError("invalid importance")
    if raw.get("type") not in TYPES or raw.get("region") not in {"中国", "美国", "全球"}:
        raise ValueError("invalid priority classification")
    if source.get("level") != SOURCES[source_id][2]:
        raise ValueError("invalid evidence level")
    title = string(raw.get("title"), 300)
    if not title.strip(): raise ValueError("empty priority title")
    return {
        "id": item_id, "sourceId": source_id, "title": title,
        "summary": string(raw.get("summary"), 1600), "publishedAt": published,
        "type": raw["type"], "region": raw["region"],
        "sector": string(raw.get("sector"), 80), "company": string(raw.get("company"), 160),
        "importance": importance,
        "source": {"name": string(source.get("name"), 120), "url": url,
                   "level": source["level"], "platform": string(source.get("platform", ""), 80)},
    }


def collect(specs: list[dict], now: datetime, fetcher=fetch_public) -> dict:
    rows = []
    for spec in specs:
        source_id = spec["id"]
        try:
            body = fetcher(spec["url"])
            parser = parse_mittrchina_items if spec["adapter"] == "mittrchina_json" else parse_feed_items
            items = [wire_item(x, source_id) for x in parser(body, spec)][:24]
            rows.append({"sourceId": source_id, "status": "ok" if items else "empty", "items": items})
        except (HTTPError, OSError, ValueError, KeyError, TypeError) as error:
            rows.append({"sourceId": source_id, "status": "error", "errorType": type(error).__name__, "items": []})
    return {"schemaVersion": 1, "policyVersion": POLICY, "configHash": config_hash(specs),
            "checkedAt": timestamp(now), "sources": rows}


def finalize(previous: dict, scan: dict, specs: list[dict], now: datetime) -> dict:
    if scan.get("schemaVersion") != 1 or scan.get("policyVersion") != POLICY or scan.get("configHash") != config_hash(specs):
        raise ValueError("priority collection provenance mismatch")
    checked = datetime.fromisoformat(scan["checkedAt"].replace("Z", "+00:00"))
    if checked.tzinfo is None or checked > now + timedelta(minutes=5) or now - checked > timedelta(hours=1):
        raise ValueError("priority scan is stale or has an invalid clock")
    rows = scan.get("sources")
    if not isinstance(rows, list) or len(rows) != len(SOURCES) or {x.get("sourceId") for x in rows} != set(SOURCES):
        raise ValueError("priority scan coverage mismatch")
    if all(x.get("status") == "error" for x in rows):
        raise ValueError("all priority sources failed; preserve the last good version")
    previous_date = previous.get("generatedAt")
    if previous_date and datetime.fromisoformat(previous_date.replace("Z", "+00:00")) > checked:
        raise ValueError("older priority scan must not replace a newer version")
    items = {}
    for item in previous.get("items", []):
        verified = wire_item(item, item.get("sourceId", ""))
        items[verified["id"]] = verified
    for row in rows:
        if row.get("status") not in {"ok", "empty", "error"} or not isinstance(row.get("items"), list) or len(row["items"]) > 24:
            raise ValueError("invalid per-source priority status")
        if row["status"] == "error" and row["items"]:
            raise ValueError("failed source cannot publish candidates")
        for item in row["items"]:
            verified = wire_item(item, row["sourceId"])
            items[verified["id"]] = verified
    kept = []
    for item in items.values():
        day = datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00"))
        if day.tzinfo is None: day = day.replace(tzinfo=timezone.utc)
        if now - timedelta(days=7) <= day <= now + timedelta(days=1): kept.append(item)
    kept.sort(key=lambda x: (x["publishedAt"], x["id"]), reverse=True)
    kept = kept[:72]
    result = {"schemaVersion": 1, "policyVersion": POLICY,
              "generatedAt": scan["checkedAt"], "contentHash": hashlib.sha256(compact(kept).encode()).hexdigest(),
              "sourceState": "degraded" if any(x["status"] == "error" for x in rows) else "healthy",
              "sourceChecks": [{"sourceId": x["sourceId"], "status": x["status"]} for x in rows], "items": kept}
    if len(compact(result).encode()) > LIMIT: raise ValueError("priority snapshot exceeds publication budget")
    return result


def github(path: str, method="GET", data=None, allow_not_found=False):
    args = ["gh", "api", f"repos/{REPO}/{path}", "--method", method]
    if data is not None: args += ["--input", "-"]
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        if allow_not_found and "HTTP 404" in result.stderr: return None
        raise RuntimeError("priority GitHub operation failed; no credentials logged")
    return json.loads(result.stdout) if result.stdout else None


def publish(scan: dict, specs: list[dict], now: datetime) -> dict:
    import base64
    finalize({}, scan, specs, now)  # Validate before creating any public ref.
    # The data branch prevents every news update from rebuilding the static site.
    branch = github(f"git/ref/heads/{BRANCH}", allow_not_found=True)
    if branch is None:
        main = github("git/ref/heads/main")
        github("git/refs", "POST", {"ref": f"refs/heads/{BRANCH}", "sha": main["object"]["sha"]})
    current = github(f"contents/{DATA_PATH}?ref={BRANCH}", allow_not_found=True)
    previous = json.loads(base64.b64decode(current["content"])) if current else {}
    snapshot = finalize(previous, scan, specs, now)
    content = compact(snapshot) + "\n"
    body = {"message": "data: publish bounded priority intelligence snapshot", "branch": BRANCH,
            "content": base64.b64encode(content.encode()).decode()}
    if current: body["sha"] = current["sha"]  # Optimistic concurrency, no force push.
    receipt = github(f"contents/{DATA_PATH}", "PUT", body)
    return {"branch": BRANCH, "commit": receipt["commit"]["sha"], "contentHash": snapshot["contentHash"],
            "itemCount": len(snapshot["items"]), "sourceState": snapshot["sourceState"], "generatedAt": snapshot["generatedAt"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["collect", "publish"])
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args(); specs = source_specs(); now = datetime.now(timezone.utc)
    if args.mode == "collect":
        data = collect(specs, now)
        if all(row["status"] == "error" for row in data["sources"]):
            raise SystemExit("All priority publishers failed; no new successful snapshot")
        args.file.write_text(compact(data) + "\n", encoding="utf-8")
        print(compact({"checkedAt": data["checkedAt"], "sources": [{"id": x["sourceId"], "status": x["status"], "items": len(x["items"])} for x in data["sources"]]}))
    else:
        if args.file.stat().st_size > LIMIT: raise SystemExit("Priority scan artifact exceeds budget")
        print(compact(publish(json.loads(args.file.read_text()), specs, now)))


if __name__ == "__main__": main()
