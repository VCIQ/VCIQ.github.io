import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildSharePreferencePayload } from "../lib/share-preference-sync";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("only Recommendation is personalization-first; all scoped channels are newest-first", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /if \(channel !== "recommend"\)/u);
  assert.match(feed, /right\.publishedAt\.localeCompare\(left\.publishedAt\)[\s\S]*right\.importance - left\.importance/u);
  assert.match(feed, /personalizedHomepageRecommendationScore\(right, preferences, favoriteProfile\)/u);
  assert.match(feed, /const hero = index === 0 && !normalizedQuery && channel === "recommend"/u);
  assert.match(feed, /推荐频道按个性化价值排序；关注、快讯与专题频道以最新信息优先/u);
});

test("right rail is a 45-day missed-signal recommender rather than a today-only top list", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /const MISSED_SIGNAL_WINDOW_DAYS = 45/u);
  assert.match(feed, /const CURRENT_RECOMMENDATION_EXCLUSION = 12/u);
  assert.match(feed, /currentRecommendationKeys/u);
  assert.match(feed, /favoriteHrefKeys\.has\(key\)/u);
  assert.match(feed, /!engagement\?\.shares/u);
  assert.match(feed, /\(engagement\?\.opens \?\? 0\) < 2/u);
  assert.match(feed, /aria-label="猜你喜欢｜你可能错过的重要信号"/u);
  assert.match(feed, /FOR YOU · MISSED SIGNALS/u);
  assert.match(feed, /<strong>猜你喜欢<\/strong>/u);
  assert.doesNotMatch(feed, /今日重大信号 TOP 10/u);
});

test("homepage Share keeps local UX and also sends best-effort private preference learning", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  const sync = await source("lib/share-preference-sync.ts");
  assert.match(feed, /recordArticleShare/u);
  assert.match(feed, /syncSharePreference/u);
  assert.match(feed, /flushPendingSharePreferences/u);
  assert.match(sync, /\/api\/tracking-admin\/v1\/preferences\/share/u);
  assert.match(sync, /credentials: "include"/u);
  assert.match(sync, /"content-type": "text\/plain;charset=UTF-8"/u);
  assert.match(sync, /vciq:share-preference:pending:v1/u);
  assert.match(sync, /canonicalHotnessKey/u);
});

test("Share identity is canonical by article URL rather than surface-local id", () => {
  const first = buildSharePreferencePayload({
    id: "homepage-event-123",
    href: "https://example.com/news/42?utm_source=homepage&ref=feed",
    title: "Same article",
  });
  const second = buildSharePreferencePayload({
    id: "hot-page-item-987",
    href: "https://example.com/news/42?utm_medium=hot",
    title: "Same article",
  });

  assert.ok(first && second);
  assert.equal(first.item.id, "https://example.com/news/42");
  assert.equal(second.item.id, first.item.id);
});
