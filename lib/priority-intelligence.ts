import { homepageEventIdentityKeys, homepageMaterialUrl } from "@/lib/homepage-event-identity";
import prioritySourcePolicy from "@/config/priority_source_policy.json";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export const PRIORITY_FEED_URL = "https://raw.githubusercontent.com/VCIQ/VCIQ.github.io/intelligence-live/public/data/priority_intelligence.json";
export const PRIORITY_FEED_MAX_BYTES = 300_000;
export const PRIORITY_FEED_SOURCE_HOSTS: Readonly<Record<string, string>> = Object.freeze(
  Object.fromEntries(prioritySourcePolicy.sources.map((row) => [row.id, row.articleHost])),
);
const PRIORITY_FEED_SOURCE_LEVELS: Readonly<Record<string, string>> = Object.freeze(
  Object.fromEntries(prioritySourcePolicy.sources.map((row) => [row.id, row.level])),
);
export type PriorityIntelligenceSnapshot = {
  schemaVersion: 1;
  policyVersion: "priority-publisher-v1";
  generatedAt: string;
  contentHash: string;
  sourceState: "healthy" | "degraded";
  items: LiveIntelligenceEvent[];
  collectionTrace?: Array<{ id: string; sourceId: string; title: string; url: string; reason: string }>;
  collectionSummary?: { scanned: number; filtered: number; expired: number; capacityHeld: number; pendingSources: number; traceTruncated: boolean };
};
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid priority feed object");
  return value as Record<string, unknown>;
}
function text(value: unknown, max: number): string {
  if (typeof value !== "string" || value.length > max) throw new Error("Invalid priority feed text");
  return value;
}
const EVENT_TYPES = new Set(["融资", "产业投资", "产品发布", "技术突破", "商业进展", "公司动态", "并购", "财报", "政策", "监管文件", "IPO", "论文", "人物观点"]);

/** Separate, bounded, public data only; never accepts profile/feedback payloads. */
export function parsePriorityIntelligence(value: unknown, now = Date.now()): PriorityIntelligenceSnapshot {
  const raw = object(value);
  if (raw.schemaVersion !== 1 || raw.policyVersion !== "priority-publisher-v1" ||
    !Array.isArray(raw.items) || raw.items.length > 72 ||
    !["healthy", "degraded"].includes(String(raw.sourceState))) throw new Error("Unsupported priority feed contract");
  const generatedAt = text(raw.generatedAt, 40);
  if (!Number.isFinite(Date.parse(generatedAt)) || Date.parse(generatedAt) > now + 300_000) throw new Error("Invalid priority feed clock");
  const contentHash = text(raw.contentHash, 64);
  if (!/^[a-f0-9]{64}$/u.test(contentHash)) throw new Error("Invalid priority feed version");
  const seen = new Set<string>();
  const items = raw.items.map((input): LiveIntelligenceEvent => {
    const row = object(input); const source = object(row.source);
    const id = text(row.id, 180); const sourceId = text(row.sourceId, 100);
    const expectedHost = PRIORITY_FEED_SOURCE_HOSTS[sourceId];
    const url = new URL(text(source.url, 1600));
    if (!expectedHost || !id.startsWith(`${sourceId}-`) || seen.has(id) || url.protocol !== "https:" || url.hostname !== expectedHost || url.username || url.password) throw new Error("Invalid priority feed identity");
    seen.add(id);
    const title = text(row.title, 300); const publishedAt = text(row.publishedAt, 40);
    if (!title.trim() || !Number.isFinite(Date.parse(publishedAt)) || Date.parse(publishedAt) > now + 86_400_000) throw new Error("Invalid priority event");
    if (!EVENT_TYPES.has(String(row.type)) || !["中国", "美国", "全球"].includes(String(row.region)) ||
      typeof row.importance !== "number" || !Number.isFinite(row.importance) || row.importance < 0 || row.importance > 100) throw new Error("Invalid priority event classification");
    const level = PRIORITY_FEED_SOURCE_LEVELS[sourceId] as "官方披露" | "媒体报道";
    if (source.level !== level) throw new Error("Invalid priority evidence role");
    const entityState = row.entityResolutionStatus;
    if (entityState !== undefined && !["matched", "ambiguous", "unresolved"].includes(String(entityState))) throw new Error("Invalid entity status");
    const mentions = row.entityMentions === undefined ? [] : row.entityMentions;
    if (!Array.isArray(mentions) || mentions.length > 12) throw new Error("Invalid entity evidence");
    const entityMentions = mentions.map((input) => {
      const mention = object(input);
      if (!["company", "person"].includes(String(mention.kind)) || !["title", "summary"].includes(String(mention.field))) throw new Error("Invalid entity evidence field");
      const alias = text(mention.alias, 100); const field = mention.field as "title" | "summary";
      if (!alias.trim() || !String(row[field]).toLowerCase().includes(alias.toLowerCase())) throw new Error("Entity evidence not present in publisher text");
      return { id: text(mention.id, 180), kind: mention.kind as "company" | "person", name: text(mention.name, 100), alias, field };
    });
    const firstSeenAt = row.firstSeenAt === undefined ? undefined : text(row.firstSeenAt, 40);
    if (firstSeenAt && (!Number.isFinite(Date.parse(firstSeenAt)) || Date.parse(firstSeenAt) > now + 300_000)) throw new Error("Invalid observation time");
    if (row.publicationTimePrecision !== undefined && !["day", "second"].includes(String(row.publicationTimePrecision))) throw new Error("Invalid timestamp precision");
    return {
      id, sourceId, title, publishedAt, summary: text(row.summary, 1600),
      type: row.type as LiveIntelligenceEvent["type"], region: row.region as LiveIntelligenceEvent["region"],
      sector: text(row.sector, 80), company: text(row.company, 160), importance: row.importance,
      firstSeenAt, publicationTimePrecision: row.publicationTimePrecision as "day" | "second" | undefined,
      entityResolutionStatus: entityState as LiveIntelligenceEvent["entityResolutionStatus"], entityMentions,
      mentionedCompanies: [...new Set(entityMentions.filter((x) => x.kind === "company").map((x) => x.name))],
      mentionedPeople: [...new Set(entityMentions.filter((x) => x.kind === "person").map((x) => x.name))],
      source: { name: text(source.name, 120), url: url.href, level, platform: text(source.platform ?? "", 80) },
    };
  });
  let collectionSummary: PriorityIntelligenceSnapshot["collectionSummary"];
  if (raw.collectionSummary !== undefined) {
    const value = object(raw.collectionSummary);
    const number = (key: string) => { const n = value[key]; if (typeof n !== "number" || !Number.isSafeInteger(n) || n < 0 || n > 100_000) throw new Error("Invalid collection counter"); return n; };
    collectionSummary = { scanned: number("scanned"), filtered: number("filtered"), expired: number("expired"), capacityHeld: number("capacityHeld"), pendingSources: number("pendingSources"), traceTruncated: value.traceTruncated === true };
  }
  const trace = raw.collectionTrace ?? [];
  if (!Array.isArray(trace) || trace.length > 120) throw new Error("Invalid collection trace size");
  const collectionTrace = trace.map((input) => {
    const row = object(input); const sourceId = text(row.sourceId, 100); const url = text(row.url, 1600);
    if (!PRIORITY_FEED_SOURCE_HOSTS[sourceId] || (url && (new URL(url).hostname !== PRIORITY_FEED_SOURCE_HOSTS[sourceId] || new URL(url).protocol !== "https:" || new URL(url).username || new URL(url).password))) throw new Error("Invalid collection trace host");
    const reason = text(row.reason, 80);
    if (!["accepted", "invalid-publication-date", "missing-title-or-url", "source-filter-or-invalid-record", "snapshot-capacity", "outside-retention"].includes(reason)) throw new Error("Invalid collection trace reason");
    return { id: text(row.id, 180), sourceId, title: text(row.title, 240), url, reason };
  });
  return { schemaVersion: 1, policyVersion: "priority-publisher-v1", generatedAt, contentHash, sourceState: raw.sourceState as "healthy" | "degraded", items, collectionTrace, collectionSummary };
}

