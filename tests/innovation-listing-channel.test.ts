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

const lifecycle = JSON.parse(
  read("config/innovation_listing_lifecycle.json"),
) as {
  projects: Array<{
    company: string;
    broker: string;
    route: string;
    lifecycleStatus: string;
    stage: string;
    stockCode: string;
    sources: Array<{ url: string; level: string }>;
  }>;
};

const trackingSeeds = JSON.parse(
  read("config/innovation_capital_tracking_seeds.json"),
) as {
  track: { slug: string; name: string };
  brokers: Array<{ name: string; aliases: string[] }>;
  projects: Array<{ name: string }>;
  institutions: Array<{ name: string; institutionTypes: string[] }>;
  governance: { duplicateRule: string; opportunityRule: string };
};

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


test("innovation capital tracking seeds cover reviewed projects, brokers and capital institutions", () => {
  assert.equal(trackingSeeds.track.slug, "innovation-capital");
  assert.equal(trackingSeeds.track.name, "科创资本");
  assert.equal(trackingSeeds.brokers.length, 5);
  assert.ok(trackingSeeds.projects.length >= 46);
  assert.ok(trackingSeeds.institutions.length >= 150);
  assert.ok(
    trackingSeeds.institutions.every(
      (item) => !item.institutionTypes.includes("strategic-shareholder"),
    ),
  );
  assert.match(trackingSeeds.governance.duplicateRule, /aliases/u);
  assert.match(trackingSeeds.governance.opportunityRule, /潜在项目源/u);
});

test("innovation capital remains a derived public channel while backend tracking gets its own lane", () => {
  const automation = read("config/automation_jobs.json");
  const workflow = read(".github/workflows/tracking-discovery.yml");
  const sync = read("tools/sync_innovation_capital_tracking.py");

  assert.match(workflow, /sync_innovation_capital_tracking\.py/u);
  assert.match(sync, /TRACK_SLUG = "innovation-capital"/u);
  assert.match(sync, /relationship-candidate-does-not-imply-confirmed/u);
  assert.doesNotMatch(automation, /"id": "innovation-capital"[\s\S]*"publicObjectTypes"/u);
});


test("listing lifecycle migrates accepted or listed hard-tech projects without losing broker lineage", () => {
  const unitree = lifecycle.projects.find((item) => item.company.includes("宇树科技"));
  const landspace = lifecycle.projects.find((item) => item.company.includes("蓝箭航天"));
  const mthreads = lifecycle.projects.find((item) => item.company.includes("摩尔线程"));
  const metax = lifecycle.projects.find((item) => item.company.includes("沐曦"));
  const enflame = lifecycle.projects.find((item) => item.company.includes("燧原科技"));
  assert.ok(unitree);
  assert.ok(landspace);
  assert.ok(mthreads);
  assert.ok(metax);
  assert.ok(enflame);
  assert.equal(unitree.broker, "中信证券");
  assert.equal(unitree.route, "STAR");
  assert.equal(unitree.lifecycleStatus, "listed");
  assert.equal(unitree.stockCode, "688836");
  assert.equal(landspace.broker, "中金公司");
  assert.equal(landspace.lifecycleStatus, "exchange-review");
  assert.equal(mthreads.broker, "中信证券");
  assert.equal(mthreads.stockCode, "688795");
  assert.equal(metax.broker, "华泰联合");
  assert.equal(metax.stockCode, "688802");
  assert.equal(enflame.broker, "中信证券");
  assert.equal(enflame.lifecycleStatus, "registration-review");
  for (const project of lifecycle.projects) {
    assert.ok(["中信证券", "中信建投", "中金公司", "国泰海通", "华泰联合"].includes(project.broker));
    assert.ok(project.sources.some((source) => source.level === "regulatory"));
    assert.ok(project.sources.every((source) => /^https:\/\//u.test(source.url)));
  }
});
