"""Extract a short article-body excerpt without navigation/recommendation text.

No network calls; returns an excerpt, never an invented summary. Explicit body
containers outrank metadata. Unscoped paragraphs are not trusted as body text.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

VOID = {"meta", "link", "img", "br", "hr", "input", "source", "wbr", "area", "embed", "param", "track", "col", "base"}
BODY = re.compile(r"(?:^|[\s_-])(?:article[-_]?(?:body|content|detail)|post[-_]?(?:body|content)|entry[-_]content|news[-_]?(?:body|content)|content[-_]detail)(?:$|[\s_-])", re.I)
NOISE = re.compile(r"(?:^|[\s_-])(?:related|recommend(?:ed|ation)?|sidebar|breadcrumb|comment|share|footer|advert(?:isement)?|copyright)(?:$|[\s_-])", re.I)

def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

class BodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []
        self.paragraph: list[str] | None = None
        self.blocks: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        identity = str(a.get("id", "")) + " " + str(a.get("class", ""))
        parent_body = self.stack[-1][1] if self.stack else False
        parent_noise = self.stack[-1][2] if self.stack else False
        body = parent_body or tag == "article" or bool(BODY.search(identity)) or a.get("itemprop") == "articleBody"
        noise = parent_noise or tag in {"nav", "aside", "footer", "script", "style", "noscript", "form"} or bool(NOISE.search(identity))
        if tag == "meta":
            self.meta[str(a.get("property") or a.get("name") or "").lower()] = a.get("content") or ""
        if tag not in VOID:
            self.stack.append((tag, body, noise))
        if tag == "p" and body and not noise:
            self.paragraph = []

    def handle_data(self, data):
        if self.stack and self.stack[-1][1] and not self.stack[-1][2]:
            if self.paragraph is not None:
                self.paragraph.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self.paragraph is not None:
            value = clean(" ".join(self.paragraph))
            if len(value) >= 30 and not re.match(r"^(?:免责声明|相关阅读|推荐阅读|责任编辑|Copyright)", value, re.I):
                self.blocks.append(value)
            self.paragraph = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

def article_body_summary(body: str, limit: int = 500) -> str:
    parser = BodyParser()
    parser.feed(body)
    if parser.blocks:
        return clean(" ".join(parser.blocks[:3]))[:limit].rstrip()
    # Metadata is preferable to arbitrary <p>s from a sidebar or footer.
    for key in ("og:description", "twitter:description", "description"):
        candidate = clean(parser.meta.get(key, ""))
        if candidate and not re.match(r"^(?:相关阅读|相关推荐|猜你喜欢|下一篇|上一篇)", candidate):
            return candidate[:limit].rstrip()
    return ""
