import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {
  projectReviewedInvestorHomepageEvents,
  mergeReviewedInvestorHomepageEvents,
} from "../lib/homepage-investor-reviewed-events";
import original from "../config/innovation_investor_evidence.json";

const read = (file: string) => fs.readFileSync(new URL("../" + file, import.meta.url), "utf8");
const time = Date.parse("2026-10-10T12:00:00Z");

test("recent official original disclosures reach homepage; no portfolio, fund or retrospective record", () => {
  const items = projectReviewedInvestorHomepageEvents(original.records, time);
  const urls = new Set(items.map(i => i.source.url.toLowerCase().replace(/\/$/u, "")));
  assert.equal(items.length, urls.size);
  assert.ok(items.some(i => i.id === "investor-reviewed:a16z-typesafe-ai-investment-2026"));
  assert.ok(items.some(i => i.id === "investor-reviewed:eclipse-oxide-series-d-2026"));
  assert.ok(items.every(i => i.source.level === "官方披露" && i.sourceId === "investor-reviewed-evidence"));
  assert.ok(items.every(i => !i.id.includes("utec-eureka-portfolio") && !i.id.includes("graphcore")));
  assert.ok(items.every(i => Date.parse(i.publishedAt) <= time));
});

test("one official article carrying a deal and a viewpoint yields only one homepage item", () => {
  const items = projectReviewedInvestorHomepageEvents(original.records, time);
  const typesafe = items.filter(i => i.source.url.includes("investing-in-typesafe-ai"));
  const oxide = items.filter(i => i.source.url.includes("built-for-the-compute-ownership-era"));
  assert.equal(typesafe.length, 1);
  assert.equal(oxide.length, 1);
  assert.equal(typesafe[0].type, "产业投资");
  assert.equal(oxide[0].type, "产业投资");
});

test("retrospective evidence date and unclear original date can never appear as new today", () => {
  const sample = original.records.find(r => r.id === "a16z-typesafe-ai-investment-2026")!;
  const candidates = [
    {...sample, id: "retro", date: "2020-01-01"},
    {...sample, id: "year", datePrecision: "year"},
    {...sample, id: "no-locator", source: {...sample.source, locator: ""}},
    {...sample, id: "no-publishedAt", source: {...sample.source, publishedAt: null}},
    {...sample, id: "different-kind", kind: "portfolio-relationship"},
  ];
  assert.deepEqual(projectReviewedInvestorHomepageEvents(candidates as typeof original.records, time), []);
});

test("old releases are not replayed after the publication freshness window", () => {
  const items = projectReviewedInvestorHomepageEvents(original.records, Date.parse("2027-01-01T00:00:00Z"));
  assert.deepEqual(items, []);
});

test("canonical article takes precedence; other reviewed originals remain visible after live archive loads", () => {
  const items = projectReviewedInvestorHomepageEvents(original.records, time);
  const existing = {...items[0], id: "canonical-news"}; 
  const merged = mergeReviewedInvestorHomepageEvents([existing], items);
  assert.equal(merged.filter(x => x.source.url === existing.source.url).length, 1);
  assert.equal(merged[0].id, "canonical-news");
  assert.ok(merged.some(x => x.sourceId === "investor-reviewed-evidence"));
});

test("homepage integration is routed via normal innovation and personalized focus policies", () => {
  const page = read("app/page.tsx");
  const feed = read("components/homepage-news-feed.tsx");
  assert.match(page, /investorEnrichedInnovationFeed/);
  assert.match(page, /investorEvents=\{investorHomepageEvents\}/);
  assert.match(feed, /mergeReviewedInvestorHomepageEvents\(articles, investorEvents\)/);
  assert.match(feed, /mergePriorityCandidates\(\s*allArticles,/);
  assert.match(feed, /matchesHomepageInnovationCapitalChannel\(item, innovationCapital\)/);
  assert.match(feed, /buildHomepageFocusSelection/);
  assert.doesNotMatch(page, /innovation-investor-review-queue\.json/);
});
