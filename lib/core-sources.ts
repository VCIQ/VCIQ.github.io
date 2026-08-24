import intelligenceSourcesConfig from "@/config/intelligence_sources.json";
import wechatSourcesConfig from "@/config/wechat_sources.json";

export type CoreSourceKind = "微信公众号" | "媒体 / 研究" | "官方 / 原始";

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
  lifecycle: "tracked";
};

type UnknownRecord = Record<string, unknown>;

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
};

export function coreSourcesByKind(kind: CoreSourceKind): CoreSource[] {
  return coreSources.filter((item) => item.kind === kind);
}
