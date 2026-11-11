#!/usr/bin/env python3
"""Collect public source metadata for operator review."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from tools.wechat_public_sources import WeChatPageParser

PUBLISHER = "https://www.zhidx.com"
PUBLISHER_INDEX = PUBLISHER + "/p/category/%E6%9C%BA%E5%99%A8%E4%BA%BA%E6%97%A0%E4%BA%BA%E6%9C%BA"
WECHAT = "https://mp.weixin.qq.com"
USER_AGENT = "VCIQ-ResearchBot/1.0 (+https://vciq.github.io/)"
DETAIL_LIMIT = 3
MAX_BYTES = 2_000_000
PUBLISHER_ARTICLE = re.compile(r"https://www\.zhidx\.com/p/\d+\.html\Z")
WECHAT_ARTICLE = re.compile(r"https://mp\.weixin\.qq\.com/s/[A-Za-z0-9_-]+\Z")


class SourceUnavailable(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_page(url: str, media_types: set[str]) -> str:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with build_opener(NoRedirect()).open(request, timeout=12) as response:
            if response.headers.get_content_type() not in media_types:
                raise SourceUnavailable("unexpected_content_type")
            data = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise SourceUnavailable(f"http_{exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise SourceUnavailable("network_error") from exc
    if len(data) > MAX_BYTES:
        raise SourceUnavailable("response_too_large")
    return data.decode("utf-8", errors="replace")


def read_robots(origin: str) -> RobotFileParser:
    robots = RobotFileParser()
    try:
        text = read_page(origin + "/robots.txt", {"text/plain"})
    except SourceUnavailable as exc:
        if str(exc) != "http_404":
            raise SourceUnavailable(f"robots_{exc}") from exc
        text = ""
    robots.parse(text.splitlines())
    return robots


def read_html(url: str, robots: RobotFileParser) -> str:
    if not robots.can_fetch(USER_AGENT, url):
        raise SourceUnavailable("robots_disallowed")
    return read_page(url, {"text/html", "application/xhtml+xml"})


class PublisherPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: dict[str, None] = {}
        self.articles: list[dict] = []
        self._structured_data: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            target = urljoin(PUBLISHER_INDEX, values["href"])
            if PUBLISHER_ARTICLE.fullmatch(target):
                self.links[target] = None
        if tag == "script" and values.get("type") == "application/ld+json":
            self._structured_data = []

    def handle_data(self, data):
        if self._structured_data is not None:
            self._structured_data.append(data)

    def handle_endtag(self, tag):
        if tag != "script" or self._structured_data is None:
            return
        text = "".join(self._structured_data)
        self._structured_data = None
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            return
        if isinstance(record, dict) and record.get("@type") == "NewsArticle":
            self.articles.append(record)


def publisher_candidate(url: str, source: str) -> dict:
    parser = PublisherPage()
    parser.feed(source)
    for item in parser.articles:
        if item.get("url") != url:
            continue
        title = item.get("headline")
        date = item.get("datePublished")
        if not isinstance(title, str) or not isinstance(date, str):
            continue
        title = " ".join(title.split())
        if not title or len(title) > 220 or "<" in title or ">" in title:
            continue
        try:
            day = datetime.fromisoformat(date).date().isoformat()
        except ValueError:
            continue
        return {"sourceKind": "publisher-website", "publisher": "智东西", "title": title,
                "publishedAt": day, "url": url}
    raise SourceUnavailable("article_metadata_missing")


def collect_publisher() -> dict:
    robots = read_robots(PUBLISHER)
    index = PublisherPage()
    index.feed(read_html(PUBLISHER_INDEX, robots))
    candidates = []
    errors = []
    for url in list(index.links)[:DETAIL_LIMIT]:
        try:
            candidates.append(publisher_candidate(url, read_html(url, robots)))
        except SourceUnavailable as exc:
            errors.append(str(exc))
            if str(exc) in {"http_401", "http_403", "http_429", "network_error"}:
                break
    if not candidates:
        return {"status": errors[0] if errors else "no_article_links", "candidates": [], "errors": errors}
    return {"status": "partial" if errors else "candidates_found", "candidates": candidates, "errors": errors}


def verify_original() -> dict:
    snapshot = json.loads(Path("config/innovation_wechat_media.json").read_text(encoding="utf-8"))
    approved = [row for row in snapshot if WECHAT_ARTICLE.fullmatch(row["url"])]
    if not approved:
        raise SourceUnavailable("no_approved_original")
    target = max(approved, key=lambda row: row["publishedAt"])
    parser = WeChatPageParser()
    parser.feed(read_html(target["url"], read_robots(WECHAT)))
    if not parser.content:
        raise SourceUnavailable("verification_or_unreadable_original")
    return {"status": "original_readable", "candidates": [], "errors": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("publisher", "verify-original"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = collect_publisher() if args.mode == "publisher" else verify_original()
    except SourceUnavailable as exc:
        result = {"status": str(exc), "candidates": [], "errors": []}
    args.output.write_text(json.dumps({"mode": args.mode, **result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(f"## 微信来源预览\n\n来源：`{args.mode}` · 结果：`{result['status']}`\n\n")
            for item in result["candidates"]:
                stream.write(f"- <a href=\"{html.escape(item['url'])}\">{html.escape(item['title'])}</a> · {item['publisher']} 官网 · {item['publishedAt']} · 待审核\n")
    print(f"source={args.mode} status={result['status']} candidates={len(result['candidates'])}")
    return 0 if result["status"] in {"candidates_found", "partial", "original_readable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
