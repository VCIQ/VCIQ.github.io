import { readFileSync } from "node:fs";
import { join } from "node:path";

import intelligenceSourcesConfig from "@/config/intelligence_sources.json";
import listedCompanyDisclosureSourcesConfig from "@/config/listed_company_disclosure_sources.json";
import officialCompanySourcesConfig from "@/config/official_company_sources.json";
import sourceCoreReviewsConfig from "@/config/source_core_reviews.json";
import sourceLifecyclePolicyConfig from "@/config/source_lifecycle_policy.json";
import wechatSourcesConfig from "@/config/wechat_sources.json";
import {
  evaluateSourcePromotion,
  type SourceCoreReview,
  type SourceLifecycle,
  type SourceLifecyclePolicy,
  type SourcePromotionEvaluation,
  type SourcePromotionMetrics,
} from "@/lib/source-lifecycle";

export type CoreSourceKind = "微信公众号" | "媒体 / 研究" | "官方 / 原始";
export type { SourceLifecycle } from "@/lib/source-lifecycle";
export type SourceHealthStatus = "ok" | "partial" | "error" | "unknown";
export type SourceRole = "primary" | "corroboration" | "discovery";

export type SourceEndpoint = {
  id: string;
  label: string;
  platform: string;
  status: SourceHealthStatus;
  evidenceGrade?: string;
  scanned: number;
  accepted: number;
  lastSuccessAt?: string;
  collectionState?: string;
  publicationEligible?: boolean;
  sourceIds: string[];
};

export type CoreSource = {
  id: string;
  name: string;
  kind: CoreSourceKind;
  platform: string;
  sourceLevel: string;
  sourceRole: SourceRole;
  region: string;
  sectors: string[];
  keywords: string[];
  companies: string[];
  people: string[];
  url?: string;
  lifecycle: SourceLifecycle;
  promotion?: SourcePromotionEvaluation;
  healthStatus: SourceHealthStatus;
  healthUpdatedAt?: string;
  endpoints: SourceEndpoint[];
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

function text(value: unknown, limit = 160): string {
  return typeof value === "string"
    ? value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, limit)
    : "";
}

