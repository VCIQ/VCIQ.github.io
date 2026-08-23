import publicOutcomes from "@/public/data/person_research_outcomes.json";
import {
  personResearchQueue,
  type PersonResearchQueue,
  type PersonResearchQueueItem,
} from "@/lib/person-research-queue";
import type { PersonResearchTaskType } from "@/lib/person-research-agenda";

export const personResearchTaskTypeLabels: Record<PersonResearchTaskType, string> = {
  identity_verification: "身份核验",
  first_party_evidence: "补一手证据",
  viewpoint_verification: "观点变化核验",
  execution_verification: "组织执行核验",
  freshness_update: "近期证据补齐",
};

export const personResearchQueryStrategyLabels: Record<string, string> = {
  official_profile: "官方人物页",
  personal_homepage: "个人主页",
  role_official: "任职 / 官方核验",
  topic_speech: "主题演讲",
  topic_interview: "主题访谈",
  full_context_interview: "完整上下文访谈",
  paper_academic: "论文 / 学术材料",
  latest_speech_interview: "近期演讲 / 访谈",
  recency_year: "年份限定更新",
  topic_direct: "主题直查",
  topic_recent: "近期主题直查",
  generic: "通用检索",
};

export const personResearchSourceTypeLabels: Record<string, string> = {
  video_platform: "视频平台",
  academic: "学术 / 研究来源",
  official: "官方 / 机构来源",
  social: "本人社交平台",
  code: "代码 / 开发者来源",
  media: "专业媒体",
  general_web: "一般网页",
};

const TASK_TYPES: PersonResearchTaskType[] = [
  "identity_verification",
  "first_party_evidence",
  "viewpoint_verification",
  "execution_verification",
  "freshness_update",
];

export type PersonResearchStrategyRow = {
  strategy: string;
  label: string;
  attempts: number;
  candidateFound: number;
  noEvidence: number;
  errors: number;
  candidates: number;
  successRate: number;
  averageCandidates: number;
  costSampleSize: number;
  averageCostUnits: number;
  averageDurationMs: number;
  candidateYieldPerCost: number;
};

export type PersonResearchSourceRow = {
  sourceType: string;
  label: string;
  taskAttempts: number;
  yieldAttempts: number;
  candidates: number;
  yieldRate: number;
  taskCoverage: number;
};

export type PersonResearchTaskStrategy = {
  taskType: PersonResearchTaskType;
  taskLabel: string;
  mode: "observed" | "rule_prior" | "insufficient";
  strategy: string;
  strategyLabel: string;
  sourceType: string;
  sourceTypeLabel: string;
  attempts: number;
  expectedSuccessRate: number;
  averageCandidates: number;
  averageCostUnits: number;
  candidateYieldPerCost: number;
  queueExamples: Array<{
    personName: string;
    personRoute: string;
    question: string;
  }>;
};

export type PersonResearchStrategyView = {
  generatedAt: string;
  attemptCount: number;
  observedStrategyCount: number;
  observedSourceTypeCount: number;
  measuredCostStrategyCount: number;
  strategies: PersonResearchStrategyRow[];
  sources: PersonResearchSourceRow[];
  taskStrategies: PersonResearchTaskStrategy[];
  methodology: string;
};

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as UnknownRecord
    : {};
}

function entries(value: unknown) {
  return Object.entries(record(value));
}

function text(value: unknown, limit = 500) {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function integer(value: unknown, min = 0, max = 100_000) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return min;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}

function boundedNumber(value: unknown, min = 0, max = 100_000, fallback = 0) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function ratio(numerator: number, denominator: number) {
  return denominator > 0 ? Math.round((numerator / denominator) * 1_000) / 1_000 : 0;
}

function strategyLabel(strategy: string) {
  return personResearchQueryStrategyLabels[strategy] ?? (strategy || "未分类策略");
}

function sourceLabel(sourceType: string) {
  return personResearchSourceTypeLabels[sourceType] ?? (sourceType || "未分类来源");
}

