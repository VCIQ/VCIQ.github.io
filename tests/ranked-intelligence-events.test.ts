import assert from "node:assert/strict";
import test from "node:test";

import {
  areLikelySameHomepageEvent,
  mergeRankedIntelligenceIntoArticlePayload,
  parseRankedIntelligenceProjection,
  rankedIntelligenceItemToArticle,
} from "../lib/ranked-intelligence";
import type { ArticlePayload, LiveIntelligenceEvent } from "../lib/use-articles";

function canonicalTeenEvent(): LiveIntelligenceEvent {
  return {
    id: "canonical-teen",
    title: "OpenAI 推出 ChatGPT 青少年版，加强家长控制与安全防护",
    summary: "canonical summary",
    type: "产品发布",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    publishedAt: "2026-08-18",
    importance: 88,
    source: {
      name: "OpenAI News",
      url: "https://openai.com/news/teen-chatgpt",
      level: "官方披露",
      platform: "公司官网",
    },
    mentionedCompanies: ["OpenAI"],
    matchedTrackingTerms: ["ChatGPT"],
    eventClusterId: "crawler-event-teen",
    duplicateCount: 1,
  };
}

function teenProjection() {
  return {
    schemaVersion: 1,
    generatedAt: "2026-08-18T16:00:00Z",
    source: "google-alerts-rss",
    contentHash: "event-hash",
    items: [{
      id: "intel-event-private",
      title: "OpenAI收紧青少年使用ChatGPT限制：推出专属版本强化安全防护",
      summary: "media summary",
      href: "https://eastmoney.example/openai-teen",
      source: "东方财富",
      publishedAt: "2026-08-18T14:05:00Z",
      priority: "P0",
      score: 100,
      eventTypes: ["Product"],
      entities: [
        { objectType: "company", name: "OpenAI" },
        { objectType: "technology", name: "ChatGPT" },
      ],
      tracks: ["AI / AGI"],
      eventClusterId: "intel-event-private",
      duplicateCount: 3,
      relatedSources: [{
        source: "搜狐",
        href: "https://sohu.example/openai-teen",
        title: "OpenAI收紧青少年使用ChatGPT限制：推出专属版加强安全防护",
        publishedAt: "2026-08-18T11:48:00Z",
      }, {
        source: "163.com",
        href: "https://163.example/chatgpt-teen",
        title: "ChatGPT 推出青少年版_网易视频",
        publishedAt: "2026-08-18T12:20:00Z",
      }],
    }],
  } as const;
}

test("public projection maps folded source evidence onto the homepage event", () => {
  const item = parseRankedIntelligenceProjection(teenProjection()).items[0];
  const article = rankedIntelligenceItemToArticle(item);
  assert.equal(article.eventClusterId, "intel-event-private");
  assert.equal(article.duplicateCount, 3);
  assert.equal(article.relatedSources?.length, 2);
  assert.equal(article.relatedSources?.[0].name, "搜狐");
  assert.equal(article.relatedSources?.[0].platform, "Google Alerts RSS");
});

test("cross-pipeline versions of the screenshot event are semantically the same event", () => {
  const canonical = canonicalTeenEvent();
  const projected = rankedIntelligenceItemToArticle(
    parseRankedIntelligenceProjection(teenProjection()).items[0],
  );
  assert.equal(areLikelySameHomepageEvent(canonical, projected), true);
});

test("semantic merge keeps one canonical event card and folds all publisher evidence", () => {
  const canonical = canonicalTeenEvent();
  const payload: ArticlePayload = {
    schemaVersion: 1,
    generatedAt: "2026-08-18T15:00:00Z",
    articleCount: 1,
    articles: [canonical],
  };
  const merged = mergeRankedIntelligenceIntoArticlePayload(payload, teenProjection());
  assert.equal(merged.articleCount, 1);
  const event = merged.articles[0];
  assert.equal(event.id, "canonical-teen");
  assert.equal(event.importance, 100);
  assert.equal(event.eventClusterId, "crawler-event-teen");
  assert.equal(event.duplicateCount, 4);
  assert.deepEqual(
    event.relatedSources?.map((source) => source.name),
    ["东方财富", "搜狐", "163.com"],
  );
});

test("same company and event type do not collapse unrelated product launches", () => {
  const teen = canonicalTeenEvent();
  const voice: LiveIntelligenceEvent = {
    ...canonicalTeenEvent(),
    id: "voice",
    title: "OpenAI 为 ChatGPT 推出全新实时语音翻译功能",
    source: { ...canonicalTeenEvent().source, url: "https://openai.com/news/voice-translation" },
    eventClusterId: "crawler-event-voice-translation",
  };
  assert.equal(areLikelySameHomepageEvent(teen, voice), false);
});
