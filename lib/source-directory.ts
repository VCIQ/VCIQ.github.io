import { readFileSync } from "node:fs";
import { join } from "node:path";

import intelligenceSourcesConfig from "@/config/intelligence_sources.json";
import sourceCoreReviewsConfig from "@/config/source_core_reviews.json";
import sourceLifecyclePolicyConfig from "@/config/source_lifecycle_policy.json";
import {
  coreSources,
  type CoreSource,
  type CoreSourceKind,
  type SourceEndpoint,
  type SourceHealthStatus,
  type SourceRole,
} from "@/lib/core-sources";
import {
  evaluateSourcePromotion,
  type SourceCoreReview,
  type SourceLifecyclePolicy,
  type SourcePromotionMetrics,
} from "@/lib/source-lifecycle";

export type SourceDirectoryKind =
  | CoreSourceKind
  | "论文 / 原始研究"
  | "X / 发现";

export type SourceDirectoryEntry = Omit<CoreSource, "kind"> & {
  kind: SourceDirectoryKind;
};

type UnknownRecord = Record<string, unknown>;

type HealthContext = {
  generatedAt?: string;
  sources: UnknownRecord;
};

function record(value: unknown): UnknownRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : {};
}

function text(value: unknown, limit = 240): string {
  return typeof value === "string"
    ? value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, limit)
    : "";
}

