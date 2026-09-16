import { companies } from "@/lib/catalog-data";
import {
  listedCompanyDisclosures,
  listedDisclosureGeneratedAt,
  type ListedDisclosureEvent,
} from "@/lib/listed-company-disclosure-data";
import { homepageMaterialUrl } from "@/lib/homepage-event-identity";
import type {
  LiveIntelligenceEvent,
  Region,
} from "@/lib/use-articles";

const MAX_DISCLOSURE_AGE_DAYS = 400;
const DEFAULT_DISCLOSURE_LIMIT = 48;
const COMPANY_FIRST_PAGE_DISCLOSURE_TARGET = 6;
const COMPANY_DISCLOSURE_PROMOTION_WINDOW_DAYS = 45;

const MATERIAL_RULES: Record<
  string,
  { type: LiveIntelligenceEvent["type"]; importance: number }
> = {
  招股与上市: { type: "IPO", importance: 96 },
  定期报告与业绩: { type: "财报", importance: 92 },
  证券发行与融资: { type: "融资", importance: 90 },
  并购与资产交易: { type: "并购", importance: 95 },
  股权激励: { type: "公司动态", importance: 84 },
  股份回购: { type: "公司动态", importance: 89 },
  重大经营与风险: { type: "监管文件", importance: 90 },
};

const MATERIAL_BUSINESS_SIGNAL_RE = /(?:重大合同|重大事项|战略合作|合作协议|订单|中标|交付|量产|扩产|停产|复产|处罚|诉讼|仲裁|调查|风险|控制权|重组|收购|并购|出售资产|交易进展|盈利|亏损|收入|利润|业绩|回购|发行|融资|募资|上市|签署|终止上市|破产|清算)|\b(?:business update|trading update|inside information|strategic partnership|material contract|major transaction|acquisition|disposal|litigation|investigation|revenue|profit|loss|guidance|repurchase|financing|offering)\b/iu;

const ROUTINE_DISCLOSURE_RE = /(?:股东大会通知|董事会会议通知|监事会会议通知|独立董事|会计师事务所|审计机构|章程修订|制度修订|日常关联交易预计|年度股东大会|一般性授权)|\b(?:notice of annual general meeting|notice of meeting|monthly return|re-election of directors|re-appointment of auditor|general mandate)\b/iu;

const companyBySlug = new Map(companies.map((company) => [company.slug, company]));

function normalizedRegion(event: ListedDisclosureEvent): Region {
  const company = companyBySlug.get(event.companySlug);
  if (company?.region === "中国" || company?.region === "美国" || company?.region === "全球") {
    return company.region;
  }
  return event.market === "美股" ? "美国" : "中国";
}

function materialRule(event: ListedDisclosureEvent) {
  const rule = MATERIAL_RULES[event.documentType];
  if (!rule) return null;
  if (event.source.level !== "监管文件" || event.fallback) return null;

  if (event.documentType === "重大经营与风险") {
    const text = `${event.title} ${event.summary}`;
    if (ROUTINE_DISCLOSURE_RE.test(text) && !MATERIAL_BUSINESS_SIGNAL_RE.test(text)) {
      return null;
    }
    if (!MATERIAL_BUSINESS_SIGNAL_RE.test(text)) return null;
  }

  return rule;
}

function disclosureCutoff() {
  const anchor = Date.parse(listedDisclosureGeneratedAt);
  if (!Number.isFinite(anchor)) return Number.NEGATIVE_INFINITY;
  return anchor - MAX_DISCLOSURE_AGE_DAYS * 86_400_000;
}

function adjustedImportance(event: ListedDisclosureEvent, base: number) {
  const title = event.title;
  if (/(?:年度报告|半年度报告|季度报告|业绩预告|业绩快报)|\b(?:annual report|interim report|quarterly results|profit warning)\b/iu.test(title)) {
    return Math.max(base, 93);
  }
  if (/(?:重大资产重组|收购|并购|控制权|重大合同)|\b(?:acquisition|major transaction|material contract)\b/iu.test(title)) {
    return Math.max(base, 95);
  }
  return base;
}

function uniqueStrings(values: readonly (string | undefined)[]) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = String(raw ?? "").trim();
    const key = value.normalize("NFKC").toLocaleLowerCase("zh-CN");
    if (!value || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result;
}

