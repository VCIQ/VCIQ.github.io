import assert from "node:assert/strict";
import test from "node:test";

import {
  dailyBriefEventKey,
  dailyBriefFavoriteInput,
  dailyBriefPermalink,
  dailyBriefTrackingHref,
} from "../components/daily-brief-actions";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

function event(overrides: Partial<LiveIntelligenceEvent> = {}): LiveIntelligenceEvent {
  return {
    id: "article-a",
    title: "OpenAI 发布新的 Agent Runtime",
    summary: "OpenAI 发布新的 Agent Runtime，并同步更新开发者工具。",
    type: "产品发布",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    publishedAt: "2026-08-24",
    importance: 88,
    source: {
      name: "OpenAI",
      url: "https://openai.com/example",
      level: "官方披露",
      platform: "官网",
    },
    eventClusterId: "cluster-openai-runtime",
    mentionedCompanies: ["OpenAI"],
    mentionedPeople: ["Sam Altman"],
    matchedTrackingTerms: ["Agent Runtime"],
    relatedSources: [
      {
        name: "TechCrunch",
        url: "https://techcrunch.com/example",
        level: "媒体报道",
        platform: "媒体",
        title: "OpenAI launches runtime",
        publishedAt: "2026-08-24",
      },
    ],
    ...overrides,
  };
}

test("Daily Brief actions use the event cluster as the stable interaction key", () => {
  const first = event({ id: "article-a" });
  const second = event({ id: "article-b" });

  assert.equal(dailyBriefEventKey(first), "cluster-openai-runtime");
  assert.equal(dailyBriefEventKey(second), "cluster-openai-runtime");
  assert.equal(
    dailyBriefFavoriteInput(first).id,
    dailyBriefFavoriteInput(second).id,
  );
  assert.equal(
    dailyBriefPermalink(first),
    "/?event=cluster-openai-runtime#daily-brief",
  );
});

test("Daily Brief favorites keep event evidence and research metadata", () => {
  const favorite = dailyBriefFavoriteInput(event());

  assert.equal(favorite.channel, "technology");
  assert.equal(favorite.channelLabel, "核心技术");
  assert.equal(favorite.company, "OpenAI");
  assert.deepEqual(favorite.sectors, ["AI / AGI"]);
  assert.ok(favorite.keywords?.includes("Sam Altman"));
  assert.equal(favorite.sources?.length, 2);
  assert.equal(favorite.href, "/?event=cluster-openai-runtime#daily-brief");
});

test("Daily Brief tracking deep-link preserves the selected event context", () => {
  const href = dailyBriefTrackingHref(event());

  assert.match(href, /^https:\/\/vciq-tracking-console\.pages\.dev\//u);
  assert.match(href, /OpenAI/u);
  assert.match(href, /homepage-daily-brief/u);
});
