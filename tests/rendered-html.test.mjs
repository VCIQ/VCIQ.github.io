import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { cleanSearchText, formatSearchDate } from "../scripts/search-index-format.mjs";

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

test("search result formatting cleans HTML artifacts and normalizes dates", () => {
  assert.equal(
    cleanSearchText('官方&nbsp;表示 &amp; <b>机器人</b> &#x2026;'),
    "官方 表示 & 机器人 …",
  );
  assert.equal(formatSearchDate("2026-09-14T12:34:56.000Z"), "2026-09-14");
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
      indexed.has(`${cleanSearchText(item.title, 220)}\u0000${cleanSearchText(item.href, 1000)}`),
      `ranked-intelligence item missing from global search index: ${item.title}`,
    );
  }
});

test("global search event text is presentation-safe", () => {
  const searchIndex = readJson("../public/data/article_search_index.json");

  for (const record of searchIndex.records ?? []) {
    assert.doesNotMatch(
      `${record.title} ${record.text}`,
      /&(?:nbsp|amp|quot|apos|lt|gt|hellip|ldquo|rdquo|lsquo|rsquo|#\d+|#x[0-9a-f]+);/iu,
      `HTML entity leaked into search result: ${record.title}`,
    );
    assert.doesNotMatch(
      record.text ?? "",
      /\b\d{4}-\d{2}-\d{2}T\d/u,
      `raw ISO timestamp leaked into search result metadata: ${record.title}`,
    );
  }
});
