import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizePersonResearchQueue,
  normalizePersonResearchQueueItem,
} from "../lib/person-research-queue";

function item(overrides: Record<string, unknown> = {}) {
  return {
    rank: 1,
    personSlug: "test-person",
    personName: "测试人物",
    taskId: "person-research-test",
    taskType: "viewpoint_verification",
    priority: "P0",
    status: "open",
    target: "世界模型",
    question: "测试人物在世界模型上的观点是否真实发生变化？",
    successCriteria: "需要跨时间一手证据直接比较。",
    executor: "person_video",
    searchQueries: ["测试人物 世界模型 完整访谈"],
    evidenceBasisCount: 2,
    candidateEvidenceCount: 0,
    score: 999,
    scoreBreakdown: {
      priority: 40,
      taskType: 25,
      status: 5,
      evidenceGap: 12,
      recency: 8,
      crossValidation: 12,
      queryReadiness: 6,
      researchHistory: 0,
    },
    whyNow: ["P0 研究任务", "需要跨时间一手材料直接比较"],
    personRoute: "/people/test-person/",
    queryBudget: 1,
    researchMemory: {
      attempts: 0,
      yieldingAttempts: 0,
      zeroYieldStreak: 0,
      lastOutcome: "",
      lastAttemptAt: "",
      nextEligibleDate: "",
    },
    cooldownActive: false,
    ...overrides,
  };
}

test("queue item recomputes score and keeps one scheduled active query", () => {
  const normalized = normalizePersonResearchQueueItem(item());
  assert.ok(normalized);
  assert.equal(normalized.score, 108);
  assert.deepEqual(normalized.searchQueries, ["测试人物 世界模型 完整访谈"]);
  assert.equal(normalized.queryBudget, 1);
  assert.equal(normalized.personRoute, "/people/test-person/");
});

test("research history is part of the recomputed score", () => {
  const normalized = normalizePersonResearchQueueItem(item({
    score: 5_000,
    scoreBreakdown: {
      priority: 40,
      taskType: 25,
      status: 5,
      evidenceGap: 12,
      recency: 8,
      crossValidation: 12,
      queryReadiness: 6,
      researchHistory: -6,
    },
  }));
  assert.ok(normalized);
  assert.equal(normalized.score, 102);
  assert.equal(normalized.scoreBreakdown.researchHistory, -6);
});

test("queue boundary rejects closed states and unsupported executors", () => {
  assert.equal(normalizePersonResearchQueueItem(item({ status: "supported" })), null);
  assert.equal(normalizePersonResearchQueueItem(item({ status: "blocked" })), null);
  assert.equal(normalizePersonResearchQueueItem(item({ executor: "free_agent" })), null);
});

test("non-video tasks cannot smuggle browser search queries or query budget", () => {
  const normalized = normalizePersonResearchQueueItem(item({
    taskType: "execution_verification",
    executor: "cross_channel",
    searchQueries: ["https://evil.example/query"],
    queryBudget: 1,
  }));
  assert.ok(normalized);
  assert.deepEqual(normalized.searchQueries, []);
  assert.equal(normalized.queryBudget, 0);
});

test("queue derives public counters from normalized rows instead of trusting payload", () => {
  const normalized = normalizePersonResearchQueue({
    schemaVersion: 2,
    generatedAt: "2026-08-22T00:00:00Z",
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 10 },
    candidateTaskCount: 200,
    selectedPeopleCount: 99,
    selectedTaskCount: 99,
    allocatedQuerySlots: 99,
    queue: [
      item(),
      item({
        rank: 2,
        personSlug: "second-person",
        personName: "第二人物",
        taskId: "person-research-second",
        taskType: "execution_verification",
        executor: "cross_channel",
        searchQueries: [],
        queryBudget: 0,
      }),
      item({ rank: 3, taskId: "closed", status: "supported" }),
    ],
    methodology: "test",
  });
  assert.equal(normalized.selectedPeopleCount, 2);
  assert.equal(normalized.selectedTaskCount, 2);
  assert.equal(normalized.allocatedQuerySlots, 1);
  assert.equal(normalized.candidateTaskCount, 200);
});

test("public boundary re-enforces people task and active-query budgets", () => {
  const rows = Array.from({ length: 12 }, (_, personIndex) => [0, 1, 2].map((taskIndex) => item({
    rank: personIndex * 3 + taskIndex + 1,
    personSlug: `person-${personIndex}`,
    personName: `人物 ${personIndex}`,
    taskId: `task-${personIndex}-${taskIndex}`,
    searchQueries: [`人物 ${personIndex} query ${taskIndex}`],
    queryBudget: 1,
  }))).flat();
  const normalized = normalizePersonResearchQueue({
    researchDate: "2026-08-22",
    limits: { people: 4, tasks: 7, tasksPerPerson: 2, activeQuerySlots: 3 },
    queue: rows,
  });
  assert.equal(normalized.selectedPeopleCount, 4);
  assert.equal(normalized.selectedTaskCount, 7);
  assert.equal(normalized.allocatedQuerySlots, 3);
  assert.deepEqual(normalized.queue.map((row) => row.rank), [1, 2, 3, 4, 5, 6, 7]);
  const perPerson = new Map<string, number>();
  for (const row of normalized.queue) {
    perPerson.set(row.personSlug, (perPerson.get(row.personSlug) ?? 0) + 1);
  }
  assert.ok([...perPerson.values()].every((count) => count <= 2));
  assert.equal(normalized.queue.filter((row) => row.queryBudget === 1).length, 3);
});

test("public boundary recomputes cooldown and withholds query budget", () => {
  const normalized = normalizePersonResearchQueue({
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 10 },
    queue: [item({
      cooldownActive: false,
      researchMemory: {
        attempts: 2,
        yieldingAttempts: 0,
        zeroYieldStreak: 2,
        lastOutcome: "no_yield",
        lastAttemptAt: "2026-08-21T01:00:00+00:00",
        nextEligibleDate: "2026-08-23",
      },
    })],
  });
  assert.equal(normalized.queue.length, 1);
  assert.equal(normalized.queue[0].cooldownActive, true);
  assert.equal(normalized.queue[0].queryBudget, 0);
  assert.deepEqual(normalized.queue[0].searchQueries, []);
});

test("outcome memory summary clamps invalid source counters", () => {
  const normalized = normalizePersonResearchQueue({
    outcomeMemory: {
      attemptCount: 3,
      yieldingAttemptCount: 2,
      zeroYieldAttemptCount: 1,
      acceptedEvidenceCount: 9,
      newEvidenceCount: 4,
      cooldownTaskCount: 1,
      sources: [
        {
          source: "YouTube",
          attempts: 2,
          yieldingAttempts: 99,
          failedAttempts: 99,
          acceptedEvidenceCount: 7,
          newEvidenceCount: 3,
          yieldRate: 2,
        },
        { source: "", attempts: 5 },
      ],
    },
    queue: [],
  });
  assert.equal(normalized.outcomeMemory.attemptCount, 3);
  assert.equal(normalized.outcomeMemory.sources.length, 1);
  assert.equal(normalized.outcomeMemory.sources[0].yieldingAttempts, 2);
  assert.equal(normalized.outcomeMemory.sources[0].failedAttempts, 2);
  assert.equal(normalized.outcomeMemory.sources[0].yieldRate, 1);
});

test("person route is reconstructed from slug instead of trusting arbitrary payload", () => {
  const normalized = normalizePersonResearchQueueItem(item({ personRoute: "https://evil.example/" }));
  assert.ok(normalized);
  assert.equal(normalized.personRoute, "/people/test-person/");
});
