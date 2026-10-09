"""Bounded official-page discovery. Produces review candidates, never investment facts.

No credentials, browser automation, full-text republication or writes to config/public.
A successful HTTP response is not evidence of portfolio completeness or a deal.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import socket
import time
from urllib import error, parse, request, robotparser

ROOT = Path(__file__).resolve().parents[1]
AGENT = "VCIQ-Research-Scout/1.0 (+https://vciq.github.io/)"
MAX_BYTES = 1_048_576  # bounded 1 MiB for reviewed official news/portfolio listings
MAX_ROBOTS_BYTES = 200_000
TIMEOUT = 8
MAX_REDIRECTS = 2
TOPIC = re.compile(r"invest|funding|portfolio|perspective|insight|thesis|research|news|article|podcast|team|投资|融资|观点|洞察|访谈|项目|合伙人|团队", re.I)
SKIP = re.compile(r"/(login|sign-in|jobs|careers|privacy|legal)(/|$)", re.I)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ScoutError(Exception):
    pass


def host_key(host: str) -> str:
    return host.lower().removeprefix("www.")


def validate_url(url: str, allowed_host: str, resolve_dns: bool = True) -> str:
    parts = parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ScoutError("unsafe-url")
    if parts.port not in (None, 443) or host_key(parts.hostname) != host_key(allowed_host):
        raise ScoutError("off-domain")
    try:
        literal = ipaddress.ip_address(parts.hostname)
    except ValueError:
        literal = None
    if literal is not None or parts.hostname.endswith((".local", ".internal")) or parts.hostname == "localhost":
        raise ScoutError("nonpublic-host")
    if resolve_dns:
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ScoutError("nonpublic-address")
    return parse.urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def get_bytes(url: str, limit: int) -> tuple[bytes, str]:
    opener = request.build_opener(NoRedirect())
    req = request.Request(url, headers={"User-Agent":AGENT, "Accept":"text/html,text/plain;q=0.9", "Accept-Encoding":"identity"})
    with opener.open(req, timeout=TIMEOUT) as response:
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ScoutError("body-too-large")
        return body, response.headers.get("Content-Type", "")


def robot_policy(url: str, allowed_host: str) -> robotparser.RobotFileParser:
    parts = parse.urlsplit(url)
    robots_url = parse.urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    validate_url(robots_url, allowed_host)
    rules = robotparser.RobotFileParser()
    try:
        body, _ = get_bytes(robots_url, MAX_ROBOTS_BYTES)
        rules.parse(body.decode("utf-8", errors="replace").splitlines())
    except error.HTTPError as exc:
        if exc.code in (404, 410):
            rules.parse(["User-agent: *", "Disallow:"])
        else:
            raise ScoutError(f"robots-unavailable-http-{exc.code}") from exc
    return rules


def fetch_page(url: str, allowed_host: str) -> tuple[str, str, str]:
    for _ in range(MAX_REDIRECTS + 1):
        url = validate_url(url, allowed_host)
        rules = robot_policy(url, allowed_host)
        if not rules.can_fetch(AGENT, url):
            raise ScoutError("robots-disallowed")
        delay = rules.crawl_delay(AGENT) or rules.crawl_delay("*") or 0
        if delay > 10:
            raise ScoutError("robots-delay-exceeds-budget")
        if delay:
            time.sleep(delay)
        try:
            body, content_type = get_bytes(url, MAX_BYTES)
        except error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                url = validate_url(parse.urljoin(url, exc.headers.get("Location", "")), allowed_host)
                continue
            raise
        if "text/html" not in content_type.lower() and "application/xhtml+xml" not in content_type.lower():
            raise ScoutError("non-html-adapter-required")
        charset = re.search(r"charset=([a-zA-Z0-9_-]+)", content_type)
        encoding = charset.group(1) if charset else "utf-8"
        try:
            html = body.decode(encoding, errors="replace")
        except LookupError:
            html = body.decode("utf-8", errors="replace")
        return url, html, hashlib.sha256(body).hexdigest()
    raise ScoutError("redirect-budget-exhausted")


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, str]] = []
        self.href = None
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "a" and not self.hidden:
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data):
        if self.href and not self.hidden:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag == "a" and self.href:
            self.rows.append((self.href, " ".join(" ".join(self.parts).split())))
            self.href = None
            self.parts = []


def extract_candidates(html: str, source_url: str, institution_id: str) -> list[dict]:
    parser = Links()
    parser.feed(html)
    host = parse.urlsplit(source_url).hostname or ""
    candidates = {}
    for href, title in parser.rows:
        if not title or len(title) > 400:
            continue
        try:
            url = validate_url(parse.urljoin(source_url, href), host, resolve_dns=False)
        except (ScoutError, ValueError):
            continue
        parts = parse.urlsplit(url)
        if parts.query or parts.path == "/" or SKIP.search(parts.path) or not TOPIC.search(title + " " + parts.path):
            continue
        key = hashlib.sha256(f"{institution_id}:{url}".encode()).hexdigest()[:24]
        candidates[url] = {
            "id":key, "institutionId":institution_id, "title":title, "url":url,
            "discoveredOn":source_url, "publishedAt":None,
            "claimStatus":"unreviewed-navigation-candidate", "investmentRelationConfirmed":False,
        }
        if len(candidates) >= 12:
            break
    return list(candidates.values())


def scout(institution: dict) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    identity = institution["id"]
    official_url = institution["officialUrl"]
    url = institution.get("discoveryUrl") or official_url
    result = {"institutionId":identity, "sourceUrl":url, "checkedAt":started, "status":"unavailable", "candidates":[]}
    try:
        # Alternate entry points must remain on the reviewed official domain.
        allowed_host = parse.urlsplit(official_url).hostname or ""
        validate_url(url, allowed_host, resolve_dns=False)
        final_url, html, digest = fetch_page(url, allowed_host)
        candidates = extract_candidates(html, final_url, identity)
        result.update(status="candidates-found" if candidates else "no-candidates-adapter-review", candidates=candidates, contentSha256=digest, finalUrl=final_url)
    except error.HTTPError as exc:
        result["reason"] = f"http-{exc.code}"
    except (ScoutError, OSError, ValueError, TimeoutError) as exc:
        # No raw response/error body or credential is included in artifacts.
        result["reason"] = str(exc) if isinstance(exc, ScoutError) else type(exc).__name__
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    output = args.output.resolve()
    for protected in (ROOT / "config", ROOT / "public"):
        if output.is_relative_to(protected):
            parser.error("Scout artifacts must not overwrite config/ or public/.")
    roster = json.loads((ROOT / "config/innovation_global_investors.json").read_text())
    institutions = roster["institutions"][:max(1, min(args.limit, 30))]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(scout, institutions))
    payload = {
        "schemaVersion":1, "generatedAt":datetime.now(timezone.utc).isoformat(),
        "mode":"official-page-navigation-discovery-only", "autoPublication":False,
        "institutionsExamined":len(results),
        "candidateCount":sum(len(row["candidates"]) for row in results),
        "unavailableCount":sum(row["status"] == "unavailable" for row in results),
        "limitations":"Homepage links only, not a complete portfolio or verified deal/speech feed. No publication dates or investment roles inferred.",
        "results":results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key:payload[key] for key in ("mode", "institutionsExamined", "candidateCount", "unavailableCount", "autoPublication")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
