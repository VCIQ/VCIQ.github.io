import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath: string) =>
  fs.readFileSync(path.join(root, relativePath), "utf8");

type Project = {
  id: string;
  company: string;
  broker: string;
  route: string;
  routeConfidence: string;
  capitalMarketPath: string;
  pool: string;
  stage: string;
  firstGuidanceDate: string;
  latestEventDate: string;
  everFiledBefore: boolean;
  fifteenthTags: string[];
  source: { title: string; url: string; kind: string };
};

type Watchlist = {
  asOf: string;
  brokers: string[];
  policyThemes: string[];
  projects: Project[];
};

const watchlist = JSON.parse(
  read("config/innovation_listing_watchlist.json"),
) as Watchlist;

test("innovation listing watchlist has five target brokers and unique projects", () => {
  assert.deepEqual(watchlist.brokers, [
    "中信证券",
    "中信建投",
    "中金公司",
    "国泰海通",
    "华泰联合",
  ]);
  assert.match(watchlist.asOf, /^\d{4}-\d{2}-\d{2}$/u);
  assert.ok(watchlist.projects.length >= 25);

  const ids = new Set<string>();
  for (const project of watchlist.projects) {
    assert.equal(ids.has(project.id), false, project.id);
    ids.add(project.id);
    assert.ok(watchlist.brokers.includes(project.broker), project.broker);
    assert.match(project.firstGuidanceDate, /^\d{4}-\d{2}-\d{2}$/u);
    assert.match(project.latestEventDate, /^\d{4}-\d{2}-\d{2}$/u);
    assert.ok(project.fifteenthTags.length > 0, project.company);
    assert.doesNotThrow(() => new URL(project.source.url));
  }
});

test("core pool only contains explicitly classified STAR or ChiNext routes", () => {
  for (const project of watchlist.projects.filter((item) => item.pool === "core")) {
    assert.ok(["STAR", "ChiNext"].includes(project.route), project.company);
    assert.notEqual(project.routeConfidence, "unconfirmed", project.company);
    assert.notEqual(project.routeConfidence, "official-a-share-only", project.company);
  }
});

test("refile projects preserve historical filing state", () => {
  const refiles = watchlist.projects.filter((item) => item.pool === "refile");
  assert.ok(refiles.length > 0);
  assert.ok(refiles.every((item) => item.everFiledBefore));
});

test("innovation capital page is a derived channel, not a fifth core research object", () => {
  const page = read("app/innovation-capital/page.tsx");
  const header = read("components/site-header.tsx");
  const sitemap = read("app/sitemap.ts");
  const automation = read("config/automation_jobs.json");

  assert.match(page, /科创频道/u);
  assert.match(page, /十五五/u);
  assert.match(page, /A\+H/u);
  assert.match(header, /"\/innovation-capital"/u);
  assert.match(sitemap, /"\/innovation-capital"/u);
  assert.match(automation, /innovation_listing_watchlist\.json/u);
});

test("innovation discovery bridge remains evidence-only", () => {
  const bridge = read("tools/crawl_with_innovation_listing_watchlist.py");
  assert.match(bridge, /discovery-only/u);
  assert.match(bridge, /待交叉验证/u);
  assert.doesNotMatch(bridge, /write_text\([^)]*innovation_listing_watchlist/u);
});
