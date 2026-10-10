import type { InnovationCapitalFeedProjection } from "@/lib/homepage-innovation-capital-channel";
import type { LiveIntelligenceEvent, Region } from "@/lib/use-articles";

/** Editorially selected original disclosures, never the raw scout candidate queue. */
export type InvestorHomepageSelection = {
  investmentEvidenceId: string;
  sector: string;
  region: string;
  importance: number;
};
export type InvestorHomepagePolicy = {
  schemaVersion: number;
  publicationMode: string;
  selections: InvestorHomepageSelection[];
};
type Firm = { id: string; name: string; officialUrl: string };
type Identity = { id: string; observedNames: string[] };
type Evidence = {
  id: string;
  institutionId: string;
  project: string | null;
  kind: string;
  date: string;
  datePrecision: string;
  title: string;
  summary: string;
  participation: string | null;
  round: string | null;
  investorAmount: {value: number; currency: string} | null;
  realizedProceeds: unknown;
  source: {url: string; title: string; publisher: string; kind: string; publishedAt: string | null};
  speakers?: Array<{name: string; attribution: string; projectResponsibility: string}>;
};

const DAY_MS = 86_400_000;
const PUBLICATION_WINDOW_DAYS = 30;
export const INVESTOR_HOMEPAGE_EVENT_PREFIX = "investor-original-source:";

export function investorMaterialUrl(value: string): string {
  const parsed = new URL(value);
  if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password ||
      (parsed.port && parsed.port !== "443") || parsed.search || parsed.hash) {
    throw new Error("Investor publication requires a canonical, credential-free HTTPS original URL");
  }
  return "https://" + parsed.hostname.toLowerCase().replace(/^www\./u, "") + (parsed.pathname.replace(/\/+$/u, "") || "/");
}

/** Browser article links may carry UTM tags. Match only the same HTTPS host/path. */
function comparableArticleUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password) return null;
    return "https://" + parsed.hostname.toLowerCase().replace(/^www\./u, "") + (parsed.pathname.replace(/\/+$/u, "") || "/");
  } catch { return null; }
}

function sourceHost(value: string): string {
  return new URL(investorMaterialUrl(value)).hostname;
}

function strictDate(value: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(value)) return NaN;
  const date = Date.parse(value + "T00:00:00Z");
  return Number.isFinite(date) && new Date(date).toISOString().slice(0, 10) === value ? date : NaN;
}

function publicRegion(value: string): Region {
  if (value !== "中国" && value !== "美国" && value !== "全球") {
    throw new Error("Investor publication requires a valid region");
  }
  return value;
}

/**
 * Fail closed on stale, mislabeled or unreviewed entries, including entries
 * outside the current publication window. Dates remain day-precision.
 */
