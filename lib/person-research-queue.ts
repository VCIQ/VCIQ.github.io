import publicQueue from "@/public/data/person_research_queue.json";
import { researchPeople } from "@/lib/people-data";
import { replaceLegacyPersonIdentityText } from "@/lib/person-name-normalization";
import type {
  PersonResearchTaskStatus,
  PersonResearchTaskType,
} from "@/lib/person-research-agenda";

export type PersonResearchExecutor = "person_video" | "cross_channel" | "official_source";
export type PersonResearchWorkstream = "research" | "maintenance";

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
  researchCostEfficiency: number;
};

export type PersonResearchQueueItem = {
  rank: number;
  workstreamRank: number;
  workstream: PersonResearchWorkstream;
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
  costSampleSize: number;
  expectedSuccessRate: number;
  expectedEvidenceYield: number;
  queryUnitCost: number;
  expectedYieldPerCost: number;
  allocationUtility: number;
  averageQueryDurationMs: number;
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
    researchTasks: number;
    maintenanceTasks: number;
    tasksPerPerson: number;
    activeQuerySlots: number;
    maintenanceQuerySlots: number;
  };
  candidateTaskCount: number;
  candidateResearchTaskCount: number;
  candidateMaintenanceTaskCount: number;
  selectedPeopleCount: number;
  selectedTaskCount: number;
  selectedResearchTaskCount: number;
  selectedMaintenanceTaskCount: number;
  allocatedQuerySlots: number;
  allocatedResearchQuerySlots: number;
  allocatedMaintenanceQuerySlots: number;
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
const WORKSTREAMS = new Set<PersonResearchWorkstream>(["research", "maintenance"]);
const MAINTENANCE_TASK_TYPES = new Set<PersonResearchTaskType>([
  "identity_verification",
  "freshness_update",
]);
const canonicalPeopleBySlug = new Map(researchPeople.map((person) => [person.slug, person]));

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

function inferredWorkstream(taskType: PersonResearchTaskType): PersonResearchWorkstream {
  return MAINTENANCE_TASK_TYPES.has(taskType) ? "maintenance" : "research";
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
    researchCostEfficiency: signedInteger(row.researchCostEfficiency, -8, 8),
  };
}

function computeAllocationUtility(score: number, expectedYieldPerCost: number) {
  const efficiency = Math.min(2, Math.max(0, expectedYieldPerCost));
  return Math.round(score * (0.5 + efficiency) * 1_000) / 1_000;
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
  const rawQuestion = text(row.question, 620);
  if (
    !personSlug ||
    !taskId ||
    !rawQuestion ||
    !TASK_TYPES.has(taskType) ||
    !PRIORITIES.has(priority) ||
    !STATUSES.has(status) ||
    !EXECUTORS.has(executor)
  ) return null;

  const rawWorkstream = text(row.workstream, 40) as PersonResearchWorkstream;
  const workstream = WORKSTREAMS.has(rawWorkstream)
    ? rawWorkstream
    : inferredWorkstream(taskType);
  const breakdown = scoreBreakdown(row.scoreBreakdown);
  const recomputedScore = Object.values(breakdown).reduce((sum, value) => sum + value, 0);
  const rawQueryBudget = integer(row.queryBudget, 0, 1);
  const cooldownUntil = text(row.cooldownUntil, 40);
  const rawSearchQueries = executor === "person_video" && rawQueryBudget > 0
    ? stringList(row.searchQueries, 1, 220)
    : [];
  const expectedSuccessRate = boundedNumber(row.expectedSuccessRate, 0, 1, 0.5);
  const expectedEvidenceYield = boundedNumber(row.expectedEvidenceYield, 0, 50, 0.5);
  const queryUnitCost = boundedNumber(row.queryUnitCost, 1, 10, 1);
  const expectedYieldPerCost = boundedNumber(
    row.expectedYieldPerCost,
    0,
    50,
    expectedEvidenceYield / queryUnitCost,
  );
  const allocationUtility = computeAllocationUtility(recomputedScore, expectedYieldPerCost);
  const rawPersonName = text(row.personName, 160) || personSlug;
  const person = canonicalPeopleBySlug.get(personSlug);
  const legacyLabels = [rawPersonName];
  const canonical = (value: string) => person
    ? replaceLegacyPersonIdentityText(value, legacyLabels, person)
    : value;
  const canonicalSearch = (value: string) => person
    ? replaceLegacyPersonIdentityText(value, legacyLabels, person, "search")
    : value;
  const searchQueries = rawSearchQueries.map(canonicalSearch);

  return {
    rank: integer(row.rank, 1, 10_000),
    workstreamRank: integer(row.workstreamRank, 1, 10_000),
    workstream,
    personSlug,
    personName: person?.name ?? rawPersonName,
    taskId,
    taskType,
    priority,
    status,
    target: canonical(text(row.target, 200)),
    question: canonical(rawQuestion),
    successCriteria: canonical(text(row.successCriteria, 700)),
    executor,
    searchQueries,
    queryStrategy: text(row.queryStrategy, 80),
    queryStrategyLabel: text(row.queryStrategyLabel, 120),
    strategySampleSize: integer(row.strategySampleSize, 0, 500),
    costSampleSize: integer(row.costSampleSize, 0, 500),
    expectedSuccessRate,
    expectedEvidenceYield,
    queryUnitCost,
    expectedYieldPerCost,
    allocationUtility,
    averageQueryDurationMs: integer(row.averageQueryDurationMs, 0, 600_000),
    topHistoricalSourceType: text(row.topHistoricalSourceType, 80),
    topHistoricalSourceTypeLabel: text(row.topHistoricalSourceTypeLabel, 120),
    evidenceBasisCount: integer(row.evidenceBasisCount, 0, 10),
    candidateEvidenceCount: integer(row.candidateEvidenceCount, 0, 10),
    score: recomputedScore,
    scoreBreakdown: breakdown,
    whyNow: stringList(row.whyNow, 6, 220).map(canonical),
    cooldownUntil,
    personRoute: internalPersonRoute(row.personRoute, personSlug),
    queryBudget: searchQueries.length ? rawQueryBudget : 0,
  };
}

