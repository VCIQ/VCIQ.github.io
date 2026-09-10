import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("homepage labels distinguish the follow feed from explicit followed sectors", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /label: "关注流"/u);
  assert.match(feed, /已关注赛道 \{preferences\.followedSectors\.length\}/u);
  assert.doesNotMatch(feed, /个性化：关注 \{preferences\.followedSectors\.length\}/u);
});

test("homepage exposes person and company event channels after HBM", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(
    feed,
    /\{ id: "hbm", label: "HBM"[\s\S]*\{ id: "people", label: "人物" \}[\s\S]*\{ id: "companies", label: "公司" \}/u,
  );
});

test("person and company channels use formal entity-library gates instead of prose keywords", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  const policy = await source("lib/homepage-entity-channels.ts");
  assert.match(feed, /matchesHomepagePersonEntityChannel\(item, entityChannels\)/u);
  assert.match(feed, /matchesHomepageCompanyEntityChannel\(item, entityChannels\)/u);
  assert.match(policy, /hasFormalEntityMention\(item\.mentionedPeople, index\.people\.keys\)/u);
  assert.match(policy, /hasFormalEntityMention\(item\.mentionedCompanies, index\.companies\.keys\)/u);
  assert.doesNotMatch(feed, /id: "people", label: "人物", keywords:/u);
  assert.doesNotMatch(feed, /id: "companies", label: "公司", keywords:/u);
});

test("research events keep a semantic research label in the homepage feed", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /item\.type === "论文" \? "研究 \/ 论文" : item\.type/u);
  assert.match(feed, /<span>\{eventTypeLabel\(item\)\}<\/span>/u);
});

test("research-library pages do not duplicate homepage event streams", async () => {
  const splitLayout = await source("components/channel-split-layout.tsx");
  const people = await source("app/people/page.tsx");
  const companies = await source("app/companies/page.tsx");

  assert.match(splitLayout, /showUpdates \?\? channel !== "technology"/u);
  assert.match(people, /showUpdates=\{false\}/u);
  assert.match(companies, /showUpdates=\{false\}/u);
  assert.match(people, /事件新闻统一进入首页“人物”频道/u);
  assert.match(companies, /事件新闻统一进入首页“公司”频道/u);
});

test("homepage utility actions offer share and event-specific deep research", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /recordArticleShare/u);
  assert.match(feed, /vciq:favorite-share-request/u);
  assert.match(feed, /分享这条情报/u);
  assert.match(feed, /buildResearchInvestigationHref\(item\.id\)/u);
  assert.match(feed, />\s*深研此条\s*</u);
  assert.doesNotMatch(feed, />\s*深度研究\s*</u);
});
