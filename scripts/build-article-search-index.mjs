#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = process.cwd();
const ARTICLE_INPUT = path.join(ROOT, "public", "data", "articles.json");
const RANKED_INPUT = path.join(ROOT, "public", "data", "ranked-intelligence.json");
const OUTPUT = path.join(ROOT, "public", "data", "article_search_index.json");

function cleanText(value, maxLength = 320) {
  if (typeof value !== "string") return "";
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function cleanList(value, itemLength = 120, maxItems = 12) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => cleanText(item, itemLength))
    .filter(Boolean)
    .slice(0, maxItems);
}

function buildArticleRecord(article) {
  const title = cleanText(article?.title, 220);
  const company = cleanText(article?.company, 100);
  const sector = cleanText(article?.sector, 80);
  const eventType = cleanText(article?.type, 40);
  const region = cleanText(article?.region, 24) || "全球";
  const sourceName = cleanText(article?.source?.name, 90);
  const publishedAt = cleanText(article?.publishedAt, 12);
  const summary = cleanText(article?.summary, 180);
  const href = article?.companySlug
    ? `/companies/${cleanText(article.companySlug, 160)}`
    : cleanText(article?.source?.url, 1000);

  if (!title || !href) return null;

  const text = cleanText(
    [company, sector, eventType, region, sourceName, publishedAt, summary]
      .filter(Boolean)
      .join(" · "),
    420,
  );

  return {
    type: "事件",
    title,
    text,
    href,
    region,
  };
}

function buildRankedRecord(item) {
  const title = cleanText(item?.title, 220);
  const href = cleanText(item?.href, 1000);
  if (!title || !href) return null;

  const sourceName = cleanText(item?.source, 90);
  const publishedAt = cleanText(item?.publishedAt, 12);
  const summary = cleanText(item?.summary, 180);
  const tracks = cleanList(item?.tracks, 80, 6);
  const eventTypes = cleanList(item?.eventTypes, 60, 8);
  const entities = Array.isArray(item?.entities)
    ? item.entities
      .map((entity) => cleanText(entity?.name, 120))
      .filter(Boolean)
      .slice(0, 10)
    : [];

  const text = cleanText(
    [
      ...entities,
      ...tracks,
      ...eventTypes,
      sourceName,
      publishedAt,
      summary,
    ]
      .filter(Boolean)
      .join(" · "),
    420,
  );

  return {
    type: "事件",
    title,
    text,
    href,
    region: "全球",
  };
}

function newestGeneratedAt(...values) {
  let best = "";
  let bestTime = Number.NEGATIVE_INFINITY;
  for (const value of values) {
    if (typeof value !== "string" || !value) continue;
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed) && parsed > bestTime) {
      best = value;
      bestTime = parsed;
    } else if (!best && !Number.isFinite(parsed)) {
      best = value;
    }
  }
  return best;
}

const articlePayload = JSON.parse(readFileSync(ARTICLE_INPUT, "utf8"));
const rankedPayload = JSON.parse(readFileSync(RANKED_INPUT, "utf8"));
const articles = Array.isArray(articlePayload?.articles) ? articlePayload.articles : [];
const rankedItems = Array.isArray(rankedPayload?.items) ? rankedPayload.items : [];

// The homepage merges ranked-intelligence.json into articles.json before rendering.
// Keep the lightweight global-search index on the same visible event universe so an
// event shown in “猜你喜欢” is always recoverable by title without loading articles.json.
const records = [
  ...articles.map(buildArticleRecord),
  ...rankedItems.map(buildRankedRecord),
].filter(Boolean);

const output = {
  schemaVersion: 1,
  generatedAt: newestGeneratedAt(articlePayload?.generatedAt, rankedPayload?.generatedAt),
  recordCount: records.length,
  records,
};

writeFileSync(OUTPUT, `${JSON.stringify(output)}\n`, "utf8");
console.log(
  `Built article search index: ${records.length} records (${articles.length} articles + ${rankedItems.length} ranked) -> ${path.relative(ROOT, OUTPUT)}`,
);
