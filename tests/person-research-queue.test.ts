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
    queryStrategy: "full_context_interview",
    queryStrategyLabel: "完整上下文访谈",
    strategySampleSize: 4,
    costSampleSize: 4,
    expectedSuccessRate: 0.75,
    expectedEvidenceYield: 1.2,
    queryUnitCost: 1,
    expectedYieldPerCost: 1.2,
    allocationUtility: 999,
    averageQueryDurationMs: 10_000,
    topHistoricalSourceType: "video_platform",
    topHistoricalSourceTypeLabel: "视频平台",
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
      researchOutcomeMemory: 0,
      researchStrategyROI: 0,
      researchCostEfficiency: 0,
    },
    whyNow: ["P0 研究任务", "需要跨时间一手材料直接比较"],
    personRoute: "/people/test-person/",
    queryBudget: 1,
    ...overrides,
  };
}

test("queue item recomputes score and allocation utility while keeping one scheduled active query", () => {
  const normalized = normalizePersonResearchQueueItem(item());
  assert.ok(normalized);
  assert.equal(normalized.score, 108);
  assert.equal(normalized.allocationUtility, 183.6);
  assert.deepEqual(normalized.searchQueries, ["测试人物 世界模型 完整访谈"]);
  assert.equal(normalized.queryBudget, 1);
  assert.equal(normalized.personRoute, "/people/test-person/");
  assert.equal(normalized.queryStrategy, "full_context_interview");
  assert.equal(normalized.expectedSuccessRate, 0.75);
});

test("strategy and cost metrics are bounded and cannot inflate the public score arbitrarily", () => {
  const normalized = normalizePersonResearchQueueItem(item({
    expectedSuccessRate: 9,
    expectedEvidenceYield: 999,
    queryUnitCost: -5,
    expectedYieldPerCost: 999,
    allocationUtility: 999999,
    averageQueryDurationMs: 9999999,
    scoreBreakdown: {
      priority: 40,
      taskType: 25,
      status: 5,
      evidenceGap: 12,
      recency: 8,
      crossValidation: 12,
      queryReadiness: 6,
      researchOutcomeMemory: 0,
      researchStrategyROI: 999,
      researchCostEfficiency: 999,
    },
  }));
  assert.ok(normalized);
  assert.equal(normalized.expectedSuccessRate, 1);
  assert.equal(normalized.expectedEvidenceYield, 50);
  assert.equal(normalized.queryUnitCost, 1);
  assert.equal(normalized.expectedYieldPerCost, 50);
  assert.equal(normalized.averageQueryDurationMs, 600_000);
  assert.equal(normalized.scoreBreakdown.researchStrategyROI, 12);
  assert.equal(normalized.scoreBreakdown.researchCostEfficiency, 8);
  assert.equal(normalized.score, 128);
  assert.equal(normalized.allocationUtility, 320);
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
    schemaVersion: 1,
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

test("public boundary allocates the scarce query slot by cost-adjusted utility", () => {
  const normalized = normalizePersonResearchQueue({
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 1 },
    queue: [
      item({
        personSlug: "high-score-slow",
        personName: "高分慢检索",
        taskId: "high-score-slow-task",
        expectedYieldPerCost: 0.1,
      }),
      item({
        rank: 2,
        personSlug: "slightly-lower-fast",
        personName: "稍低分快检索",
        taskId: "slightly-lower-fast-task",
        expectedYieldPerCost: 1.5,
        scoreBreakdown: {
          priority: 40,
          taskType: 25,
          status: 5,
          evidenceGap: 12,
          recency: 0,
          crossValidation: 12,
          queryReadiness: 6,
          researchOutcomeMemory: 0,
          researchStrategyROI: 0,
          researchCostEfficiency: 0,
        },
      }),
    ],
  });
  assert.equal(normalized.queue[0]?.personSlug, "high-score-slow");
  assert.equal(normalized.queue[0]?.queryBudget, 0);
  assert.equal(normalized.queue[1]?.personSlug, "slightly-lower-fast");
  assert.equal(normalized.queue[1]?.queryBudget, 1);
  assert.ok((normalized.queue[1]?.allocationUtility ?? 0) > (normalized.queue[0]?.allocationUtility ?? 0));
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

test("person route is reconstructed from slug instead of trusting arbitrary payload", () => {
  const normalized = normalizePersonResearchQueueItem(item({ personRoute: "https://evil.example/" }));
  assert.ok(normalized);
  assert.equal(normalized.personRoute, "/people/test-person/");
});

test("persisted queue text uses the canonical person identity for known slugs", () => {
  const normalized = normalizePersonResearchQueueItem(item({
    personSlug: "jensen-huang",
    personName: "黄仁勋(Jensen Huang",
    question: "能否找到 黄仁勋(Jensen Huang 围绕 AI 的本人演讲？",
    searchQueries: ["黄仁勋(Jensen Huang AI 演讲"],
    target: "黄仁勋(Jensen Huang · AI",
    successCriteria: "黄仁勋(Jensen Huang 的一手材料直接命中主题。",
  }));
  assert.ok(normalized);
  assert.equal(normalized.personName, "黄仁勋");
  assert.equal(normalized.question.includes("黄仁勋(Jensen Huang"), false);
  assert.ok(normalized.question.includes("黄仁勋（Jensen Huang）"));
  assert.deepEqual(normalized.searchQueries, ["黄仁勋 Jensen Huang AI 演讲"]);
  assert.equal(normalized.target.includes("黄仁勋(Jensen Huang"), false);
  assert.equal(normalized.successCriteria.includes("黄仁勋(Jensen Huang"), false);
});