function normalizedStrategies(outcomes: UnknownRecord): PersonResearchStrategyRow[] {
  const costStats = record(outcomes.queryStrategyCostStats);
  return entries(outcomes.queryStrategyStats)
    .map(([strategy, raw]) => {
      const stat = record(raw);
      const cost = record(costStats[strategy]);
      const attempts = integer(stat.attempts, 0, 500);
      const candidateFound = Math.min(attempts, integer(stat.candidateFound, 0, 500));
      const noEvidence = Math.min(attempts, integer(stat.noEvidence, 0, 500));
      const errors = Math.min(attempts, integer(stat.errors, 0, 500));
      const candidates = integer(stat.candidates, 0, 10_000);
      const costSampleSize = integer(cost.attempts, 0, 500);
      const averageCostUnits = costSampleSize > 0 ? boundedNumber(cost.averageCostUnits, 1, 10, 1) : 1;
      const averageDurationMs = costSampleSize > 0 ? integer(cost.averageDurationMs, 0, 600_000) : 0;
      const averageCandidates = ratio(candidates, attempts);
      return {
        strategy,
        label: strategyLabel(strategy),
        attempts,
        candidateFound,
        noEvidence,
        errors,
        candidates,
        successRate: ratio(candidateFound, attempts),
        averageCandidates,
        costSampleSize,
        averageCostUnits,
        averageDurationMs,
        candidateYieldPerCost: Math.round((averageCandidates / Math.max(1, averageCostUnits)) * 1_000) / 1_000,
      };
    })
    .filter((row) => row.attempts > 0)
    .sort((a, b) =>
      b.candidateYieldPerCost - a.candidateYieldPerCost ||
      b.successRate - a.successRate ||
      b.attempts - a.attempts ||
      a.label.localeCompare(b.label, "zh-CN"),
    );
}

function normalizedSources(outcomes: UnknownRecord): PersonResearchSourceRow[] {
  const aggregate = new Map<string, PersonResearchSourceRow>();
  for (const [, rawMatrix] of entries(outcomes.taskSourceMatrix)) {
    for (const [sourceType, raw] of entries(rawMatrix)) {
      const stat = record(raw);
      const row = aggregate.get(sourceType) ?? {
        sourceType,
        label: sourceLabel(sourceType),
        taskAttempts: 0,
        yieldAttempts: 0,
        candidates: 0,
        yieldRate: 0,
        taskCoverage: 0,
      };
      row.taskAttempts += integer(stat.attempts, 0, 500);
      row.yieldAttempts += integer(stat.yieldAttempts, 0, 500);
      row.candidates += integer(stat.candidates, 0, 10_000);
      row.taskCoverage += 1;
      aggregate.set(sourceType, row);
    }
  }
  return [...aggregate.values()]
    .map((row) => ({
      ...row,
      yieldAttempts: Math.min(row.taskAttempts, row.yieldAttempts),
      yieldRate: ratio(Math.min(row.taskAttempts, row.yieldAttempts), row.taskAttempts),
    }))
    .sort((a, b) =>
      b.yieldRate - a.yieldRate ||
      b.candidates - a.candidates ||
      b.taskCoverage - a.taskCoverage ||
      a.label.localeCompare(b.label, "zh-CN"),
    );
}

function observedTaskStrategy(
  outcomes: UnknownRecord,
  taskType: PersonResearchTaskType,
): Omit<PersonResearchTaskStrategy, "taskType" | "taskLabel" | "queueExamples"> | null {
  const taskStrategies = record(record(outcomes.taskStrategyStats)[taskType]);
  const taskCosts = record(record(outcomes.taskStrategyCostStats)[taskType]);
  const rows = Object.entries(taskStrategies)
    .map(([strategy, raw]) => {
      const stat = record(raw);
      const cost = record(taskCosts[strategy]);
      const attempts = integer(stat.attempts, 0, 500);
      const candidateFound = Math.min(attempts, integer(stat.candidateFound, 0, 500));
      const candidates = integer(stat.candidates, 0, 10_000);
      const averageCandidates = ratio(candidates, attempts);
      const costSamples = integer(cost.attempts, 0, 500);
      const averageCostUnits = costSamples > 0 ? boundedNumber(cost.averageCostUnits, 1, 10, 1) : 1;
      return {
        strategy,
        strategyLabel: strategyLabel(strategy),
        attempts,
        expectedSuccessRate: ratio(candidateFound, attempts),
        averageCandidates,
        averageCostUnits,
        candidateYieldPerCost: Math.round((averageCandidates / Math.max(1, averageCostUnits)) * 1_000) / 1_000,
      };
    })
    .filter((row) => row.attempts > 0)
    .sort((a, b) =>
      b.candidateYieldPerCost - a.candidateYieldPerCost ||
      b.expectedSuccessRate - a.expectedSuccessRate ||
      b.attempts - a.attempts,
    );
  if (!rows.length) return null;

  const sourceRows = entries(record(outcomes.taskSourceMatrix)[taskType])
    .map(([sourceType, raw]) => {
      const stat = record(raw);
      const attempts = integer(stat.attempts, 0, 500);
      const yieldAttempts = Math.min(attempts, integer(stat.yieldAttempts, 0, 500));
      return {
        sourceType,
        yieldRate: ratio(yieldAttempts, attempts),
        candidates: integer(stat.candidates, 0, 10_000),
      };
    })
    .sort((a, b) => b.yieldRate - a.yieldRate || b.candidates - a.candidates);

  return {
    mode: "observed",
    ...rows[0],
    sourceType: sourceRows[0]?.sourceType ?? "",
    sourceTypeLabel: sourceRows[0] ? sourceLabel(sourceRows[0].sourceType) : "",
  };
}

