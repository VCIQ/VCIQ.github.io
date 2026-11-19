import {
  companies,
  institutionCatalog,
  type Institution,
} from "./catalog-data";
import type { IntelligenceEvent } from "./intelligence-data";
import {
  institutionDirectory,
  type InstitutionDirectoryEntry,
  type InstitutionRankingCategory,
} from "./institution-ranking-data";
import { getInstitutionProfile } from "./research-content";

export type InstitutionSectorContext = {
  slug: string;
  name: string;
  aliases?: string[];
  keywords?: string[];
  subsectors?: string[];
};

export type InstitutionActivityEvidence =
  | "direct-event"
  | "portfolio-event"
  | "focus"
  | "ranking";

export type InstitutionActivityRelation = {
  institution: InstitutionDirectoryEntry;
  directEvents: IntelligenceEvent[];
  portfolioEvents: IntelligenceEvent[];
  relatedEvents: IntelligenceEvent[];
  evidence: InstitutionActivityEvidence[];
  active: boolean;
  publicActivityScore: number;
  latestActivity?: string;
};

type ExtendedEvent = IntelligenceEvent & {
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
};

type NormalizedEventEvidence = {
  explicitInstitutions: string[];
  searchableText: string;
  companyTerms: string[];
};

type PortfolioIdentity = {
  slugs: Set<string>;
  names: Set<string>;
  sectors: string[];
};

const catalogBySlug = new Map(
  institutionCatalog.map((institution) => [institution.slug, institution]),
);
const companyBySlug = new Map(companies.map((company) => [company.slug, company]));
const identityCache = new Map<string, string[]>();
const portfolioCache = new Map<string, PortfolioIdentity>();

const genericFocusTerms = new Set(
  [
    "科技",
    "产业",
    "投资",
    "资本",
    "企业",
    "创业",
    "数字化",
    "消费",
    "全阶段",
    "全球",
  ].map(normalizeInstitutionTerm),
);

const sectorExpansions: Record<string, string[]> = {
  ai: ["AI", "人工智能", "AGI", "企业科技", "企业软件", "企业服务", "TMT", "智能体", "大模型"],
  aiagi: ["AI", "人工智能", "AGI", "企业科技", "企业软件", "企业服务", "TMT", "智能体", "大模型"],
  robotics: ["机器人", "具身智能", "自动驾驶", "先进制造", "智能制造", "工业", "国防科技", "硬科技"],
  机器人: ["机器人", "具身智能", "自动驾驶", "先进制造", "智能制造", "工业", "国防科技", "硬科技"],
  semiconductor: ["半导体", "芯片", "集成电路", "先进制造", "硬科技"],
  半导体: ["半导体", "芯片", "集成电路", "先进制造", "硬科技"],
  newenergy: ["新能源", "能源", "气候科技", "碳中和", "储能", "电池"],
  新能源: ["新能源", "能源", "气候科技", "碳中和", "储能", "电池"],
  biotech: ["生物科技", "医疗", "医药", "生命科学", "AI制药"],
  生物科技: ["生物科技", "医疗", "医药", "生命科学", "AI制药"],
  quantum: ["量子计算", "量子", "硬科技"],
  量子计算: ["量子计算", "量子", "硬科技"],
  commercialspace: ["商业航天", "航天", "卫星", "国防科技", "硬科技"],
  商业航天: ["商业航天", "航天", "卫星", "国防科技", "硬科技"],
  smartmanufacturing: ["智能制造", "先进制造", "制造", "工业", "硬科技"],
  智能制造: ["智能制造", "先进制造", "制造", "工业", "硬科技"],
};

const investmentTerms = [
  "风险投资",
  "创业投资",
  "私募股权",
  "股权投资",
  "投资机构",
  "创投",
  "venturecapital",
  "privateequity",
  "cvc",
  "国资投资",
  "并购投资",
].map(normalizeInstitutionTerm);

