import {
  validateInvestorResearch,
  type InnovationInvestor,
  type InvestorEvidenceRecord,
} from "@/lib/innovation-investor-research";
import type { InnovationCapitalFeedItem } from "@/lib/homepage-innovation-capital-channel";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

/**
 * A bounded publication bridge from the committed, source-traceable research
 * ledger to the existing homepage feed. This does NOT publish daily scout
 * navigation, self-reported financial performance or unreviewed candidates.
 */
export type InvestorHomepagePublication = {
  events: LiveIntelligenceEvent[];
  innovationItems: InnovationCapitalFeedItem[];
};

const DAY_MS = 86_400_000;
export const INVESTOR_HOMEPAGE_LOOKBACK_DAYS = 14;
export const INVESTOR_HOMEPAGE_MAX_ARTICLES = 12;

function materialUrl(input: string): string {
  const url = new URL(input);
  if (url.protocol !== "https:" || url.username || url.password ||
      !url.hostname || /^(localhost|127\.|10\.|192\.168\.)/u.test(url.hostname)) {
    throw new Error("Investor homepage publication requires a public HTTPS source");
  }
  url.hash = "";
  for (const key of [...url.searchParams.keys()]) {
    if (/^(utm_|gclid$|fbclid$)/iu.test(key)) url.searchParams.delete(key);
  }
  return url.toString().replace(/\/$/u, "");
}

function acceptedSource(record: InvestorEvidenceRecord): boolean {
  // Only exact-date investment/project or authored institutional viewpoints.
  // Company-reported metrics, unattributed historical items and media
  // republications must stay in the detailed research record.
  if (!record.project || record.datePrecision !== "day" ||
      record.date !== record.source.publishedAt ||
      record.source.kind !== "investor-official") return false;
  if (record.kind === "investment") return Boolean(record.participation);
  if (record.kind === "viewpoint") return true;
  if (record.kind === "outcome") {
    return record.resultStatus === "listed" || record.resultStatus === "acquired";
  }
  return false;
}

function priority(kind: string): number {
  if (kind === "investment") return 0;
  if (kind === "outcome") return 1;
  return 2;
}

export function buildInvestorHomepagePublication(
  records: readonly InvestorEvidenceRecord[],
  institutions: readonly InnovationInvestor[],
  nowMs: number,
): InvestorHomepagePublication {
  const invalid = validateInvestorResearch(institutions, records);
  if (invalid.length) throw new Error(`Unreviewed investor data may not be published: ${invalid.join("; ")}`);
  if (!Number.isFinite(nowMs)) throw new Error("Investor publication requires a valid observation clock");

  const byInstitution = new Map(institutions.map((item) => [item.id, item]));
  const grouped = new Map<string, InvestorEvidenceRecord[]>();
  for (const record of records) {
    if (!acceptedSource(record)) continue;
    const publishedMs = Date.parse(`${record.date}T00:00:00Z`);
    if (!Number.isFinite(publishedMs) || publishedMs > nowMs ||
        nowMs - publishedMs > INVESTOR_HOMEPAGE_LOOKBACK_DAYS * DAY_MS) continue;
    if (!byInstitution.has(record.institutionId)) continue;
    const key = JSON.stringify([record.institutionId, materialUrl(record.source.url)]);
    const existing = grouped.get(key) ?? [];
    existing.push(record);
    grouped.set(key, existing);
  }

  const events: LiveIntelligenceEvent[] = [];
  const innovationItems: InnovationCapitalFeedItem[] = [];
  const groups = [...grouped.values()].sort((a, b) =>
    b[0].date.localeCompare(a[0].date) || a[0].id.localeCompare(b[0].id),
  );
  for (const group of groups.slice(0, INVESTOR_HOMEPAGE_MAX_ARTICLES)) {
    const rows = [...group].sort((a, b) => priority(a.kind) - priority(b.kind) || a.id.localeCompare(b.id));
    const lead = rows[0];
    const institution = byInstitution.get(lead.institutionId)!;
    const projects = [...new Set(rows.map((r) => r.project).filter((p): p is string => Boolean(p)))];
    const authors = [...new Set(rows.flatMap((r) => r.speakers.map((person) => person.name)))];
    const hasInvestment = lead.kind === "investment";
    const isCapitalOutcome = lead.kind === "outcome";
    const eventId = `investor-source-${lead.id}`;
    const eventClusterId = `investor-research-${lead.id}`;
    const importance = hasInvestment
      ? (lead.participation === "lead" || lead.participation === "co-lead" ? 92 : 85)
      : isCapitalOutcome ? 88 : 79;
    const event: LiveIntelligenceEvent = {
      id: eventId,
      eventClusterId,
      title: lead.title,
      summary: `${lead.summary} 来源为机构官网；投资条款、个人交易责任及经营结果未披露的部分不能推断。`,
      type: hasInvestment ? "产业投资" : isCapitalOutcome ?
        (lead.resultStatus === "acquired" ? "并购" : "IPO") : "人物观点",
      region: institution.regionGroup === "中国相关" ? "中国" : "全球",
      sector: "产业投资",
      company: lead.project!,
      mentionedCompanies: projects,
      mentionedPeople: authors,
      institutions: [institution.name],
      matchedTrackingTerms: [], // Do not fabricate an explicit personal follow.
      sourceId: `investor-official-research-${institution.id}`,
      publishedAt: lead.date, // Day precision; no fabricated intraday timestamp.
      publicationTimePrecision: "day",
      importance,
      qualityStatus: "可用", // Original investor claims are NOT independent validation.
      qualityScore: 82,
      qualitySignals: ["机构原始披露", "观点与交易角色分开", "未独立验证基金回报"],
      source: {
        name: institution.name,
        url: lead.source.url,
        level: "官方披露",
        platform: "投资机构官方网站",
      },
    };
    events.push(event);
    innovationItems.push({
      eventId,
      sourceUrl: lead.source.url,
      publishedAt: lead.date,
      eventClusterId,
      matchedObjects: [
        {type: "institution", name: institution.name},
        ...projects.map((name) => ({type: "discovered-company" as const, name})),
      ],
      reasonCodes: [
        "CAPITAL_INSTITUTION",
        hasInvestment ? "FUNDING_EVENT" : isCapitalOutcome ? "LISTING_EVENT" : "INVESTOR_VIEWPOINT",
        "PRIMARY_EVIDENCE",
        "INVESTOR_SOURCE_RESEARCH",
      ],
      evidenceTier: "primary",
      innovationPriority: importance,
    });
  }
  return {events, innovationItems};
}
