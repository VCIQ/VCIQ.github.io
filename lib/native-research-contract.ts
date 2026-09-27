export const NATIVE_RESEARCH_ADMIN_ORIGIN = "https://vciq-tracking-console.pages.dev";
export const NATIVE_RESEARCH_PUBLIC_ORIGIN = "https://vciq.github.io";
export const NATIVE_RESEARCH_REPORTS_PATH = "/data/native_research_reports.json";
export const NATIVE_RESEARCH_WORKFLOW_FILE = "native-event-research.yml";

export function validResearchEventId(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,179}$/.test(value);
}
export function validResearchRequestId(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
}
export function researchResultHref(eventId: string, requestId?: string, runId?: number) {
  const params = new URLSearchParams({ event: eventId });
  if (requestId && validResearchRequestId(requestId)) params.set("request", requestId);
  if (runId && Number.isSafeInteger(runId) && runId > 0) params.set("run", String(runId));
  return `/research-agent/investigate/result/?${params}`;
}
export function researchLaunchUrl(eventId: string, requestId: string, nonce: string) {
  if (!validResearchEventId(eventId) || !validResearchRequestId(requestId) || !validResearchRequestId(nonce)) throw new Error("研究请求身份无效。");
  const url = new URL("/research/launch", NATIVE_RESEARCH_ADMIN_ORIGIN);
  url.searchParams.set("event", eventId);
  url.searchParams.set("request", requestId);
  url.hash = new URLSearchParams({ nonce }).toString();
  return url.toString();
}
export function safeResearchUrl(value: unknown): string {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password && !url.pathname.includes("/alerts/feeds/") ? url.toString() : "";
  } catch { return ""; }
}
export const RESEARCH_SECTIONS = {
  facts: "来源陈述", history: "历史变化", relationships: "关联对象", industryImpact: "产业影响",
  bullCase: "正向假设", bearCase: "反向假设", unknowns: "证据缺口", nextEvidence: "下一步取证",
} as const;
export type ResearchClaim = { text: string; kind: "source_statement" | "inference" | "unknown"; evidenceIds: string[] };
export type ResearchEvidence = { id: string; title: string; url: string; excerpt: string; sourceName: string; publishedAt: string; verificationStatus: string };
export type NativeResearchReport = {
  schemaVersion: 2; eventId: string; requestId: string; runId: string; runUrl: string; title: string; sector: string;
  sourceUrl: string; status: "completed-draft" | "evidence-insufficient" | "model-unavailable" | "event-unavailable";
  requestedAt: string; completedAt: string; note: string; methodology: string; modelUsed: boolean;
  reviewStatus: "automated_unreviewed"; evidence: ResearchEvidence[];
  analysis: { executiveSummary: ResearchClaim; sections: Record<keyof typeof RESEARCH_SECTIONS, ResearchClaim[]> } | null;
};
function object(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
function text(value: unknown, limit: number) { return typeof value === "string" ? value.slice(0, limit) : ""; }
function claim(value: unknown, evidence: Set<string>): ResearchClaim | null {
  const row = object(value);
  if (!row || typeof row.text !== "string" || !row.text.trim() || row.text.length > 1000
    || !["source_statement", "inference", "unknown"].includes(String(row.kind))
    || !Array.isArray(row.evidenceIds) || row.evidenceIds.length === 0 || row.evidenceIds.length > 16
    || row.evidenceIds.some((id) => typeof id !== "string" || !evidence.has(id))) return null;
  return { text: row.text, kind: row.kind as ResearchClaim["kind"], evidenceIds: row.evidenceIds as string[] };
}
export function parseNativeResearchReports(value: unknown): NativeResearchReport[] {
  const payload = object(value);
  if (!payload || payload.schemaVersion !== 2 || !Array.isArray(payload.results) || payload.results.length > 40) throw new Error("研究报告索引格式不符。");
  return payload.results.map((value) => {
    const row = object(value);
    if (!row || row.schemaVersion !== 2 || !validResearchEventId(row.eventId) || !validResearchRequestId(row.requestId)
      || row.reviewStatus !== "automated_unreviewed"
      || !["completed-draft", "evidence-insufficient", "model-unavailable", "event-unavailable"].includes(String(row.status))) throw new Error("研究报告身份或状态校验失败。");
    const evidence = (Array.isArray(row.evidence) ? row.evidence : []).slice(0, 16).map((value) => {
      const source = object(value);
      if (!source || !/^N\d{3}$/.test(String(source.id)) || !safeResearchUrl(source.url)) throw new Error("研究证据链接无效。");
      return { id: String(source.id), title: text(source.title, 300), url: safeResearchUrl(source.url), excerpt: text(source.excerpt, 2500), sourceName: text(source.sourceName, 160), publishedAt: text(source.publishedAt, 80), verificationStatus: text(source.verificationStatus, 80) };
    });
    let analysis: NativeResearchReport["analysis"] = null;
    if (row.status === "completed-draft") {
      const raw = object(row.analysis);
      const rawSections = object(raw?.sections);
      const ids = new Set(evidence.map((source) => source.id));
      const summary = claim(raw?.executiveSummary, ids);
      if (!rawSections || !summary || row.modelUsed !== true || ids.size !== evidence.length) throw new Error("报告不满足证据合同。");
      const sections = {} as Record<keyof typeof RESEARCH_SECTIONS, ResearchClaim[]>;
      for (const name of Object.keys(RESEARCH_SECTIONS) as Array<keyof typeof RESEARCH_SECTIONS>) {
        const values = rawSections[name];
        if (!Array.isArray(values) || !values.length || values.length > 4) throw new Error("研究章节缺失。");
        sections[name] = values.map((entry) => {
          const item = claim(entry, ids);
          if (!item || (name === "facts" && item.kind !== "source_statement")) throw new Error("研究结论没有合法证据关联。");
          return item;
        });
      }
      analysis = { executiveSummary: summary, sections };
    }
    return {
      schemaVersion: 2, eventId: row.eventId, requestId: row.requestId,
      runId: text(row.runId, 30), runUrl: safeResearchUrl(row.runUrl), title: text(row.title, 300), sector: text(row.sector, 120),
      sourceUrl: safeResearchUrl(row.sourceUrl), status: row.status as NativeResearchReport["status"], requestedAt: text(row.requestedAt, 80), completedAt: text(row.completedAt, 80),
      note: text(row.note, 1000), methodology: text(row.methodology, 1000), modelUsed: row.modelUsed === true,
      reviewStatus: "automated_unreviewed", evidence, analysis,
    } as NativeResearchReport;
  });
}