function selectLaneAware(
  normalized: PersonResearchQueueItem[],
  limits: PersonResearchQueue["limits"],
) {
  const research = normalized.filter((item) => item.workstream === "research");
  const maintenance = normalized.filter((item) => item.workstream === "maintenance");
  const selected: PersonResearchQueueItem[] = [];
  const selectedPeople = new Set<string>();
  const tasksPerPerson = new Map<string, number>();

  const add = (items: PersonResearchQueueItem[], laneLimit: number) => {
    let laneCount = selected.filter((item) => item.workstream === items[0]?.workstream).length;
    for (const item of items) {
      if (selected.length >= limits.tasks || laneCount >= laneLimit) break;
      if (selected.includes(item)) continue;
      const personTaskCount = tasksPerPerson.get(item.personSlug) ?? 0;
      if (personTaskCount >= limits.tasksPerPerson) continue;
      if (!selectedPeople.has(item.personSlug) && selectedPeople.size >= limits.people) continue;
      selected.push(item);
      selectedPeople.add(item.personSlug);
      tasksPerPerson.set(item.personSlug, personTaskCount + 1);
      laneCount += 1;
    }
  };

  add(research, limits.researchTasks);
  add(maintenance, limits.maintenanceTasks);
  if (selected.length < limits.tasks) add(research, limits.tasks);
  return { selected, selectedPeople };
}

