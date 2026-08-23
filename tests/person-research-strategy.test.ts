import assert from "node:assert/strict";
import test from "node:test";

import {
  buildPersonResearchStrategyView,
} from "../lib/person-research-strategy";
import {
  normalizePersonResearchQueue,
} from "../lib/person-research-queue";

function queueFor(taskType = "viewpoint_verification") {
  return normalizePersonResearchQueue({
    generatedAt: "2026-08-22T00:00:00Z",
    researchDate: "2026-08-22",
    limits: { people: 10, tasks: 20, tasksPerPerson: 2, activeQuerySlots: 10 },
    queue: [{
      rank: 1,
      personSlug: "alice",
      personName: "Alice",
      taskId: "task-a",
      taskType,
      priority: "P0",
      status: "open",
      target: "世界模型",
      question: "Alice 的观点是否真实变化？",
      successCriteria: "比较跨时间一手材料。",
      executor: "person_video",
      searchQueries: ["Alice 世界模型 完整访谈"],
      queryStrategy: "full_context_interview",
      queryStrategyLabel: "完整上下文访谈",
      strategySampleSize: 0,
      costSampleSize: 0,
      expectedSuccessRate: 0.5,
      expectedEvidenceYield: 0.5,
      queryUnitCost: 1,
      expectedYieldPerCost: 0.5,
      allocationUtility: 100,
      averageQueryDurationMs: 0,
      topHistoricalSourceType: "",
      topHistoricalSourceTypeLabel: "",
      evidenceBasisCount: 0,
      candidateEvidenceCount: 0,
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
      whyNow: ["P0 研究任务"],
      personRoute: "/people/alice/",
      queryBudget: 1,
    }],
  });
}

test("strategy view recomputes observed success and candidate yield per measured cost", () => {
  const view = buildPersonResearchStrategyView({
    generatedAt: "2026-08-22T00:00:00Z",
    attempts: [{ taskId: "a" }, { taskId: "b" }],
    queryStrategyStats: {
      topic_speech: {
        attempts: 2,
        candidateFound: 1,
        noEvidence: 1,
        errors: 0,
        candidates: 4,
        successRate: 99,
        averageCandidates: 99,
      },
    },
    queryStrategyCostStats: {
      topic_speech: {
        attempts: 2,
        averageCostUnits: 2,
        averageDurationMs: 20_000,
      },
    },
    taskStrategyStats: {
      viewpoint_verification: {
        topic_speech: {
          attempts: 2,
          candidateFound: 1,
          candidates: 4,
        },
      },
    },
    taskStrategyCostStats: {
      viewpoint_verification: {
        topic_speech: {
          attempts: 2,
          averageCostUnits: 2,
        },
      },
    },
    taskSourceMatrix: {
      viewpoint_verification: {
        video_platform: {
          attempts: 2,
          yieldAttempts: 1,
          candidates: 4,
        },
      },
    },
  }, queueFor());

  assert.equal(view.attemptCount, 2);
  assert.equal(view.strategies[0]?.successRate, 0.5);
  assert.equal(view.strategies[0]?.averageCandidates, 2);
  assert.equal(view.strategies[0]?.averageCostUnits, 2);
  assert.equal(view.strategies[0]?.candidateYieldPerCost, 1);
  assert.equal(view.taskStrategies.find((row) => row.taskType === "viewpoint_verification")?.mode, "observed");
  assert.equal(view.sources[0]?.yieldRate, 0.5);
});

test("no history is shown as rule prior rather than fabricated observed success", () => {
  const view = buildPersonResearchStrategyView({ attempts: [] }, queueFor());
  const viewpoint = view.taskStrategies.find((row) => row.taskType === "viewpoint_verification");
  assert.ok(viewpoint);
  assert.equal(view.attemptCount, 0);
  assert.equal(view.observedStrategyCount, 0);
  assert.equal(view.observedSourceTypeCount, 0);
  assert.equal(viewpoint.mode, "rule_prior");
  assert.equal(viewpoint.attempts, 0);
  assert.equal(viewpoint.strategy, "full_context_interview");
});

test("source yield uses all task attempts as denominator and clamps impossible counts", () => {
  const view = buildPersonResearchStrategyView({
    attempts: [{}, {}, {}],
    taskSourceMatrix: {
      first_party_evidence: {
        academic: { attempts: 3, yieldAttempts: 99, candidates: 6 },
      },
      viewpoint_verification: {
        academic: { attempts: 2, yieldAttempts: 1, candidates: 2 },
      },
    },
  }, normalizePersonResearchQueue({ queue: [] }));
  const academic = view.sources.find((row) => row.sourceType === "academic");
  assert.ok(academic);
  assert.equal(academic.taskAttempts, 5);
  assert.equal(academic.yieldAttempts, 4);
  assert.equal(academic.yieldRate, 0.8);
  assert.equal(academic.taskCoverage, 2);
});
