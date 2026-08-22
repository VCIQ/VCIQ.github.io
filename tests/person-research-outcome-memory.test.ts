import assert from "node:assert/strict";
import test from "node:test";

import { normalizePersonResearchQueue } from "../lib/person-research-queue";

function queueItem(overrides: Record<string, unknown> = {}) {
  return {
    rank: 1,
    personSlug: "memory-person",
    personName: "记忆测试人物",
    taskId: "memory-task",
    taskType: "first_party_evidence",
    priority: "P0",
    status: "open",
    target: "一手材料",
    question: "是否能找到新的完整一手材料？",
    successCriteria: "只接受可追溯的一手材料。",
    executor: "person_video",
    searchQueries: ["记忆测试人物 完整访谈"],
    evidenceBasisCount: 0,
    candidateEvidenceCount: 0,
    scoreBreakdown: {
      priority: 40,
      taskType: 12,
      status: 5,
      evidenceGap: 16,
      recency: 0,
      crossValidation: 0,
      queryReadiness: 6,
      researchOutcomeMemory: -18,
    },
    whyNow: ["近期主动检索零产出，进入短期冷却避免重复消耗预算"],
    cooldownUntil: "2026-08-25",
    personRoute: "/people/memory-person/",
    queryBudget: 1,
    ...overrides,
  };
}

test("public queue recomputes the outcome-memory score component", () => {
  const normalized = normalizePersonResearchQueue({
    schemaVersion: 2,
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 10 },
    queue: [queueItem()],
  });
  assert.equal(normalized.queue[0]?.scoreBreakdown.researchOutcomeMemory, -18);
  assert.equal(normalized.queue[0]?.score, 61);
});

test("cooldown prevents an active browser query even when payload requests budget", () => {
  const normalized = normalizePersonResearchQueue({
    schemaVersion: 2,
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 10 },
    allocatedQuerySlots: 99,
    queue: [queueItem()],
  });
  assert.equal(normalized.allocatedQuerySlots, 0);
  assert.equal(normalized.queue[0]?.queryBudget, 0);
  assert.deepEqual(normalized.queue[0]?.searchQueries, []);
});
