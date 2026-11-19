import rawArticles from "@/public/data/articles.json";
import rawInbox from "@/config/tracking_capture_inbox.json";
import rawEntityRecords from "@/config/tracking_entity_records.json";
import { people } from "@/lib/catalog-data";
import { companyCandidateSnapshot } from "@/lib/company-candidate-data";
import {
  companyEntities,
  normalizeCompanyIdentity,
  resolveArticleCompanyEntities,
} from "@/lib/company-entity-registry";
import { companyRegistryEntries } from "@/lib/company-registry";
import {
  normalizeTrackingCaptureInbox,
  stableTrackingCaptureHash,
  type TrackingCaptureEntityType,
  type TrackingCaptureRecord,
} from "@/lib/tracking-capture";
import {
  publishedTrackingCaptureDescriptor,
} from "@/lib/tracking-entity-publication";
import {
  normalizeTrackingEntityRecordManifest,
  trackingEntityPriorityLabel,
  trackingEntityPriorityStars,
  type TrackingEntityAnalystNote,
  type TrackingEntityResearchRecord,
} from "@/lib/tracking-entity-records";
import { slugifyTrack, userTrackingConfig } from "@/lib/user-tracking";

export type TrackingResearchEntityType = TrackingCaptureEntityType;
export type TrackingResearchEntityState = "formal" | "candidate" | "tracked";
export type TrackingResearchTimelineOrigin = "manual-capture" | "intelligence" | "analyst-note";

export type TrackingResearchTimelineItem = {
  id: string;
  origin: TrackingResearchTimelineOrigin;
  title: string;
  summary: string;
  url: string;
  sourceName: string;
  eventType: string;
  channel: string;
  channelLabel: string;
  eventDate: string;
  observedAt: string;
  sortAt: string;
  capturedBy: string;
  captureIds: string[];
  reasons: string[];
  note: string;
};

export type TrackingResearchEntity = {
  id: string;
  entityType: TrackingResearchEntityType;
  slug: string;
  name: string;
  aliases: string[];
  trackSlugs: string[];
  trackNames: string[];
  state: TrackingResearchEntityState;
  formalHref: string;
  formalLabel: string;
  candidateStatus: string;
  summary: string;
  firstTrackedAt: string;
  lastActivityAt: string;
  captureCount: number;
  articleCount: number;
  reasons: string[];
  notes: string[];
  priority: number;
  priorityLabel: string;
  priorityStars: string;
  researchThesis: string;
  analystNotes: TrackingEntityAnalystNote[];
  researchRecord?: TrackingEntityResearchRecord;
  timeline: TrackingResearchTimelineItem[];
};

type RawArticle = {
  id?: string;
  title?: string;
  summary?: string;
  type?: string;
  region?: string;
  sector?: string;
  company?: string;
  companySlug?: string;
  companySlugs?: string[];
  companyCandidateSlugs?: string[];
  companyMatch?: { slug: string; method: string; confidence: number };
  companyMatches?: { slug: string; method: string; confidence: number }[];
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  publishedAt?: string;
  firstSeenAt?: string;
  trackSlugs?: string[];
  source?: {
    name?: string;
    platform?: string;
    url?: string;
  };
};

type RawArticlePayload = {
  generatedAt?: string;
  articles?: RawArticle[];
};

type MutableEntity = {
  id: string;
  entityType: TrackingResearchEntityType;
  name: string;
  aliases: Set<string>;
  trackSlugs: Set<string>;
  trackNames: Set<string>;
  formalSlug: string;
  formalHref: string;
  formalLabel: string;
  formalSummary: string;
  candidateStatus: string;
  captures: TrackingCaptureRecord[];
  reasons: Set<string>;
  notes: Set<string>;
  researchRecord?: TrackingEntityResearchRecord;
  configured: boolean;
};

const captureInbox = normalizeTrackingCaptureInbox(rawInbox);
const entityRecordManifest = normalizeTrackingEntityRecordManifest(rawEntityRecords);
const articlesPayload = rawArticles as RawArticlePayload;
const articles = articlesPayload.articles ?? [];

