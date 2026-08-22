import publicQueue from "@/public/data/person_research_queue.json";
import type {
  PersonResearchTaskStatus,
  PersonResearchTaskType,
} from "@/lib/person-research-agenda";

export type PersonResearchExecutor = "person_video" | "cross_channel" | "official_source";

export type PersonResearchQueueScoreBreakdown = {
  priority: number;
  taskType: number;
  status: number;
  evidenceGap: number;
  recency: number;
  crossValidation: number;
  queryReadiness: number;
  researchOutcomeMemory: number;
  researchStrategyROI: number;
};

export type PersonResearchQueueItem = {
  rank: number;
  personSlug: string;
  personName: string;
  taskId: string;
  taskType: PersonResearchTaskType;
  priority: "P0" | "P1" | "P2" | "P3";
  status: Exclude<PersonResearchTaskStatus, "supported" | "blocked">;
  target: string;
  question: string;
  successCriteria: string;
  executor: PersonResearchExecutor;
  searchQueries: string[];
  queryStrategy: string;
  queryStrategyLabel: string;
  strategySampleSize: number;
  expectedSuccessRate: number;
  expectedEvidenceYield: number;
  queryUnitCost: number;
  topHistoricalSourceType: string;
  topHistoricalSourceTypeLabel: string;
  evidenceBasisCount: number;
  candidateEvidenceCount: number;
  score: number;
  scoreBreakdown: PersonResearchQueueScoreBreakdown;
  whyNow: string[];
  cooldownUntil: string;
  personRoute: string;
  queryBudget: number;
};

export type PersonResearchQueue = {
  schemaVersion: number;
  generatedAt: string;
  researchDate: string;
  limits: {
    people: number;
    tasks: number;
    tasksPerPerson: number;
    activeQuerySlots: number;
  };
  candidateTaskCount: number;
  selectedPeopleCount: number;
  selectedTaskCount: number;
  allocatedQuerySlots: number;
  outcomeMemoryAttemptCount: number;
  queue: PersonResearchQueueItem[];
  methodology: string;
};

const TASK_TYPES = new Set<PersonResearchTaskType>([
  "identity_verification",
  "first_party_evidence",
  "viewpoint_verification",
  "execution_verification",
  "freshness_update",
]);
const PRIORITIES = new Set(["P0", "P1", "P2", "P3"] as const);
const STATUSES = new Set(["open", "candidate_found"] as const);
const EXECUTORS = new Set<PersonResearchExecutor>([
  "person_video",
  "cross_channel",
  "official_source",
]);

function text(value: unknown, limit = 1_000) {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function integer(value: unknown, min = 0, max = 10_000) {
  const number = Number(value);
  if (!Number.isFinite(number)) return min;
  return Math.min(max, Math.max(min, Math.trunc(number)));
}

function integerOr(value: unknown, fallback: number, min: number, max: number) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(number)));
}

function signedInteger(value: unknown, min = -100, max = 200) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.min(max, Math.max(min, Math.trunc(number)));
}

function boundedNumber(value: unknown, min: number, max: number, fallback = 0) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, number));
}

function stringList(value: unknown, limit: number, itemLimit = 260) {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = text(raw, itemLimit);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function internalPersonRoute(value: unknown, slug: string) {
  const route = text(value, 260);
  if (route === `/people/${slug}/`) return route;
  return `/people/${slug}/`;
}

function scoreBreakdown(value: unknown): PersonResearchQueueScoreBreakdown {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  return {
    priority: signedInteger(row.priority),
    taskType: signedInteger(row.taskType),
    status: signedInteger(row.status),
    evidenceGap: signedInteger(row.evidenceGap),
    recency: signedInteger(row.recency),
    crossValidation: signedInteger(row.crossValidation),
    queryReadiness: signedInteger(row.queryReadiness),
    researchOutcomeMemory: signedInteger(row.researchOutcomeMemory),
    researchStrategyROI: signedInteger(row.researchStrategyROI, -12, 12),
  };
}

export function normalizePersonResearchQueueItem(value: unknown): PersonResearchQueueItem | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const personSlug = text(row.personSlug, 180);
  const taskId = text(row.taskId, 180);
  const taskType = text(row.taskType, 80) as PersonResearchTaskType;
  const priority = text(row.priority, 8) as PersonResearchQueueItem["priority"];
  const status = text(row.status, 40) as PersonResearchQueueItem["status"];
  const executor = text(row.executor, 40) as PersonResearchExecutor;
  const question = text(row.question, 620);
  if (
    !personSlug ||
    !taskId ||
    !question ||
    !TASK_TYPES.has(taskType) ||
    !PRIORITIES.has(priority) ||
    !STATUSES.has(status) ||
    !EXECUTORS.has(executor)
  ) return null;

  const breakdown = scoreBreakdown(row.scoreBreakdown);
  const recomputedScore = Object.values(breakdown).reduce((sum, value) => sum + value, 0);
  const queryBudget = integer(row.queryBudget, 0, 1);
  const cooldownUntil = text(row.cooldownUntil, 40);
  const searchQueries = executor === "person_video" && queryBudget > 0
    ? stringList(row.searchQueries, 1, 220)
    : [];

  return {
    rank: integer(row.rank, 1, 10_000),
    personSlug,
    personName: text(row.personName, 160) || personSlug,
    taskId,
    taskType,
    priority,
    status,
    target: text(row.target, 200),
    question,
    successCriteria: text(row.successCriteria, 700),
    executor,
    searchQueries,
    queryStrategy: text(row.queryStrategy, 80),
    queryStrategyLabel: text(row.queryStrategyLabel, 120),
    strategySampleSize: integer(row.strategySampleSize, 0, 500),
    expectedSuccessRate: boundedNumber(row.expectedSuccessRate, 0, 1, 0.5),
    expectedEvidenceYield: boundedNumber(row.expectedEvidenceYield, 0, 50, 0.5),
    queryUnitCost: integerOr(row.queryUnitCost, 1, 1, 10),
    topHistoricalSourceType: text(row.topHistoricalSourceType, 80),
    topHistoricalSourceTypeLabel: text(row.topHistoricalSourceTypeLabel, 120),
    evidenceBasisCount: integer(row.evidenceBasisCount, 0, 10),
    candidateEvidenceCount: integer(row.candidateEvidenceCount, 0, 10),
    score: recomputedScore,
    scoreBreakdown: breakdown,
    whyNow: stringList(row.whyNow, 6, 220),
    cooldownUntil,
    personRoute: internalPersonRoute(row.personRoute, personSlug),
    queryBudget: searchQueries.length ? queryBudget : 0,
  };
}

