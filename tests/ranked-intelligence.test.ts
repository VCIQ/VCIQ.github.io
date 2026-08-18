import assert from "node:assert/strict";
import test from "node:test";

import {
  mergeRankedIntelligenceIntoArticlePayload,
  parseRankedIntelligenceProjection,
  rankedIntelligenceItemToArticle,
} from "../lib/ranked-intelligence";
import type { ArticlePayload } from "../lib/use-articles";

const projection = {
  schemaVersion: 1,
  generatedAt: "2026-08-18T06:00:00Z",
  source: "google-alerts-rss",
  contentHash: "abc",
  items: [{
    id: "story-1",
    title: "OpenAI 发布新产品",
    summary: "来自 Google Alerts RSS 的高相关公开情报。",
    href: "https://example.com/story-1",
    source: "Example Media",
    publishedAt: "2026-08-18T05:00:00Z",
    priority: "P0",
    score: 96,
    eventTypes: ["Product"],
    entities: [
      { objectType: "company", name: "OpenAI" },
      { objectType: "technology", name: "ChatGPT" },
    ],
    tracks: ["AI / AGI"],
  }],
} as const;

function basePayload(): ArticlePayload {
  return {
    schemaVersion: 1,
    generatedAt: "2026-08-18T04:00:00Z",
    articleCount: 0,
    articles: [],
    sourceStatus: [],
  };
}

test("parses the public-safe ranked intelligence contract", () => {
  const parsed = parseRankedIntelligenceProjection(projection);
  assert.equal(parsed.items.length, 1);
  assert.equal(parsed.items[0].score, 96);
  assert.equal(parsed.items[0].href, "https://example.com/story-1");
});

test("maps ranked intelligence to homepage article semantics", () => {
  const item = parseRankedIntelligenceProjection(projection).items[0];
  const article = rankedIntelligenceItemToArticle(item);
  assert.equal(article.type, "产品发布");
  assert.equal(article.company, "OpenAI");
  assert.equal(article.sector, "AI / AGI");
  assert.equal(article.importance, 96);
  assert.equal(article.curated, true);
  assert.equal(article.source.platform, "Google Alerts RSS");
  assert.deepEqual(article.matchedTrackingTerms, ["ChatGPT", "AI / AGI"]);
});

test("adds a new ranked intelligence article without mutating canonical payload", () => {
  const base = basePayload();
  const merged = mergeRankedIntelligenceIntoArticlePayload(base, projection);
  assert.equal(base.articles.length, 0);
  assert.equal(merged.articleCount, 1);
  assert.equal(merged.articles[0].title, "OpenAI 发布新产品");
});

test("dedupes by canonical publisher URL and boosts an existing event", () => {
  const base = basePayload();
  base.articleCount = 1;
  base.articles = [{
    id: "canonical-1",
    title: "OpenAI 发布新产品",
    summary: "原始抓取摘要",
    type: "公司动态",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    publishedAt: "2026-08-18",
    importance: 70,
    source: {
      name: "Example Media",
      url: "https://example.com/story-1#tracking-fragment",
      level: "媒体报道",
      platform: "专业媒体",
    },
    matchedTrackingTerms: ["OpenAI"],
  }];

  const merged = mergeRankedIntelligenceIntoArticlePayload(base, projection);
  assert.equal(merged.articleCount, 1);
  assert.equal(merged.articles[0].id, "canonical-1");
  assert.equal(merged.articles[0].importance, 96);
  assert.equal(merged.articles[0].curated, true);
  assert.deepEqual(merged.articles[0].matchedTrackingTerms, ["OpenAI", "ChatGPT", "AI / AGI"]);
});

test("malformed optional projection fails open to canonical article data", () => {
  const base = basePayload();
  const merged = mergeRankedIntelligenceIntoArticlePayload(base, { schemaVersion: 2 });
  assert.equal(merged, base);
});
