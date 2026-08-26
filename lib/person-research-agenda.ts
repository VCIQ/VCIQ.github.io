import publicAgenda from "@/public/data/person_research_agenda.json";
import { researchPeople } from "@/lib/people-data";
import { replaceLegacyPersonIdentityText } from "@/lib/person-name-normalization";

export type PersonResearchTaskType =
  | "identity_verification"
  | "first_party_evidence"
  | "viewpoint_verification"
  | "execution_verification"
  | "freshness_update";

export type PersonResearchTaskStatus = "open" | "candidate_found" | "supported" | "blocked";

export type PersonResearchTaskEvidence = {
  title: string;
  url: string;
  source: string;
  sourceLevel?: string;
  date: string;
};

export type PersonResearchTask = {
  id: string;
  taskType: PersonResearchTaskType;
  priority: "P0" | "P1" | "P2" | "P3";
  target: string;
  question: string;
  objective: string;
  preferredEvidence: string[];
  searchQueries: string[];
  successCriteria: string;
  evidenceBasis: PersonResearchTaskEvidence[];
  candidateEvidence: PersonResearchTaskEvidence[];
  status: PersonResearchTaskStatus;
};

export type PersonResearchAgendaEntry = {
  personName: string;
  openCount: number;
  tasks: PersonResearchTask[];
};

type PersonResearchAgenda = {
  schemaVersion: number;
  generatedAt: string;
  personCount: number;
  taskCount: number;
  openTaskCount: number;
  people: Record<string, PersonResearchAgendaEntry>;
  methodology: string;
};

const TASK_TYPES = new Set<PersonResearchTaskType>([
  "identity_verification",
  "first_party_evidence",
  "viewpoint_verification",
  "execution_verification",
  "freshness_update",
]);
const TASK_STATUSES = new Set<PersonResearchTaskStatus>([
  "open",
  "candidate_found",
  "supported",
  "blocked",
]);
const TASK_PRIORITIES = new Set(["P0", "P1", "P2", "P3"] as const);

function text(value: unknown, limit = 1_000) {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function stringList(value: unknown, limit: number) {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of value) {
    const normalized = text(item, 240);
    const key = normalized.toLocaleLowerCase("zh-CN");
    if (!normalized || seen.has(key)) continue;
    seen.add(key);
    result.push(normalized);
    if (result.length >= limit) break;
  }
  return result;
}

function safeHttpUrl(value: unknown) {
  const raw = text(value, 1_200);
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : "";
  } catch {
    return "";
  }
}

function normalizeEvidence(value: unknown): PersonResearchTaskEvidence | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const url = safeHttpUrl(row.url);
  if (!url) return null;
  return {
    title: text(row.title, 300) || "未命名证据",
    url,
    source: text(row.source, 180) || "公开来源",
    sourceLevel: text(row.sourceLevel, 80) || undefined,
    date: text(row.date, 80),
  };
}

export function normalizePersonResearchTask(value: unknown): PersonResearchTask | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const taskType = text(row.taskType, 80) as PersonResearchTaskType;
  const status = text(row.status, 40) as PersonResearchTaskStatus;
  const priority = text(row.priority, 8) as PersonResearchTask["priority"];
  const id = text(row.id, 160);
  const question = text(row.question, 520);
  const successCriteria = text(row.successCriteria, 620);
  if (
    !id ||
    !question ||
    !successCriteria ||
    !TASK_TYPES.has(taskType) ||
    !TASK_STATUSES.has(status) ||
    !TASK_PRIORITIES.has(priority)
  ) return null;

  return {
    id,
    taskType,
    status,
    priority,
    target: text(row.target, 180),
    question,
    objective: text(row.objective, 620),
    preferredEvidence: stringList(row.preferredEvidence, 5),
    searchQueries: stringList(row.searchQueries, 3),
    successCriteria,
    evidenceBasis: Array.isArray(row.evidenceBasis)
      ? row.evidenceBasis.map(normalizeEvidence).filter((item): item is PersonResearchTaskEvidence => Boolean(item)).slice(0, 3)
      : [],
    candidateEvidence: Array.isArray(row.candidateEvidence)
      ? row.candidateEvidence.map(normalizeEvidence).filter((item): item is PersonResearchTaskEvidence => Boolean(item)).slice(0, 4)
      : [],
  };
}

export function normalizePersonResearchAgenda(value: unknown): PersonResearchAgenda {
  const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const rawPeople = row.people && typeof row.people === "object" ? row.people as Record<string, unknown> : {};
  const people: Record<string, PersonResearchAgendaEntry> = {};
  for (const [slug, rawEntry] of Object.entries(rawPeople)) {
    if (!rawEntry || typeof rawEntry !== "object") continue;
    const entry = rawEntry as Record<string, unknown>;
    const tasks = Array.isArray(entry.tasks)
      ? entry.tasks.map(normalizePersonResearchTask).filter((item): item is PersonResearchTask => Boolean(item))
      : [];
    if (!tasks.length) continue;
    people[slug] = {
      personName: text(entry.personName, 160),
      openCount: tasks.filter((task) => task.status !== "supported").length,
      tasks,
    };
  }
  const entries = Object.values(people);
  return {
    schemaVersion: Number(row.schemaVersion) || 1,
    generatedAt: text(row.generatedAt, 80),
    personCount: entries.length,
    taskCount: entries.reduce((sum, entry) => sum + entry.tasks.length, 0),
    openTaskCount: entries.reduce((sum, entry) => sum + entry.openCount, 0),
    people,
    methodology: text(row.methodology, 800),
  };
}

const canonicalPeopleBySlug = new Map(researchPeople.map((person) => [person.slug, person]));

function canonicalizeAgendaEntry(slug: string, entry: PersonResearchAgendaEntry): PersonResearchAgendaEntry {
  const person = canonicalPeopleBySlug.get(slug);
  if (!person) return entry;
  const legacyLabels = [entry.personName];
  return {
    ...entry,
    personName: person.name,
    tasks: entry.tasks.map((task) => ({
      ...task,
      target: replaceLegacyPersonIdentityText(task.target, legacyLabels, person),
      question: replaceLegacyPersonIdentityText(task.question, legacyLabels, person),
      objective: replaceLegacyPersonIdentityText(task.objective, legacyLabels, person),
      searchQueries: task.searchQueries.map((query) =>
        replaceLegacyPersonIdentityText(query, legacyLabels, person, "search")
      ),
      successCriteria: replaceLegacyPersonIdentityText(task.successCriteria, legacyLabels, person),
    })),
  };
}

const normalizedAgenda = normalizePersonResearchAgenda(publicAgenda);
export const personResearchAgenda: PersonResearchAgenda = {
  ...normalizedAgenda,
  people: Object.fromEntries(
    Object.entries(normalizedAgenda.people).map(([slug, entry]) => [slug, canonicalizeAgendaEntry(slug, entry)]),
  ),
};

export function getPersonResearchAgenda(slug: string): PersonResearchAgendaEntry | null {
  return personResearchAgenda.people[slug] ?? null;
}