function disclosureQualitySignals(event: ListedDisclosureEvent) {
  const signals = ["正式公司档案", "官方监管披露"];
  if (/cninfo/iu.test(event.discoveredVia) || event.source.name.includes("巨潮")) {
    signals.push("CNINFO 结构化披露");
  } else if (event.market === "美股") {
    signals.push("SEC 官方披露");
  } else {
    signals.push("交易所官方披露");
  }
  return signals;
}

function projectDisclosureEvent(event: ListedDisclosureEvent): LiveIntelligenceEvent | null {
  const company = companyBySlug.get(event.companySlug);
  const rule = materialRule(event);
  if (!company || !rule) return null;
  const publishedAtMs = Date.parse(event.publishedAt);
  if (Number.isFinite(publishedAtMs) && publishedAtMs < disclosureCutoff()) return null;

  return {
    id: `listed-disclosure:${event.id}`,
    title: event.title,
    summary: `${event.exchange} · ${event.documentType}。${event.summary}`,
    type: rule.type,
    region: normalizedRegion(event),
    sector: company.sector,
    company: company.name,
    companySlug: company.slug,
    sourceId: "listed-company-disclosures",
    publishedAt: event.publishedAt,
    importance: adjustedImportance(event, rule.importance),
    source: {
      name: event.source.name,
      url: event.source.url,
      level: "监管文件",
      platform: event.exchange,
    },
    curated: true,
    qualityStatus: "高可信",
    qualitySignals: disclosureQualitySignals(event),
    duplicateCount: 1,
    mentionedCompanies: [company.name],
    matchedTrackingTerms: [company.name, event.ticker, event.documentType, event.exchange],
  };
}

export function projectHomepageCompanyDisclosureEvents(
  limit = DEFAULT_DISCLOSURE_LIMIT,
): LiveIntelligenceEvent[] {
  const events = listedCompanyDisclosures
    .flatMap((company) => company.events)
    .map(projectDisclosureEvent)
    .filter((event): event is LiveIntelligenceEvent => Boolean(event))
    .sort(
      (left, right) =>
        right.publishedAt.localeCompare(left.publishedAt) ||
        right.importance - left.importance ||
        left.title.localeCompare(right.title, "zh-CN"),
    );

  const result: LiveIntelligenceEvent[] = [];
  const seenUrls = new Set<string>();
  for (const event of events) {
    const key = homepageMaterialUrl(event.source.url);
    if (!key || seenUrls.has(key)) continue;
    seenUrls.add(key);
    result.push(event);
    if (result.length >= limit) break;
  }
  return result;
}

function normalizedTitle(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "")
    .slice(0, 180);
}

function titleIdentity(event: LiveIntelligenceEvent) {
  const title = normalizedTitle(event.title);
  if (!title) return "";
  return `${event.companySlug ?? event.company ?? "unknown"}:${title}`;
}

function enrichCanonicalCompanyEvent(
  canonical: LiveIntelligenceEvent,
  disclosure: LiveIntelligenceEvent,
): LiveIntelligenceEvent {
  return {
    ...canonical,
    company: canonical.company || disclosure.company,
    companySlug: canonical.companySlug ?? disclosure.companySlug,
    qualityStatus: canonical.qualityStatus ?? disclosure.qualityStatus,
    qualitySignals: uniqueStrings([
      ...(canonical.qualitySignals ?? []),
      ...(disclosure.qualitySignals ?? []),
    ]),
    mentionedCompanies: uniqueStrings([
      ...(canonical.mentionedCompanies ?? []),
      ...(disclosure.mentionedCompanies ?? []),
    ]),
    matchedTrackingTerms: uniqueStrings([
      ...(canonical.matchedTrackingTerms ?? []),
      ...(disclosure.matchedTrackingTerms ?? []),
    ]),
    importance: Math.max(canonical.importance, disclosure.importance),
  };
}

/**
 * Keep the canonical article pool authoritative when an article already points
 * at the same official filing. Otherwise admit a bounded, material subset of
 * official listed-company disclosures into the homepage company channel only.
 */
