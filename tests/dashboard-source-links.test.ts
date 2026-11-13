import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SourceArticleLink } from "../components/source-article-link";
import test from "node:test";

// Normalize line endings so the extraction below works on CRLF checkouts too.
const dashboard = readFileSync(new URL("../components/dashboard.tsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
const eventTitle = dashboard.match(/function EventTitle[\s\S]*?\n}\n\nfunction MarketSummary/)?.[0] ?? "";

test("homepage title delegates source navigation to the guarded link component", () => {
  assert.match(eventTitle, /<SourceArticleLink href=\{item\.source\.url\}>/);
  assert.doesNotMatch(eventTitle, /companySlug|personSlug|\/companies\/|\/people\//);

  const share = renderToStaticMarkup(createElement(SourceArticleLink, {
    href: "https://mp.weixin.qq.com/s/hNvk76l8FzVEhglIQqebJg",
  }, "已验证分享结构"));
  assert.match(share, /<a\s/u);
  assert.match(share, /target="_blank"/u);
  assert.match(share, /rel="noreferrer"/u);

  const temporary = renderToStaticMarkup(createElement(SourceArticleLink, {
    href: "https://mp.weixin.qq.com/s?new=1&signature=temp&timestamp=1794138303",
  }, "临时链接"));
  assert.match(temporary, /原文链接待更新/u);
  assert.doesNotMatch(temporary, /<a\s|href=/u);
});
