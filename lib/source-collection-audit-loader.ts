import { readFileSync } from "node:fs";
import { join } from "node:path";
import { buildSourceCollectionAudit } from "./source-collection-audit.mjs";
import type { SourceDirectoryEntry } from "./source-directory";

function load(name: string): Record<string, unknown> | undefined {
  try {
    const value: unknown = JSON.parse(readFileSync(join(process.cwd(), "public", "data", name), "utf8"));
    if (value && typeof value === "object" && !Array.isArray(value)) return value as Record<string, unknown>;
  } catch { /* A missing observation is unavailable, never a healthy empty set. */ }
  return undefined;
}

export function loadSourceCollectionAudit(directory: SourceDirectoryEntry[]) {
  const articles = load("articles.json");
  return buildSourceCollectionAudit({
    health: load("source_health.json"),
    articleSourceStatus: articles?.sourceStatus,
    directory,
  });
}
