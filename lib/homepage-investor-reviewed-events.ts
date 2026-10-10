import { homepageMaterialUrl } from "@/lib/homepage-event-identity";
import { REVIEWED_INVESTOR_SOURCE_ID } from "@/lib/homepage-reviewed-investor-merge";
import type { InnovationCapitalFeedProjection } from "@/lib/homepage-innovation-capital-channel";
import {
  globalInnovationInvestors,
  investorEvidenceRecords,
  type InnovationInvestor,
  type InvestorEvidenceRecord,
} from "@/lib/innovation-investor-research";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";


export const REVIEWED_INVESTOR_WINDOW_DAYS = 45;
const DAY_MS = 86_400_000;
const MAX_HOMEPAGE_INVESTOR_EVENTS = 24;

type ReviewedEvidence = InvestorEvidenceRecord;
type Institution = InnovationInvestor;

/**
 * Project only explicitly published, dated investor evidence onto the homepage.
 * Homepage entries are display projections, never edits to the article archive.
 * The daily navigation scout is deliberately NOT an input to this module.
 */
export function projectReviewedInvestorHomepageEvents(
  records: readonly ReviewedEvidence[] = investorEvidenceRecords,
  institutions: readonly Institution[] = globalInnovationInvestors,
  nowMs: number = Date.now(),
): LiveIntelligenceEvent[] {
  const firms = new Map(institutions.map((firm) => [firm.id, firm]));
  const sourceGroups = new Map<string, ReviewedEvidence[]>();
  const validDate = /^\d{4}-\d{2}-\d{2}$/u;

  for (const record of records) {
    const firm = firms.get(record.institutionId);
    if (!firm || !record.project || record.datePrecision !== "day" ||
        record.source.kind !== "investor-official" ||
        !record.source.publishedAt || !validDate.test(record.date) ||
        record.source.publishedAt !== record.date) continue;
    if (record.kind !== "investment" &&
        !(record.kind === "viewpoint" && record.speakers.length > 0) &&
        !(record.kind === "outcome" && ["listed", "acquired"].includes(record.resultStatus ?? ""))) {
      continue;
    }
    const publishedMs = Date.parse(record.date + "T00:00:00Z");
    if (!Number.isFinite(publishedMs) || publishedMs > nowMs + DAY_MS ||
        nowMs - publishedMs > REVIEWED_INVESTOR_WINDOW_DAYS * DAY_MS) continue;
    // In-scope HTTPS official host, with no embedded credentials, non-standard ports,
    // cross-site redirects or made-up article dates. This checks approved source metadata,
    // not third-party investment outcomes or unreviewed discovery candidates.
    let sourceUrl: URL;
    let officialUrl: URL;
    try {
      sourceUrl = new URL(record.source.url);
      officialUrl = new URL(firm.officialUrl);
    } catch { continue; }
    const host = (value: URL) => value.hostname.toLowerCase().replace(/^www\./u, "");
    if (sourceUrl.protocol !== "https:" || sourceUrl.username || sourceUrl.password ||
        (sourceUrl.port && sourceUrl.port !== "443") ||
        host(sourceUrl) !== host(officialUrl)) continue;
    const key = record.institutionId + ":" + homepageMaterialUrl(record.source.url);
    if (!key.endsWith(":") && !sourceGroups.has(key)) sourceGroups.set(key, []);
    sourceGroups.get(key)?.push(record);
  }

  const result: LiveIntelligenceEvent[] = [];
  for (const group of sourceGroups.values()) {
    // Multiple facts from the SAME investor article must not make two homepage stories.
    const lead = group.find((row) => row.kind === "investment") ??
      group.find((row) => row.kind === "outcome") ??
      group.find((row) => row.kind === "viewpoint");
    if (!lead || !lead.project) continue;
    const firm = firms.get(lead.institutionId);
    if (!firm) continue;
    const speakers = [...new Set(group.flatMap((row) =>
      row.speakers.map((person) => person.name.trim()).filter(Boolean)))].slice(0, 8);
    const relatedPointOfView = lead.kind === "investment" &&
      group.some((row) => row.kind === "viewpoint" && row.speakers.length > 0);
    const additionalContext = relatedPointOfView && speakers.length
      ? " 同篇原文还包含署名观点：" + speakers.join("、") + "；署名不能证明个人交易签约责任。"
      : "";
    const title = lead.kind === "viewpoint" ? "投资人观点｜" + lead.title.trim() : lead.title.trim();
    const summary = (lead.summary.trim() + additionalContext +
      " 来源为机构官方披露，不代表独立尽调或基金现金回报。").slice(0, 780);
    const type: LiveIntelligenceEvent["type"] =
      lead.kind === "investment" ? "产业投资" :
      lead.kind === "outcome" ? (lead.resultStatus === "listed" ? "IPO" : "并购") :
      "人物观点";
    const importance = lead.kind === "investment" ? (
      ["lead", "co-lead", "sole-investor"].includes(lead.participation ?? "") ? 92 : 86
    ) : lead.kind === "outcome" ? 90 : 85;
    result.push({
      id: "reviewed-investor:" + lead.id,
      title,
      summary,
      type,
      region: firm.regionGroup.includes("中国") ? "中国" : "全球",
      sector: "科创投资",
      company: lead.project,
      sourceId: REVIEWED_INVESTOR_SOURCE_ID,
      authors: speakers,
      institutions: [firm.name],
      publishedAt: lead.date, // Exact day precision; never synthesize an hour.
      publicationTimePrecision: "day",
      importance,
      source: {
        name: lead.source.publisher,
        url: lead.source.url,
        level: "官方披露",
        platform: "全球投资机构原文",
      },
      curated: true,
      qualityStatus: "可用",
      qualityScore: 82,
      qualitySignals: [
        "投资机构官网原文",
        "原始发表日期已记录",
        "观点与投资事实分开，投资回报未知",
      ],
      mentionedCompanies: [lead.project],
      mentionedPeople: speakers,
      // Never forge matchedTrackingTerms: that field is an *explicit* focus
      // signal, not a list of interesting institutions we happen to mention.
    });
  }

  return result.sort((a, b) =>
    b.publishedAt.localeCompare(a.publishedAt) ||
    b.importance - a.importance || a.id.localeCompare(b.id),
  ).slice(0, MAX_HOMEPAGE_INVESTOR_EVENTS);
}

