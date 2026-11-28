"""Bounded, best-effort extraction of public publisher article evidence."""
from __future__ import annotations

import ipaddress
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit


def is_safe_public_http_url(url: str) -> bool:
    try:
        parts = urlsplit(str(url or ""))
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return False
        host = parts.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return True
        return address.is_global
    except ValueError:
        return False


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self._jsonld_buffer: list[str] = []
        self._in_title = False
        self._title_buffer: list[str] = []
        self._skip_depth = 0
        self._text_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "meta":
            key = (attrs_map.get("property") or attrs_map.get("name") or "").lower()
            value = attrs_map.get("content", "").strip()
            if key and value and key in {
                "og:title", "og:description", "description",
                "article:published_time", "article:modified_time",
            }:
                self.meta[key] = value[:2000]
        if tag.lower() == "script" and "ld+json" in attrs_map.get("type", "").lower():
            self._in_jsonld = True
            self._jsonld_buffer = []
        if tag.lower() == "title":
            self._in_title = True
            self._title_buffer = []
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._jsonld_buffer))
            self._jsonld_buffer = []
            self._in_jsonld = False
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_buffer.append(data)
        elif self._in_title:
            self._title_buffer.append(data)
        elif not self._skip_depth:
            value = re.sub(r"\s+", " ", data).strip()
            if value:
                self._text_buffer.append(value)

    def result(self) -> dict[str, Any]:
        title = " ".join(" ".join(self._title_buffer).split())[:500]
        article_bodies: list[str] = []
        for raw in self.jsonld:
            try:
                parsed = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            objects = parsed if isinstance(parsed, list) else [parsed]
            for obj in objects:
                if isinstance(obj, dict):
                    graph = obj.get("@graph", [])
                    objects.extend(graph if isinstance(graph, list) else [])
                    body = obj.get("articleBody")
                    if isinstance(body, str) and body.strip():
                        article_bodies.append(body.strip()[:12000])
        body = max(article_bodies, key=len) if article_bodies else ""
        visible = " ".join(" ".join(self._text_buffer).split())[:12000]
        return {
            "htmlTitle": title or self.meta.get("og:title"),
            "metaDescription": self.meta.get("og:description") or self.meta.get("description"),
            "publishedTime": self.meta.get("article:published_time"),
            "modifiedTime": self.meta.get("article:modified_time"),
            "articleBody": body or visible,
            "bodyExtractionMethod": "jsonld_articleBody" if body else ("visible_text_fallback" if visible else "metadata_only"),
        }


def extract_article_evidence(html: str) -> dict[str, Any]:
    parser = _ArticleParser()
    parser.feed(str(html or "")[:1_000_000])
    return parser.result()
