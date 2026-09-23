import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  buildInnovationCapitalThesisMemory,
  currentInnovationCapitalThesisObservations,
  type InnovationCapitalThesisMemory,
} from "../lib/innovation-capital-thesis-memory";
import type {
  InnovationCapitalResearchModel,
  InnovationResearchHypothesis,
} from "../lib/innovation-capital-research";

function model(asOf: string, hypothesis: InnovationResearchHypothesis): InnovationCapitalResearchModel {
  return {
    asOf,
    projectCount: 1,
    lifecycleCount: 0,
    institutionCount: 0,
    matureCandidateCount: 0,
    unknownRouteCount: 1,
    aPlusHCount: 0,
    refileCount: 0,
    hypotheses: [hypothesis],
    tasks: [],
    methodology: "test",
  };
}

const baseMetrics = {
  sampleUnit: "project" as const,
  universeCount: 3,
  supportCount: 1,
  contrastCount: 2,
  neutralCount: 0,
  evidenceCoveredCount: 3,
  evidenceCoveragePct: 100,
  supportSharePct: 33.3,
  supportDefinition: "支持",
  contrastDefinition: "对照",
};

const baseHypothesis: InnovationResearchHypothesis = {
  id: "route-migration",
  title: "路线迁移",
  status: "watch",
  evidence: "样本 1",
  nextCheck: "下一节点",
  metrics: baseMetrics,
};

test("innovation capital thesis memory initiates then reaffirms only on a newer universe date", () => {
  const first = buildInnovationCapitalThesisMemory({}, model("2026-09-22", baseHypothesis), "2026-09-23T00:00:00Z");
  const firstCurrent = currentInnovationCapitalThesisObservations(first)[0];
  assert.equal(firstCurrent.lastTransition, "initiated");
  assert.equal(firstCurrent.observationCount, 1);
  assert.equal(firstCurrent.metrics?.supportCount, 1);
  assert.deepEqual(firstCurrent.metricDelta, {
    supportDelta: 0,
    contrastDelta: 0,
    universeDelta: 0,
    evidenceCoverageDeltaPct: 0,
    supportShareDeltaPct: 0,
  });

  const sameDay = buildInnovationCapitalThesisMemory(first, model("2026-09-22", baseHypothesis), "2026-09-23T01:00:00Z");
  assert.deepEqual(sameDay, first);

  const nextDay = buildInnovationCapitalThesisMemory(first, model("2026-09-23", baseHypothesis), "2026-09-24T00:00:00Z");
  const reaffirmed = currentInnovationCapitalThesisObservations(nextDay)[0];
  assert.equal(reaffirmed.lastTransition, "reaffirmed");
  assert.equal(reaffirmed.observationCount, 2);
  assert.equal(reaffirmed.lastSeenAt, "2026-09-23");
});

test("innovation capital thesis memory records revisions and status-direction changes", () => {
  const first = buildInnovationCapitalThesisMemory({}, model("2026-09-22", baseHypothesis), "2026-09-23T00:00:00Z");
  const revisedHypothesis = {
    ...baseHypothesis,
    evidence: "样本 2",
    metrics: {
      ...baseMetrics,
      universeCount: 4,
      supportCount: 2,
      contrastCount: 2,
      supportSharePct: 50,
    },
  };
  const revised = buildInnovationCapitalThesisMemory(first, model("2026-09-23", revisedHypothesis), "2026-09-24T00:00:00Z");
  let current = currentInnovationCapitalThesisObservations(revised)[0];
  assert.equal(current.lastTransition, "revised");
  assert.ok(current.supersedesId);
  assert.equal(current.metricDelta?.supportDelta, 1);
  assert.equal(current.metricDelta?.universeDelta, 1);
  assert.equal(current.metricDelta?.supportShareDeltaPct, 16.7);
  assert.equal(revised.observationCount, 2);

  const observedHypothesis = { ...revisedHypothesis, status: "observed" as const };
  const changed = buildInnovationCapitalThesisMemory(revised, model("2026-09-24", observedHypothesis), "2026-09-25T00:00:00Z");
  current = currentInnovationCapitalThesisObservations(changed)[0];
  assert.equal(current.lastTransition, "direction_changed");
  assert.equal(changed.observationCount, 3);
});

test("innovation capital thesis memory records a return to an earlier thesis version", () => {
  const first = buildInnovationCapitalThesisMemory({}, model("2026-09-22", baseHypothesis), "2026-09-23T00:00:00Z");
  const revised = buildInnovationCapitalThesisMemory(
    first,
    model("2026-09-23", { ...baseHypothesis, evidence: "样本 2" }),
    "2026-09-24T00:00:00Z",
  );
  const returned = buildInnovationCapitalThesisMemory(
    revised,
    model("2026-09-24", baseHypothesis),
    "2026-09-25T00:00:00Z",
  );
  const current = currentInnovationCapitalThesisObservations(returned)[0];
  assert.equal(current.lastTransition, "returned");
  assert.ok(current.returnedToId);
  assert.equal(returned.observationCount, 3);
});

test("legacy thesis observations are metric-backfilled without inventing a revision", () => {
  const first = buildInnovationCapitalThesisMemory({}, model("2026-09-22", baseHypothesis), "2026-09-23T00:00:00Z");
  const legacy = structuredClone(first);
  delete legacy.observations[0].metrics;
  delete legacy.observations[0].metricDelta;

  const migrated = buildInnovationCapitalThesisMemory(
    legacy,
    model("2026-09-22", baseHypothesis),
    "2026-09-23T02:00:00Z",
  );
  const current = currentInnovationCapitalThesisObservations(migrated)[0];
  assert.equal(migrated.observationCount, 1);
  assert.equal(current.id, first.observations[0].id);
  assert.equal(current.lastTransition, "initiated");
  assert.equal(current.metrics?.supportCount, 1);
  assert.equal(current.metricDelta?.supportDelta, 0);
});

test("published memory contract keeps current pointers valid", () => {
  const raw = JSON.parse(
    fs.readFileSync(new URL("../public/data/innovation_capital_thesis_memory.json", import.meta.url), "utf8"),
  ) as InnovationCapitalThesisMemory;
  const ids = new Set(raw.observations.map((item) => item.id));
  assert.equal(raw.schemaVersion, 1);
  assert.ok(raw.generatedAt);
  assert.ok(raw.asOf);
  assert.ok(raw.currentObservationIds.length > 0);
  assert.ok(raw.currentObservationIds.every((id) => ids.has(id)));
  const current = currentInnovationCapitalThesisObservations(raw);
  assert.ok(current.every((item) => item.metrics));
  assert.ok(current.every((item) => item.metricDelta));
});
