import { homepageEventIdentityKeys } from "@/lib/homepage-event-identity";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export const PRIORITY_FEED_URL = "https://raw.githubusercontent.com/VCIQ/VCIQ.github.io/intelligence-live/public/data/priority_intelligence.json";
export const PRIORITY_FEED_MAX_BYTES = 300_000;
export const PRIORITY_FEED_SOURCE_HOSTS: Readonly<Record<string, string>> = Object.freeze({
  "amd-newsroom": "newsroom.amd.com",
  "mittrchina-public-news": "www.mittrchina.com",
});
export type PriorityIntelligenceSnapshot = {
  schemaVersion: 1;
  policyVersion: "priority-publisher-v1";
  generatedAt: string;
  contentHash: string;
  sourceState: "healthy" | "degraded";
  items: LiveIntelligenceEvent[];
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
    const level = sourceId === "amd-newsroom" ? "官方披露" : "媒体报道";
    if (source.level !== level) throw new Error("Invalid priority evidence role");
    return {
      id, sourceId, title, publishedAt, summary: text(row.summary, 1600),
      type: row.type as LiveIntelligenceEvent["type"], region: row.region as LiveIntelligenceEvent["region"],
      sector: text(row.sector, 80), company: text(row.company, 160), importance: row.importance,
      source: { name: text(source.name, 120), url: url.href, level, platform: text(source.platform ?? "", 80) },
    };
  });
  return { schemaVersion: 1, policyVersion: "priority-publisher-v1", generatedAt, contentHash, sourceState: raw.sourceState as "healthy" | "degraded", items };
}

export function mergePriorityCandidates(baseline: readonly LiveIntelligenceEvent[], incoming: readonly LiveIntelligenceEvent[]): LiveIntelligenceEvent[] {
  // Keep reviewed canonical metadata when the archive already knows this material.
  const result = [...baseline]; const seen = new Set(baseline.flatMap(homepageEventIdentityKeys));
  for (const item of incoming) {
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
