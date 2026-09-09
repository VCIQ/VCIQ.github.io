import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildSharePreferenceSyncPayload } from "../lib/share-preference-sync";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("homepage Share sends the same event payload into private preference learning", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /syncSharePreference\(homepageFeedFavoriteInput\(item\)\)/u);
  assert.match(feed, /flushPendingSharePreferences\(\)/u);
  assert.match(feed, /recordArticleShare/u);
  assert.match(feed, /vciq:favorite-share-request/u);
});

test("Share preference sync targets the protected endpoint and keeps a retry queue", async () => {
  const sync = await source("lib/share-preference-sync.ts");
  assert.match(sync, /\/api\/tracking-admin\/v1\/preferences\/share/u);
  assert.match(sync, /credentials:\s*"include"/u);
  assert.match(sync, /"content-type":\s*"text\/plain;charset=UTF-8"/u);
  assert.match(sync, /vciq:share-preference:pending:v1/u);
  assert.match(sync, /filter\(\(entry\) => entry\.item\.id !== item\.id\)/u);
});

test("Share payload preserves ranking dimensions without exposing private identity", () => {
  const payload = buildSharePreferenceSyncPayload({
    id: "daily-brief:event:event-42",
    href: "https://example.com/ai-chip",
    title: "AI chip update",
    summary: "A material update.",
    channel: "technology",
    channelLabel: "核心赛道",
    keywords: ["AI", "HBM"],
    sectors: ["半导体"],
    sources: [{ name: "Example", url: "https://example.com/ai-chip", level: "A" }],
    region: "全球",
    company: "Example Corp",
    publishedAt: "2026-09-08T00:00:00Z",
    importance: 93,
    eventType: "Technology",
  });

  assert.ok(payload);
  assert.equal(payload.item.id, "daily-brief:event:event-42");
  assert.deepEqual(payload.item.keywords, ["AI", "HBM"]);
  assert.deepEqual(payload.item.sectors, ["半导体"]);
  assert.equal(payload.item.company, "Example Corp");
  assert.equal(payload.item.eventType, "Technology");
  assert.equal("actor" in payload, false);
  assert.equal("email" in payload, false);
});
