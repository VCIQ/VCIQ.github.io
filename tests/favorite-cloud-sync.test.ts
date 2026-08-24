import assert from "node:assert/strict";
import test from "node:test";

import { mergeFavoriteCloudRecords } from "../lib/favorite-cloud-sync";
import type { FavoriteCloudRecord } from "../lib/favorite-preference-sync";
import type { FavoriteItem } from "../lib/favorites";

function localFavorite(overrides: Partial<FavoriteItem> = {}): FavoriteItem {
  return {
    id: "favorite-a",
    href: "https://vciq.github.io/companies/openai/",
    title: "OpenAI",
    summary: "本地保存的完整摘要",
    channel: "companies",
    channelLabel: "核心公司",
    keywords: ["AI Agent"],
    sectors: ["AI / AGI"],
    sources: [{ name: "OpenAI", url: "https://openai.com/", level: "官方披露" }],
    region: "美国",
    company: "OpenAI",
    publishedAt: "2026-08-24",
    importance: 88,
    eventType: "公司动态",
    savedAt: "2026-08-24T08:00:00.000Z",
    ...overrides,
  };
}

function cloudRecord(
  action: FavoriteCloudRecord["action"],
  overrides: Partial<FavoriteCloudRecord["item"]> = {},
): FavoriteCloudRecord {
  return {
    action,
    updatedAt: "2026-08-24T10:00:00.000Z",
    item: {
      id: "favorite-a",
      href: "https://vciq.github.io/companies/openai/",
      title: "OpenAI",
      summary: "云端摘要",
      channel: "companies",
      channelLabel: "核心公司",
      keywords: ["AI Agent"],
      sectors: ["AI / AGI"],
      sources: [{ name: "OpenAI", url: "https://openai.com/", level: "官方披露" }],
      region: "美国",
      company: "OpenAI",
      publishedAt: "2026-08-24",
      importance: 88,
      eventType: "公司动态",
      savedAt: "2026-08-24T08:00:00.000Z",
      ...overrides,
    },
  };
}

test("empty browser restores active cloud favorites", () => {
  const result = mergeFavoriteCloudRecords([], [
    cloudRecord("save"),
    cloudRecord("save", {
      id: "favorite-b",
      href: "https://vciq.github.io/companies/anthropic/",
      title: "Anthropic",
      company: "Anthropic",
      savedAt: "2026-08-24T09:00:00.000Z",
    }),
  ]);

  assert.equal(result.items.length, 2);
  assert.equal(result.restored, 2);
  assert.equal(result.removed, 0);
  assert.deepEqual(
    new Set(result.items.map((item) => item.id)),
    new Set(["favorite-a", "favorite-b"]),
  );
});

test("cloud remove tombstone deletes stale browser favorite", () => {
  const result = mergeFavoriteCloudRecords(
    [localFavorite()],
    [cloudRecord("remove")],
  );

  assert.equal(result.items.length, 0);
  assert.equal(result.restored, 0);
  assert.equal(result.removed, 1);
});

test("cloud save keeps richer local fields when legacy cloud record is sparse", () => {
  const result = mergeFavoriteCloudRecords(
    [localFavorite()],
    [cloudRecord("save", {
      summary: "",
      keywords: [],
      sectors: [],
      sources: [],
      region: "",
      company: "",
      publishedAt: "",
      eventType: "",
    })],
  );

  assert.equal(result.items.length, 1);
  assert.equal(result.restored, 0);
  assert.equal(result.items[0].summary, "本地保存的完整摘要");
  assert.deepEqual(result.items[0].keywords, ["AI Agent"]);
  assert.deepEqual(result.items[0].sectors, ["AI / AGI"]);
  assert.equal(result.items[0].sources[0].url, "https://openai.com/");
  assert.equal(result.items[0].publishedAt, "2026-08-24");
});
