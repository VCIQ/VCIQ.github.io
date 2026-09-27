import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

type JsonRecord = Record<string, unknown>;

const ROOT = process.cwd();
const requestPath = resolve(ROOT, "work/research-agent/native_request.json");
const outputPath = resolve(ROOT, "public/data/native_research_results.json");

async function json(path: string, fallback: unknown): Promise<unknown> {
  try {
    return JSON.parse(await readFile(path, "utf8")) as unknown;
  } catch {
    return fallback;
  }
}

function record(value: unknown): JsonRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonRecord
    : null;
}

function recordList(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.map(record).filter((row): row is JsonRecord => row !== null)
    : [];
}

const requestValue = await json(requestPath, null);
const request = record(requestValue);
if (!request || !String(request.eventId || "").trim()) process.exit(0);

const report = record(await json(resolve(ROOT, "public/data/research_agent_daily.json"), {})) ?? {};
const existing = record(await json(outputPath, { schemaVersion: 1, generatedAt: "", results: [] })) ?? {};
const evidence = recordList(report.evidence);
const changes = recordList(report.changes);

const normalizedUrl = String(request.url || "").replace(/\/+$/, "");
const matchingEvidence = evidence.filter((row) => {
  const url = String(row.url || "").replace(/\/+$/, "");
  if (normalizedUrl && url === normalizedUrl) return true;
  const entity = String(row.entityName || "").trim().toLocaleLowerCase("zh-CN");
  const company = String(request.company || "").trim().toLocaleLowerCase("zh-CN");
  return Boolean(company && entity === company);
});
const evidenceIds = new Set(
  matchingEvidence.map((row) => String(row.id || "")).filter(Boolean),
);
const requestEventId = String(request.eventId || "");
const matchingChanges = changes.filter((row) => {
  if (String(row.eventId || "") === requestEventId) return true;
  if (Array.isArray(row.eventIds) && row.eventIds.some((id) => String(id) === requestEventId)) return true;
  return Array.isArray(row.evidenceIds)
    && row.evidenceIds.some((id) => evidenceIds.has(String(id)));
});

const analysis = record(report.analysis) ?? {};
const result = {
  eventId: requestEventId,
  title: String(request.title || ""),
  sourceUrl: String(request.url || ""),
  requestedAt: String(request.requestedAt || ""),
  completedAt: String(report.generatedAt || new Date().toISOString()),
  runStatus: String(report.runStatus || "unknown"),
  status: matchingEvidence.length || matchingChanges.length ? "evidence-linked" : "no-event-specific-evidence",
  executiveSummary: matchingEvidence.length || matchingChanges.length
    ? String(analysis.executiveSummary || "")
    : "",
  changeIds: matchingChanges.map((row) => String(row.id || "")).filter(Boolean),
  evidenceIds: matchingEvidence.map((row) => String(row.id || "")).filter(Boolean),
  changes: matchingChanges.slice(0, 12),
  evidence: matchingEvidence.slice(0, 16),
  note: matchingEvidence.length || matchingChanges.length
    ? "结果来自本轮公开 Research Agent 产物中与请求事件绑定的 evidence/change。"
    : "本轮 Research Agent 未形成与该事件直接绑定的公开 evidence/change；保留请求记录，不把通用日报冒充为专属研究结果。",
};

const previous = recordList(existing.results);
const results = [
  result,
  ...previous.filter((row) => String(row.eventId || "") !== requestEventId),
].slice(0, 100);

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(
  outputPath,
  JSON.stringify({ schemaVersion: 1, generatedAt: new Date().toISOString(), results }, null, 2) + "\n",
  "utf8",
);
console.log(`Published native research result state for ${requestEventId}: ${result.status}`);