function strings(value: unknown, limit = 24): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = text(raw, 120);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function safeHttpUrl(value: unknown): string | undefined {
  const raw = text(value, 1600);
  if (!raw) return undefined;
  try {
    const url = new URL(raw);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function healthStatus(value: unknown): SourceHealthStatus {
  const status = text(value, 20).toLocaleLowerCase("en-US");
  if (status === "ok") return "ok";
  if (status === "partial" || status === "empty") return "partial";
  if (status === "error" || status === "failed") return "error";
  return "unknown";
}

function loadHealthContext(): HealthContext {
  try {
    const path = join(process.cwd(), "public", "data", "source_health.json");
    const payload = record(JSON.parse(readFileSync(path, "utf-8")));
    return {
      generatedAt: text(payload.generatedAt, 80) || undefined,
      sources: record(payload.sources),
    };
  } catch {
    return { sources: {} };
  }
}

const healthContext = loadHealthContext();
const lifecyclePolicy = sourceLifecyclePolicyConfig as SourceLifecyclePolicy;

function loadCoreReviewIndex(): Map<string, SourceCoreReview> {
  const payload = record(sourceCoreReviewsConfig);
  const reviews = Array.isArray(payload.reviews) ? payload.reviews : [];
  const result = new Map<string, SourceCoreReview>();
  for (const raw of reviews) {
    const item = record(raw);
    const sourceId = text(item.sourceId, 180);
    const decision = text(item.decision, 40);
    const reviewedAt = text(item.reviewedAt, 80);
    const reviewer = text(item.reviewer, 120);
    const note = text(item.note, 600);
    if (
      !sourceId
      || !reviewedAt
      || !reviewer
      || !note
      || !["approve_core", "reject_core"].includes(decision)
    ) continue;
    const review: SourceCoreReview = {
      sourceId,
      decision: decision as SourceCoreReview["decision"],
      reviewedAt,
      reviewer,
      note,
    };
    const previous = result.get(sourceId);
    if (!previous || review.reviewedAt > previous.reviewedAt) {
      result.set(sourceId, review);
    }
  }
  return result;
}

const coreReviewIndex = loadCoreReviewIndex();

function healthRow(runtimeId: string): UnknownRecord | undefined {
  const row = record(healthContext.sources[runtimeId]);
  return Object.keys(row).length ? row : undefined;
}

function currentHealthRow(runtimeId: string): UnknownRecord | undefined {
  const row = healthRow(runtimeId);
  return row && row.missingFromCurrentRun !== true ? row : undefined;
}

function endpointFor(runtimeId: string, label: string, platform: string): SourceEndpoint {
  const row = currentHealthRow(runtimeId);
  return {
    id: `endpoint:${runtimeId}`,
    label,
    platform,
    status: row ? healthStatus(row.lastStatus) : "unknown",
    evidenceGrade: row ? text(row.evidenceGrade, 8) || undefined : undefined,
    scanned: row ? numberValue(row.scanned) : 0,
    accepted: row ? numberValue(row.accepted) : 0,
    lastSuccessAt: row ? text(row.lastSuccessAt, 80) || undefined : undefined,
    collectionState: row ? text(row.collectionState, 40) || undefined : undefined,
    publicationEligible: row && typeof row.publicationEligible === "boolean"
      ? row.publicationEligible
      : undefined,
    sourceIds: row ? [runtimeId] : [],
  };
}

function promotionMetrics(runtimeId: string): SourcePromotionMetrics | undefined {
  const row = healthRow(runtimeId);
  if (!row) return undefined;
  const performance = record(row.performance);
  if (!Object.keys(performance).length) return undefined;
  const samples = Array.isArray(performance.samples) ? performance.samples.map(record) : [];
  const persistedObservedDates = Array.isArray(performance.observedDates)
    ? performance.observedDates
      .map((value) => text(value, 80).slice(0, 10))
      .filter(Boolean)
    : [];
  const observedDays = new Set(
    persistedObservedDates.length
      ? persistedObservedDates
      : samples
        .map((sample) => text(sample.at, 80).slice(0, 10))
        .filter(Boolean),
  ).size;
  const manualQuality = record(performance.manualQuality);
  const collectionState = text(row.collectionState, 40);
  return {
    runs: optionalNumber(performance.runs),
    observedDays,
    scanned: optionalNumber(performance.scanned),
    availabilityRate: optionalNumber(performance.availabilityRate),
    validYieldRate: optionalNumber(performance.validYieldRate),
    activeCollection: collectionState ? collectionState === "active" : undefined,
    publicationEligible: typeof row.publicationEligible === "boolean"
      ? row.publicationEligible
      : undefined,
    performanceReviewRequired: typeof performance.reviewRequired === "boolean"
      ? performance.reviewRequired
      : undefined,
    reviewedRecords: optionalNumber(manualQuality.reviewedRecords),
    misattributionRate: optionalNumber(manualQuality.misattributionRate),
    evidenceSourceId: runtimeId,
  };
}

function applyPromotion(
  source: SourceDirectoryEntry,
  runtimeId: string,
): SourceDirectoryEntry {
  const promotion = evaluateSourcePromotion({
    trackingEligible: source.lifecycle !== "candidate",
    metrics: promotionMetrics(runtimeId),
    review: coreReviewIndex.get(source.id),
    policy: lifecyclePolicy,
  });
  return {
    ...source,
    lifecycle: promotion.lifecycle,
    promotion,
  };
}

function paperHomepage(platform: string, configuredUrl?: string): string | undefined {
  if (platform.toLocaleLowerCase("en-US") === "arxiv") return "https://arxiv.org/";
  return configuredUrl;
}

function paperEndpointLabel(platform: string): string {
  if (platform.toLocaleLowerCase("en-US") === "arxiv") return "arXiv Atom API";
  return `${platform || "研究源"} feed / API`;
}

function buildPaperSources(): SourceDirectoryEntry[] {
  const config = record(intelligenceSourcesConfig);
  const papers = Array.isArray(config.papers) ? config.papers : [];
  return papers.flatMap((raw): SourceDirectoryEntry[] => {
    const paper = record(raw);
    const runtimeId = text(paper.id, 100);
    const name = text(paper.name, 160);
    if (!runtimeId || !name || paper.enabled === false || numberValue(paper.maxItems) <= 0) {
      return [];
    }
    const platform = text(paper.platform, 80) || "研究仓库";
    const sourceLevel = text(paper.sourceLevel, 80) || "原始材料";
    const sector = text(paper.sector, 80);
    const configuredUrl = safeHttpUrl(paper.url);
    const endpoint = endpointFor(runtimeId, paperEndpointLabel(platform), platform);
    const source: SourceDirectoryEntry = {
      id: `paper:${runtimeId}`,
      name,
      kind: "论文 / 原始研究",
      platform,
      sourceLevel,
      sourceRole: "primary",
      region: text(paper.region, 60) || "全球",
      sectors: sector ? [sector] : [],
      keywords: strings(paper.keywords, 24),
      companies: strings(paper.trackedCompanies, 20),
      people: [],
      url: paperHomepage(platform, configuredUrl),
      lifecycle: "tracked",
      healthStatus: endpoint.status,
      healthUpdatedAt: healthContext.generatedAt,
      endpoints: [endpoint],
    };
    return [applyPromotion(source, runtimeId)];
  });
}

function xProfileUrl(handle: string): string | undefined {
  const clean = handle.replace(/^@+/, "").replace(/[^A-Za-z0-9_]/g, "");
  return clean ? `https://x.com/${clean}` : undefined;
}

function buildXProfileSources(): SourceDirectoryEntry[] {
  const config = record(intelligenceSourcesConfig);
  const profiles = Array.isArray(config.xProfiles) ? config.xProfiles : [];
  return profiles.flatMap((raw): SourceDirectoryEntry[] => {
    const profile = record(raw);
    const runtimeId = text(profile.id, 100);
    const name = text(profile.name, 160);
    const handle = text(profile.handle, 80);
    if (!runtimeId || !name || !handle || profile.enabled === false) return [];
    const endpoint = endpointFor(runtimeId, "X 公开时间线", "X");
    const profileKind = text(profile.kind, 40);
    const company = text(profile.company, 140);
    const source: SourceDirectoryEntry = {
      id: `x:${runtimeId}`,
      name: `${name} @${handle.replace(/^@+/, "")}`,
      kind: "X / 发现",
      platform: "X",
      sourceLevel: "公开社交信号",
      sourceRole: "discovery",
      region: text(profile.region, 60) || "全球",
      sectors: [],
      keywords: [],
      companies: company ? [company] : [],
      people: profileKind === "person" ? [name] : [],
      url: xProfileUrl(handle),
      lifecycle: "tracked",
      healthStatus: endpoint.status,
      healthUpdatedAt: healthContext.generatedAt,
      endpoints: [endpoint],
    };
    return [applyPromotion(source, runtimeId)];
  });
}

export const researchPaperSources = buildPaperSources();
export const xDiscoverySources = buildXProfileSources();

export const sourceDirectory: SourceDirectoryEntry[] = [
  ...(coreSources as SourceDirectoryEntry[]),
  ...researchPaperSources,
  ...xDiscoverySources,
].sort((left, right) =>
  left.kind.localeCompare(right.kind, "zh-CN")
  || left.sourceRole.localeCompare(right.sourceRole, "en-US")
  || left.name.localeCompare(right.name, "zh-CN"),
);

export const sourceDirectoryStats = {
  total: sourceDirectory.length,
  papers: researchPaperSources.length,
  xProfiles: xDiscoverySources.length,
  primary: sourceDirectory.filter((source) => source.sourceRole === "primary").length,
  corroboration: sourceDirectory.filter((source) => source.sourceRole === "corroboration").length,
  discovery: sourceDirectory.filter((source) => source.sourceRole === "discovery").length,
  healthy: sourceDirectory.filter((source) => source.healthStatus === "ok").length,
  partial: sourceDirectory.filter((source) => source.healthStatus === "partial").length,
  error: sourceDirectory.filter((source) => source.healthStatus === "error").length,
  unknown: sourceDirectory.filter((source) => source.healthStatus === "unknown").length,
  candidate: sourceDirectory.filter((source) => source.lifecycle === "candidate").length,
  tracked: sourceDirectory.filter((source) => source.lifecycle === "tracked").length,
  core: sourceDirectory.filter((source) => source.lifecycle === "core").length,
  evidencePending: sourceDirectory.filter((source) => source.promotion?.state === "evidence_pending").length,
  reviewPending: sourceDirectory.filter((source) => source.promotion?.state === "review_pending").length,
  blocked: sourceDirectory.filter((source) => source.promotion?.state === "blocked").length,
};

export function sourcesByDirectoryKind(kind: SourceDirectoryKind): SourceDirectoryEntry[] {
  return sourceDirectory.filter((source) => source.kind === kind);
}

export type { SourceHealthStatus, SourceRole } from "@/lib/core-sources";