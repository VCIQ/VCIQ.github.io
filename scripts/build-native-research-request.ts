import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const ROOT = process.cwd();
const eventId = (process.env.NATIVE_RESEARCH_EVENT_ID || "").trim();
const outputPath = resolve(ROOT, "work/research-agent/native_request.json");

function rows(value: unknown, key: string): Record<string, unknown>[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  const candidate = (value as Record<string, unknown>)[key];
  return Array.isArray(candidate)
    ? candidate.filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object" && !Array.isArray(row)))
    : [];
}

async function loadJson(path: string) {
  return JSON.parse(await readFile(resolve(ROOT, path), "utf8")) as unknown;
}

if (!eventId) {
  process.exit(0);
}

const [articlesPayload, rankedPayload] = await Promise.all([
  loadJson("public/data/articles.json"),
  loadJson("public/data/ranked-intelligence.json").catch(() => ({})),
]);

const candidates = [
  ...rows(articlesPayload, "articles"),
  ...rows(rankedPayload, "items"),
];
const event = candidates.find((row) => String(row.id || "").trim() === eventId);
if (!event) {
  throw new Error(`Native research event not found in published datasets: ${eventId}`);
}

const source = event.source && typeof event.source === "object" && !Array.isArray(event.source)
  ? event.source as Record<string, unknown>
  : {};

const request = {
  schemaVersion: 1,
  eventId,
  requestedAt: new Date().toISOString(),
  title: String(event.title || "").trim(),
  url: String(source.url || event.url || "").trim(),
  summary: String(event.summary || event.description || "").trim(),
  sector: String(event.sector || "").trim(),
  company: String(event.company || "").trim(),
  publishedAt: String(event.publishedAt || "").trim(),
  sourceName: String(source.name || event.sourceName || "").trim(),
  sourceLevel: String(source.level || event.sourceLevel || "").trim(),
  instruction: "围绕指定事件优先完成事实核验、历史变化、关系扩展、产业影响、bull/bear case 与下一证据；事件上下文只是研究起点，不得自动视为已验证事实。",
};

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, JSON.stringify(request, null, 2) + "\n", "utf8");
console.log(`Prepared native research request for ${eventId}`);
