import type { LiveIntelligenceEvent } from "./use-articles";

export const RESEARCH_EVENT_LEDGER_PATH = "/data/research_event_ledger.json";
const MAX_LEDGER_BYTES = 4_000_000;

type LedgerProvenance = {
  firstSeenAt: string;
  lastSeenAt: string;
  sourceDataset: string;
  snapshotGeneratedAt: string;
  sourceCommit: string;
  sourceBlob: string;
};

export type ResearchLedgerEvent = LiveIntelligenceEvent & {
  researchLedgerProvenance: LedgerProvenance;
};

function object(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function text(value: unknown, limit: number) {
  return typeof value === "string" ? value.slice(0, limit) : "";
}

function safeHttps(value: unknown) {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || url.pathname.includes("/alerts/feeds/")) return "";
    return url.toString();
  } catch {
    return "";
  }
}

export function parseResearchLedgerEvent(value: unknown, eventId: string): ResearchLedgerEvent | null {
  const payload = object(value);
  if (!payload || payload.schemaVersion !== 1 || !object(payload.events)) return null;
  const raw = object((payload.events as Record<string, unknown>)[eventId]);
  const event = object(raw?.event);
  const source = object(event?.source);
  if (!raw || raw.eventId !== eventId || raw.status !== "active" || !event || event.id !== eventId
    || typeof event.title !== "string" || !event.title.trim()
    || typeof event.summary !== "string" || !event.summary.trim()
    || !source || !safeHttps(source.url)
    || [event.qualityStatus, event.verificationStatus, event.reviewStatus, event.publicationTier].includes("rejected")) return null;
  const firstSeenAt = text(raw.firstSeenAt, 80);
  const lastSeenAt = text(raw.lastSeenAt, 80);
  const sourceDataset = text(raw.sourceDataset, 120);
  if (!firstSeenAt || !lastSeenAt || !["public/data/articles.json", "public/data/ranked-intelligence.json"].includes(sourceDataset)) return null;
  return {
    ...event,
    researchLedgerProvenance: {
      firstSeenAt,
      lastSeenAt,
      sourceDataset,
      snapshotGeneratedAt: text(raw.snapshotGeneratedAt, 80),
      sourceCommit: /^[a-f0-9]{40}$/.test(text(raw.sourceCommit, 40)) ? text(raw.sourceCommit, 40) : "",
      sourceBlob: /^[a-f0-9]{40}$/.test(text(raw.sourceBlob, 40)) ? text(raw.sourceBlob, 40) : "",
    },
  } as ResearchLedgerEvent;
}

export async function loadResearchLedgerEvent(eventId: string): Promise<ResearchLedgerEvent | null> {
  const response = await fetch(RESEARCH_EVENT_LEDGER_PATH, { cache: "no-store" });
  if (!response.ok) return null;
  const declared = Number(response.headers.get("content-length") || 0);
  if (declared > MAX_LEDGER_BYTES) throw new Error("Research Event Ledger exceeds client read budget");
  const raw = await response.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_LEDGER_BYTES) throw new Error("Research Event Ledger exceeds client read budget");
  return parseResearchLedgerEvent(JSON.parse(raw) as unknown, eventId);
}
