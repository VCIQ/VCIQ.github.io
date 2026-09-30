import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export const BATCH6_PRIORITY_URL =
  "https://raw.githubusercontent.com/VCIQ/VCIQ.github.io/intelligence-live/public/data/batch6_priority_candidates.json";
const MAX_BYTES = 180_000;
const TYPES = new Set(["融资", "并购", "IPO", "产品发布", "技术突破", "公司动态"]);
const SECTORS = new Set(["科创资本", "风险投资", "AI安全", "AI智能终端", "AI网络通信", "半导体", "商业航天", "空天信息", "6G"]);

export type Batch6PrioritySnapshot = {
  schemaVersion: 1;
  policyVersion: "batch6-priority-v1";
  generatedAt: string;
  contentHash: string;
  sourceState: "healthy" | "degraded";
  items: LiveIntelligenceEvent[];
};

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid Batch-6 object");
  return value as Record<string, unknown>;
}
function text(value: unknown, max: number): string {
  if (typeof value !== "string" || value.length > max) throw new Error("Invalid Batch-6 text");
  return value;
}
function publicUrl(value: unknown): URL {
  const url = new URL(text(value, 1800));
  if (url.protocol !== "https:" || url.username || url.password || url.hostname === "localhost" || url.hostname.endsWith(".local")) {
    throw new Error("Invalid Batch-6 URL");
  }
  if (/^(?:127\.|10\.|192\.168\.|169\.254\.|0\.)/u.test(url.hostname)
    || /^172\.(?:1[6-9]|2\d|3[01])\./u.test(url.hostname)) throw new Error("Invalid Batch-6 host");
  return url;
}

export function parseBatch6Priority(value: unknown, now = Date.now()): Batch6PrioritySnapshot {
  const raw = object(value);
  if (raw.schemaVersion !== 1 || raw.policyVersion !== "batch6-priority-v1"
    || !Array.isArray(raw.items) || raw.items.length > 72
    || !["healthy", "degraded"].includes(String(raw.sourceState))) throw new Error("Unsupported Batch-6 contract");
  const generatedAt = text(raw.generatedAt, 40);
  if (!Number.isFinite(Date.parse(generatedAt)) || Date.parse(generatedAt) > now + 300_000) throw new Error("Invalid Batch-6 clock");
  const contentHash = text(raw.contentHash, 64);
  if (!/^[a-f0-9]{64}$/u.test(contentHash)) throw new Error("Invalid Batch-6 version");
  const seen = new Set<string>();
  const items = raw.items.map((input): LiveIntelligenceEvent => {
    const row = object(input); const source = object(row.source);
    const id = text(row.id, 180);
    if (!id.startsWith("batch6-rss-") || seen.has(id) || row.sourceId !== "batch6-google-alerts") throw new Error("Invalid Batch-6 identity");
    seen.add(id);
    const url = publicUrl(source.url);
    const publishedAt = text(row.publishedAt, 40);
    const importance = row.importance;
    if (!Number.isFinite(Date.parse(publishedAt)) || Date.parse(publishedAt) > now + 86_400_000
      || !TYPES.has(String(row.type)) || !SECTORS.has(String(row.sector))
      || typeof importance !== "number" || importance < 75 || importance > 100
      || source.level !== "待交叉验证" || source.platform !== "Google Alerts RSS") {
      throw new Error("Invalid Batch-6 candidate");
    }
    const firstSeenAt = row.firstSeenAt === undefined ? undefined : text(row.firstSeenAt, 40);
    if (firstSeenAt && !Number.isFinite(Date.parse(firstSeenAt))) throw new Error("Invalid Batch-6 first observation");
    return {
      id, sourceId: "batch6-google-alerts", title: text(row.title, 300), summary: text(row.summary, 360),
      publishedAt, type: row.type as LiveIntelligenceEvent["type"], region: "全球",
      sector: text(row.sector, 80), company: "", importance, firstSeenAt,
      source: { name: text(source.name, 100), url: url.href, level: "待交叉验证", platform: "Google Alerts RSS" },
    };
  });
  return { schemaVersion: 1, policyVersion: "batch6-priority-v1", generatedAt, contentHash,
    sourceState: raw.sourceState as "healthy" | "degraded", items };
}

export async function readBatch6Priority(fetchImpl: typeof fetch, signal: AbortSignal): Promise<Batch6PrioritySnapshot> {
  const url = BATCH6_PRIORITY_URL + "?window=" + Math.floor(Date.now() / 60_000);
  const response = await fetchImpl(url, { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal });
  if (!response.ok) throw new Error("科创 RSS 快速候选暂不可读（HTTP " + response.status + "）。");
  if (Number(response.headers.get("content-length") ?? 0) > MAX_BYTES) throw new Error("科创 RSS 快速候选超过安全长度。");
  const body = await response.text();
  if (new TextEncoder().encode(body).byteLength > MAX_BYTES) throw new Error("科创 RSS 快速候选超过安全长度。");
  return parseBatch6Priority(JSON.parse(body));
}