export function normalizeInstitutionTerm(value: string): string {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[\s·•・()（）\[\]【】{}<>《》,，.。:：;；'"“”‘’_\-/\\&+]/gu, "")
    .trim();
}

function entryKey(entry: InstitutionDirectoryEntry): string {
  return entry.profileSlug ?? entry.name;
}

function uniqueEvents(events: IntelligenceEvent[]): IntelligenceEvent[] {
  const result: IntelligenceEvent[] = [];
  const seen = new Set<string>();
  for (const event of events) {
    const key = event.id || event.source.url;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(event);
  }
  return result.sort((left, right) =>
    right.publishedAt.localeCompare(left.publishedAt),
  );
}

function catalogInstitutionFor(
  entry: InstitutionDirectoryEntry,
): Institution | undefined {
  return entry.profileSlug ? catalogBySlug.get(entry.profileSlug) : undefined;
}

function identityTerms(entry: InstitutionDirectoryEntry): string[] {
  const key = entryKey(entry);
  const cached = identityCache.get(key);
  if (cached) return cached;

  const catalog = catalogInstitutionFor(entry);
  const terms = [
    entry.name,
    entry.fullName ?? "",
    catalog?.name ?? "",
    catalog?.englishName ?? "",
  ]
    .map(normalizeInstitutionTerm)
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index);
  identityCache.set(key, terms);
  return terms;
}

function portfolioIdentities(entry: InstitutionDirectoryEntry): PortfolioIdentity {
  const key = entryKey(entry);
  const cached = portfolioCache.get(key);
  if (cached) return cached;

  const catalog = catalogInstitutionFor(entry);
  const identity: PortfolioIdentity = {
    slugs: new Set<string>(),
    names: new Set<string>(),
    sectors: [],
  };
  if (!catalog) {
    portfolioCache.set(key, identity);
    return identity;
  }

  for (const item of getInstitutionProfile(catalog).portfolio) {
    if (item.slug) {
      identity.slugs.add(item.slug);
      const company = companyBySlug.get(item.slug);
      if (company) identity.sectors.push(company.sector);
    }
    const normalizedName = normalizeInstitutionTerm(item.name);
    if (normalizedName) identity.names.add(normalizedName);
  }
  portfolioCache.set(key, identity);
  return identity;
}

function aliasCanAppearInText(alias: string): boolean {
  if (!alias) return false;
  if (/^[a-z0-9]+$/u.test(alias)) return alias.length >= 4;
  return alias.length >= 2;
}

function normalizedEventEvidence(event: ExtendedEvent): NormalizedEventEvidence {
  return {
    explicitInstitutions: (event.institutions ?? [])
      .map(normalizeInstitutionTerm)
      .filter(Boolean),
    searchableText: normalizeInstitutionTerm(
      [
        event.title,
        event.summary,
        event.company,
        ...(event.institutions ?? []),
        ...(event.mentionedCompanies ?? []),
        ...(event.mentionedPeople ?? []),
      ].join(" "),
    ),
    companyTerms: [event.company, ...(event.mentionedCompanies ?? [])]
      .map(normalizeInstitutionTerm)
      .filter(Boolean),
  };
}

function directEventMatches(
  entry: InstitutionDirectoryEntry,
  evidence: NormalizedEventEvidence,
): boolean {
  const aliases = identityTerms(entry);
  if (
    aliases.some((alias) =>
      evidence.explicitInstitutions.some(
        (value) => value === alias || value.includes(alias) || alias.includes(value),
      ),
    )
  ) {
    return true;
  }

  return aliases.some(
    (alias) => aliasCanAppearInText(alias) && evidence.searchableText.includes(alias),
  );
}

function portfolioEventMatches(
  entry: InstitutionDirectoryEntry,
  event: ExtendedEvent,
  evidence: NormalizedEventEvidence,
): boolean {
  const portfolio = portfolioIdentities(entry);
  if (event.companySlug && portfolio.slugs.has(event.companySlug)) return true;
  return evidence.companyTerms.some((company) => portfolio.names.has(company));
}

