import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const ROOT = process.cwd();
const requestPath = resolve(ROOT, "work/research-agent/native_request.json");
const outputPath = resolve(ROOT, "public/data/native_research_results.json");

async function json(path: string, fallback: unknown) {
  try {
    return JSON.parse(await readFile(path, "utf8")) as any;
  } catch {
    return fallback;
  }
}

const request = await json(requestPath, null);
if (!request || typeof request !== "object" || !request.eventId) process.exit(0);

const report = await json(resolve(ROOT, "public/data/research_agent_daily.json"), {});
const existing = await json(outputPath, { schemaVersion: 1, generatedAt: "", results: [] });
const evidence = Array.isArray(report.evidence) ? report.evidence : [];
const changes = Array.isArray(report.changes) ? report.changes : [];

const normalizedUrl = String(request.url || "").replace(/\/+$/, "");
const matchingEvidence = evidence.filter((row: any) => {
  const url = String(row?.url || "").replace(/\/+$/, "");
  if (normalizedUrl && url === normalizedUrl) return true;
  const entity = String(row?.entityName || "").trim().toLocaleLowerCase("zh-CN");
  const company = String(request.company || "").trim().toLocaleLowerCase("zh-CN");
  return Boolean(company && entity === company);
});
const evidenceIds = new Set(matchingEvidence.map((row: any) => String(row?.id || "")).filter(Boolean));
const matchingChanges = changes.filter((row: any) => {
  if (String(row?.eventId || "") === request.eventId) return true;
  if (Array.isArray(row?.eventIds) && row.eventIds.some((id: unknown) => String(id) === request.eventId)) return true;
  return Array.isArray(row?.evidenceIds) && row.evidenceIds.some((id: unknown) => evidenceIds.has(String(id)));
});

const result = {
  eventId: request.eventId,
  title: request.title,
  sourceUrl: request.url,
  requestedAt: request.requestedAt,
  completedAt: String(report.generatedAt || new Date().toISOString()),
  runStatus: String(report.runStatus || "unknown"),
  status: matchingEvidence.length || matchingChanges.length ? "evidence-linked" : "no-event-specific-evidence",
  executiveSummary: matchingEvidence.length || matchingChanges.length
    ? String(report?.analysis?.executiveSummary || "")
    : "",
  changeIds: matchingChanges.map((row: any) => String(row?.id || "")).filter(Boolean),
  evidenceIds: matchingEvidence.map((row: any) => String(row?.id || "")).filter(Boolean),
  changes: matchingChanges.slice(0, 12),
  evidence: matchingEvidence.slice(0, 16),
  note: matchingEvidence.length || matchingChanges.length
    ? "结果来自本轮公开 Research Agent 产物中与请求事件绑定的 evidence/change。"
    : "本轮 Research Agent 未形成与该事件直接绑定的公开 evidence/change；保留请求记录，不把通用日报冒充为专属研究结果。",
};

const previous = Array.isArray(existing.results) ? existing.results : [];
const results = [result, ...previous.filter((row: any) => String(row?.eventId || "") !== request.eventId)].slice(0, 100);
await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, JSON.stringify({ schemaVersion: 1, generatedAt: new Date().toISOString(), results }, null, 2) + "\n", "utf8");
console.log(`Published native research result state for ${request.eventId}: ${result.status}`);
