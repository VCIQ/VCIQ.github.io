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
});

test("late-stage hard-tech signals are promoted for review without becoming listing probability", () => {
  const rows = buildInnovationOpportunityPool();
  const galactic = rows.find((item) => item.slug === "galactic-energy");
  assert.ok(galactic);
  assert.ok(galactic.lateStageRounds.some((round) => /D轮/u.test(round)));
  assert.ok(galactic.policyThemes.includes("航空航天"));
  assert.match(client, /不代表上市成功概率或投资评级/u);
  assert.doesNotMatch(client, /上市概率\s*\d|成功率\s*\d/u);
});

test("innovation capital channel renders the institution-derived opportunity source", () => {
  assert.match(page, /buildInnovationOpportunityPool/u);
  assert.match(page, /InnovationOpportunityPool/u);
  assert.match(client, /硬科技潜在项目源/u);
  assert.match(client, /机构组合线索/u);
  assert.match(client, /D \/ E \/ Pre-IPO/u);
});