function strings(value: unknown, limit = 24): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of value) {
    const item = text(raw, 100);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function safeHttpUrl(value: unknown): string | undefined {
  const raw = text(value, 1200);
  if (!raw) return undefined;
  try {
    const url = new URL(raw);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function sourceKind(platform: string, sourceLevel: string): CoreSourceKind {
  if (platform === "微信") return "微信公众号";
  if (["官方披露", "原始材料", "监管文件"].includes(sourceLevel)) {
    return "官方 / 原始";
  }
  return "媒体 / 研究";
}

function sourceRole(sourceLevel: string, platform: string): SourceRole {
  if (["官方披露", "原始材料", "监管文件"].includes(sourceLevel)) return "primary";
  if (platform === "微信") return "discovery";
  return "corroboration";
}

function sectorKeys(value: unknown): string[] {
  const source = record(value);
  return Object.keys(source).map((item) => text(item, 80)).filter(Boolean).slice(0, 16);
}

function flattenSectorKeywords(value: unknown): string[] {
  const source = record(value);
  return strings(Object.values(source).flatMap((entry) => Array.isArray(entry) ? entry : []), 32);
}

function normalizedIdentity(value: unknown): string {
  return text(value, 240)
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/g, "");
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
    const review = record(raw);
    const sourceId = text(review.sourceId, 180);
    const decision = text(review.decision, 40);
    const reviewedAt = text(review.reviewedAt, 80);
    const reviewer = text(review.reviewer, 120);
    const note = text(review.note, 600);
    if (
      !sourceId
      || !reviewedAt
      || !reviewer
      || !note
      || !["approve_core", "reject_core"].includes(decision)
    ) continue;
    const parsed: SourceCoreReview = {
      sourceId,
      decision: decision as SourceCoreReview["decision"],
      reviewedAt,
      reviewer,
      note,
    };
    const previous = result.get(sourceId);
    if (!previous || parsed.reviewedAt > previous.reviewedAt) result.set(sourceId, parsed);
  }
  return result;
}

const coreReviewIndex = loadCoreReviewIndex();

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

function bestEvidenceGrade(values: string[]): string | undefined {
  const rank = new Map([
    ["A", 0],
    ["B", 1],
    ["C", 2],
    ["D", 3],
  ]);
  return values
    .filter((value) => rank.has(value))
    .sort((left, right) => (rank.get(left) ?? 99) - (rank.get(right) ?? 99))[0];
}

function newestTimestamp(values: string[]): string | undefined {
  return values.filter(Boolean).sort((left, right) => right.localeCompare(left))[0];
}

function channelLabel(sourceId: string, platform: string): string {
  const id = sourceId.toLocaleLowerCase("en-US");
  // A media entity can retain its historical `user-track-wechat-*` runtime
  // id while the accepted article comes from a verified publisher-owned
  // website or official cross-platform account. Explicit runtime provenance
  // must win over the legacy id prefix in the source directory.
  if (platform === "官方网站") return "官网文章";
  if (platform === "搜狐号") return "官方同步稿 · 搜狐号";
  if (id.includes("sohu")) return "搜狐公开页";
  if (id.includes("wechat") || platform === "微信") return "微信公开索引";
  if (id.includes("sec") || platform.includes("SEC")) return "监管披露";
  if (id.includes("cninfo") || platform.includes("巨潮")) return "交易所 / 公告平台";
  if (id.includes("auto-media")) return "公开网页";
  return platform || "公开网页";
}

function combineChannelStatus(statuses: SourceHealthStatus[]): SourceHealthStatus {
  if (!statuses.length) return "unknown";
  const unique = new Set(statuses);
  if (unique.size === 1) return statuses[0];
  if (unique.has("partial")) return "partial";
  if (unique.has("ok") && unique.has("error")) return "partial";
  if (unique.has("ok")) return "ok";
  if (unique.has("error")) return "error";
  return "unknown";
}

function overallPublisherStatus(endpoints: SourceEndpoint[]): SourceHealthStatus {
  if (endpoints.some((endpoint) => endpoint.status === "ok")) return "ok";
  if (endpoints.some((endpoint) => endpoint.status === "partial")) return "partial";
  if (endpoints.some((endpoint) => endpoint.status === "error")) return "error";
  return "unknown";
}

function healthRows(
  matcher: (sourceId: string, item: UnknownRecord) => boolean,
): Array<{ sourceId: string; item: UnknownRecord }> {
  return Object.entries(healthContext.sources).flatMap(([sourceId, raw]) => {
    const item = record(raw);
    return matcher(sourceId, item) ? [{ sourceId, item }] : [];
  });
}

function activeHealthRows(
  matcher: (sourceId: string, item: UnknownRecord) => boolean,
): Array<{ sourceId: string; item: UnknownRecord }> {
  return healthRows(matcher).filter(({ item }) => item.missingFromCurrentRun !== true);
}

function buildEndpoints(
  rows: Array<{ sourceId: string; item: UnknownRecord }>,
  fallback: { id: string; label: string; platform: string },
): SourceEndpoint[] {
  const groups = new Map<string, Array<{ sourceId: string; item: UnknownRecord }>>();
  for (const row of rows) {
    const platform = text(row.item.platform, 80);
    const label = channelLabel(row.sourceId, platform);
    const existing = groups.get(label) ?? [];
    existing.push(row);
    groups.set(label, existing);
  }

  const endpoints = [...groups.entries()].map(([label, grouped]): SourceEndpoint => {
    const statuses = grouped.map(({ item }) => healthStatus(item.lastStatus));
    const grades = grouped.map(({ item }) => text(item.evidenceGrade, 8)).filter(Boolean);
    const lastSuccesses = grouped.map(({ item }) => text(item.lastSuccessAt, 80)).filter(Boolean);
    const collectionStates = grouped.map(({ item }) => text(item.collectionState, 40)).filter(Boolean);
    const publicationEligibleValues = grouped
      .map(({ item }) => item.publicationEligible)
      .filter((value): value is boolean => typeof value === "boolean");
    return {
      id: `${fallback.id}:${normalizedIdentity(label) || "channel"}`,
      label,
      platform: text(grouped[0]?.item.platform, 80) || fallback.platform,
      status: combineChannelStatus(statuses),
      evidenceGrade: bestEvidenceGrade(grades),
      scanned: grouped.reduce((total, { item }) => total + numberValue(item.scanned), 0),
      accepted: grouped.reduce((total, { item }) => total + numberValue(item.accepted), 0),
      lastSuccessAt: newestTimestamp(lastSuccesses),
      collectionState: collectionStates.includes("active")
        ? "active"
        : collectionStates[0] || undefined,
      publicationEligible: publicationEligibleValues.length
        ? publicationEligibleValues.some(Boolean)
        : undefined,
      sourceIds: grouped.map(({ sourceId }) => sourceId).sort(),
    };
  });

  if (!endpoints.length) {
    endpoints.push({
      id: fallback.id,
      label: fallback.label,
      platform: fallback.platform,
      status: "unknown",
      scanned: 0,
      accepted: 0,
      sourceIds: [],
    });
  }

  return endpoints.sort((left, right) => {
    const order = (endpoint: SourceEndpoint) => {
      if (endpoint.label === "微信公开索引") return 0;
      if (endpoint.status === "ok") return 1;
      if (endpoint.status === "partial") return 2;
      if (endpoint.status === "error") return 3;
      return 4;
    };
    return order(left) - order(right) || left.label.localeCompare(right.label, "zh-CN");
  });
}

function feedEndpoints(id: string, platform: string): SourceEndpoint[] {
  const rows = activeHealthRows((sourceId) => sourceId === id);
  return buildEndpoints(rows, {
    id: `feed:${id}`,
    label: platform || "公开网络",
    platform: platform || "公开网络",
  });
}

function publisherMatcher(
  id: string,
  name: string,
  aliases: string[],
): (sourceId: string, item: UnknownRecord) => boolean {
  const publisherKeys = [name, ...aliases].map(normalizedIdentity).filter(Boolean);
  const configKey = normalizedIdentity(id);
  return (sourceId, item) => {
    const sourceIdKey = normalizedIdentity(sourceId);
    const observedNameKey = normalizedIdentity(item.name);
    const nameMatch = publisherKeys.some((key) =>
      key.length >= 3
      && observedNameKey
      && (observedNameKey === key || observedNameKey.includes(key)),
    );
    const idMatch = Boolean(configKey && sourceIdKey.includes(configKey));
    return nameMatch || idMatch;
  };
}

function publisherEndpoints(
  id: string,
  name: string,
  aliases: string[],
  fallbackLabel: string,
  fallbackPlatform: string,
): SourceEndpoint[] {
  const rows = activeHealthRows(publisherMatcher(id, name, aliases));
  return buildEndpoints(rows, {
    id,
    label: fallbackLabel,
    platform: fallbackPlatform,
  });
}

function wechatEndpoints(id: string, name: string): SourceEndpoint[] {
  return publisherEndpoints(
    `wechat:${id}`,
    name,
    [],
    "微信公开索引",
    "微信",
  );
}

function buildFeedSources(): CoreSource[] {
  const config = record(intelligenceSourcesConfig);
  const feeds = Array.isArray(config.feeds) ? config.feeds : [];
  return feeds.flatMap((value): CoreSource[] => {
    const feed = record(value);
    const id = text(feed.id, 100);
    const name = text(feed.name, 140);
    if (!id || !name || feed.enabled === false) return [];
    const platform = text(feed.platform, 80) || "公开网络";
    const sourceLevel = text(feed.sourceLevel, 60) || "待交叉验证";
    const explicitSector = text(feed.sector, 80);
    const endpoints = feedEndpoints(id, platform);
    return [{
      id: `feed:${id}`,
      name,
      kind: sourceKind(platform, sourceLevel),
      platform,
      sourceLevel,
      sourceRole: sourceRole(sourceLevel, platform),
      region: text(feed.region, 60) || "全球",
      sectors: explicitSector ? [explicitSector] : [],
      keywords: strings(feed.keywords, 28),
      companies: strings(feed.trackedCompanies, 18),
      people: strings(feed.trackedPeople, 18),
      url: safeHttpUrl(feed.url),
      lifecycle: "tracked",
      healthStatus: overallPublisherStatus(endpoints),
      healthUpdatedAt: healthContext.generatedAt,
      endpoints,
    }];
  });
}

function buildWechatSources(): CoreSource[] {
  const config = record(wechatSourcesConfig);
  const accounts = Array.isArray(config.accounts) ? config.accounts : [];
  return accounts.flatMap((value): CoreSource[] => {
    const account = record(value);
    const id = text(account.id, 100);
    const name = text(account.name, 140);
    if (!id || !name || account.enabled === false) return [];
    const sectorKeywords = account.sectorKeywords;
    const endpoints = wechatEndpoints(id, name);
    return [{
      id: `wechat:${id}`,
      name,
      kind: "微信公众号",
      platform: "微信",
      sourceLevel: text(account.sourceLevel, 60) || "媒体报道",
      sourceRole: "discovery",
      region: text(account.region, 60) || "中国",
      sectors: sectorKeys(sectorKeywords),
      keywords: flattenSectorKeywords(sectorKeywords),
      companies: strings(account.companies, 20),
      people: strings(account.people, 20),
      lifecycle: "tracked",
      healthStatus: overallPublisherStatus(endpoints),
      healthUpdatedAt: healthContext.generatedAt,
      endpoints,
    }];
  });
}

function buildOfficialCompanySources(): CoreSource[] {
  const config = record(officialCompanySourcesConfig);
  const companies = Array.isArray(config.companies) ? config.companies : [];
  return companies.flatMap((value): CoreSource[] => {
    const company = record(value);
    const slug = text(company.slug, 100);
    const name = text(company.name, 140);
    if (!slug || !name || company.enabled === false) return [];
    const aliases = strings(company.aliases, 20);
    const newsUrls = strings(company.newsUrls, 12);
    const sector = text(company.sector, 80);
    const endpoints = publisherEndpoints(
      `official-company:${slug}`,
      name,
      aliases,
      "官方网站",
      "官方网站",
    );
    return [{
      id: `official-company:${slug}`,
      name,
      kind: "官方 / 原始",
      platform: "官方网站",
      sourceLevel: "官方披露",
      sourceRole: "primary",
      region: text(company.region, 60) || "全球",
      sectors: sector ? [sector] : [],
      keywords: [],
      companies: [name],
      people: [],
      url: safeHttpUrl(newsUrls[0]) || safeHttpUrl(company.homepage),
      lifecycle: newsUrls.length ? "tracked" : "candidate",
      healthStatus: overallPublisherStatus(endpoints),
      healthUpdatedAt: healthContext.generatedAt,
      endpoints,
    }];
  });
}

function buildRegulatorySources(): CoreSource[] {
  const config = record(listedCompanyDisclosureSourcesConfig);
  const officialSources = record(config.officialSources);
  return Object.entries(officialSources).flatMap(([id, raw]): CoreSource[] => {
    const item = record(raw);
    const name = text(item.name, 140);
    if (!id || !name) return [];
    const aliases = strings(item.hosts, 12);
    const endpoints = publisherEndpoints(
      `regulatory:${id}`,
      name,
      aliases,
      "监管 / 交易所",
      "监管机构",
    );
    return [{
      id: `regulatory:${id}`,
      name,
      kind: "官方 / 原始",
      platform: "监管机构",
      sourceLevel: "监管文件",
      sourceRole: "primary",
      region: id === "sec" ? "美国" : id === "hkex" ? "中国香港" : "中国",
      sectors: [],
      keywords: ["监管披露", "交易所公告"],
      companies: [],
      people: [],
      url: safeHttpUrl(item.homepage),
      lifecycle: "tracked",
      healthStatus: overallPublisherStatus(endpoints),
      healthUpdatedAt: healthContext.generatedAt,
      endpoints,
    }];
  });
}

function sourceIdentity(source: CoreSource): string {
  return `${source.kind}\u0000${source.name}`.toLocaleLowerCase("zh-CN");
}

function promotionRows(source: CoreSource): Array<{ sourceId: string; item: UnknownRecord }> {
  if (source.id.startsWith("feed:")) {
    const runtimeId = source.id.slice("feed:".length);
    return healthRows((sourceId) => sourceId === runtimeId);
  }
  return healthRows(publisherMatcher(source.id, source.name, source.companies));
}

function promotionMetricsFromRow(
  row: { sourceId: string; item: UnknownRecord },
): SourcePromotionMetrics | undefined {
  const performance = record(row.item.performance);
  if (!Object.keys(performance).length) return undefined;
  const samples = Array.isArray(performance.samples) ? performance.samples.map(record) : [];
  const observedDays = new Set(
    samples
      .map((sample) => text(sample.at, 80).slice(0, 10))
      .filter(Boolean),
  ).size;
  const manualQuality = record(performance.manualQuality);
  const collectionState = text(row.item.collectionState, 40);
  return {
    runs: optionalNumber(performance.runs),
    observedDays,
    scanned: optionalNumber(performance.scanned),
    availabilityRate: optionalNumber(performance.availabilityRate),
    validYieldRate: optionalNumber(performance.validYieldRate),
    activeCollection: collectionState ? collectionState === "active" : undefined,
    publicationEligible: typeof row.item.publicationEligible === "boolean"
      ? row.item.publicationEligible
      : undefined,
    performanceReviewRequired: typeof performance.reviewRequired === "boolean"
      ? performance.reviewRequired
      : undefined,
    reviewedRecords: optionalNumber(manualQuality.reviewedRecords),
    misattributionRate: optionalNumber(manualQuality.misattributionRate),
    evidenceSourceId: row.sourceId,
  };
}

function promotionEvidenceScore(metrics: SourcePromotionMetrics): number {
  return (metrics.activeCollection === true ? 1_000_000_000 : 0)
    + (metrics.publicationEligible === true ? 100_000_000 : 0)
    + (metrics.performanceReviewRequired === false ? 10_000_000 : 0)
    + (metrics.observedDays ?? 0) * 100_000
    + (metrics.runs ?? 0) * 10_000
    + (metrics.reviewedRecords ?? 0) * 100
    + (metrics.scanned ?? 0)
    + Math.round((metrics.availabilityRate ?? 0) * 100)
    + Math.round((metrics.validYieldRate ?? 0) * 100);
}

function bestPromotionEvidence(source: CoreSource): SourcePromotionMetrics | undefined {
  return promotionRows(source)
    .map(promotionMetricsFromRow)
    .filter((value): value is SourcePromotionMetrics => Boolean(value))
    .sort((left, right) => promotionEvidenceScore(right) - promotionEvidenceScore(left))[0];
}

function applyLifecyclePromotion(source: CoreSource): CoreSource {
  const promotion = evaluateSourcePromotion({
    trackingEligible: source.lifecycle !== "candidate",
    metrics: bestPromotionEvidence(source),
    review: coreReviewIndex.get(source.id),
    policy: lifecyclePolicy,
  });
  return {
    ...source,
    lifecycle: promotion.lifecycle,
    promotion,
  };
}

export const coreSources: CoreSource[] = (() => {
  const seen = new Set<string>();
  const result: CoreSource[] = [];
  for (const rawSource of [
    ...buildWechatSources(),
    ...buildFeedSources(),
    ...buildOfficialCompanySources(),
    ...buildRegulatorySources(),
  ]) {
    const source = applyLifecyclePromotion(rawSource);
    const identity = sourceIdentity(source);
    if (seen.has(identity)) continue;
    seen.add(identity);
    result.push(source);
  }
  return result.sort((left, right) =>
    left.kind.localeCompare(right.kind, "zh-CN")
    || left.sourceRole.localeCompare(right.sourceRole, "en-US")
    || left.name.localeCompare(right.name, "zh-CN"),
  );
})();

export const coreSourceStats = {
  total: coreSources.length,
  wechat: coreSources.filter((item) => item.kind === "微信公众号").length,
  official: coreSources.filter((item) => item.kind === "官方 / 原始").length,
  media: coreSources.filter((item) => item.kind === "媒体 / 研究").length,
  primary: coreSources.filter((item) => item.sourceRole === "primary").length,
  corroboration: coreSources.filter((item) => item.sourceRole === "corroboration").length,
  discovery: coreSources.filter((item) => item.sourceRole === "discovery").length,
  sectors: new Set(coreSources.flatMap((item) => item.sectors)).size,
  regions: new Set(coreSources.map((item) => item.region)).size,
  healthy: coreSources.filter((item) => item.healthStatus === "ok").length,
  partial: coreSources.filter((item) => item.healthStatus === "partial").length,
  error: coreSources.filter((item) => item.healthStatus === "error").length,
  unknown: coreSources.filter((item) => item.healthStatus === "unknown").length,
  candidate: coreSources.filter((item) => item.lifecycle === "candidate").length,
  tracked: coreSources.filter((item) => item.lifecycle === "tracked").length,
  core: coreSources.filter((item) => item.lifecycle === "core").length,
  evidencePending: coreSources.filter((item) => item.promotion?.state === "evidence_pending").length,
  reviewPending: coreSources.filter((item) => item.promotion?.state === "review_pending").length,
  blocked: coreSources.filter((item) => item.promotion?.state === "blocked").length,
};

export function coreSourcesByKind(kind: CoreSourceKind): CoreSource[] {
  return coreSources.filter((item) => item.kind === kind);
}
