import evidence from "@/config/innovation_investor_evidence.json";
import roster from "@/config/innovation_global_investors.json";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

type InvestorEvidence = (typeof evidence.records)[number];
type InvestorRecord = Pick<InvestorEvidence, "id" | "institutionId" | "project" | "kind" | "date" |
  "datePrecision" | "title" | "summary" | "participation" | "source" | "investorAmount" | "roundAmount">;

export const REVIEWED_INVESTOR_EVENT_PREFIX = "reviewed-investor-investment:";

/** A dated first-party investment disclosure; not a source-scout navigation candidate. */
export function projectReviewedInvestorHomepageEvents(
  records: readonly InvestorRecord[] = evidence.records,
  now: Date = new Date(),
): LiveIntelligenceEvent[] {
  const firms = new Map(roster.institutions.map((firm) => [firm.id, firm]));
  const nowMs = now.getTime();
  if (!Number.isFinite(nowMs)) return [];
  const results: LiveIntelligenceEvent[] = [];
  const seen = new Set<string>();
  for (const row of records) {
    if (row.kind !== "investment" || row.datePrecision !== "day" || !row.project) continue;
    if (row.source.kind !== "investor-official" && row.source.kind !== "company-official") continue;
    if (row.source.publishedAt !== row.date) continue;
    const date = Date.parse(row.date + "T00:00:00Z");
    if (!Number.isFinite(date) || date > nowMs + 86_400_000 || nowMs - date > 14 * 86_400_000) continue;
    const firm = firms.get(row.institutionId);
    if (!firm || !row.source.url.startsWith("https://") || !row.source.locator) continue;
    try {
      const u = new URL(row.source.url);
      if (u.protocol !== "https:" || u.username || u.password || !u.hostname) continue;
    } catch { continue; }
    const dedupeKey = row.institutionId + "::" + row.project + "::" + row.date + "::" + (row.round ?? "");
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    const location = firm.regionGroup === "中国" ? "中国" : "全球";
    results.push({
      id: REVIEWED_INVESTOR_EVENT_PREFIX + row.id,
      title: row.title,
      summary: row.summary,
      type: "产业投资",
      region: location,
      sector: "科创",
      company: row.project,
      institutions: [firm.name],
      publishedAt: row.date,
      importance: row.participation === "lead" || row.participation === "co-lead" ? 85 : 77,
      source: {name: firm.name + " · 官网披露", url: row.source.url, level: "官方披露", platform: "机构研究证据"},
      qualityStatus: "高可信",
      entityResolutionStatus: "matched",
      publicationTimePrecision: "day",
      curated: false,
    });
  }
  return results.sort((a, b) => b.publishedAt.localeCompare(a.publishedAt) || a.id.localeCompare(b.id));
}
