import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function source(path: string) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("reviewed WeChat media and project page use the same safe public link", () => {
  assert.match(source("components/homepage-news-feed.tsx"),
    /<SourceArticleLink href=\{item\.url\}>\{item\.title\}/u);
  assert.match(source("app/innovation-capital/page.tsx"),
    /<SourceArticleLink href=\{item\.url\}>查看微信原文/u);
});

test("saved and researched links cannot re-open an expiring search redirect", () => {
  const favorites = source("components/favorites-page.tsx");
  assert.match(favorites, /<SourceArticleLink[\s\S]*?fallbackAs="div"/u);
  assert.match(favorites, /function SafeFavoriteCardLink/u);
  assert.match(favorites, /isNonDurableWeChatArticleUrl\(item\.href\)/u);
  const sharing = source("components/wechat-share-compat.tsx");
  assert.match(sharing, /isNonDurableWeChatArticleUrl\(normalized\.url\)/u);
  assert.match(sharing, /disabled=\{sourceUnavailable\}/u);
  assert.match(sharing, /sourceUnavailable\s*\?\s*\(/u);
});

test("directory source links preserve audit data but block stale originals", () => {
  const directory = source("components/channel-update-directory-client.tsx");
  assert.match(directory, /<SourceArticleLink[\s\S]*?fallbackAs="div"/u);
  assert.match(directory, /<SourceArticleLink[\s\S]*?href=\{source\.href\}/u);
  assert.match(directory, /disabled=\{isNonDurableWeChatArticleUrl\(item\.href\)\}/u);
});