export function normalizePersonResearchQueue(
  value: unknown,
  options: { requirePublishedPerson?: boolean } = {},
): PersonResearchQueue {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const limitsRow = row.limits && typeof row.limits === "object"
    ? row.limits as Record<string, unknown>
    : {};
  const tasks = integerOr(limitsRow.tasks, 20, 1, 100);
  const limits = {
    people: integerOr(limitsRow.people, 10, 1, 50),
    tasks,
    researchTasks: integerOr(limitsRow.researchTasks, Math.min(14, tasks), 1, tasks),
    maintenanceTasks: integerOr(limitsRow.maintenanceTasks, Math.min(6, tasks), 0, tasks),
    tasksPerPerson: integerOr(limitsRow.tasksPerPerson, 2, 1, 10),
    activeQuerySlots: integerOr(limitsRow.activeQuerySlots, 10, 1, 50),
    maintenanceQuerySlots: integerOr(limitsRow.maintenanceQuerySlots, 2, 0, 10),
  };
  const normalized = Array.isArray(row.queue)
    ? row.queue
        .map(normalizePersonResearchQueueItem)
        .filter((item): item is PersonResearchQueueItem => Boolean(item))
        .filter((item) => !options.requirePublishedPerson || canonicalPeopleBySlug.has(item.personSlug))
        .sort((a, b) => b.score - a.score || b.allocationUtility - a.allocationUtility || a.rank - b.rank || a.taskId.localeCompare(b.taskId))
    : [];

  const { selected, selectedPeople } = selectLaneAware(normalized, limits);
  const laneRanks: Record<PersonResearchWorkstream, number> = { research: 0, maintenance: 0 };
  const reranked = selected.map((item, index) => {
    laneRanks[item.workstream] += 1;
    return { ...item, rank: index + 1, workstreamRank: laneRanks[item.workstream] };
  });

  const researchDate = text(row.researchDate, 40);
  const queryCandidates = reranked
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => {
      const inCooldown = Boolean(item.cooldownUntil && researchDate && item.cooldownUntil > researchDate);
      return item.executor === "person_video" && item.searchQueries.length > 0 && item.queryBudget > 0 && !inCooldown;
    });

  const orderedQueries = (workstream: PersonResearchWorkstream) => queryCandidates
    .filter(({ item }) => item.workstream === workstream)
    .sort((a, b) => b.item.allocationUtility - a.item.allocationUtility || b.item.score - a.item.score || a.index - b.index);

  const allocatedIndexes = new Set<number>();
  const allocatedPeople = new Set<string>();
  for (const candidate of orderedQueries("research")) {
    if (allocatedIndexes.size >= limits.activeQuerySlots) break;
    if (allocatedPeople.has(candidate.item.personSlug)) continue;
    allocatedPeople.add(candidate.item.personSlug);
    allocatedIndexes.add(candidate.index);
  }
  let maintenanceAllocated = 0;
  for (const candidate of orderedQueries("maintenance")) {
    if (allocatedIndexes.size >= limits.activeQuerySlots || maintenanceAllocated >= limits.maintenanceQuerySlots) break;
    if (allocatedPeople.has(candidate.item.personSlug)) continue;
    allocatedPeople.add(candidate.item.personSlug);
    allocatedIndexes.add(candidate.index);
    maintenanceAllocated += 1;
  }

  const bounded = reranked.map((item, index) => ({
    ...item,
    searchQueries: allocatedIndexes.has(index) ? item.searchQueries.slice(0, 1) : [],
    queryBudget: allocatedIndexes.has(index) ? 1 : 0,
  }));

  const research = bounded.filter((item) => item.workstream === "research");
  const maintenance = bounded.filter((item) => item.workstream === "maintenance");
  const researchQueries = research.filter((item) => item.queryBudget > 0).length;
  const maintenanceQueries = maintenance.filter((item) => item.queryBudget > 0).length;
  const rawCandidateResearch = integer(row.candidateResearchTaskCount, 0, 100_000);
  const rawCandidateMaintenance = integer(row.candidateMaintenanceTaskCount, 0, 100_000);
  const inferredCandidateResearch = normalized.filter((item) => item.workstream === "research").length;
  const inferredCandidateMaintenance = normalized.filter((item) => item.workstream === "maintenance").length;

  return {
    schemaVersion: integerOr(row.schemaVersion, 1, 1, 10),
    generatedAt: text(row.generatedAt, 80),
    researchDate,
    limits,
    candidateTaskCount: Math.max(integer(row.candidateTaskCount), normalized.length),
    candidateResearchTaskCount: Math.max(rawCandidateResearch, inferredCandidateResearch),
    candidateMaintenanceTaskCount: Math.max(rawCandidateMaintenance, inferredCandidateMaintenance),
    selectedPeopleCount: selectedPeople.size,
    selectedTaskCount: bounded.length,
    selectedResearchTaskCount: research.length,
    selectedMaintenanceTaskCount: maintenance.length,
    allocatedQuerySlots: researchQueries + maintenanceQueries,
    allocatedResearchQuerySlots: researchQueries,
    allocatedMaintenanceQuerySlots: maintenanceQueries,
    outcomeMemoryAttemptCount: integer(row.outcomeMemoryAttemptCount, 0, 100_000),
    queue: bounded,
    methodology: text(row.methodology, 1_600),
  };
}

export const personResearchQueue = normalizePersonResearchQueue(publicQueue, {
  requirePublishedPerson: true,
});