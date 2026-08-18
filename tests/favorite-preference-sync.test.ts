import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  bootstrapFavoritePreferenceHistory,
  buildFavoritePreferenceSyncPayload,
} from "../lib/favorite-preference-sync";

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

test("favorite history bootstrap sends one compact private preference request", async () => {
  const previousWindow = globalThis.window;
  const previousFetch = globalThis.fetch;
  const capturedBodies: Array<Record<string, unknown>> = [];

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location: { origin: "https://vciq.github.io" } },
  });
  Object.defineProperty(globalThis, "fetch", {
    configurable: true,
    value: async (_input: RequestInfo | URL, init?: RequestInit) => {
      capturedBodies.push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
      return new Response("{}", { status: 200 });
    },
  });

  try {
    const ok = await bootstrapFavoritePreferenceHistory([
      {
        id: "company-openai",
        href: "/companies/openai/",
        title: "OpenAI",
        channel: "companies",
        channelLabel: "核心公司",
        keywords: ["AI Agent"],
        savedAt: "2026-08-10T09:00:00Z",
      },
      {
        id: "technology-robotics",
        href: "/technology/robotics/",
        title: "机器人",
        channel: "technology",
        channelLabel: "核心赛道",
        sectors: ["机器人"],
        savedAt: "2026-07-20T09:00:00Z",
      },
    ]);

    assert.equal(ok, true);
    assert.equal(capturedBodies.length, 1);
    const capturedBody = capturedBodies[0] ?? {};
    assert.equal(capturedBody.bootstrap, true);
    assert.equal(Array.isArray(capturedBody.items), true);
    assert.equal((capturedBody.items as unknown[]).length, 2);
  } finally {
    if (previousWindow === undefined) Reflect.deleteProperty(globalThis, "window");
    else Object.defineProperty(globalThis, "window", { configurable: true, value: previousWindow });
    Object.defineProperty(globalThis, "fetch", { configurable: true, value: previousFetch });
  }
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
  assert.match(source, /bootstrapFavoritePreferenceHistory/);
  assert.match(source, /preferenceBootstrapStarted/);
});