function meaningfulTerms(values: string[]): string[] {
  return values
    .map(normalizeInstitutionTerm)
    .filter(Boolean)
    .filter((value) => !genericFocusTerms.has(value))
    .filter((value, index, all) => all.indexOf(value) === index);
}

function sectorTerms(sector: InstitutionSectorContext): string[] {
  const identity = [
    sector.slug,
    sector.name,
    ...(sector.aliases ?? []),
    ...(sector.keywords ?? []),
    ...(sector.subsectors ?? []),
  ];
  const expansionKeys = [sector.slug, sector.name].map(normalizeInstitutionTerm);
  const expansions = expansionKeys.flatMap((key) => sectorExpansions[key] ?? []);
  return meaningfulTerms([...identity, ...expansions]);
}

function termsOverlap(left: string[], right: string[]): boolean {
  return left.some((leftTerm) =>
    right.some((rightTerm) => {
      if (leftTerm === rightTerm) return true;
      if (leftTerm.length < 3 || rightTerm.length < 3) return false;
      return leftTerm.includes(rightTerm) || rightTerm.includes(leftTerm);
    }),
  );
}

function focusMatches(
  entry: InstitutionDirectoryEntry,
  sector: InstitutionSectorContext,
): boolean {
  const catalog = catalogInstitutionFor(entry);
  if (!catalog) return false;
  const portfolio = portfolioIdentities(entry);
  const institutionTerms = meaningfulTerms([
    ...catalog.sectors,
    ...entry.sectors,
    ...portfolio.sectors,
  ]);
  return termsOverlap(institutionTerms, sectorTerms(sector));
}

function sectorIdentity(sector: InstitutionSectorContext): string {
  return normalizeInstitutionTerm(
    [sector.slug, sector.name, ...(sector.aliases ?? []), ...(sector.keywords ?? [])].join(" "),
  );
}

function isInvestmentTrack(sector: InstitutionSectorContext): boolean {
  const combined = sectorIdentity(sector);
  return investmentTerms.some((term) => combined.includes(term));
}

function requestedRankingCategories(
  sector: InstitutionSectorContext,
): InstitutionRankingCategory[] {
  const combined = sectorIdentity(sector);
  const selected: InstitutionRankingCategory[] = [];
  if (combined.includes(normalizeInstitutionTerm("早期投资"))) selected.push("早期投资");
  if (
    combined.includes(normalizeInstitutionTerm("创业投资")) ||
    combined.includes(normalizeInstitutionTerm("风险投资")) ||
    combined.includes("venturecapital") ||
    combined.includes("创投")
  ) {
    selected.push("早期投资", "创业投资");
  }
  if (
    combined.includes(normalizeInstitutionTerm("私募股权")) ||
    combined.includes("privateequity")
  ) {
    selected.push("私募股权");
  }
  if (combined.includes(normalizeInstitutionTerm("国资投资"))) selected.push("国资投资");
  if (combined.includes("cvc") || combined.includes(normalizeInstitutionTerm("战略投资"))) {
    selected.push("战略投资者/CVC");
  }
  if (combined.includes(normalizeInstitutionTerm("并购投资"))) selected.push("并购投资");
  return [...new Set(selected)];
}

function rankingMatches(
  entry: InstitutionDirectoryEntry,
  sector: InstitutionSectorContext,
): boolean {
  if (!isInvestmentTrack(sector)) return false;
  const requested = requestedRankingCategories(sector);
  if (!requested.length) return Boolean(entry.rankings.length || entry.profileSlug);
  return entry.rankings.some((ranking) => requested.includes(ranking.category));
}

function scoreRelation(
  directEvents: IntelligenceEvent[],
  portfolioEvents: IntelligenceEvent[],
  ranking: boolean,
): number {
  const directScore = directEvents.reduce(
    (total, event) => total + 4 + Math.max(1, Math.round(event.importance / 20)),
    0,
  );
  const portfolioScore = portfolioEvents.reduce(
    (total, event) => total + 1 + Math.max(0, Math.round(event.importance / 40)),
    0,
  );
  return directScore + portfolioScore + (ranking ? 3 : 0);
}

