import publicQueue from "@/public/data/person_research_queue.json";
import type {
  PersonResearchTaskStatus,
  PersonResearchTaskType,
} from "@/lib/person-research-agenda";

export type PersonResearchExecutor = "person_video" | "cross_channel" | "official_source";
export type PersonResearchOutcome = "new_evidence" | "rediscovered" | "no_yield" | "error" | "";

export type PersonResearchQueueScoreBreakdown = {
  priority: number;
  taskType: number;
  status: number;
  evidenceGap: number;
  recency: number;
  crossValidation: number;
  queryReadiness: number;
  researchHistory: number;
};

export type PersonResearchTaskMemory = {
  attempts: number;
  yieldingAttempts: number;
  zeroYieldStreak: number;
  lastOutcome: PersonResearchOutcome;
  lastAttemptAt: string;
  nextEligibleDate: string;
};

export type PersonResearchOutcomeSource = {
  source: string;
  attempts: number;
  yieldingAttempts: number;
  failedAttempts: number;
  acceptedEvidenceCount: number;
  newEvidenceCount: number;
  yieldRate: number | null;
};

export type PersonResearchOutcomeMemorySummary = {
  attemptCount: number;
  yieldingAttemptCount: number;
  zeroYieldAttemptCount: number;
  acceptedEvidenceCount: number;
  newEvidenceCount: number;
  cooldownTaskCount: number;
  sources: PersonResearchOutcomeSource[];
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
  evidenceBasisCount: number;
  candidateEvidenceCount: number;
  score: number;
  scoreBreakdown: PersonResearchQueueScoreBreakdown;
  whyNow: string[];
  personRoute: string;
  queryBudget: number;
  researchMemory: PersonResearchTaskMemory;
  cooldownActive: boolean;
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
  usedQuerySlotsToday: number;
  allocatedQuerySlots: number;
  outcomeMemory: PersonResearchOutcomeMemorySummary;
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
const OUTCOMES = new Set<PersonResearchOutcome>([
  "new_evidence",
  "rediscovered",
  "no_yield",
  "error",
  "",
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

function ratio(value: unknown) {
  if (value === null || value === undefined) return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.min(1, Math.max(0, number));
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

function isoDate(value: unknown) {
  const candidate = text(value, 40).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(candidate) ? candidate : "";
}

function isCooldownActive(nextEligibleDate: string, researchDate: string) {
  return Boolean(nextEligibleDate && researchDate && researchDate < nextEligibleDate);
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
    researchHistory: signedInteger(row.researchHistory, -20, 10),
  };
}

function taskMemory(value: unknown): PersonResearchTaskMemory {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const lastOutcome = text(row.lastOutcome, 40) as PersonResearchOutcome;
  return {
    attempts: integer(row.attempts, 0, 10_000),
    yieldingAttempts: integer(row.yieldingAttempts, 0, 10_000),
    zeroYieldStreak: integer(row.zeroYieldStreak, 0, 100),
    lastOutcome: OUTCOMES.has(lastOutcome) ? lastOutcome : "",
    lastAttemptAt: text(row.lastAttemptAt, 80),
    nextEligibleDate: isoDate(row.nextEligibleDate),
  };
}

function outcomeMemorySummary(value: unknown): PersonResearchOutcomeMemorySummary {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const sources: PersonResearchOutcomeSource[] = [];
  if (Array.isArray(row.sources)) {
    for (const raw of row.sources) {
      if (!raw || typeof raw !== "object") continue;
      const source = raw as Record<string, unknown>;
      const name = text(source.source, 100);
      if (!name) continue;
      const attempts = integer(source.attempts, 0, 100_000);
      sources.push({
        source: name,
        attempts,
        yieldingAttempts: Math.min(attempts, integer(source.yieldingAttempts, 0, 100_000)),
        failedAttempts: Math.min(attempts, integer(source.failedAttempts, 0, 100_000)),
        acceptedEvidenceCount: integer(source.acceptedEvidenceCount, 0, 1_000_000),
        newEvidenceCount: integer(source.newEvidenceCount, 0, 1_000_000),
        yieldRate: ratio(source.yieldRate),
      });
      if (sources.length >= 6) break;
    }
  }
  return {
    attemptCount: integer(row.attemptCount, 0, 1_000_000),
    yieldingAttemptCount: integer(row.yieldingAttemptCount, 0, 1_000_000),
    zeroYieldAttemptCount: integer(row.zeroYieldAttemptCount, 0, 1_000_000),
    acceptedEvidenceCount: integer(row.acceptedEvidenceCount, 0, 1_000_000),
    newEvidenceCount: integer(row.newEvidenceCount, 0, 1_000_000),
    cooldownTaskCount: integer(row.cooldownTaskCount, 0, 100_000),
    sources,
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
  const recomputedScore = Object.values(breakdown).reduce((sum, component) => sum + component, 0);
  const queryBudget = integer(row.queryBudget, 0, 1);
  const searchQueries = executor === "person_video" && queryBudget > 0
    ? stringList(row.searchQueries, 1, 220)
    : [];
  const memory = taskMemory(row.researchMemory);

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
    evidenceBasisCount: integer(row.evidenceBasisCount, 0, 10),
    candidateEvidenceCount: integer(row.candidateEvidenceCount, 0, 10),
    score: recomputedScore,
    scoreBreakdown: breakdown,
    whyNow: stringList(row.whyNow, 6, 220),
    personRoute: internalPersonRoute(row.personRoute, personSlug),
    queryBudget: searchQueries.length ? queryBudget : 0,
    researchMemory: memory,
    cooldownActive: false,
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
  const researchDate = isoDate(row.researchDate);
  const usedQuerySlotsToday = integer(row.usedQuerySlotsToday, 0, limits.activeQuerySlots);
  const normalized = Array.isArray(row.queue)
    ? row.queue
        .map(normalizePersonResearchQueueItem)
        .filter((item): item is PersonResearchQueueItem => Boolean(item))
        .sort((a, b) => b.score - a.score || a.rank - b.rank || a.taskId.localeCompare(b.taskId))
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
  const bounded = selected.map((item, index) => {
    const cooldownActive = isCooldownActive(item.researchMemory.nextEligibleDate, researchDate);
    const canAllocate =
      item.executor === "person_video" &&
      item.searchQueries.length > 0 &&
      !cooldownActive &&
      !queryPeople.has(item.personSlug) &&
      usedQuerySlotsToday + allocatedQuerySlots < limits.activeQuerySlots;
    if (canAllocate) {
      queryPeople.add(item.personSlug);
      allocatedQuerySlots += 1;
    }
    return {
      ...item,
      rank: index + 1,
      searchQueries: canAllocate ? item.searchQueries.slice(0, 1) : [],
      queryBudget: canAllocate ? 1 : 0,
      cooldownActive,
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
    usedQuerySlotsToday,
    allocatedQuerySlots,
    outcomeMemory: outcomeMemorySummary(row.outcomeMemory),
    queue: bounded,
    methodology: text(row.methodology, 1_000),
  };
}

export const personResearchQueue = normalizePersonResearchQueue(publicQueue);
