#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { cleanSearchText, formatSearchDate } from "./search-index-format.mjs";

const ROOT = process.cwd();
const ARTICLE_INPUT = path.join(ROOT, "public", "data", "articles.json");
const RANKED_INPUT = path.join(ROOT, "public", "data", "ranked-intelligence.json");
const OUTPUT = path.join(ROOT, "public", "data", "article_search_index.json");

function cleanList(value, itemLength = 120, maxItems = 12) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => cleanSearchText(item, itemLength))
    .filter(Boolean)
    .slice(0, maxItems);
}

function uniqueText(values) {
  const seen = new Set();
  return values.filter((value) => {
    const cleaned = cleanSearchText(value, 160);
    const key = cleaned.toLocaleLowerCase("zh-CN");
    if (!cleaned || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function buildArticleRecord(article) {
  const title = cleanSearchText(article?.title, 220);
  const company = cleanSearchText(article?.company, 100);
  const sector = cleanSearchText(article?.sector, 80);
  const eventType = cleanSearchText(article?.type, 40);
  const region = cleanSearchText(article?.region, 24) || "全球";
  const sourceName = cleanSearchText(article?.source?.name, 90);
  const publishedAt = formatSearchDate(article?.publishedAt);
  const summary = cleanSearchText(article?.summary, 180);
  const href = article?.companySlug
    ? `/companies/${cleanSearchText(article.companySlug, 160)}`
    : cleanSearchText(article?.source?.url, 1000);

  if (!title || !href) return null;

  const text = cleanSearchText(
    uniqueText([company, sector, eventType, sourceName, publishedAt, summary])
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
  const title = cleanSearchText(item?.title, 220);
  const href = cleanSearchText(item?.href, 1000);
  if (!title || !href) return null;

  const sourceName = cleanSearchText(item?.source, 90);
  const publishedAt = formatSearchDate(item?.publishedAt);
  const summary = cleanSearchText(item?.summary, 180);
  const tracks = cleanList(item?.tracks, 80, 2);
  const eventTypes = cleanList(item?.eventTypes, 60, 2);
  const entities = Array.isArray(item?.entities)
    ? item.entities
      .map((entity) => cleanSearchText(entity?.name, 120))
      .filter(Boolean)
      .slice(0, 2)
    : [];

  const text = cleanSearchText(
    uniqueText([
      ...entities,
      ...tracks,
      ...eventTypes,
      sourceName,
      publishedAt,
      summary,
    ])
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