export function mergeHomepageCompanyChannelEvents(
  articleEvents: readonly LiveIntelligenceEvent[],
  disclosureEvents: readonly LiveIntelligenceEvent[],
  canonicalArticleEvents: readonly LiveIntelligenceEvent[] = articleEvents,
): LiveIntelligenceEvent[] {
  const merged = [...articleEvents];
  const canonicalByUrl = new Map<string, LiveIntelligenceEvent>();
  for (const article of canonicalArticleEvents) {
    const key = homepageMaterialUrl(article.source.url);
    if (key && !canonicalByUrl.has(key)) canonicalByUrl.set(key, article);
  }
  const seenUrls = new Set(
    articleEvents.map((event) => homepageMaterialUrl(event.source.url)).filter(Boolean),
  );
  const seenTitles = new Set(
    articleEvents.map(titleIdentity).filter(Boolean),
  );

  for (const event of disclosureEvents) {
    const urlKey = homepageMaterialUrl(event.source.url);
    const titleKey = titleIdentity(event);
    const canonical = urlKey ? canonicalByUrl.get(urlKey) : undefined;
    if (canonical) {
      const existingIndex = merged.findIndex((item) =>
        item.id === canonical.id ||
        (urlKey && homepageMaterialUrl(item.source.url) === urlKey),
      );
      const base = existingIndex >= 0 ? merged[existingIndex] : canonical;
      const enriched = enrichCanonicalCompanyEvent(base, event);
      if (existingIndex >= 0) merged[existingIndex] = enriched;
      else merged.push(enriched);
      if (urlKey) seenUrls.add(urlKey);
      if (titleKey) seenTitles.add(titleKey);
      continue;
    }

    if ((urlKey && seenUrls.has(urlKey)) || (titleKey && seenTitles.has(titleKey))) continue;
    merged.push(event);
    if (urlKey) seenUrls.add(urlKey);
    if (titleKey) seenTitles.add(titleKey);
  }

  return merged;
}

export function isOfficialCompanyDisclosureEvent(event: LiveIntelligenceEvent) {
  return event.sourceId === "listed-company-disclosures" ||
    event.qualitySignals?.includes("官方监管披露") === true;
}

/**
 * The company channel is primarily a recency feed, but a pure newest-first sort
 * can bury the official filings that make the channel materially different from
 * the generic recommendation feed. Promote a bounded set of recent, material
 * regulatory disclosures into the first page without changing their timestamps
 * or removing any ordinary company events.
 */
export function interleaveHomepageCompanyDisclosureEvents(
  rankedEvents: readonly LiveIntelligenceEvent[],
  firstPageLimit = 24,
): LiveIntelligenceEvent[] {
  const result = [...rankedEvents];
  if (firstPageLimit <= 0 || result.length <= 1) return result;

  const timestamps = result
    .map((event) => Date.parse(event.publishedAt))
    .filter(Number.isFinite);
  const anchor = timestamps.length ? Math.max(...timestamps) : Number.NaN;
  const cutoff = Number.isFinite(anchor)
    ? anchor - COMPANY_DISCLOSURE_PROMOTION_WINDOW_DAYS * 86_400_000
    : Number.NEGATIVE_INFINITY;
  const eligible = (event: LiveIntelligenceEvent) => {
    if (!isOfficialCompanyDisclosureEvent(event)) return false;
    const timestamp = Date.parse(event.publishedAt);
    return !Number.isFinite(timestamp) || timestamp >= cutoff;
  };

  const pageSize = Math.min(firstPageLimit, result.length);
  const eligibleCount = result.filter(eligible).length;
  const target = Math.min(
    COMPANY_FIRST_PAGE_DISCLOSURE_TARGET,
    eligibleCount,
    pageSize,
  );
  const currentCount = result.slice(0, pageSize).filter(eligible).length;
  const needed = Math.max(0, target - currentCount);
  if (!needed) return result;

  const promotions = result.slice(pageSize).filter(eligible).slice(0, needed);
  if (!promotions.length) return result;
  const promotionIds = new Set(promotions.map((event) => event.id));
  const mixed = result.filter((event) => !promotionIds.has(event.id));
  const slots = Array.from({ length: target }, (_, index) =>
    Math.min(
      pageSize - 1,
      Math.max(0, Math.floor(((index + 1) * pageSize) / (target + 1))),
    ),
  );

  let slotCursor = 0;
  for (const promotion of promotions) {
    while (
      slotCursor < slots.length &&
      isOfficialCompanyDisclosureEvent(mixed[slots[slotCursor]] as LiveIntelligenceEvent)
    ) {
      slotCursor += 1;
    }
    const slot = slots[slotCursor] ?? pageSize - 1;
    mixed.splice(Math.min(slot, mixed.length), 0, promotion);
    slotCursor += 1;
  }

  return mixed;
}
