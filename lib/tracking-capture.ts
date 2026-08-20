import {
  normalizeTrackingEntityResolution,
  resolveTrackingEntity,
  type TrackingEntityResolution,
} from "@/lib/entity-resolution";
import { assertSingleTrackingEntityName } from "@/lib/tracking-entity-integrity";
import {
  cloneTrackingConfig,
  slugifyTrack,
  validatePersonLabel,
  validateTrackingKeyword,
  type UserTrackingConfig,
} from "@/lib/user-tracking";

export const TRACKING_CAPTURE_INBOX_PATH = "config/tracking_capture_inbox.json";
export const TRACKING_ADMIN_TOKEN_SESSION_KEY = "no1lize:tracking-admin-token";
export const TRACKING_CAPTURE_CHANGED_EVENT = "vciq:tracking-capture-changed";

export type TrackingCaptureEntityType = "company" | "person" | "topic";
export type TrackingCaptureStatus = "queued" | "applied" | "dismissed";

export type TrackingCaptureSource = {
  articleId: string;
  title: string;
  url: string;
  summary: string;
  sourceName: string;
  channel: string;
  channelLabel: string;
  eventType: string;
};

export type TrackingCaptureRecord = {
  id: string;
  entityType: TrackingCaptureEntityType;
  canonicalName: string;
  rawSelection: string;
  aliases: string[];
  trackSlugs: string[];
  trackNames: string[];
  source: TrackingCaptureSource;
  capturedAt: string;
  capturedBy: string;
  status: TrackingCaptureStatus;
  appliedTo: string[];
  reasons: string[];
  note: string;
  resolution?: TrackingEntityResolution;
};

export type TrackingCaptureInbox = {
  schemaVersion: 1;
  generatedAt: string;
  records: TrackingCaptureRecord[];
};

export type TrackingCaptureEntityDraft = {
  entityType: TrackingCaptureEntityType;
  name: string;
};

export type ApplyTrackingCaptureInput = {
  config: UserTrackingConfig;
  inbox: TrackingCaptureInbox;
  entities: TrackingCaptureEntityDraft[];
  selectedTrackSlugs: string[];
  newTrackName?: string;
  reasons?: string[];
  note?: string;
  source: TrackingCaptureSource;
  capturedAt: string;
  capturedBy: string;
};

export type ApplyTrackingCaptureResult = {
  config: UserTrackingConfig;
  inbox: TrackingCaptureInbox;
  records: TrackingCaptureRecord[];
  addedCount: number;
  duplicateCount: number;
  reviewCount: number;
  rejectedCount: number;
  reclassifiedCount: number;
  trackSlugs: string[];
};

const ENTITY_TYPES: TrackingCaptureEntityType[] = ["company", "person", "topic"];
const STATUSES: TrackingCaptureStatus[] = ["queued", "applied", "dismissed"];

function cleanText(value: unknown, maxLength = 240): string {
  return typeof value === "string"
    ? value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength)
    : "";
}

function cleanUrl(value: unknown): string {
  const url = cleanText(value, 1200);
  return /^https?:\/\//i.test(url) ? url : "";
}

function uniqueStrings(value: unknown, maxItems = 40): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = cleanText(raw, 160);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= maxItems) break;
  }
  return result;
}

export function stableTrackingCaptureHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function normalizeSource(value: unknown): TrackingCaptureSource {
  const raw = value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
  return {
    articleId: cleanText(raw.articleId, 200),
    title: cleanText(raw.title, 240),
    url: cleanUrl(raw.url),
    summary: cleanText(raw.summary, 800),
    sourceName: cleanText(raw.sourceName, 160),
    channel: cleanText(raw.channel, 40),
    channelLabel: cleanText(raw.channelLabel, 60),
    eventType: cleanText(raw.eventType, 80),
  };
}

function normalizeRecord(value: unknown): TrackingCaptureRecord | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const entityType = ENTITY_TYPES.includes(raw.entityType as TrackingCaptureEntityType)
    ? (raw.entityType as TrackingCaptureEntityType)
    : null;
  const status = STATUSES.includes(raw.status as TrackingCaptureStatus)
    ? (raw.status as TrackingCaptureStatus)
    : "queued";
  const canonicalName = cleanText(raw.canonicalName, 120);
  const source = normalizeSource(raw.source);
  if (!entityType || !canonicalName || !source.url || !source.title) return null;
  const trackSlugs = uniqueStrings(raw.trackSlugs, 20);
  const id = cleanText(raw.id, 160) || trackingCaptureId({
    entityType,
    canonicalName,
    sourceUrl: source.url,
    trackSlugs,
  });
  const resolution = normalizeTrackingEntityResolution(raw.resolution);
  return {
    id,
    entityType,
    canonicalName,
    rawSelection: cleanText(raw.rawSelection, 160) || canonicalName,
    aliases: uniqueStrings(raw.aliases, 20),
    trackSlugs,
    trackNames: uniqueStrings(raw.trackNames, 20),
    source,
    capturedAt: cleanText(raw.capturedAt, 80),
    capturedBy: cleanText(raw.capturedBy, 120),
    status,
    appliedTo: uniqueStrings(raw.appliedTo, 40),
    reasons: uniqueStrings(raw.reasons, 12),
    note: cleanText(raw.note, 800),
    ...(resolution ? { resolution } : {}),
  };
}

