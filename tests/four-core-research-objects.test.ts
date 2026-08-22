import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  coreResearchObjectStats,
  coreTechnologyEntities,
} from "../lib/core-research-objects";
import { publishedTrackingResearchEntities } from "../lib/published-tracking-entity-research";
import { technologyTopicDefinitions } from "../lib/technology-topics";
import { trackedSectors } from "../lib/tracked-sectors";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath: string) =>
  fs.readFileSync(path.join(root, relativePath), "utf8");

test("primary navigation exposes one technology research channel plus people and companies", () => {
  const source = read("components/site-header.tsx");
  for (const label of ["科技研究", "核心人物", "核心公司"]) {
    assert.match(source, new RegExp(label, "u"));
  }
  assert.match(source, /["']\/technologies["']/u);
  assert.doesNotMatch(source, /["']\/technology["']/u);
  assert.doesNotMatch(source, /上市跟踪/u);
  assert.doesNotMatch(source, /["']\/ipo["']/u);
  assert.doesNotMatch(source, /投资机构["']/u);
  assert.doesNotMatch(source, /研究报告["']/u);
});

test("technology research channel preserves tracks topics and concrete technologies as separate layers", () => {
  const page = read("app/technologies/page.tsx");
  for (const marker of [
    "L1 / CORE TRACKS",
    "L2 / TECHNOLOGY TOPICS",
    "L3 / TECHNOLOGY ENTITIES",
    "核心赛道",
    "重点技术主题",
    "核心技术对象",
  ]) {
    assert.match(page, new RegExp(marker, "u"));
  }
  assert.equal(technologyTopicDefinitions.length, 20);
  assert.equal(coreResearchObjectStats.topicCount, technologyTopicDefinitions.length);
});

test("dedicated listed-market routes are removed from source and sitemap", () => {
  assert.equal(fs.existsSync(path.join(root, "app/ipo/page.tsx")), false);
  assert.equal(fs.existsSync(path.join(root, "app/ipo/[slug]/page.tsx")), false);

  const sitemap = read("app/sitemap.ts");
  assert.doesNotMatch(sitemap, /["'`]\/ipo/u);
  assert.doesNotMatch(sitemap, /listedCompaniesForDisplay/u);
  assert.match(sitemap, /["']\/technologies["']/u);
  assert.match(sitemap, /\/technologies\/tracks\//u);
  assert.doesNotMatch(sitemap, /\/technology\//u);
});

test("research report evidence links to core company profiles, never retired IPO routes", () => {
  const reader = read("app/reports/pdf/[slug]/page.tsx");
  assert.match(reader, /coreCompanySlugs/u);
  assert.match(reader, /`\/companies\/\$\{report\.companySlug\}`/u);
  assert.doesNotMatch(reader, /`\/ipo\//u);
});

test("core technology layer publishes specific substantive topic entities", () => {
  const page = read("app/technologies/page.tsx");
  assert.match(page, /coreTechnologyEntities/u);
  assert.match(page, /核心技术对象/u);

  const publishedTopics = publishedTrackingResearchEntities.filter(
    (entity) => entity.entityType === "topic",
  );
  assert.ok(coreTechnologyEntities.length <= publishedTopics.length);
  assert.ok(
    coreTechnologyEntities.every((entity) =>
      publishedTopics.some((topic) => topic.id === entity.id),
    ),
  );
  assert.equal(coreResearchObjectStats.trackCount, trackedSectors.length);
});

test("homepage update stream aggregates four objects instead of auxiliary channels", () => {
  const source = read("components/homepage-channel-updates.tsx");
  for (const label of ["核心技术", "核心赛道", "核心人物", "核心公司"]) {
    assert.match(source, new RegExp(label, "u"));
  }
  assert.doesNotMatch(source, /key:\s*["']institutions["']/u);
  assert.doesNotMatch(source, /key:\s*["']reports["']/u);
});

test("public artifact audit rejects retired IPO routes without blocking migration code", () => {
  const audit = read("scripts/audit-public-artifact.mjs");
  assert.match(audit, /relativePath\.startsWith\(["']ipo\//u);
  assert.match(audit, /publicPageMarkers/u);
  assert.match(audit, /上市跟踪/u);
});

test("global layout describes the layered technology research scope", () => {
  const layout = read("app/layout.tsx");
  assert.doesNotMatch(layout, /ipo\/\[slug\]\/market-detail\.css/u);
  assert.match(layout, /核心赛道、重点技术主题、核心技术对象、核心人物与核心公司/u);
});
