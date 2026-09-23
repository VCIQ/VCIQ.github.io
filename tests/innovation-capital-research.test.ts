import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { buildInnovationCapitalResearchModel } from "../lib/innovation-capital-research";

const researchPage = fs.readFileSync(new URL("../app/research-agent/page.tsx", import.meta.url), "utf8");
const capitalPage = fs.readFileSync(new URL("../app/innovation-capital/page.tsx", import.meta.url), "utf8");
const panel = fs.readFileSync(
  new URL("../app/research-agent/innovation-capital-research-panel.tsx", import.meta.url),
  "utf8",
);

test("innovation capital research model creates bounded evidence-safe research tasks", () => {
  const model = buildInnovationCapitalResearchModel();
  assert.ok(model.projectCount > 0);
  assert.ok(model.institutionCount > 0);
  assert.ok(model.tasks.length >= 6);
  assert.ok(model.hypotheses.length >= 7);
  assert.ok(model.tasks.some((item) => item.taskType === "lifecycle_validation"));
  assert.ok(model.tasks.some((item) => item.taskType === "cross_market_path"));
  assert.ok(model.tasks.some((item) => item.taskType === "capital_network"));
  assert.ok(model.tasks.some((item) => item.taskType === "mature_discovery"));
  assert.ok(model.tasks.every((item, index) => item.rank === index + 1));
  assert.ok(model.tasks.every((item) => item.score >= 0 && item.score <= 100));
  assert.ok(model.hypotheses.every((item) => item.metrics.universeCount >= item.metrics.supportCount + item.metrics.contrastCount));
  assert.ok(model.hypotheses.every((item) => item.metrics.evidenceCoveragePct >= 0 && item.metrics.evidenceCoveragePct <= 100));
  assert.ok(model.hypotheses.every((item) => item.metrics.supportSharePct >= 0 && item.metrics.supportSharePct <= 100));
});

test("research model preserves unknown-route and non-ranking governance", () => {
  const model = buildInnovationCapitalResearchModel();
  assert.ok(model.unknownRouteCount > 0);
  assert.match(model.methodology, /不输出上市概率/u);
  assert.match(model.methodology, /券商排名/u);
  const maintenance = model.tasks.find((item) => item.taskType === "evidence_maintenance");
  assert.ok(maintenance);
  assert.match(maintenance.successCriteria, /不得根据行业属性推断/u);
});

test("research agent exposes a dedicated innovation capital queue anchor", () => {
  assert.match(researchPage, /InnovationCapitalResearchPanel/u);
  assert.match(researchPage, /href="#queuecf"/u);
  assert.match(panel, /id="queuecf"/u);
  assert.match(panel, /Research Queue/u);
  assert.match(panel, /Thesis Watch/u);
  assert.match(panel, /Maintenance Queue/u);
});

test("innovation capital page links its dataset to the research queue", () => {
  assert.match(capitalPage, /buildInnovationCapitalResearchModel/u);
  assert.match(capitalPage, /\/research-agent\/#queuecf/u);
  assert.match(capitalPage, /规律研究/u);
});


test("quantitative thesis metrics use explicit support and contrast definitions", () => {
  const model = buildInnovationCapitalResearchModel();
  const byId = new Map(model.hypotheses.map((item) => [item.id, item]));
  assert.equal(byId.get("broker-sector-specialization")?.metrics.supportCount, 5);
  assert.equal(byId.get("broker-sector-specialization")?.metrics.universeCount, 23);
  assert.equal(byId.get("state-jump-over-duration")?.metrics.supportCount, 13);
  assert.equal(byId.get("state-jump-over-duration")?.metrics.contrastCount, 1);
  assert.equal(byId.get("route-migration")?.metrics.supportCount, 1);
  assert.equal(byId.get("hard-tech-lifecycle")?.metrics.supportCount, 6);
  assert.equal(byId.get("capital-repeat")?.metrics.supportCount, 16);
  assert.equal(byId.get("late-stage-to-guidance")?.metrics.supportCount, 0);
  assert.equal(byId.get("late-stage-to-guidance")?.status, "watch");
});