export function normalizeTrackingCaptureInbox(value: unknown): TrackingCaptureInbox {
  const raw = value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
  const records = Array.isArray(raw.records)
    ? raw.records.map(normalizeRecord).filter((record): record is TrackingCaptureRecord => Boolean(record))
    : [];
  const unique = records.filter(
    (record, index) => records.findIndex((candidate) => candidate.id === record.id) === index,
  );
  unique.sort((left, right) =>
    right.capturedAt.localeCompare(left.capturedAt) ||
    left.canonicalName.localeCompare(right.canonicalName, "zh-CN"),
  );
  return {
    schemaVersion: 1,
    generatedAt: cleanText(raw.generatedAt, 80),
    records: unique,
  };
}

export function trackingCaptureId(input: {
  entityType: TrackingCaptureEntityType;
  canonicalName: string;
  sourceUrl: string;
  trackSlugs: string[];
}): string {
  const key = [
    input.entityType,
    cleanText(input.canonicalName, 120).toLocaleLowerCase("zh-CN"),
    cleanUrl(input.sourceUrl),
    [...input.trackSlugs].sort().join("|"),
  ].join("::");
  return `capture-${stableTrackingCaptureHash(key)}`;
}

function normalizeEntityDraft(draft: TrackingCaptureEntityDraft): TrackingCaptureEntityDraft {
  if (draft.entityType !== "topic") {
    assertSingleTrackingEntityName(draft.entityType, draft.name);
  }

  const rawName = cleanText(draft.name, 120);
  if (!rawName) throw new Error("追踪对象名称不能为空。");
  if (/^https?:\/\//i.test(rawName)) throw new Error("追踪对象名称不能是网址。");

  if (draft.entityType === "person") {
    const parsed = validatePersonLabel(rawName);
    if (!parsed.valid) throw new Error(`人物标签无效：${parsed.message}`);
    return { entityType: "person", name: parsed.normalized };
  }
  if (draft.entityType === "topic") {
    const parsed = validateTrackingKeyword(rawName);
    if (!parsed.valid) throw new Error(`技术／主题无效：${parsed.message}`);
    return { entityType: "topic", name: parsed.normalized };
  }
  const companyName = rawName.replace(/\s*公司$/u, "").trim();
  if (companyName.length < 2) throw new Error("公司名称至少需要两个有效字符。");
  return { entityType: "company", name: companyName };
}

function appendUnique(values: string[], value: string): { values: string[]; added: boolean } {
  const key = value.toLocaleLowerCase("zh-CN");
  if (values.some((item) => item.toLocaleLowerCase("zh-CN") === key)) {
    return { values, added: false };
  }
  return { values: [...values, value], added: true };
}

function ensureTrack(
  config: UserTrackingConfig,
  newTrackName: string,
): { config: UserTrackingConfig; slug: string } {
  const name = cleanText(newTrackName, 60);
  if (!name) return { config, slug: "" };
  const existing = config.tracks.find(
    (track) => track.name.toLocaleLowerCase("zh-CN") === name.toLocaleLowerCase("zh-CN"),
  );
  if (existing) return { config, slug: existing.slug };

  const base = slugifyTrack(name);
  let slug = base;
  let suffix = 2;
  while (config.tracks.some((track) => track.slug === slug)) {
    slug = `${base}-${suffix}`;
    suffix += 1;
  }
  return {
    config: {
      ...config,
      tracks: [
        ...config.tracks,
        {
          slug,
          name,
          enabled: true,
          custom: true,
          keywords: [],
          people: [],
          sampleCompanies: [],
        },
      ],
    },
    slug,
  };
}

export function applyTrackingCapture(input: ApplyTrackingCaptureInput): ApplyTrackingCaptureResult {
  let config = cloneTrackingConfig(input.config);
  const ensured = ensureTrack(config, input.newTrackName ?? "");
  config = ensured.config;

  const selected = uniqueStrings(
    [...input.selectedTrackSlugs, ...(ensured.slug ? [ensured.slug] : [])],
    20,
  ).filter((slug) => config.tracks.some((track) => track.slug === slug));
  if (!selected.length) throw new Error("请至少选择一个目标赛道，或填写一个新赛道名称。");

  const source = normalizeSource(input.source);
  if (!source.url || !source.title) throw new Error("来源文章标题和 URL 不完整，不能保存采集记录。");
  const entities = input.entities
    .map(normalizeEntityDraft)
    .map((entity) => ({
      entity,
      resolution: resolveTrackingEntity({
        requestedType: entity.entityType,
        name: entity.name,
        source,
      }),
    }))
    .filter(
      (row, index, rows) =>
        rows.findIndex((candidate) => {
          const leftType = row.resolution.status === "resolved"
            ? row.resolution.entityType
            : row.entity.entityType;
          const rightType = candidate.resolution.status === "resolved"
            ? candidate.resolution.entityType
            : candidate.entity.entityType;
          const leftName = row.resolution.status === "resolved"
            ? row.resolution.canonicalName
            : row.entity.name;
          const rightName = candidate.resolution.status === "resolved"
            ? candidate.resolution.canonicalName
            : candidate.entity.name;
          return (
            row.resolution.status === candidate.resolution.status &&
            leftType === rightType &&
            leftName.toLocaleLowerCase("zh-CN") === rightName.toLocaleLowerCase("zh-CN")
          );
        }) === index,
    );
  if (!entities.length) throw new Error("请至少添加一个公司、人物或技术／主题。");

  const trackNames = selected
    .map((slug) => config.tracks.find((track) => track.slug === slug)?.name ?? "")
    .filter(Boolean);
  const records: TrackingCaptureRecord[] = [];
  let addedCount = 0;
  let duplicateCount = 0;
  let reviewCount = 0;
  let rejectedCount = 0;
  let reclassifiedCount = 0;

  for (const { entity, resolution } of entities) {
    const resolved = resolution.status === "resolved";
    const entityType = resolved ? resolution.entityType : entity.entityType;
    const canonicalName = resolved ? resolution.canonicalName : entity.name;
    const appliedTo: string[] = [];

    if (resolution.status === "review") reviewCount += 1;
    if (resolution.status === "rejected") rejectedCount += 1;
    if (resolution.reclassified) reclassifiedCount += 1;

    if (resolved) {
      const field = entityType === "company"
        ? "sampleCompanies"
        : entityType === "person"
          ? "people"
          : "keywords";
      config = {
        ...config,
        tracks: config.tracks.map((track) => {
          if (!selected.includes(track.slug)) return track;
          const append = appendUnique(track[field], canonicalName);
          appliedTo.push(`${track.slug}:${field}`);
          if (append.added) addedCount += 1;
          else duplicateCount += 1;
          return append.added ? { ...track, [field]: append.values } : track;
        }),
      };
    }

    const id = trackingCaptureId({
      entityType: entity.entityType,
      canonicalName: entity.name,
      sourceUrl: source.url,
      trackSlugs: selected,
    });
    records.push({
      id,
      entityType,
      canonicalName,
      rawSelection: entity.name,
      aliases:
        canonicalName.toLocaleLowerCase("zh-CN") === entity.name.toLocaleLowerCase("zh-CN")
          ? []
          : [entity.name],
      trackSlugs: selected,
      trackNames,
      source,
      capturedAt: cleanText(input.capturedAt, 80),
      capturedBy: cleanText(input.capturedBy, 120),
      status:
        resolution.status === "resolved"
          ? "applied"
          : resolution.status === "review"
            ? "queued"
            : "dismissed",
      appliedTo,
      reasons: uniqueStrings(input.reasons ?? [], 12),
      note: cleanText(input.note, 800),
      resolution,
    });
  }

  const current = normalizeTrackingCaptureInbox(input.inbox);
  const nextRecords = [...current.records];
  for (const record of records) {
    const index = nextRecords.findIndex((candidate) => candidate.id === record.id);
    if (index >= 0) nextRecords[index] = record;
    else nextRecords.push(record);
  }

  return {
    config,
    inbox: normalizeTrackingCaptureInbox({
      schemaVersion: 1,
      generatedAt: input.capturedAt,
      records: nextRecords,
    }),
    records,
    addedCount,
    duplicateCount,
    reviewCount,
    rejectedCount,
    reclassifiedCount,
    trackSlugs: selected,
  };
}
