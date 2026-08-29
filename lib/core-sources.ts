import { readFileSync } from "node:fs";
import { join } from "node:path";

import intelligenceSourcesConfig from "@/config/intelligence_sources.json";
import wechatSourcesConfig from "@/config/wechat_sources.json";

export type CoreSourceKind = "微信公众号" | "媒体 / 研究" | "官方 / 原始";
export type SourceLifecycle = "candidate" | "tracked" | "core";
export type SourceHealthStatus = "ok" | "partial" | "error" | "unknown";

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
  region: string;
  sectors: string[];
  keywords: string[];
  companies: string[];
  people: string[];
  url?: string;
  lifecycle: SourceLifecycle;
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

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
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
  if (id.includes("wechat") || platform === "微信") return "微信公开索引";
  if (id.includes("sohu")) return "搜狐公开页";
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

function activeHealthRows(
  matcher: (sourceId: string, item: UnknownRecord) => boolean,
): Array<{ sourceId: string; item: UnknownRecord }> {
  return Object.entries(healthContext.sources).flatMap(([sourceId, raw]) => {
    const item = record(raw);
    if (item.missingFromCurrentRun === true || !matcher(sourceId, item)) return [];
    return [{ sourceId, item }];
  });
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

function wechatEndpoints(id: string, name: string): SourceEndpoint[] {
  const publisherKey = normalizedIdentity(name);
  const configKey = normalizedIdentity(id);
  const rows = activeHealthRows((sourceId, item) => {
    const sourceIdKey = normalizedIdentity(sourceId);
    const observedNameKey = normalizedIdentity(item.name);
    const nameMatch = Boolean(
      publisherKey
      && observedNameKey
      && (observedNameKey === publisherKey || observedNameKey.includes(publisherKey)),
    );
    const idMatch = Boolean(configKey && sourceIdKey.includes(configKey));
    return nameMatch || idMatch;
  });
  const endpoints = buildEndpoints(rows, {
    id: `wechat:${id}`,
    label: "微信公开索引",
    platform: "微信",
  });
  if (!endpoints.some((endpoint) => endpoint.label === "微信公开索引")) {
    endpoints.unshift({
      id: `wechat:${id}:wechat-index`,
      label: "微信公开索引",
      platform: "微信",
      status: "unknown",
      scanned: 0,
      accepted: 0,
      sourceIds: [],
    });
  }
  return endpoints;
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

function sourceIdentity(source: CoreSource): string {
  return `${source.kind}\u0000${source.name}`.toLocaleLowerCase("zh-CN");
}

export const coreSources: CoreSource[] = (() => {
  const seen = new Set<string>();
  const result: CoreSource[] = [];
  for (const source of [...buildWechatSources(), ...buildFeedSources()]) {
    const identity = sourceIdentity(source);
    if (seen.has(identity)) continue;
    seen.add(identity);
    result.push(source);
  }
  return result.sort((left, right) =>
    left.kind.localeCompare(right.kind, "zh-CN") || left.name.localeCompare(right.name, "zh-CN"),
  );
})();

export const coreSourceStats = {
  total: coreSources.length,
  wechat: coreSources.filter((item) => item.kind === "微信公众号").length,
  official: coreSources.filter((item) => item.kind === "官方 / 原始").length,
  media: coreSources.filter((item) => item.kind === "媒体 / 研究").length,
  sectors: new Set(coreSources.flatMap((item) => item.sectors)).size,
  regions: new Set(coreSources.map((item) => item.region)).size,
  healthy: coreSources.filter((item) => item.healthStatus === "ok").length,
  partial: coreSources.filter((item) => item.healthStatus === "partial").length,
  error: coreSources.filter((item) => item.healthStatus === "error").length,
  unknown: coreSources.filter((item) => item.healthStatus === "unknown").length,
  core: coreSources.filter((item) => item.lifecycle === "core").length,
};

export function coreSourcesByKind(kind: CoreSourceKind): CoreSource[] {
  return coreSources.filter((item) => item.kind === kind);
}