/**
 * Add an explicit "reviewed capital evidence" source annotation to the same
 * build-derived 科创 projection. It is *not* a bypass for raw scout candidates.
 * Recent investor viewpoints are included only when attributable to a named
 * speaker in the reviewed official evidence, not generic market commentary.
 */
export function withReviewedInvestorInnovationProjection(
  base: InnovationCapitalFeedProjection,
  reviewed: readonly LiveIntelligenceEvent[],
  institutions: readonly Institution[] = globalInnovationInvestors,
): InnovationCapitalFeedProjection {
  const names = new Set(institutions.map((firm) => firm.name));
  const additions: InnovationCapitalFeedProjection["items"] = [];
  for (const event of reviewed) {
    const name = event.institutions?.[0];
    if (event.sourceId !== REVIEWED_INVESTOR_SOURCE_ID || !name || !names.has(name) ||
        event.source.level !== "官方披露") continue;
    const url = homepageMaterialUrl(event.source.url);
    if (!url) continue;
    const isViewpoint = event.type === "人物观点";
    const reasons = ["CAPITAL_INSTITUTION", "PRIMARY_EVIDENCE", "REVIEWED_INVESTOR_EVIDENCE"];
    if (isViewpoint) reasons.push("REVIEWED_INVESTOR_VIEWPOINT");
    else if (event.type === "IPO") reasons.push("LISTING_EVENT");
    else if (event.type === "并购") reasons.push("LISTING_EVENT");
    else reasons.push("FUNDING_EVENT");
    additions.push({
      eventId: event.id, sourceUrl: event.source.url,
      publishedAt: event.publishedAt, eventClusterId: "",
      matchedObjects: [{type: "institution", name}],
      reasonCodes: reasons,
      evidenceTier: "primary",
      innovationPriority: isViewpoint ? 70 : 90,
    });
  }
  const urlKeys = new Set(additions.map((row) => homepageMaterialUrl(row.sourceUrl)));
  const idKeys = new Set(additions.map((row) => row.eventId));
  const merged = [...additions, ...base.items.filter((row) =>
    !idKeys.has(row.eventId) && !urlKeys.has(homepageMaterialUrl(row.sourceUrl))
  )].sort((a, b) =>
    b.publishedAt.localeCompare(a.publishedAt) ||
    b.innovationPriority - a.innovationPriority ||
    a.eventId.localeCompare(b.eventId),
  ).slice(0, 240);
  return {...base, eventCount: merged.length, items: merged};
}
