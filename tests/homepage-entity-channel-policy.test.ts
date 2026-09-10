import assert from "node:assert/strict";
import test from "node:test";

import {
  buildHomepageEntityChannelSets,
  matchesHomepageCompanyEntityChannel,
  matchesHomepagePersonEntityChannel,
  normalizeHomepageEntityKey,
} from "../lib/homepage-entity-channels";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const index = buildHomepageEntityChannelSets({
  people: {
    slugs: ["jensen-huang"],
    keys: [
      normalizeHomepageEntityKey("Jensen Huang"),
      normalizeHomepageEntityKey("黄仁勋"),
    ],
  },
  companies: {
    slugs: ["nvidia"],
    keys: [
      normalizeHomepageEntityKey("NVIDIA"),
      normalizeHomepageEntityKey("英伟达"),
    ],
  },
});

function event(
  patch: Partial<LiveIntelligenceEvent> = {},
): LiveIntelligenceEvent {
  return {
    id: "event-1",
    title: "测试事件",
    summary: "测试摘要",
    type: "公司动态",
    region: "全球",
    sector: "AI / AGI",
    company: "科技产业",
    publishedAt: "2026-09-09",
    importance: 80,
    source: {
      name: "测试来源",
      url: "https://example.com/event-1",
      level: "媒体报道",
      platform: "测试",
    },
    ...patch,
  };
}

test("generic person NER does not enter the people channel", () => {
  assert.equal(
    matchesHomepagePersonEntityChannel(
      event({ type: "人物观点", mentionedPeople: ["Random Researcher"] }),
      index,
    ),
    false,
  );
});

test("formal person slugs and exact formal aliases enter the people channel", () => {
  assert.equal(
    matchesHomepagePersonEntityChannel(event({ personSlug: "jensen-huang" }), index),
    true,
  );
  assert.equal(
    matchesHomepagePersonEntityChannel(event({ mentionedPeople: ["黄仁勋"] }), index),
    true,
  );
  assert.equal(
    matchesHomepagePersonEntityChannel(event({ personSlug: "unknown-person" }), index),
    false,
  );
});

test("generic company mentions do not enter the company channel", () => {
  assert.equal(
    matchesHomepageCompanyEntityChannel(
      event({ mentionedCompanies: ["Acme Startup"] }),
      index,
    ),
    false,
  );
});

test("formal company slugs and exact formal aliases enter the company channel", () => {
  assert.equal(
    matchesHomepageCompanyEntityChannel(event({ companySlug: "nvidia" }), index),
    true,
  );
  assert.equal(
    matchesHomepageCompanyEntityChannel(event({ mentionedCompanies: ["英伟达"] }), index),
    true,
  );
  assert.equal(
    matchesHomepageCompanyEntityChannel(event({ companySlug: "unknown-company" }), index),
    false,
  );
});
