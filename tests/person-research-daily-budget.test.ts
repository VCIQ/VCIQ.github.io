import assert from "node:assert/strict";
import test from "node:test";

import { normalizePersonResearchQueue } from "../lib/person-research-queue";

function item(index: number) {
  return {
    rank: index + 1,
    personSlug: `person-${index}`,
    personName: `人物 ${index}`,
    taskId: `task-${index}`,
    taskType: "first_party_evidence",
    priority: "P1",
    status: "open",
    target: "目标",
    question: `问题 ${index}`,
    successCriteria: "找到新的身份匹配一手材料。",
    executor: "person_video",
    searchQueries: [`query ${index}`],
    evidenceBasisCount: 0,
    candidateEvidenceCount: 0,
    scoreBreakdown: {
      priority: 28,
      taskType: 12,
      status: 5,
      evidenceGap: 16,
      recency: 0,
      crossValidation: 0,
      queryReadiness: 6,
      researchHistory: 0,
    },
    whyNow: [],
    personRoute: `/people/person-${index}/`,
    queryBudget: 1,
    researchMemory: {
      attempts: 0,
      yieldingAttempts: 0,
      zeroYieldStreak: 0,
      lastOutcome: "",
      lastAttemptAt: "",
      nextEligibleDate: "",
    },
  };
}

test("used same-day slots reduce newly allocated public query budget", () => {
  const normalized = normalizePersonResearchQueue({
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 10 },
    usedQuerySlotsToday: 8,
    allocatedQuerySlots: 99,
    queue: Array.from({ length: 6 }, (_, index) => item(index)),
  });
  assert.equal(normalized.usedQuerySlotsToday, 8);
  assert.equal(normalized.allocatedQuerySlots, 2);
  assert.equal(normalized.queue.filter((row) => row.queryBudget === 1).length, 2);
  assert.equal(normalized.usedQuerySlotsToday + normalized.allocatedQuerySlots, 10);
});

test("used query slots are clamped to the configured daily limit", () => {
  const normalized = normalizePersonResearchQueue({
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 4 },
    usedQuerySlotsToday: 999,
    queue: [item(0)],
  });
  assert.equal(normalized.usedQuerySlotsToday, 4);
  assert.equal(normalized.allocatedQuerySlots, 0);
  assert.equal(normalized.queue[0].queryBudget, 0);
});
