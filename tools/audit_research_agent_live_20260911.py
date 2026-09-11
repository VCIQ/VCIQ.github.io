#!/usr/bin/env python3
"""One-off live acceptance for #489/#487. Never writes production or calls model APIs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

BASE = "https://vciq.github.io"
RELEASE = "244b0a242a72345765cbb25a767e0ff44a285ebe"
BLOBS = {
    "daily": "27e66b741689a8bc724ab06ed8358a6ad5145189",
    "snapshot": "2cfc8cbf61641b0496c64dd44c2d148b18bd1a99",
}
COUNTS = {"technology": 19, "track": 27, "person": 138, "ventureCompany": 63}
LABELS = {"technology": "核心技术", "track": "核心赛道", "person": "核心人物", "ventureCompany": "核心公司"}
INVALID = ("class-presiden-thomas-sonderman", "massachusetts-governo-chris-ballance")
OUT = Path("work/research-agent-live-audit")
OUT.mkdir(parents=True, exist_ok=True)
RESULT = {
    "checkedAt": datetime.now(timezone.utc).isoformat(),
    "expectedSourceSha": RELEASE,
    "origin": BASE,
    "runUrl": f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'VCIQ/VCIQ.github.io')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
    "scope": "Read-only public CDN and fresh Chromium contexts; no production changes, model calls, or private admin navigation.",
    "checks": [], "http": {}, "browser": [],
}


def check(name: str, passed: bool, detail: object = None) -> None:
    RESULT["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
    print(json.dumps({"check": name, "passed": bool(passed), "detail": detail}, ensure_ascii=False), flush=True)


def fetch(path: str, key: str) -> bytes | None:
    url = urljoin(BASE, path)
    if urlsplit(url).netloc != "vciq.github.io":
        raise ValueError("Audit requests must stay on the public VCIQ origin")
    for attempt in range(2):
        try:
            req = Request(url, headers={"User-Agent": "VCIQ-ReadOnly-Release-Audit/1.0", "Cache-Control": "no-cache"})
            with urlopen(req, timeout=30) as response:
                raw = response.read(12_000_001)
                if len(raw) > 12_000_000:
                    raise ValueError("Response exceeds bounded audit size")
                RESULT["http"][key] = {
                    "url": url, "finalUrl": response.url, "status": response.status,
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "headers": {k: response.headers.get(k) for k in ("Date", "Age", "ETag", "Last-Modified", "Cache-Control", "X-Cache")},
                }
            return raw
        except Exception as exc:
            RESULT["http"][key] = {"url": url, "error": str(exc), "attempt": attempt + 1}
            if attempt == 0:
                time.sleep(2)
    return None


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        row = dict(attrs)
        if row.get("id"):
            self.ids.add(str(row["id"]))
        if tag == "a" and row.get("href"):
            self.hrefs.append(str(row["href"]))


def audit_http() -> tuple[dict, dict]:
    paths = {"provenance": "/build-provenance.json", "html": "/research-agent/", "daily": "/data/research_agent_daily.json", "snapshot": "/data/research_agent_snapshot.json"}
    raw = {key: fetch(path, key) for key, path in paths.items()}
    for key in paths:
        check(f"http.{key}.200", raw[key] is not None, RESULT["http"][key])
    decoded: dict = {}
    for key in ("provenance", "daily", "snapshot"):
        try:
            decoded[key] = json.loads(raw[key] or b"")
        except (ValueError, TypeError):
            check(f"http.{key}.json", False)
            decoded[key] = {}
    provenance, daily, snapshot = (decoded[k] for k in ("provenance", "daily", "snapshot"))
    check("live.source_sha_matches_release", provenance.get("sourceSha") == RELEASE, provenance)
    for key, expected in BLOBS.items():
        actual = blob_sha(raw[key]) if raw[key] is not None else None
        check(f"live.{key}.matches_published_blob", actual == expected, {"actual": actual, "expected": expected})
    for key, expected in COUNTS.items():
        scope = daily.get("researchScope", {}).get(key, {})
        rows = snapshot.get("datasets", {}).get(key)
        count = len(rows) if isinstance(rows, dict) else None
        check(f"coverage.{key}", scope.get("status") == "active" and scope.get("count") == expected and count == expected, {"scope": scope, "snapshotCount": count})
    memory = daily.get("thesisMemory", {})
    observations = memory.get("observations", [])
    ids = [row.get("id") for row in observations]
    current = memory.get("currentObservationIds", [])
    check("memory.real_observations", len(observations) == 9 and memory.get("observationCount") == 9, {"actual": len(observations), "declared": memory.get("observationCount")})
    check("memory.current_pointers", len(current) == 9 and all(x in ids for x in current) and len(set(ids)) == len(ids), current)
    check("memory.evidence_snapshots", bool(observations) and all(row.get("evidence") for row in observations))
    RESULT["memory"] = {"count": len(observations), "firstObservation": observations[0] if observations else None}
    parser = Links()
    parser.feed((raw["html"] or b"").decode("utf-8", errors="replace"))
    check("html.history_anchor", "history" in parser.ids)
    check("html.thesis_memory_anchor", "thesis-memory-title" in parser.ids)
    people = sorted({urlsplit(urljoin(BASE, href)).path for href in parser.hrefs if urlsplit(urljoin(BASE, href)).netloc == "vciq.github.io" and urlsplit(urljoin(BASE, href)).path.startswith("/people/")})
    check("html.no_known_invalid_people_links", not any(bad in href for bad in INVALID for href in parser.hrefs))
    check("html.people_links_present", bool(people), people)
    if len(people) > 30:
        check("http.people_links.bounded_scope", False, len(people))
    else:
        for index, path in enumerate(people):
            value = fetch(path, f"person_{index}")
            check(f"http.person.{path}", value is not None, RESULT["http"][f"person_{index}"])
    return daily, snapshot


def audit_browser(daily: dict) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, width, height in (("desktop", 1440, 1000), ("tablet", 768, 1024), ("mobile", 390, 844), ("small-mobile", 360, 800)):
            row: dict = {"name": name, "viewport": {"width": width, "height": height}, "pageErrors": [], "assetErrors": [], "requestFailures": [], "blockedWriteMethods": []}
            RESULT["browser"].append(row)
            context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1, locale="zh-CN", timezone_id="Asia/Shanghai", service_workers="block")
            def read_only_route(route):
                if route.request.method not in ("GET", "HEAD", "OPTIONS"):
                    row["blockedWriteMethods"].append({"method": route.request.method, "url": route.request.url})
                    route.abort()
                else:
                    route.continue_()
            context.route("**/*", read_only_route)
            page = context.new_page()
            page.on("pageerror", lambda error: row["pageErrors"].append(str(error)))
            page.on("requestfailed", lambda request: row["requestFailures"].append({"url": request.url, "failure": request.failure, "method": request.method}))
            page.on("response", lambda response: row["assetErrors"].append({"url": response.url, "status": response.status}) if response.status >= 400 and response.url.startswith(BASE + "/_next/") else None)
            try:
                response = page.goto(BASE + "/research-agent/", wait_until="networkidle", timeout=60000)
                page.locator("main").wait_for()
                page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")
                check(f"browser.{name}.http200", response is not None and response.status == 200)
                page.screenshot(path=str(OUT / f"{name}-first-screen.png"))
                details = page.locator("#brief details").first
                if details.count():
                    details.locator("summary").click()
                    check(f"browser.{name}.coverage_expands", details.get_attribute("open") is not None)
                text = re.sub(r"\s+", "", page.locator("#brief").inner_text())
                for key, expected in COUNTS.items():
                    check(f"browser.{name}.coverage.{key}", re.search(re.escape(LABELS[key]) + str(expected) + r"(?!\d)", text) is not None)
                dimensions = page.evaluate("({viewport:innerWidth, document:document.documentElement.scrollWidth, body:document.body.scrollWidth})")
                row["dimensions"] = dimensions
                check(f"browser.{name}.no_document_horizontal_overflow", max(dimensions["document"], dimensions["body"]) <= width + 1, dimensions)
                if details.count():
                    details.screenshot(path=str(OUT / f"{name}-coverage.png"))
                memory = page.locator('section[aria-labelledby="thesis-memory-title"]')
                memory.scroll_into_view_if_needed()
                check(f"browser.{name}.memory_nonempty", memory.locator("article").count() >= 3 and "Joby Aviation" in memory.inner_text())
                memory.screenshot(path=str(OUT / f"{name}-memory.png"))
                expanded = memory.locator("details")
                if expanded.count():
                    expanded.first.locator("summary").click()
                visible = memory.locator("article:visible").count()
                check(f"browser.{name}.all_memory_observations_visible", visible == 9, visible)
                for target in ("brief", "theses", "changes", "queue", "history"):
                    page.locator(f'main a[href="#{target}"]').first.click()
                    page.wait_for_timeout(400)
                    rect = page.locator(f"#{target}").bounding_box()
                    navigated = page.evaluate("location.hash") == "#" + target
                    check(f"browser.{name}.navigation.{target}", navigated and rect is not None and rect["y"] < height and rect["y"] + rect["height"] > 0, rect)
                row["historyText"] = page.locator("#history").inner_text()
                page.screenshot(path=str(OUT / f"{name}-history.png"))
                citation = page.locator('main a[href^="#evidence-"]').first
                if citation.count():
                    target = citation.get_attribute("href")
                    citation.click()
                    page.wait_for_timeout(400)
                    check(f"browser.{name}.evidence_anchor", page.evaluate("location.hash") == target and page.locator(target).count() == 1)
                else:
                    check(f"browser.{name}.evidence_anchor", False, "No evidence citation")
                check(f"browser.{name}.no_javascript_runtime_errors", not row["pageErrors"], row["pageErrors"])
                check(f"browser.{name}.no_failed_static_assets", not row["assetErrors"], row["assetErrors"])
                if name == "desktop":
                    link = page.locator('#queue a[href^="/people/"]').first
                    if link.count():
                        destination = urljoin(BASE, link.get_attribute("href"))
                        link.click()
                        page.wait_for_url(destination, timeout=30000)
                        page.locator("h1").first.wait_for()
                        check("browser.person_route_click", page.url == destination, {"url": page.url, "title": page.locator("h1").first.inner_text()})
                    else:
                        check("browser.person_route_click", False, "No queue person link")
            except Exception as exc:
                row["exception"] = str(exc)
                check(f"browser.{name}.completed", False, str(exc))
                try:
                    page.screenshot(path=str(OUT / f"{name}-failure.png"))
                except Exception:
                    pass
            finally:
                context.close()
        browser.close()


try:
    daily, _ = audit_http()
    audit_browser(daily)
except Exception:
    check("audit.completed", False, traceback.format_exc())
finally:
    failed = [row["name"] for row in RESULT["checks"] if not row["passed"]]
    RESULT["completedAt"] = datetime.now(timezone.utc).isoformat()
    RESULT["summary"] = {"checks": len(RESULT["checks"]), "passed": len(RESULT["checks"]) - len(failed), "failed": failed}
    (OUT / "live-audit.json").write_text(json.dumps(RESULT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(RESULT["summary"], ensure_ascii=False), flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write("## Research Agent live release acceptance\n\n```json\n" + json.dumps(RESULT["summary"], ensure_ascii=False, indent=2) + "\n```\n")
    sys.exit(1 if failed else 0)