export function buildInvestorHomepageEvents(
  policy: InvestorHomepagePolicy,
  evidence: readonly Evidence[],
  firms: readonly Firm[],
  identities: readonly Identity[],
  now: Date = new Date(),
): LiveIntelligenceEvent[] {
  if (policy.schemaVersion !== 1 ||
      policy.publicationMode !== "editorial-selected-first-party-investment-disclosures" ||
      !Array.isArray(policy.selections) || policy.selections.length > 24) {
    throw new Error("Investor homepage publication policy is invalid");
  }
  if (!Number.isFinite(now.getTime())) throw new Error("Invalid publication clock");
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const byId = new Map(evidence.map((row) => [row.id, row]));
  if (byId.size !== evidence.length) throw new Error("Duplicate source evidence IDs");
  const byFirm = new Map(firms.map((firm) => [firm.id, firm]));
  const seenSelections = new Set<string>();
  const seenUrls = new Set<string>();
  const result: LiveIntelligenceEvent[] = [];

  for (const choice of policy.selections) {
    if (!choice?.investmentEvidenceId || seenSelections.has(choice.investmentEvidenceId)) {
      throw new Error("Invalid or duplicate source publication");
    }
    seenSelections.add(choice.investmentEvidenceId);
    const row = byId.get(choice.investmentEvidenceId);
    if (!row || row.kind !== "investment" || !row.project || row.datePrecision !== "day" ||
        row.source.kind !== "investor-official" || row.source.publishedAt !== row.date ||
        !row.participation || row.realizedProceeds !== null ||
        identities.filter((identity) => identity.observedNames.includes(row.project!)).length !== 1) {
      throw new Error("Unreviewed or non-event source cannot be publicly projected");
    }
    const firm = byFirm.get(row.institutionId);
    if (!firm) throw new Error("Unknown investment institution");
    const url = investorMaterialUrl(row.source.url);
    if (sourceHost(row.source.url) !== sourceHost(firm.officialUrl)) {
      throw new Error("Event source differs from the institution official domain");
    }
    if (seenUrls.has(url)) throw new Error("Cannot publish one article twice");
    seenUrls.add(url);
    const published = strictDate(row.date);
    if (!Number.isFinite(published) || published > today ||
        !row.title.trim() || !row.summary.trim() || row.title.length > 220 ||
        row.summary.length > 1_600 ||
        typeof choice.sector !== "string" || !choice.sector.trim() || choice.sector.length > 100 ||
        !Number.isInteger(choice.importance) || choice.importance < 75 || choice.importance > 95) {
      throw new Error("Invalid publication date, text or priority");
    }
    const region = publicRegion(choice.region);
    const viewpoints = evidence.filter((item) =>
      item.kind === "viewpoint" && item.institutionId === row.institutionId &&
      item.project === row.project && item.date === row.date &&
      investorMaterialUrl(item.source.url) === url);
    const people = [...new Set(viewpoints.flatMap((item) =>
      (item.speakers ?? []).filter((speaker) =>
        speaker.attribution === "paraphrase" && Boolean(speaker.projectResponsibility),
      ).map((speaker) => speaker.name.trim()).filter(Boolean),
    ))].slice(0, 8);
    // Old articles must age out. Never recycle scan time as publication time.
    if ((today - published) / DAY_MS > PUBLICATION_WINDOW_DAYS) continue;
    const summary = people.length
      ? row.summary + " 同篇另有" + people.join("、") + "的署名观点；署名不证明个人交易签约责任。"
      : row.summary;
    result.push({
      id: INVESTOR_HOMEPAGE_EVENT_PREFIX + row.id,
      title: row.title, summary: summary.slice(0, 1_600),
      type: "产业投资", region, sector: choice.sector, company: row.project,
      sourceId: "innovation-investor-original-reviewed",
      publishedAt: row.date, publicationTimePrecision: "day",
      importance: choice.importance,
      source: {name: firm.name, url: row.source.url, level: "官方披露", platform: "机构官方投资披露"},
      curated: true, qualityStatus: "可用", qualityScore: 85,
      qualitySignals: ["机构原文已对照；未证明个人交易责任或现金回报"],
      eventClusterId: "investor-official:" + url,
      mentionedCompanies: [row.project], mentionedPeople: people,
      // Do not turn institutional coverage into an artificial personal focus.
      matchedTrackingTerms: [],
    });
  }
  return result.sort((a, b) => b.publishedAt.localeCompare(a.publishedAt) || a.id.localeCompare(b.id));
}

/** Keep editorial events even after the browser reloads crawler-owned articles. */
export function mergeInvestorHomepageEvents(
  archive: readonly LiveIntelligenceEvent[],
  published: readonly LiveIntelligenceEvent[],
): LiveIntelligenceEvent[] {
  const officialUrls = new Set(published.map((item) => investorMaterialUrl(item.source.url)));
  const officialIds = new Set(published.map((item) => item.id));
  return [
    ...published,
    ...archive.filter((item) => {
      if (officialIds.has(item.id)) return false;
      const key = comparableArticleUrl(item.source.url);
      return !key || !officialUrls.has(key);
    }),
  ];
}

/** Existing "科创" projector stays authoritative for all other articles. */
export function withInvestorHomepageInnovationProjection(
  current: InnovationCapitalFeedProjection,
  published: readonly LiveIntelligenceEvent[],
): InnovationCapitalFeedProjection {
  const eventIds = new Set(published.map((item) => item.id));
  const sourceUrls = new Set(published.map((item) => investorMaterialUrl(item.source.url)));
  const retained = current.items.filter((item) => {
    if (eventIds.has(item.eventId)) return false;
    const key = comparableArticleUrl(item.sourceUrl);
    return !key || !sourceUrls.has(key);
  });
  const appended: InnovationCapitalFeedProjection["items"] = published.map((item) => ({
    eventId: item.id, sourceUrl: item.source.url, publishedAt: item.publishedAt,
    eventClusterId: item.eventClusterId ?? "",
    matchedObjects: [
      {type: "institution", name: item.source.name},
      {type: "discovered-company", name: item.company},
    ],
    reasonCodes: ["CAPITAL_INSTITUTION", "FUNDING_EVENT", "PRIMARY_EVIDENCE"],
    evidenceTier: "primary",
    innovationPriority: Math.min(95, Math.max(75, item.importance)),
  }));
  const items = [...appended, ...retained];
  return {...current, eventCount: items.length, items};
}
