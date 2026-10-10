import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import { projectReviewedInvestorHomepageEvents, REVIEWED_INVESTOR_EVENT_PREFIX } from "../lib/homepage-reviewed-investor-events";
import evidence from "../config/innovation_investor_evidence.json";

test("only dated official investment records within 14 days become homepage publication events", () => {
  const rows = projectReviewedInvestorHomepageEvents(evidence.records, new Date("2026-10-10T12:00:00Z"));
  assert.ok(rows.length >= 2);
  const typeSafe = rows.find((x) => x.id === REVIEWED_INVESTOR_EVENT_PREFIX + "a16z-typesafe-ai-investment-2026");
  const oxide = rows.find((x) => x.id === REVIEWED_INVESTOR_EVENT_PREFIX + "eclipse-oxide-series-d-2026");
  assert.ok(typeSafe);
  assert.ok(oxide);
  assert.equal(typeSafe.publishedAt, "2026-10-09");
  assert.equal(typeSafe.type, "产业投资");
  assert.equal(typeSafe.region, "全球");
  assert.equal(typeSafe.source.level, "官方披露");
  assert.equal(oxide.source.url, "https://eclipse.capital/blog/built-for-the-compute-ownership-era");
  assert.ok(rows.every((x) => x.id.startsWith(REVIEWED_INVESTOR_EVENT_PREFIX)));
  assert.ok(rows.every((x) => !x.curated));
  assert.ok(rows.every((x) => x.qualityStatus === "高可信"));
  assert.equal(rows.filter((x) => x.source.url === typeSafe.source.url).length, 1);
  assert.equal(rows.some((x) => x.type === "人物观点"), false);
});

test("historic IPO, company-reported outcomes, viewpoints and homepage navigation are never synthetic investment news", () => {
  const rows = projectReviewedInvestorHomepageEvents(evidence.records, new Date("2026-10-10T12:00:00Z"));
  assert.equal(rows.some((x) => x.title.includes("2017")), false);
  assert.equal(rows.some((x) => x.id.includes("mechmind-hk-listing")), false);
  assert.equal(rows.some((x) => x.id.includes("-thesis-")), false);
  assert.equal(rows.some((x) => x.id.includes("portfolio-relationship")), false);
  assert.ok(rows.every((x) => x.importance >= 75));
  assert.ok(rows.every((x) => x.mentionedPeople === undefined && x.matchedTrackingTerms === undefined));
});

test("unverified links, future dates, old material, missing original publication date and media reports fail closed", () => {
  const base = evidence.records.find((x) => x.id === "eclipse-oxide-series-d-2026")!;
  const rows = [
    {...base, id:"a", date:"2025-10-09"},
    {...base, id:"b", date:"2026-10-20"},
    {...base, id:"c", source:{...base.source, publishedAt:null}},
    {...base, id:"d", source:{...base.source, kind:"investor-hosted-media-report"}},
    {...base, id:"e", kind:"viewpoint"},
  ];
  assert.deepEqual(projectReviewedInvestorHomepageEvents(rows, new Date("2026-10-10T12:00:00Z")), []);
});

test("homepage switches visibility by channel without relaxing focus admission rules", () => {
  const page = fs.readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
  const feed = fs.readFileSync(new URL("../components/homepage-news-feed.tsx", import.meta.url), "utf8");
  assert.match(page, /reviewedInvestorEvents=\{reviewedInvestorEvents\}/);
  assert.match(feed, /item.id.startsWith\(REVIEWED_INVESTOR_EVENT_PREFIX\)/);
  assert.match(feed, /buildHomepageFocusSelection/);
  assert.doesNotMatch(feed, /priorityFeed.*reviewedInvestorEvents|matchedTrackingTerms:\s*\[/);
});