function buildRelation(
  entry: InstitutionDirectoryEntry,
  events: IntelligenceEvent[],
  evidenceByEvent: Map<IntelligenceEvent, NormalizedEventEvidence>,
  sector?: InstitutionSectorContext,
): InstitutionActivityRelation | null {
  const directEvents = uniqueEvents(
    events.filter((event) => directEventMatches(entry, evidenceByEvent.get(event)!)),
  );
  const directIds = new Set(directEvents.map((event) => event.id));
  const portfolioEvents = uniqueEvents(
    events
      .filter((event) => portfolioEventMatches(entry, event as ExtendedEvent, evidenceByEvent.get(event)!))
      .filter((event) => !directIds.has(event.id)),
  );
  const relatedEvents = uniqueEvents([...directEvents, ...portfolioEvents]);
  const focus = sector ? focusMatches(entry, sector) : false;
  const ranking = sector ? rankingMatches(entry, sector) : false;
  const evidence: InstitutionActivityEvidence[] = [];
  if (directEvents.length) evidence.push("direct-event");
  if (portfolioEvents.length) evidence.push("portfolio-event");
  if (focus) evidence.push("focus");
  if (ranking) evidence.push("ranking");
  if (!evidence.length) return null;

  return {
    institution: entry,
    directEvents,
    portfolioEvents,
    relatedEvents,
    evidence,
    active: directEvents.length > 0 || ranking,
    publicActivityScore: scoreRelation(directEvents, portfolioEvents, ranking),
    latestActivity: relatedEvents[0]?.publishedAt,
  };
}

function sortRelations(
  left: InstitutionActivityRelation,
  right: InstitutionActivityRelation,
): number {
  return (
    Number(right.active) - Number(left.active) ||
    right.publicActivityScore - left.publicActivityScore ||
    right.directEvents.length - left.directEvents.length ||
    right.relatedEvents.length - left.relatedEvents.length ||
    (right.latestActivity ?? "").localeCompare(left.latestActivity ?? "") ||
    right.institution.rankings.length - left.institution.rankings.length ||
    left.institution.name.localeCompare(right.institution.name, "zh-CN")
  );
}

export function getSectorInstitutionRelations(
  sector: InstitutionSectorContext,
  events: IntelligenceEvent[],
): InstitutionActivityRelation[] {
  // Normalize each event once per query, not once per institution × event.
  const evidenceByEvent = new Map(
    events.map((event) => [event, normalizedEventEvidence(event as ExtendedEvent)]),
  );
  return institutionDirectory
    .map((entry) => buildRelation(entry, events, evidenceByEvent, sector))
    .filter((relation): relation is InstitutionActivityRelation => Boolean(relation))
    .sort(sortRelations);
}

export function getArticleInstitutionRelations(
  events: IntelligenceEvent[],
): InstitutionActivityRelation[] {
  const evidenceByEvent = new Map(
    events.map((event) => [event, normalizedEventEvidence(event as ExtendedEvent)]),
  );
  return institutionDirectory
    .map((entry) => buildRelation(entry, events, evidenceByEvent))
    .filter((relation): relation is InstitutionActivityRelation => Boolean(relation))
    .sort(sortRelations);
}

export function institutionDirectoryHref(
  entry: InstitutionDirectoryEntry,
): string {
  return entry.profileSlug
    ? `/institutions/${entry.profileSlug}`
    : `/institutions?institution=${encodeURIComponent(entry.name)}`;
}

export function institutionEvidenceLabels(
  relation: InstitutionActivityRelation,
): string[] {
  const labels: string[] = [];
  if (relation.directEvents.length) labels.push(`${relation.directEvents.length} 条直接事件`);
  if (relation.portfolioEvents.length) labels.push(`${relation.portfolioEvents.length} 条组合关联`);
  if (relation.evidence.includes("focus")) labels.push("方向匹配");
  if (relation.evidence.includes("ranking")) labels.push("榜单激活");
  return labels;
}
