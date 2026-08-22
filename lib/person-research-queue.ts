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

function signedInteger(value: unknown, min = -100, max = 200) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.min(max, Math.max(min, Math.trunc(number)));
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
    evidenceBasisCount: integer(row.evidenceBasisCount, 0, 10),
    candidateEvidenceCount: integer(row.candidateEvidenceCount, 0, 10),
    score: recomputedScore,
    scoreBreakdown: breakdown,
    whyNow: stringList(row.whyNow, 5, 220),
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
    people: integer(limitsRow.people, 1, 50) || 10,
    tasks: integer(limitsRow.tasks, 1, 100) || 20,
    tasksPerPerson: integer(limitsRow.tasksPerPerson, 1, 10) || 2,
    activeQuerySlots: integer(limitsRow.activeQuerySlots, 1, 50) || 10,
  };
  const items = Array.isArray(row.queue)
    ? row.queue
        .map(normalizePersonResearchQueueItem)
        .filter((item): item is PersonResearchQueueItem => Boolean(item))
        .sort((a, b) => a.rank - b.rank || b.score - a.score)
        .slice(0, limits.tasks)
    : [];
  const people = new Set(items.map((item) => item.personSlug));
  const allocated = items.reduce((sum, item) => sum + item.queryBudget, 0);

  return {
    schemaVersion: integer(row.schemaVersion, 1, 10) || 1,
    generatedAt: text(row.generatedAt, 80),
    researchDate: text(row.researchDate, 40),
    limits,
    candidateTaskCount: integer(row.candidateTaskCount),
    selectedPeopleCount: Math.min(people.size, limits.people),
    selectedTaskCount: items.length,
    allocatedQuerySlots: Math.min(allocated, limits.activeQuerySlots),
    queue: items,
    methodology: text(row.methodology, 900),
  };
}

export const personResearchQueue = normalizePersonResearchQueue(publicQueue);
