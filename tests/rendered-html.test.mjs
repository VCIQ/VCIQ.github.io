import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const developmentPreviewMeta =
  /<meta(?=[^>]*\bname=["']codex-preview["'])(?=[^>]*\bcontent=["']development["'])[^>]*>/i;

function readJson(relativeUrl) {
  return JSON.parse(readFileSync(new URL(relativeUrl, import.meta.url), "utf8"));
}

test("renders development preview metadata", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  const response = await worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  assert.equal(response.status, 200);
  assert.match(
    response.headers.get("content-type") ?? "",
    /^text\/html\b/i,
  );
  assert.match(await response.text(), developmentPreviewMeta);
});

test("global search index covers ranked-intelligence events visible on the homepage", () => {
  const searchIndex = readJson("../public/data/article_search_index.json");
  const ranked = readJson("../public/data/ranked-intelligence.json");
  const indexed = new Set(
    (searchIndex.records ?? []).map((record) => `${record.title}\u0000${record.href}`),
  );

  for (const item of ranked.items ?? []) {
    if (typeof item?.title !== "string" || typeof item?.href !== "string") continue;
    assert.ok(
      indexed.has(`${item.title.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, 220)}\u0000${item.href.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, 1000)}`),
      `ranked-intelligence item missing from global search index: ${item.title}`,
    );
  }
});