function scheduledFallback(
  queue: PersonResearchQueue,
  taskType: PersonResearchTaskType,
): Omit<PersonResearchTaskStrategy, "taskType" | "taskLabel" | "queueExamples"> | null {
  const candidates = queue.queue
    .filter((item) => item.taskType === taskType && item.queryStrategy)
    .sort((a, b) => b.allocationUtility - a.allocationUtility || b.score - a.score);
  const best = candidates[0];
  if (!best) return null;
  return {
    mode: best.strategySampleSize > 0 ? "observed" : "rule_prior",
    strategy: best.queryStrategy,
    strategyLabel: best.queryStrategyLabel || strategyLabel(best.queryStrategy),
    sourceType: best.topHistoricalSourceType,
    sourceTypeLabel: best.topHistoricalSourceTypeLabel,
    attempts: best.strategySampleSize,
    expectedSuccessRate: best.expectedSuccessRate,
    averageCandidates: best.expectedEvidenceYield,
    averageCostUnits: best.queryUnitCost,
    candidateYieldPerCost: best.expectedYieldPerCost,
  };
}

function queueExamples(queue: PersonResearchQueue, taskType: PersonResearchTaskType) {
  return queue.queue
    .filter((item): item is PersonResearchQueueItem => item.taskType === taskType)
    .slice(0, 3)
    .map((item) => ({
      personName: item.personName,
      personRoute: item.personRoute,
      question: item.question,
    }));
}

export function buildPersonResearchStrategyView(
  rawOutcomes: unknown,
  queue: PersonResearchQueue = personResearchQueue,
): PersonResearchStrategyView {
  const outcomes = record(rawOutcomes);
  const strategies = normalizedStrategies(outcomes);
  const sources = normalizedSources(outcomes);
  const taskStrategies = TASK_TYPES.map((taskType) => {
    const observed = observedTaskStrategy(outcomes, taskType);
    const fallback = observed ?? scheduledFallback(queue, taskType);
    return {
      taskType,
      taskLabel: personResearchTaskTypeLabels[taskType],
      ...(fallback ?? {
        mode: "insufficient" as const,
        strategy: "",
        strategyLabel: "等待更多研究尝试",
        sourceType: "",
        sourceTypeLabel: "",
        attempts: 0,
        expectedSuccessRate: 0,
        averageCandidates: 0,
        averageCostUnits: 1,
        candidateYieldPerCost: 0,
      }),
      queueExamples: queueExamples(queue, taskType),
    };
  });
  const attempts = Array.isArray(outcomes.attempts)
    ? outcomes.attempts.filter((item) => item && typeof item === "object")
    : [];
  return {
    generatedAt: text(outcomes.generatedAt, 80) || queue.generatedAt,
    attemptCount: attempts.length,
    observedStrategyCount: strategies.length,
    observedSourceTypeCount: sources.length,
    measuredCostStrategyCount: strategies.filter((row) => row.costSampleSize > 0).length,
    strategies,
    sources,
    taskStrategies,
    methodology: text(outcomes.methodology, 1_400) ||
      "Strategy Memory 只统计研究过程的候选产出、来源类型与主动检索成本；它不会判断事实真假，也不能绕过任务 successCriteria。",
  };
}

export const personResearchStrategyView = buildPersonResearchStrategyView(publicOutcomes);
