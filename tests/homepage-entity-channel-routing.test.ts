import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const feed = await readFile(
  new URL("../components/homepage-news-feed.tsx", import.meta.url),
  "utf8",
);
const homepage = await readFile(
  new URL("../app/page.tsx", import.meta.url),
  "utf8",
);
const entityPolicy = await readFile(
  new URL("../lib/homepage-entity-channels.ts", import.meta.url),
  "utf8",
);
const splitLayout = await readFile(
  new URL("../components/channel-split-layout.tsx", import.meta.url),
  "utf8",
);

test("homepage exposes people and company streams after sector channels", () => {
  assert.match(feed, /\{ id: "hbm", label: "HBM"[\s\S]*\{ id: "people", label: "人物" \}[\s\S]*\{ id: "companies", label: "公司" \}/u);
});

test("people stream resolves structured mentions only against published person profiles", () => {
  assert.match(feed, /matchesHomepagePersonEntityChannel\(item, entityChannels\)/u);
  assert.match(homepage, /researchPeople\.flatMap/u);
  assert.match(homepage, /person\.name/u);
  assert.match(homepage, /person\.englishName/u);
  assert.match(entityPolicy, /index\.people\.slugs\.has\(slug\)/u);
  assert.match(entityPolicy, /hasFormalEntityMention\(item\.mentionedPeople, index\.people\.keys\)/u);
  assert.doesNotMatch(feed, /id: "people"[^\n]*keywords:/u);
});

test("company stream resolves structured mentions only against published company profiles", () => {
  assert.match(feed, /matchesHomepageCompanyEntityChannel\(item, entityChannels\)/u);
  assert.match(homepage, /formalCompanySlugs/u);
  assert.match(homepage, /companyEntities[\s\S]*formalCompanySlugs\.has\(entity\.slug\)/u);
  assert.match(entityPolicy, /index\.companies\.slugs\.has\(slug\)/u);
  assert.match(entityPolicy, /hasFormalEntityMention\(item\.mentionedCompanies, index\.companies\.keys\)/u);
  assert.doesNotMatch(feed, /id: "companies"[^\n]*keywords:/u);
});

test("research papers remain visibly typed inside topical homepage streams", () => {
  assert.match(feed, /item\.type === "论文" \? "研究 \/ 论文" : item\.type/u);
  assert.match(feed, /eventTypeLabel\(item\)/u);
});

test("technology research defaults to a directory-only layout", () => {
  assert.match(splitLayout, /showUpdates \?\? channel !== "technology"/u);
  assert.match(splitLayout, /shouldShowUpdates/u);
});
