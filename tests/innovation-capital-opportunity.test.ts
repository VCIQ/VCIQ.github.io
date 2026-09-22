import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { buildInnovationOpportunityPool } from "../lib/innovation-capital-opportunity";
import watchlist from "../config/innovation_listing_watchlist.json";

const page = fs.readFileSync(
  new URL("../app/innovation-capital/page.tsx", import.meta.url),
  "utf8",
);
const client = fs.readFileSync(
  new URL("../app/innovation-capital/innovation-opportunity-pool.tsx", import.meta.url),
  "utf8",
);
const opportunityLib = fs.readFileSync(
  new URL("../lib/innovation-capital-opportunity.ts", import.meta.url),
  "utf8",
);

function key(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase("zh-CN").replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

test("hard-tech opportunity pool stays separate from reviewed listing watchlist", () => {
  const reviewed = new Set(watchlist.projects.map((item) => key(item.company)));
  const rows = buildInnovationOpportunityPool();
  assert.ok(rows.length > 0);
  assert.ok(rows.every((item) => item.policyThemes.length > 0));
  assert.ok(rows.every((item) => !reviewed.has(key(item.name))));
  assert.ok(rows.every((item) => item.readinessScore >= 0 && item.readinessScore <= 100));
  for (const reviewedSlug of [
    "unitree",
    "landspace",
    "galactic-energy",
    "biren",
    "zhipu-ai",
    "minimax",
  ]) {
    assert.equal(rows.some((item) => item.slug === reviewedSlug), false, reviewedSlug);
  }
});

test("late-stage hard-tech signals are promoted for review without becoming listing probability", () => {
  assert.match(opportunityLib, /lateStageRound/u);
  assert.match(opportunityLib, /Pre\[- \]\?IPO/u);
  assert.match(opportunityLib, /readinessScore/u);
  assert.match(client, /D \/ E \/ Pre-IPO \/ Growth/u);
  assert.match(client, /不代表上市成功概率或投资评级/u);
  assert.doesNotMatch(client, /上市概率\s*\d|成功率\s*\d/u);
});

test("researched mature candidates surface with evidence while broker and route stay unassigned", () => {
  const rows = buildInnovationOpportunityPool();
  const elite = rows.find((item) => item.name === "艾利特机器人");
  const galbot = rows.find((item) => item.name === "银河通用");
  assert.ok(elite);
  assert.ok(galbot);
  assert.equal(elite.latestRound, "D+轮");
  assert.equal(elite.financingAmount, "6亿元人民币");
  assert.ok(elite.institutionBackers.includes("达晨财智"));
  assert.ok(elite.gaps.some((gap) => gap.includes("五大券商")));
  assert.equal(galbot.financingAmount, "25亿元人民币");
  assert.ok(galbot.institutionBackers.includes("启明创投"));
});

test("innovation capital channel renders the institution-derived opportunity source", () => {
  assert.match(page, /buildInnovationOpportunityPool/u);
  assert.match(page, /InnovationOpportunityPool/u);
  assert.match(client, /硬科技潜在项目源/u);
  assert.match(client, /机构组合线索/u);
  assert.match(client, /D \/ E \/ Pre-IPO/u);
});


test("post-counselling lifecycle projects are rendered separately from the opportunity pool", () => {
  const lifecycle = fs.readFileSync(
    new URL("../app/innovation-capital/innovation-listing-lifecycle.tsx", import.meta.url),
    "utf8",
  );
  assert.match(lifecycle, /科创上市生命周期/u);
  assert.match(lifecycle, /交易所\/监管一级公开证据/u);
  assert.match(page, /InnovationListingLifecycle/u);
});
