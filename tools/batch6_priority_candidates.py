"""Validate and publish sanitized Batch-6 RSS candidates to the data-only branch."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import ipaddress
import json
import re
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

REPO = "VCIQ/VCIQ.github.io"
BRANCH = "intelligence-live"
DATA_PATH = "public/data/batch6_priority_candidates.json"
POLICY = "batch6-priority-v1"
PUBLIC_LIMIT = 180_000
MAX_ITEMS = 72
INCOMING_MAX = 24
ALLOWED_TYPES = {"融资", "并购", "IPO", "产品发布", "技术突破", "公司动态"}
ALLOWED_SECTORS = {"科创资本", "风险投资", "AI安全", "AI智能终端", "AI网络通信", "半导体", "商业航天", "空天信息", "6G"}


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def text(value, max_length: int) -> str:
    if not isinstance(value, str) or len(value) > max_length:
        raise ValueError("invalid public text")
    return " ".join(value.split())


def public_url(value) -> str:
    raw = text(value, 1800)
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid public URL")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".local"):
        raise ValueError("private host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
        raise ValueError("private host")
    return raw


def iso(value) -> str:
    raw = text(value, 40)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def relevant_for_query(query: str, title: str, summary: str) -> bool:
    value = f"{title} {summary}"
    if query == "科创板 辅导备案":
        return "科创板" in value and any(token in value for token in ("辅导", "备案", "IPO", "上市"))
    if query == "创业板 辅导备案":
        return "创业板" in value and any(token in value for token in ("辅导", "备案", "IPO", "上市"))
    if query == "A+H 上市":
        return bool(
            re.search(r"A\s*\+\s*H", value, re.IGNORECASE)
            or (
                re.search(r"(?:H\s*股|港股|港交所)", value, re.IGNORECASE)
                and re.search(r"上市|IPO|挂牌|递表|备案|发行", value, re.IGNORECASE)
            )
        )
    if query == "Pre-IPO 融资":
        return bool(
            re.search(r"Pre[-\s]?IPO|上市前", value, re.IGNORECASE)
            and re.search(r"融资|募资|投资|增资|轮", value, re.IGNORECASE)
        )
    if query == "AI 安全":
        return bool(
            re.search(r"AI|人工智能|大模型|Agent", value, re.IGNORECASE)
            and re.search(r"安全|失控|攻击|漏洞|风险|治理|沙箱|越狱", value, re.IGNORECASE)
        )
    if query == "AI 眼镜":
        return bool(re.search(r"AI.{0,5}眼镜|智能眼镜|AR.{0,3}眼镜|XR.{0,3}眼镜", value, re.IGNORECASE))
    if query == "CXL":
        return bool(re.search(r"(?:^|[^a-z0-9])CXL(?:$|[^a-z0-9])", value, re.IGNORECASE))
    if query == "UCIe":
        return bool(re.search(r"(?:^|[^a-z0-9])UCIe(?:$|[^a-z0-9])", value, re.IGNORECASE))
    if query == "太空算力":
        return bool(
            re.search(r"太空|空间|轨道|在轨|卫星", value, re.IGNORECASE)
            and re.search(r"算力|计算|数据中心|云", value, re.IGNORECASE)
        )
    if query == "6G NTN":
        return bool(
            re.search(r"6G", value, re.IGNORECASE)
            and re.search(r"NTN|非地面|卫星|空天地", value, re.IGNORECASE)
        )
    return False


def validate_item(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("invalid item")
    source = raw.get("source")
    if not isinstance(source, dict):
        raise ValueError("invalid source")
    if raw.get("sourceId") != "batch6-google-alerts":
        raise ValueError("unexpected source id")
    item_id = text(raw.get("id"), 180)
    if not item_id.startswith("batch6-rss-"):
        raise ValueError("invalid item id")
    event_type = raw.get("type")
    sector = text(raw.get("sector"), 80)
    if event_type not in ALLOWED_TYPES or sector not in ALLOWED_SECTORS:
        raise ValueError("invalid candidate classification")
    importance = raw.get("importance")
    if isinstance(importance, bool) or not isinstance(importance, (int, float)) or not 75 <= importance <= 100:
        raise ValueError("invalid importance")
    if source.get("level") != "待交叉验证" or source.get("platform") != "Google Alerts RSS":
        raise ValueError("invalid evidence role")
    result = {
        "id": item_id,
        "sourceId": "batch6-google-alerts",
        "title": text(raw.get("title"), 300),
        "summary": text(raw.get("summary", ""), 360),
        "publishedAt": iso(raw.get("publishedAt")),
        "type": event_type,
        "region": "全球",
        "sector": sector,
        "company": "",
        "importance": importance,
        "source": {
            "name": text(source.get("name"), 100),
            "url": public_url(source.get("url")),
            "level": "待交叉验证",
            "platform": "Google Alerts RSS",
        },
        "radarQuery": text(raw.get("radarQuery"), 100),
        "radarPriority": text(raw.get("radarPriority"), 4),
    }
    if result["radarPriority"] not in {"P0", "P1", "P2"}:
        raise ValueError("invalid radar priority")
    return result


def validate_incoming(raw: dict, now: datetime) -> dict:
    if not isinstance(raw, dict) or raw.get("schemaVersion") != 1 or raw.get("policyVersion") != POLICY:
        raise ValueError("invalid Batch-6 payload")
    generated = iso(raw.get("generatedAt"))
    generated_dt = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    if generated_dt > now + timedelta(minutes=5) or now - generated_dt > timedelta(minutes=20):
        raise ValueError("stale or future Batch-6 payload")
    rows = raw.get("items")
    if not isinstance(rows, list) or len(rows) > INCOMING_MAX:
        raise ValueError("Batch-6 input exceeds item budget")
    items = [validate_item(row) for row in rows]
    if len({item["id"] for item in items}) != len(items):
        raise ValueError("duplicate Batch-6 item")
    summary = raw.get("sourceSummary", {})
    if not isinstance(summary, dict):
        raise ValueError("invalid source summary")
    counters = {}
    for key in ("configuredQueries", "rssSources", "healthySources", "failedSources", "observedItems"):
        value = summary.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 100_000:
            raise ValueError("invalid source counter")
        counters[key] = int(value)
    if counters["configuredQueries"] != 10 or counters["rssSources"] != 10:
        raise ValueError("Batch-6 coverage must contain exactly 10 queries")
    return {"generatedAt": generated, "items": items, "sourceSummary": counters}


def finalize(previous: dict, incoming: dict, now: datetime) -> dict:
    validated = validate_incoming(incoming, now)
    by_id = {}
    if isinstance(previous, dict) and previous.get("policyVersion") == POLICY:
        for row in previous.get("items", []):
            item = validate_item(row)
            if not relevant_for_query(item["radarQuery"], item["title"], item["summary"]):
                continue
            item["firstSeenAt"] = iso(row.get("firstSeenAt", previous.get("generatedAt")))
            by_id[item["id"]] = item
    for item in validated["items"]:
        item = dict(item)
        item["firstSeenAt"] = by_id.get(item["id"], {}).get("firstSeenAt", validated["generatedAt"])
        by_id[item["id"]] = item
    lower = now - timedelta(days=7)
    retained = [
        item for item in by_id.values()
        if lower <= datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00")) <= now + timedelta(days=1)
    ]
    retained.sort(key=lambda row: (row["publishedAt"], row["id"]), reverse=True)
    retained = retained[:MAX_ITEMS]
    result = {
        "schemaVersion": 1,
        "policyVersion": POLICY,
        "generatedAt": validated["generatedAt"],
        "contentHash": hashlib.sha256(compact(retained).encode()).hexdigest(),
        "sourceState": "healthy" if validated["sourceSummary"]["failedSources"] == 0 else "degraded",
        "sourceSummary": validated["sourceSummary"],
        "items": retained,
    }
    if len(compact(result).encode()) > PUBLIC_LIMIT:
        raise ValueError("Batch-6 public snapshot exceeds budget")
    return result


def github(path: str, method="GET", data=None, allow_not_found=False):
    args = ["gh", "api", "repos/" + REPO + "/" + path, "--method", method]
    if data is not None:
        args += ["--input", "-"]
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        if allow_not_found and "HTTP 404" in result.stderr:
            return None
        raise RuntimeError("Batch-6 GitHub operation failed")
    return json.loads(result.stdout) if result.stdout else None


def publish(incoming: dict, now: datetime) -> dict:
    validate_incoming(incoming, now)
    branch = github("git/ref/heads/" + BRANCH, allow_not_found=True)
    if branch is None:
        main = github("git/ref/heads/main")
        github("git/refs", "POST", {"ref": "refs/heads/" + BRANCH, "sha": main["object"]["sha"]})
    current = github("contents/" + DATA_PATH + "?ref=" + BRANCH, allow_not_found=True)
    previous = json.loads(base64.b64decode(current["content"])) if current else {}
    snapshot = finalize(previous, incoming, now)
    body = {
        "message": "data: publish bounded Batch-6 priority candidates",
        "branch": BRANCH,
        "content": base64.b64encode((compact(snapshot) + "\n").encode()).decode(),
    }
    if current:
        body["sha"] = current["sha"]
    receipt = github("contents/" + DATA_PATH, "PUT", body)
    return {
        "branch": BRANCH,
        "commit": receipt["commit"]["sha"],
        "generatedAt": snapshot["generatedAt"],
        "itemCount": len(snapshot["items"]),
        "contentHash": snapshot["contentHash"],
        "sourceState": snapshot["sourceState"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["validate", "publish"])
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    if args.file.stat().st_size > PUBLIC_LIMIT:
        raise SystemExit("Batch-6 input artifact exceeds budget")
    raw = json.loads(args.file.read_text())
    now = datetime.now(timezone.utc)
    if args.mode == "validate":
        value = validate_incoming(raw, now)
        print(compact({"ok": True, "generatedAt": value["generatedAt"], "items": len(value["items"])}))
    else:
        print(compact(publish(raw, now)))


if __name__ == "__main__":
    main()
