import archive from "@/config/native_research_event_archives.json";
import type { LiveIntelligenceEvent } from "./use-articles";

export type ResearchEventWithArchive = LiveIntelligenceEvent & {
  archiveProvenance?: { sourceCommit: string; sourcePath: string; sourceBlob: string };
};

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

export function archivedResearchEvent(eventId: string, value: unknown = archive): ResearchEventWithArchive | null {
  const root = record(value);
  if (root?.schemaVersion !== 1 || !Array.isArray(root.records)) return null;
  const row = root.records.map(record).find((candidate) => candidate?.eventId === eventId);
  if (!row || typeof row.sourceCommit !== "string" || !/^[a-f0-9]{40}$/.test(row.sourceCommit)
    || typeof row.sourceBlob !== "string" || !/^[a-f0-9]{40}$/.test(row.sourceBlob)
    || row.sourcePath !== "public/data/articles.json") return null;
  const item = record(row.event);
  const source = record(item?.source);
  if (!item || item.id !== eventId || typeof item.title !== "string" || !item.title.trim()
    || typeof item.summary !== "string" || !item.summary.trim()
    || !source || typeof source.url !== "string"
    || [item.qualityStatus, item.verificationStatus, item.reviewStatus, item.publicationTier].includes("rejected")) return null;
  try {
    const url = new URL(source.url);
    if (url.protocol !== "https:" || url.username || url.password || url.pathname.includes("/alerts/feeds/")) return null;
  } catch { return null; }
  return {
    ...item,
    archiveProvenance: { sourceCommit: row.sourceCommit, sourcePath: row.sourcePath, sourceBlob: row.sourceBlob },
  } as ResearchEventWithArchive;
}
