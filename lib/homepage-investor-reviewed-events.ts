import evidenceManifest from "@/config/innovation_investor_evidence.json";
import rosterManifest from "@/config/innovation_global_investors.json";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

/**
 * Editorial publication from dated, source-located research records, not
 * automated URL discoveries. Project records are not portfolio coverage.
 */
type InvestorRecord = (typeof evidenceManifest.records)[number];
export const INVESTOR_HOMEPAGE_POLICY = {
  maxDaysAfterOriginalPublication: 45,
  latestEventLimit: 32,
  eligibleKinds: ["investment", "outcome", "viewpoint"] as const,
} as const;

const firmById = new Map(rosterManifest.institutions.map((firm) => [firm.id, firm]));
const TYPES = {
  investment: "产业投资",
  outcome: "公司动态",
  viewpoint: "人物观点",
} as const;

function day(value: string | null | undefined): string | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/u.test(value)) return null;
  const ms = Date.parse(value + "T00:00:00Z");
  return Number.isFinite(ms) && new Date(ms).toISOString().slice(0, 10) === value ? value : null;
}

function safeOriginalUrl(raw: string): boolean {
  try {
    const value = new URL(raw);
    return value.protocol === "https:" && !!value.hostname &&
      !value.username && !value.password && !value.hash &&
      !value.hostname.endsWith(".local");
  } catch { return false; }
}

function reviewedRecord(record: InvestorRecord, nowMs: number): boolean {
  if (!["investment", "outcome", "viewpoint"].includes(record.kind)) return false;
  if (!record.project || !firmById.has(record.institutionId)) return false;
  const publicationDay = day(record.source.publishedAt);
  if (!publicationDay || !safeOriginalUrl(record.source.url)) return false;
  if (!record.source.locator?.trim()) return false;
  // Historical investment year or a later retrospective article is NOT a new event.
  if (record.datePrecision !== "day" || record.date !== publicationDay) return false;
  const when = Date.parse(publicationDay + "T00:00:00Z");
  const age = nowMs - when;
  if (!Number.isFinite(nowMs) || age < 0 || age > INVESTOR_HOMEPAGE_POLICY.maxDaysAfterOriginalPublication * 86400000) {
    return false;
  }
  if (record.kind === "investment" && !record.participation) return false;
  if (record.kind === "outcome" && !record.resultStatus) return false;
  if (record.kind === "viewpoint" && !record.speakers.length) return false;
  // Company-provided progress cannot be silently upgraded to independently verified reporting.
  return true;
}

function projectEvent(record: InvestorRecord): LiveIntelligenceEvent {
  const firm = firmById.get(record.institutionId)!;
  const region: LiveIntelligenceEvent["region"] =
    firm.regionGroup === "中国" ? "中国" :
    firm.regionGroup === "北美" ? "美国" : "全球";
  const isInvestment = record.kind === "investment";
  const isOutcome = record.kind === "outcome";
  const isOpinion = record.kind === "viewpoint";
  const people = isOpinion ? record.speakers.map((s) => s.name) : [];
  return {
    id: "investor-reviewed:" + record.id,
    title: record.title,
    summary: record.summary + " · 机构来源已整理，完整投资责任及基金回报需另行核验。",
    type: TYPES[record.kind as keyof typeof TYPES],
    region,
    sector: "科创投资",
    company: record.project!,
    sourceId: "investor-reviewed-evidence",
    publishedAt: record.source.publishedAt + "T00:00:00Z",
    publicationTimePrecision: "day",
    importance: isInvestment ? 86 : isOutcome ? 77 : 73,
    source: {
      name: firm.name,
      url: record.source.url,
      level: "官方披露",
      platform: "机构原始证据",
    },
    qualityStatus: "高可信",
    qualityScore: 85,
    mentionedCompanies: [record.project!],
    mentionedPeople: people,
    matchedTrackingTerms: [firm.name, record.project!],
    curated: true,
  };
}

export function projectReviewedInvestorHomepageEvents(
  records: readonly InvestorRecord[] = evidenceManifest.records,
  nowMs: number = Date.now(),
): LiveIntelligenceEvent[] {
  // A single article can support a deal and several opinions; one homepage
  // card per URL prevents duplicated click counts and headline impressions.
  const seen = new Set<string>();
  const output: LiveIntelligenceEvent[] = [];
  const order = [...records].filter((r) => reviewedRecord(r, nowMs))
    .sort((a, b) => {
      const rank = (r: InvestorRecord) => r.kind === "investment" ? 2 : r.kind === "outcome" ? 1 : 0;
      return b.date.localeCompare(a.date) || rank(b) - rank(a) || a.id.localeCompare(b.id);
    });
  for (const record of order) {
    const key = record.source.url.toLowerCase().replace(/\/$/u, "");
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(projectEvent(record));
    if (output.length === INVESTOR_HOMEPAGE_POLICY.latestEventLimit) break;
  }
  return output;
}

export function mergeReviewedInvestorHomepageEvents(
  articles: readonly LiveIntelligenceEvent[],
  investorEvents: readonly LiveIntelligenceEvent[],
): LiveIntelligenceEvent[] {
  const urls = new Set(articles.map((article) => article.source.url.toLowerCase().replace(/\/$/u, "")));
  return [...articles, ...investorEvents.filter((row) => {
    const key = row.source.url.toLowerCase().replace(/\/$/u, "");
    if (urls.has(key)) return false;
    urls.add(key);
    return true;
  })];
}
