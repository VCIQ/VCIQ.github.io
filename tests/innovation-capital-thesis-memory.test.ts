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

const baseHypothesis: InnovationResearchHypothesis = {
  id: "route-migration",
  title: "路线迁移",
  status: "watch",
  evidence: "样本 1",
  nextCheck: "下一节点",
};

test("innovation capital thesis memory initiates then reaffirms only on a newer universe date", () => {
  const first = buildInnovationCapitalThesisMemory({}, model("2026-09-22", baseHypothesis), "2026-09-23T00:00:00Z");
  const firstCurrent = currentInnovationCapitalThesisObservations(first)[0];
  assert.equal(firstCurrent.lastTransition, "initiated");
  assert.equal(firstCurrent.observationCount, 1);

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
  const revisedHypothesis = { ...baseHypothesis, evidence: "样本 2" };
  const revised = buildInnovationCapitalThesisMemory(first, model("2026-09-23", revisedHypothesis), "2026-09-24T00:00:00Z");
  let current = currentInnovationCapitalThesisObservations(revised)[0];
  assert.equal(current.lastTransition, "revised");
  assert.ok(current.supersedesId);
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
});
