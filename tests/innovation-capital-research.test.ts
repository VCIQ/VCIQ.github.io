import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { buildInnovationCapitalResearchModel } from "../lib/innovation-capital-research";
import watchlist from "../config/innovation_listing_watchlist.json";
import lifecycle from "../config/innovation_listing_lifecycle.json";
import trackingSeeds from "../config/innovation_capital_tracking_seeds.json";

const panel = fs.readFileSync(
  new URL("../components/innovation-capital-research-panel.tsx", import.meta.url),
  "utf8",
);
const innovationPage = fs.readFileSync(
  new URL("../app/innovation-capital/page.tsx", import.meta.url),
  "utf8",
);
const researchPage = fs.readFileSync(
  new URL("../app/research-agent/page.tsx", import.meta.url),
  "utf8",
);

test("innovation capital research model derives from reviewed channel datasets", () => {
  const model = buildInnovationCapitalResearchModel();

  assert.equal(model.stats.projectCount, watchlist.projects.length);
  assert.equal(model.stats.lifecycleCount, lifecycle.projects.length);
  assert.equal(model.stats.institutionCount, trackingSeeds.institutions.length);
  assert.equal(
    model.stats.routeUnconfirmedCount,
    watchlist.projects.filter((item) => item.route === "A-share-TBD").length,
  );
  assert.ok(model.stats.routeUnconfirmedRatio > 0);
  assert.ok(model.stats.medianGuidanceDays >= 0);
  assert.ok(model.patterns.length >= 6);
  assert.ok(model.theses.length >= 7);
  assert.ok(model.queue.length >= 7);
});

test("research queue prioritizes verifiable state changes without inferring listing route", () => {
  const model = buildInnovationCapitalResearchModel();
  const lifecycleTask = model.queue.find((item) => item.id === "lifecycle-transition");
  const routeTask = model.queue.find((item) => item.id === "route-confirmation");
  const crossMarketTask = model.queue.find((item) => item.id === "cross-market-path");
  const institutionTask = model.queue.find((item) => item.id === "institution-network");

  assert.ok(lifecycleTask);
  assert.ok(routeTask);
  assert.ok(crossMarketTask);
  assert.ok(institutionTask);
  assert.equal(lifecycleTask.priority, "P0");
  assert.equal(routeTask.priority, "P0");
  assert.match(routeTask.successCriteria, /只有.*正式文件|板块只有/u);
  assert.match(routeTask.successCriteria, /A-share-TBD/u);
  assert.match(crossMarketTask.successCriteria, /不得.*推断/u);
  assert.match(institutionTask.successCriteria, /不转化为机构评级/u);

  const ranks = model.queue.map((item) => item.rank);
  assert.deepEqual(ranks, ranks.map((_, index) => index + 1));
  assert.ok(model.queue.every((item) => item.score >= 0 && item.score <= 100));
});

test("thesis memory statements keep sample boundaries explicit", () => {
  const model = buildInnovationCapitalResearchModel();

  for (const thesis of model.theses) {
    assert.ok(thesis.nextEvidence.length > 0);
    assert.ok(thesis.caveat.length > 0);
  }

  const lifecycleThesis = model.theses.find((item) => item.id === "state-transition");
  const brokerThesis = model.theses.find((item) => item.id === "broker-specialization");
  const financingThesis = model.theses.find((item) => item.id === "late-stage-to-guidance");
  assert.ok(lifecycleThesis);
  assert.ok(brokerThesis);
  assert.ok(financingThesis);
  assert.match(brokerThesis.caveat, /不用于评价券商能力/u);
  assert.match(financingThesis.caveat, /不能推断上市路线.*成功概率/u);
});

test("innovation channel and Research Agent expose the same derived research lane", () => {
  assert.match(innovationPage, /InnovationCapitalResearchPanel/u);
  assert.match(researchPage, /InnovationCapitalResearchPanel/u);
  assert.match(researchPage, /innovation-capital-queue/u);
  assert.match(panel, /不新增“第五类核心研究对象”/u);
  assert.match(panel, /监管\/交易所\/券商原文优先/u);
  assert.match(panel, /Research Queue/u);
  assert.match(panel, /样本研究，不作结果预测/u);
  assert.doesNotMatch(panel, /上市概率\s*\d|成功率\s*\d/u);
});
