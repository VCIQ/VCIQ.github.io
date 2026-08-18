import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildFavoritePreferenceSyncPayload } from "../lib/favorite-preference-sync";

test("favorite preference payload resolves internal VCIQ links to public URLs", () => {
  const payload = buildFavoritePreferenceSyncPayload("save", {
    id: "company-openai",
    href: "/companies/openai/",
    title: "OpenAI",
    summary: "AI research company",
    channel: "companies",
    channelLabel: "核心公司",
    keywords: ["AI Agent"],
    sectors: ["AI / AGI"],
    sources: [{ name: "OpenAI", url: "https://openai.com/" }],
    company: "OpenAI",
    eventType: "Technology",
    savedAt: "2026-08-18T09:00:00Z",
  }, "https://vciq.github.io");

  assert.equal(payload?.action, "save");
  assert.equal(payload?.item.href, "https://vciq.github.io/companies/openai/");
  assert.deepEqual(payload?.item.keywords, ["AI Agent"]);
  assert.equal("email" in (payload?.item ?? {}), false);
  assert.equal("token" in (payload?.item ?? {}), false);
});

test("invalid favorite links are never sent to the preference endpoint", () => {
  const payload = buildFavoritePreferenceSyncPayload("save", {
    id: "bad",
    href: "javascript:alert(1)",
    title: "Bad",
    channel: "reports",
    channelLabel: "研究报告",
  }, "https://vciq.github.io");
  assert.equal(payload, null);
});

test("favorite UX writes local storage before best-effort preference sync", async () => {
  const source = await readFile(new URL("../lib/favorites.ts", import.meta.url), "utf8");
  const saveLocal = source.indexOf("writeFavoriteItems([item");
  const saveRemote = source.indexOf('syncFavoritePreference("save", item)');
  const removeLocal = source.indexOf("writeFavoriteItems(current.filter", source.indexOf("existingItem"));
  const removeRemote = source.indexOf('syncFavoritePreference("remove", existingItem)');

  assert.ok(saveLocal >= 0 && saveRemote > saveLocal);
  assert.ok(removeLocal >= 0 && removeRemote > removeLocal);
  assert.match(source, /void syncFavoritePreference/);
});
