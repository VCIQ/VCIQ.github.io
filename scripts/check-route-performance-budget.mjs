#!/usr/bin/env node

import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "out");

const DEFAULT_BUDGET = {
  maxSingleScriptBytes: 260_000,
  maxTotalScriptBytes: 1_000_000,
  maxHtmlBytes: 650_000,
};

const ROUTES = [
  ["/", "index.html", { maxHtmlBytes: 250_000 }],
  ["/search/", "search/index.html", { maxHtmlBytes: 100_000 }],
  ["/hot/", "hot/index.html", { maxHtmlBytes: 750_000 }],
  ["/favorites/", "favorites/index.html", { maxHtmlBytes: 80_000 }],
  // The technology object directory intentionally carries its bounded
  // build-time catalog. Keep a route-specific ceiling above the current
  // ~130 KB baseline without weakening the default 100 KB budget elsewhere.
  ["/technologies/", "technologies/index.html", { maxHtmlBytes: 150_000 }],
  ["/technology/", "technology/index.html", { maxHtmlBytes: 600_000 }],
  ["/people/", "people/index.html", { maxHtmlBytes: 450_000 }],
  ["/companies/", "companies/index.html", { maxHtmlBytes: 600_000 }],
];

const MAX_SEARCH_INDEX_BYTES = Number(
  process.env.SEARCH_INDEX_MAX_BYTES ?? 600_000,
);

let failed = false;

function fail(message) {
  failed = true;
  console.error(`ROUTE_PERFORMANCE_BUDGET_ERROR: ${message}`);
}

function localScriptSources(html) {
  return [
    ...new Set(
      [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)]
        .map((match) => match[1])
        .filter((source) => source.startsWith("/")),
    ),
  ];
}

function routeMetrics(route, relativeHtml, overrides) {
  const htmlPath = path.join(OUT, relativeHtml);
  const html = readFileSync(htmlPath, "utf8");
  const htmlBytes = statSync(htmlPath).size;
  const sources = localScriptSources(html);
  if (!sources.length) {
    fail(`${route} contains no local script assets`);
    return null;
  }

  const assets = sources.map((source) => {
    const relative = source.replace(/^\/+/, "");
    const file = path.join(OUT, relative);
    return { source, bytes: statSync(file).size };
  });
  const totalScriptBytes = assets.reduce((sum, asset) => sum + asset.bytes, 0);
  const largest = [...assets].sort((left, right) => right.bytes - left.bytes)[0];
  const budget = { ...DEFAULT_BUDGET, ...overrides };

  if ((largest?.bytes ?? 0) > budget.maxSingleScriptBytes) {
    fail(
      `${route} largest script ${largest.bytes} bytes (${largest.source}) exceeds ${budget.maxSingleScriptBytes}`,
    );
  }
  if (totalScriptBytes > budget.maxTotalScriptBytes) {
    fail(`${route} scripts total ${totalScriptBytes} bytes exceeds ${budget.maxTotalScriptBytes}`);
  }
  if (htmlBytes > budget.maxHtmlBytes) {
    fail(`${route} HTML ${htmlBytes} bytes exceeds ${budget.maxHtmlBytes}`);
  }

  return {
    route,
    htmlBytes,
    scriptCount: assets.length,
    totalScriptBytes,
    maxSingleScriptBytes: largest?.bytes ?? 0,
    largestScript: largest?.source ?? "",
    budget,
  };
}

const metrics = ROUTES.map(([route, html, overrides]) =>
  routeMetrics(route, html, overrides),
).filter(Boolean);

const searchIndexPath = path.join(OUT, "data", "article_search_index.json");
const searchIndexBytes = statSync(searchIndexPath).size;
if (searchIndexBytes > MAX_SEARCH_INDEX_BYTES) {
  fail(`article_search_index.json is ${searchIndexBytes} bytes; budget is ${MAX_SEARCH_INDEX_BYTES}`);
}

console.log(
  JSON.stringify(
    {
      routes: metrics,
      searchIndex: {
        bytes: searchIndexBytes,
        budget: MAX_SEARCH_INDEX_BYTES,
      },
    },
    null,
    2,
  ),
);

if (failed) process.exitCode = 1;