export function mergePriorityCandidates(baseline: readonly LiveIntelligenceEvent[], incoming: readonly LiveIntelligenceEvent[]): LiveIntelligenceEvent[] {
  // Keep reviewed canonical metadata when the archive already knows this material.
  const result = [...baseline]; const seen = new Set(baseline.flatMap(homepageEventIdentityKeys));
  for (const item of incoming) {
    const existing = result.findIndex((row) => homepageMaterialUrl(row.source.url) === homepageMaterialUrl(item.source.url));
    if (existing >= 0 && !result[existing].curated) {
      const row = result[existing];
      // Supplement missing mention evidence, never replace reviewed attribution,
      // title, publication date, canonical identifiers or explicit veto identity.
      result[existing] = { ...row,
        mentionedCompanies: [...new Set([...(row.mentionedCompanies ?? []), ...(item.mentionedCompanies ?? [])])],
        mentionedPeople: [...new Set([...(row.mentionedPeople ?? []), ...(item.mentionedPeople ?? [])])],
        entityResolutionStatus: row.entityResolutionStatus ?? item.entityResolutionStatus,
        entityMentions: row.entityMentions ?? item.entityMentions,
      };
    }
    const keys = homepageEventIdentityKeys(item);
    if (keys.some((key) => seen.has(key))) continue;
    result.push(item); keys.forEach((key) => seen.add(key));
  }
  return result;
}

export async function readPriorityIntelligence(fetchImpl: typeof fetch, signal: AbortSignal): Promise<PriorityIntelligenceSnapshot> {
  // Public repository only. No credentials, profile identifiers, or private hosts.
  const url = `${PRIORITY_FEED_URL}?window=${Math.floor(Date.now() / 60_000)}`;
  const response = await fetchImpl(url, { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal });
  if (!response.ok) throw new Error(`重点增量暂不可读（HTTP ${response.status}）；保留最近成功数据。`);
  if (Number(response.headers.get("content-length") ?? 0) > PRIORITY_FEED_MAX_BYTES) throw new Error("重点增量超过安全长度。");
  const reader = response.body?.getReader(); if (!reader) throw new Error("重点增量响应为空。");
  const decoder = new TextDecoder(); let content = ""; let bytes = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read(); if (done) break;
      bytes += value.byteLength; if (bytes > PRIORITY_FEED_MAX_BYTES) throw new Error("重点增量超过安全长度。");
      content += decoder.decode(value, { stream: true });
    }
    return parsePriorityIntelligence(JSON.parse(content + decoder.decode()));
  } finally { await reader.cancel().catch(() => {}); }
}