export function normalizePersonResearchQueue(value: unknown): PersonResearchQueue {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const limitsRow = row.limits && typeof row.limits === "object"
    ? row.limits as Record<string, unknown>
    : {};
  const limits = {
    people: integerOr(limitsRow.people, 10, 1, 50),
    tasks: integerOr(limitsRow.tasks, 20, 1, 100),
    tasksPerPerson: integerOr(limitsRow.tasksPerPerson, 2, 1, 10),
    activeQuerySlots: integerOr(limitsRow.activeQuerySlots, 10, 1, 50),
  };
  const normalized = Array.isArray(row.queue)
    ? row.queue
        .map(normalizePersonResearchQueueItem)
        .filter((item): item is PersonResearchQueueItem => Boolean(item))
        .sort((a, b) => b.score - a.score || b.expectedEvidenceYield - a.expectedEvidenceYield || a.rank - b.rank || a.taskId.localeCompare(b.taskId))
    : [];

  const selected: PersonResearchQueueItem[] = [];
  const selectedPeople = new Set<string>();
  const tasksPerPerson = new Map<string, number>();
  for (const item of normalized) {
    const personTaskCount = tasksPerPerson.get(item.personSlug) ?? 0;
    if (personTaskCount >= limits.tasksPerPerson) continue;
    if (!selectedPeople.has(item.personSlug) && selectedPeople.size >= limits.people) continue;
    selected.push(item);
    selectedPeople.add(item.personSlug);
    tasksPerPerson.set(item.personSlug, personTaskCount + 1);
    if (selected.length >= limits.tasks) break;
  }

  const queryPeople = new Set<string>();
  let allocatedQuerySlots = 0;
  const researchDate = text(row.researchDate, 40);
  const bounded = selected.map((item, index) => {
    const inCooldown = Boolean(item.cooldownUntil && researchDate && item.cooldownUntil > researchDate);
    const canAllocate =
      item.executor === "person_video" &&
      item.searchQueries.length > 0 &&
      !inCooldown &&
      !queryPeople.has(item.personSlug) &&
      allocatedQuerySlots < limits.activeQuerySlots;
    if (canAllocate) {
      queryPeople.add(item.personSlug);
      allocatedQuerySlots += 1;
    }
    return {
      ...item,
      rank: index + 1,
      searchQueries: canAllocate ? item.searchQueries.slice(0, 1) : [],
      queryBudget: canAllocate ? 1 : 0,
    };
  });

  return {
    schemaVersion: integerOr(row.schemaVersion, 1, 1, 10),
    generatedAt: text(row.generatedAt, 80),
    researchDate,
    limits,
    candidateTaskCount: Math.max(integer(row.candidateTaskCount), bounded.length),
    selectedPeopleCount: selectedPeople.size,
    selectedTaskCount: bounded.length,
    allocatedQuerySlots,
    outcomeMemoryAttemptCount: integer(row.outcomeMemoryAttemptCount, 0, 100_000),
    queue: bounded,
    methodology: text(row.methodology, 1_300),
  };
}

export const personResearchQueue = normalizePersonResearchQueue(publicQueue);
