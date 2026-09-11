import assert from "node:assert/strict";
import test from "node:test";

import { normalizePersonResearchQueue } from "../lib/person-research-queue";

function item(
  taskId: string,
  personSlug: string,
  taskType: string,
  priority = "P0",
) {
  return {
    rank: 1,
    personSlug,
    personName: personSlug,
    taskId,
    taskType,
    priority,
    status: "open",
    target: "AI systems",
    question: `Question ${taskId}`,
    successCriteria: "Find evidence.",
    executor: taskType === "identity_verification" ? "official_source" : "person_video",
    searchQueries: [`${personSlug} interview`],
    queryBudget: taskType === "identity_verification" ? 0 : 1,
    scoreBreakdown: {
      priority: priority === "P0" ? 40 : 28,
      taskType: 10,
      status: 5,
      evidenceGap: 5,
      recency: 0,
      crossValidation: 0,
      queryReadiness: 5,
      researchOutcomeMemory: 0,
      researchStrategyROI: 0,
      researchCostEfficiency: 0,
    },
    expectedEvidenceYield: 1,
    queryUnitCost: 1,
    expectedYieldPerCost: 1,
    whyNow: [],
  };
}

function payload(queue: unknown[]) {
  return {
    schemaVersion: 4,
    generatedAt: "2026-09-11T00:00:00Z",
    researchDate: "2026-09-11",
    limits: {
      people: 10,
      tasks: 20,
      tasksPerPerson: 2,
      activeQuerySlots: 10,
    },
    queue,
  };
}

test("legacy public queue infers Research and Maintenance workstreams", () => {
  const queue = normalizePersonResearchQueue(payload([
    item("identity", "alice", "identity_verification"),
    item("fresh", "bob", "freshness_update"),
    item("view", "carol", "viewpoint_verification"),
    item("exec", "dave", "execution_verification"),
  ]));
  const byId = new Map(queue.queue.map((row) => [row.taskId, row.workstream]));
  assert.equal(byId.get("identity"), "maintenance");
  assert.equal(byId.get("fresh"), "maintenance");
  assert.equal(byId.get("view"), "research");
  assert.equal(byId.get("exec"), "research");
});

test("public normalization preserves Research capacity before capped Maintenance", () => {
  const rows = [];
  for (let index = 0; index < 8; index += 1) {
    const slug = `person-${index}`;
    rows.push(item(`research-${index}`, slug, "viewpoint_verification", "P1"));
    rows.push(item(`maintenance-${index}`, slug, "identity_verification", "P0"));
  }
  const queue = normalizePersonResearchQueue(payload(rows));
  assert.equal(queue.selectedResearchTaskCount, 8);
  assert.equal(queue.selectedMaintenanceTaskCount, 6);
  assert.deepEqual(
    new Set(queue.queue.filter((row) => row.workstream === "research").map((row) => row.taskId)),
    new Set(Array.from({ length: 8 }, (_, index) => `research-${index}`)),
  );
});

test("Research consumes active query capacity before Maintenance", () => {
  const rows = [];
  for (let index = 0; index < 10; index += 1) {
    rows.push(item(`research-${index}`, `person-${index}`, "first_party_evidence"));
  }
  rows.push(item("maintenance-0", "person-0", "freshness_update"));
  rows.push(item("maintenance-1", "person-1", "freshness_update"));
  const queue = normalizePersonResearchQueue(payload(rows));
  assert.equal(queue.allocatedResearchQuerySlots, 10);
  assert.equal(queue.allocatedMaintenanceQuerySlots, 0);
  assert.ok(queue.queue.filter((row) => row.queryBudget > 0).every((row) => row.workstream === "research"));
});