const TYPE_LABELS: Record<TrackingResearchEntityType, string> = {
  company: "公司",
  person: "人物",
  topic: "技术／主题",
};

function text(value: unknown, limit = 1_200) {
  return String(value ?? "").normalize("NFKC").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function unique(values: Iterable<string>, limit = 100) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = text(raw, 500);
    const key = normalizeIdentity(value);
    if (!value || !key || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

export function normalizeTrackingResearchIdentity(value: string | undefined) {
  return normalizeIdentity(value ?? "");
}

// Entity timelines compare the same article text with many tracked names.
// Cache this pure normalization, with a limit for long-lived SSR processes.
const normalizedIdentityCache = new Map<string, string>();
const MAX_NORMALIZED_IDENTITY_CACHE = 16_384;

function normalizeIdentity(value: string) {
  const cached = normalizedIdentityCache.get(value);
  if (cached !== undefined) return cached;
  const normalized = text(value, 500)
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
  if (normalizedIdentityCache.size >= MAX_NORMALIZED_IDENTITY_CACHE) {
    const oldest = normalizedIdentityCache.keys().next().value;
    if (oldest !== undefined) normalizedIdentityCache.delete(oldest);
  }
  normalizedIdentityCache.set(value, normalized);
  return normalized;
}

function canonicalUrl(value: string | undefined) {
  try {
    const url = new URL(String(value ?? ""));
    for (const key of [...url.searchParams.keys()]) {
      if (/^(?:utm_|spm$|from$|ref$|source$)/iu.test(key)) url.searchParams.delete(key);
    }
    url.hash = "";
    return url.toString();
  } catch {
    return text(value, 2_000);
  }
}

function dateOnly(value: string | undefined) {
  const normalized = text(value, 80);
  const match = normalized.match(/^\d{4}-\d{2}-\d{2}/u);
  return match?.[0] ?? "";
}

function strongAlias(alias: string) {
  const normalized = normalizeIdentity(alias);
  if (!normalized) return false;
  return /[\u3400-\u9fff]/u.test(normalized)
    ? normalized.length >= 3
    : normalized.length >= 4;
}

function textContainsAlias(haystack: string, alias: string) {
  if (!strongAlias(alias)) return false;
  const normalizedAlias = normalizeIdentity(alias);
  if (/[\u3400-\u9fff]/u.test(normalizedAlias)) {
    return normalizeIdentity(haystack).includes(normalizedAlias);
  }
  const escaped = text(alias, 300).replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${escaped}(?=$|[^a-z0-9])`, "iu").test(haystack);
}

const companyAliases = new Map<string, typeof companyRegistryEntries>();
for (const company of companyRegistryEntries) {
  for (const alias of unique([
    company.name,
    company.englishName ?? "",
    ...(company.aliases ?? []),
  ])) {
    const key = normalizeCompanyIdentity(alias);
    companyAliases.set(key, [...(companyAliases.get(key) ?? []), company]);
  }
}

const peopleAliases = new Map<string, typeof people>();
for (const person of people) {
  for (const alias of unique([person.name, person.englishName])) {
    const key = normalizeIdentity(alias);
    peopleAliases.set(key, [...(peopleAliases.get(key) ?? []), person]);
  }
}

function uniqueCompany(value: string) {
  const matches = companyAliases.get(normalizeCompanyIdentity(value)) ?? [];
  return matches.length === 1 ? matches[0] : undefined;
}

function uniquePerson(value: string) {
  const matches = peopleAliases.get(normalizeIdentity(value)) ?? [];
  return matches.length === 1 ? matches[0] : undefined;
}

function candidateForName(value: string) {
  const key = normalizeIdentity(value);
  return companyCandidateSnapshot.candidates.find(
    (candidate) =>
      normalizeIdentity(candidate.name) === key ||
      candidate.aliases.some((alias) => normalizeIdentity(alias) === key),
  );
}

function entityDescriptor(entityType: TrackingResearchEntityType, rawName: string) {
  const name = text(rawName, 240);
  if (entityType === "company") {
    const formal = uniqueCompany(name);
    if (formal) {
      return {
        id: `company:${formal.slug}`,
        name: formal.name,
        aliases: unique([formal.name, formal.englishName ?? "", ...(formal.aliases ?? []), name]),
        formalSlug: formal.slug,
        formalHref: `/companies/${formal.slug}`,
        formalLabel: "正式公司档案",
        formalSummary: formal.summary,
      };
    }
  }
  if (entityType === "person") {
    const formal = uniquePerson(name);
    if (formal) {
      return {
        id: `person:${formal.slug}`,
        name: formal.name,
        aliases: unique([formal.name, formal.englishName, name]),
        formalSlug: formal.slug,
        formalHref: `/people/${formal.slug}`,
        formalLabel: "正式人物档案",
        formalSummary: formal.summary,
      };
    }
  }
  const identity = normalizeIdentity(name);
  return {
    id: `${entityType}:${identity}`,
    name,
    aliases: [name],
    formalSlug: "",
    formalHref: "",
    formalLabel: "",
    formalSummary: "",
  };
}

function buildMutableEntities() {
  const map = new Map<string, MutableEntity>();

  const ensure = (
    entityType: TrackingResearchEntityType,
    name: string,
    options: {
      trackSlug?: string;
      trackName?: string;
      configured?: boolean;
      capture?: TrackingCaptureRecord;
      record?: TrackingEntityResearchRecord;
    } = {},
  ) => {
    const descriptor = entityDescriptor(entityType, name);
    if (!descriptor.name || !descriptor.id.endsWith(normalizeIdentity(descriptor.name)) && !descriptor.formalSlug) {
      if (!descriptor.name) return undefined;
    }
    let entity = map.get(descriptor.id);
    if (!entity) {
      const candidate = entityType === "company" ? candidateForName(descriptor.name) : undefined;
      entity = {
        id: descriptor.id,
        entityType,
        name: descriptor.name,
        aliases: new Set(descriptor.aliases),
        trackSlugs: new Set(),
        trackNames: new Set(),
        formalSlug: descriptor.formalSlug,
        formalHref: descriptor.formalHref,
        formalLabel: descriptor.formalLabel,
        formalSummary: descriptor.formalSummary,
        candidateStatus: candidate?.status ?? "",
        captures: [],
        reasons: new Set(),
        notes: new Set(),
        researchRecord: undefined,
        configured: false,
      };
      map.set(descriptor.id, entity);
    }
    descriptor.aliases.forEach((alias) => entity?.aliases.add(alias));
    if (options.trackSlug) entity.trackSlugs.add(options.trackSlug);
    if (options.trackName) entity.trackNames.add(options.trackName);
    entity.configured ||= Boolean(options.configured);
    if (options.capture) {
      entity.captures.push(options.capture);
      options.capture.aliases.forEach((alias) => entity?.aliases.add(alias));
      options.capture.trackSlugs.forEach((slug) => entity?.trackSlugs.add(slug));
      options.capture.trackNames.forEach((trackName) => entity?.trackNames.add(trackName));
      (options.capture.reasons ?? []).forEach((reason) => entity?.reasons.add(reason));
      if (options.capture.note) entity.notes.add(options.capture.note);
    }
    if (options.record) {
      entity.researchRecord = options.record;
      options.record.reasons.forEach((reason) => entity?.reasons.add(reason));
    }
    return entity;
  };

  for (const track of userTrackingConfig.tracks.filter((item) => item.enabled)) {
    for (const company of track.sampleCompanies) {
      ensure("company", company, {
        trackSlug: track.slug,
        trackName: track.name,
        configured: true,
      });
    }
    for (const person of track.people) {
      ensure("person", person, {
        trackSlug: track.slug,
        trackName: track.name,
        configured: true,
      });
    }
    ensure("topic", track.name, {
      trackSlug: track.slug,
      trackName: track.name,
      configured: true,
    });
  }

  for (const capture of captureInbox.records) {
    const descriptor = publishedTrackingCaptureDescriptor(capture);
    if (!descriptor) continue;
    ensure(descriptor.entityType, descriptor.canonicalName, { capture });
  }

  for (const record of Object.values(entityRecordManifest.records)) {
    ensure(record.entityType, record.canonicalName, { record });
  }

  return [...map.values()];
}

function articleStructuredNames(article: RawArticle, entityType: TrackingResearchEntityType) {
  if (entityType === "company") {
    return unique([
      article.company ?? "",
      ...(article.mentionedCompanies ?? []),
    ]);
  }
  if (entityType === "person") return unique(article.mentionedPeople ?? []);
  return unique([article.sector ?? "", article.type ?? ""]);
}

function articleMatchesEntity(article: RawArticle, entity: MutableEntity) {
  if (!article.source?.url || !article.title) return false;
  if (entity.entityType === "company" && entity.formalSlug) {
    const storedSlugs = new Set([
      article.companySlug ?? "",
      ...(article.companySlugs ?? []),
      ...(article.companyCandidateSlugs ?? []),
      ...(article.companyMatches ?? [])
        .filter((match) => Number(match.confidence) >= 0.9)
        .map((match) => match.slug ?? ""),
      ...(article.companyMatch && Number(article.companyMatch.confidence) >= 0.9
        ? [article.companyMatch.slug ?? ""]
        : []),
    ]);
    if (storedSlugs.has(entity.formalSlug)) return true;
    if (resolveArticleCompanyEntities(article).some((company) => company.slug === entity.formalSlug)) {
      return true;
    }
  }

  const entityKeys = new Set([...entity.aliases].map(normalizeIdentity).filter(Boolean));
  if (
    articleStructuredNames(article, entity.entityType).some((name) =>
      entityKeys.has(normalizeIdentity(name)),
    )
  ) {
    return true;
  }

  if (entity.entityType === "topic") {
    if ([...(article.trackSlugs ?? [])].some((slug) => entity.trackSlugs.has(slug))) {
      const trackNameIsEntity = entity.trackNames.has(entity.name);
      if (trackNameIsEntity) return true;
    }
  }

  const combined = `${article.title ?? ""} ${article.summary ?? ""}`;
  return [...entity.aliases].some((alias) => textContainsAlias(combined, alias));
}

function articleTimelineItem(article: RawArticle): TrackingResearchTimelineItem | null {
  const url = canonicalUrl(article.source?.url);
  const title = text(article.title, 300);
  if (!url || !title) return null;
  const eventDate = dateOnly(article.publishedAt);
  const observedAt = text(article.firstSeenAt, 80);
  return {
    id: text(article.id, 200) || `article-${stableTrackingCaptureHash(`${title}|${url}`)}`,
    origin: "intelligence",
    title,
    summary: text(article.summary, 1_000),
    url,
    sourceName: text(article.source?.platform || article.source?.name, 180) || "公开来源",
    eventType: text(article.type, 100) || "公开动态",
    channel: "",
    channelLabel: "公开情报",
    eventDate,
    observedAt,
    sortAt: eventDate ? `${eventDate}T23:59:59Z` : observedAt,
    capturedBy: "",
    captureIds: [],
    reasons: [],
    note: "",
  };
}

function captureTimelineItem(capture: TrackingCaptureRecord): TrackingResearchTimelineItem {
  const eventDate = dateOnly(capture.capturedAt);
  return {
    id: capture.id,
    origin: "manual-capture",
    title: capture.source.title,
    summary: capture.source.summary,
    url: canonicalUrl(capture.source.url),
    sourceName: capture.source.sourceName || "公开来源",
    eventType: capture.source.eventType || "人工发现",
    channel: capture.source.channel,
    channelLabel: capture.source.channelLabel || "人工采集",
    eventDate,
    observedAt: capture.capturedAt,
    sortAt: capture.capturedAt || (eventDate ? `${eventDate}T23:59:59Z` : ""),
    capturedBy: capture.capturedBy,
    captureIds: [capture.id],
    reasons: unique(capture.reasons ?? []),
    note: text(capture.note, 1_000),
  };
}

function analystNoteTimelineItem(
  entity: MutableEntity,
  note: TrackingEntityAnalystNote,
): TrackingResearchTimelineItem {
  return {
    id: note.id,
    origin: "analyst-note",
    title: `${entity.name} 研究笔记`,
    summary: note.body,
    url: "",
    sourceName: "VCIQ 研究记录",
    eventType: "研究笔记",
    channel: "research",
    channelLabel: "人工研究",
    eventDate: dateOnly(note.createdAt),
    observedAt: note.createdAt,
    sortAt: note.createdAt,
    capturedBy: note.createdBy,
    captureIds: [],
    reasons: [],
    note: "",
  };
}

function buildTimeline(entity: MutableEntity) {
  const byUrl = new Map<string, TrackingResearchTimelineItem>();
  for (const article of articles) {
    if (!articleMatchesEntity(article, entity)) continue;
    const item = articleTimelineItem(article);
    if (!item) continue;
    const key = canonicalUrl(item.url) || item.id;
    const existing = byUrl.get(key);
    if (!existing || item.sortAt > existing.sortAt) byUrl.set(key, item);
  }

  for (const capture of entity.captures) {
    const item = captureTimelineItem(capture);
    const key = canonicalUrl(item.url) || item.id;
    const existing = byUrl.get(key);
    if (existing) {
      byUrl.set(key, {
        ...existing,
        origin: "manual-capture",
        observedAt: item.observedAt || existing.observedAt,
        capturedBy: item.capturedBy,
        captureIds: unique([...existing.captureIds, ...item.captureIds]),
        reasons: unique([...existing.reasons, ...item.reasons]),
        note: item.note || existing.note,
        channel: item.channel || existing.channel,
        channelLabel: item.channelLabel || existing.channelLabel,
        sortAt: item.sortAt > existing.sortAt ? item.sortAt : existing.sortAt,
      });
    } else {
      byUrl.set(key, item);
    }
  }

  for (const note of entity.researchRecord?.notes ?? []) {
    byUrl.set(`analyst:${note.id}`, analystNoteTimelineItem(entity, note));
  }

  return [...byUrl.values()]
    .sort((left, right) =>
      right.sortAt.localeCompare(left.sortAt) ||
      right.title.localeCompare(left.title, "zh-CN"),
    )
    .slice(0, 120);
}

function routeSlug(entity: MutableEntity) {
  if (entity.formalSlug) return entity.formalSlug;
  const base = slugifyTrack(entity.name);
  return `${base}-${stableTrackingCaptureHash(entity.id).slice(0, 6)}`;
}

function stateFor(entity: MutableEntity): TrackingResearchEntityState {
  if (entity.formalHref) return "formal";
  if (entity.entityType === "company" && entity.candidateStatus) return "candidate";
  return "tracked";
}

function entitySummary(entity: MutableEntity) {
  if (entity.researchRecord?.thesis) return entity.researchRecord.thesis;
  if (entity.formalSummary) return entity.formalSummary;
  const tracks = [...entity.trackNames];
  if (entity.entityType === "topic") {
    return `围绕${tracks.length ? tracks.join("、") : entity.name}持续汇集公开材料、人工发现与研究线索。`;
  }
  return `${TYPE_LABELS[entity.entityType]}追踪对象，当前关联${tracks.length || 0}个赛道和可追溯公开情报。`;
}

export const trackingResearchEntities: TrackingResearchEntity[] = buildMutableEntities()
  .map((entity) => {
    const timeline = buildTimeline(entity);
    const captureDates = entity.captures.map((capture) => capture.capturedAt).filter(Boolean);
    const recordDates = [
      entity.researchRecord?.createdAt ?? "",
      ...(entity.researchRecord?.notes ?? []).map((note) => note.createdAt),
    ].filter(Boolean);
    const firstTrackedAt = [...captureDates, ...recordDates].sort()[0] ?? "";
    const lastActivityAt = timeline[0]?.sortAt ?? firstTrackedAt;
    const articleCount = timeline.filter((item) => item.origin === "intelligence").length;
    return {
      id: entity.id,
      entityType: entity.entityType,
      slug: routeSlug(entity),
      name: entity.name,
      aliases: unique(entity.aliases),
      trackSlugs: [...entity.trackSlugs].sort(),
      trackNames: [...entity.trackNames].sort((left, right) => left.localeCompare(right, "zh-CN")),
      state: stateFor(entity),
      formalHref: entity.formalHref,
      formalLabel: entity.formalLabel,
      candidateStatus: entity.candidateStatus,
      summary: entitySummary(entity),
      firstTrackedAt,
      lastActivityAt,
      captureCount: entity.captures.length,
      articleCount,
      reasons: unique(entity.reasons),
      notes: unique(entity.notes),
      priority: entity.researchRecord?.priority ?? 0,
      priorityLabel: trackingEntityPriorityLabel(entity.researchRecord?.priority ?? 0),
      priorityStars: trackingEntityPriorityStars(entity.researchRecord?.priority ?? 0),
      researchThesis: entity.researchRecord?.thesis ?? "",
      analystNotes: entity.researchRecord?.notes ?? [],
      researchRecord: entity.researchRecord,
      timeline,
    } satisfies TrackingResearchEntity;
  })
  .sort((left, right) =>
    right.lastActivityAt.localeCompare(left.lastActivityAt) ||
    right.captureCount - left.captureCount ||
    left.name.localeCompare(right.name, "zh-CN"),
  );

const entityByRoute = new Map(
  trackingResearchEntities.map((entity) => [`${entity.entityType}:${entity.slug}`, entity]),
);

export function trackingResearchEntity(
  entityType: TrackingResearchEntityType,
  slug: string,
) {
  return entityByRoute.get(`${entityType}:${slug}`);
}

export function trackingResearchHref(
  entity: Pick<TrackingResearchEntity, "entityType" | "slug">,
) {
  return `/tracking/entities/${entity.entityType}/${entity.slug}`;
}

export function relatedTrackingResearchEntities(
  entity: TrackingResearchEntity,
  limit = 8,
) {
  const tracks = new Set(entity.trackSlugs);
  return trackingResearchEntities
    .filter((candidate) => candidate.id !== entity.id)
    .map((candidate) => ({
      candidate,
      overlap: candidate.trackSlugs.filter((slug) => tracks.has(slug)).length,
    }))
    .filter((row) => row.overlap > 0)
    .sort((left, right) =>
      right.overlap - left.overlap ||
      right.candidate.lastActivityAt.localeCompare(left.candidate.lastActivityAt),
    )
    .slice(0, limit)
    .map((row) => row.candidate);
}

export const trackingResearchStats = {
  entityCount: trackingResearchEntities.length,
  companyCount: trackingResearchEntities.filter((entity) => entity.entityType === "company").length,
  personCount: trackingResearchEntities.filter((entity) => entity.entityType === "person").length,
  topicCount: trackingResearchEntities.filter((entity) => entity.entityType === "topic").length,
  formalCount: trackingResearchEntities.filter((entity) => entity.state === "formal").length,
  candidateCount: trackingResearchEntities.filter((entity) => entity.state === "candidate").length,
  capturedCount: trackingResearchEntities.filter((entity) => entity.captureCount > 0).length,
  priorityCount: trackingResearchEntities.filter((entity) => entity.priority >= 4).length,
  noteCount: trackingResearchEntities.reduce((total, entity) => total + entity.analystNotes.length, 0),
};

export const trackingResearchGeneratedAt = text(articlesPayload.generatedAt, 80);

// Keep the imported registry live in this module's dependency graph so official
// source aliases used by resolveArticleCompanyEntities remain part of the build.
void companyEntities;
