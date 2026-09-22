import companyRegistry from "@/config/company_registry.json";
import trackingSeeds from "@/config/innovation_capital_tracking_seeds.json";
import listingWatchlist from "@/config/innovation_listing_watchlist.json";
import ventureProfiles from "@/public/data/venture_profiles.json";

type JsonRecord = Record<string, unknown>;

export type InnovationOpportunity = {
  slug: string;
  name: string;
  sector: string;
  stage: string;
  headquarters: string;
  policyThemes: string[];
  latestRound: string;
  latestDate: string;
  lateStageRounds: string[];
  institutionBackers: string[];
  evidenceScore: number;
  readinessScore: number;
  readinessBand: "重点复核" | "持续跟踪" | "资料补全";
  sourceUrl: string;
  signals: string[];
  gaps: string[];
};

const policySectorTags: Record<string, string[]> = {
  "AI / AGI": ["人工智能", "新一代信息技术"],
  "半导体": ["集成电路", "新一代信息技术"],
  "机器人": ["智能机器人", "具身智能"],
  "商业航天": ["航空航天"],
  "新能源": ["新型储能"],
  "新材料": ["新材料"],
  "生物科技": ["生物医药", "生物制造"],
  "智能制造": ["高端装备"],
};

const nonIndependentCompanySlugs = new Set(["doubao", "volcengine"]);

const lateStageRound = /(?:Series\s*[DEFG]|(?:^|[^A-Za-z])[DEFG](?:\+{0,2})?(?:轮|\b)|D轮|D\+轮|D\+\+轮|E轮|E\+轮|E\+\+轮|Pre[- ]?IPO|Growth|战略融资)/iu;

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function rows(value: unknown): JsonRecord[] {
  if (Array.isArray(value)) return value.map(record);
  const row = record(value);
  return Object.values(row).map(record);
}

function text(value: unknown, limit = 800): string {
  return typeof value === "string"
    ? value.trim().replace(/\s+/gu, " ").slice(0, limit)
    : "";
}

function normalize(value: unknown): string {
  return text(value, 400)
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function companyKeys(value: unknown): string[] {
  const raw = text(value, 180);
  if (!raw) return [];
  const keys = new Set([normalize(raw)]);
  const simplified = raw
    .replace(/(?:股份)?有限公司$|有限责任公司$|集团$|控股$|科技$|技术$|创新$/u, "")
    .replace(/\b(?:inc|corp|corporation|company|co|ltd|limited|holdings?)\.?$/iu, "")
    .trim();
  if (simplified) keys.add(normalize(simplified));
  return [...keys].filter(Boolean);
}

function seedInstitutionAliasIndex(): Map<string, string> {
  const index = new Map<string, string>();
  for (const raw of trackingSeeds.institutions) {
    const row = record(raw);
    const name = text(row.name, 160);
    for (const alias of [name, ...list(row.aliases).map((value) => text(value, 160))]) {
      for (const key of companyKeys(alias)) index.set(key, name);
    }
  }
  return index;
}

function canonicalInstitution(value: unknown, index: Map<string, string>): string {
  for (const key of companyKeys(value)) {
    const canonical = index.get(key);
    if (canonical) return canonical;
  }
  return text(value, 160);
}

function companyProfileIndex(): Map<string, JsonRecord> {
  const index = new Map<string, JsonRecord>();
  for (const row of rows(record(ventureProfiles).companies)) {
    const slug = text(row.slug, 160);
    if (slug) index.set(slug, row);
  }
  return index;
}

function institutionPortfolioLinks(): Map<string, Set<string>> {
  const aliasIndex = seedInstitutionAliasIndex();
  const result = new Map<string, Set<string>>();
  for (const institution of rows(record(ventureProfiles).institutions)) {
    const rawName = text(institution.name, 160);
    const canonical = canonicalInstitution(rawName, aliasIndex);
    const isSeed = companyKeys(rawName).some((key) => aliasIndex.has(key));
    if (!isSeed || !canonical) continue;
    for (const investment of [
      ...rows(institution.portfolio),
      ...rows(institution.recentInvestments),
    ]) {
      const slug = text(investment.companySlug, 160);
      if (!slug) continue;
      const names = result.get(slug) ?? new Set<string>();
      names.add(canonical);
      result.set(slug, names);
    }
  }
  return result;
}

function roundValues(profile: JsonRecord): string[] {
  const values: string[] = [];
  const capital = record(profile.capitalSummary);
  for (const raw of list(capital.rounds)) {
    const value = text(raw, 80);
    if (value && !values.includes(value)) values.push(value);
  }
  for (const financing of rows(profile.financing)) {
    const value = text(financing.round, 80);
    if (value && !values.includes(value)) values.push(value);
  }
  return values;
}

function reviewedCompanyKeys(): Set<string> {
  const result = new Set<string>();
  for (const project of listingWatchlist.projects) {
    for (const key of companyKeys(project.company)) result.add(key);
  }
  return result;
}

function evidenceScore(profile: JsonRecord): number {
  const value = profile.evidenceScore;
  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(0, Math.min(100, Math.round(value)))
    : 0;
}

export function buildInnovationOpportunityPool(): InnovationOpportunity[] {
  const profiles = companyProfileIndex();
  const portfolioLinks = institutionPortfolioLinks();
  const reviewed = reviewedCompanyKeys();
  const result: InnovationOpportunity[] = [];

  for (const company of rows(record(companyRegistry).companies)) {
    const slug = text(company.slug, 160);
    const name = text(company.name, 160);
    const region = text(company.region, 40);
    const sector = text(company.sector, 80);
    const stage = text(company.stage, 80);
    const status = text(company.status, 80);
    if (!slug || !name || !["中国", "中國", "香港"].includes(region)) continue;
    if (status === "已上市" || stage === "已上市" || nonIndependentCompanySlugs.has(slug)) continue;
    const identityKeys = new Set([
      ...companyKeys(name),
      ...companyKeys(company.englishName),
      ...list(company.aliases).flatMap((alias) => companyKeys(alias)),
    ]);
    const overlapsReviewed = [...identityKeys].some((key) =>
      reviewed.has(key)
      || (
        key.length >= 5
        && [...reviewed].some((reviewedKey) =>
          reviewedKey.length >= 5
          && (key.includes(reviewedKey) || reviewedKey.includes(key)))
      ));
    if (overlapsReviewed) continue;

    const policyThemes = policySectorTags[sector] ?? [];
    if (!policyThemes.length) continue;

    const profile = profiles.get(slug) ?? {};
    const capital = record(profile.capitalSummary);
    const rounds = roundValues(profile);
    const lateStageRounds = rounds.filter((value) => lateStageRound.test(value));
    const institutionBackers = [...(portfolioLinks.get(slug) ?? new Set<string>())]
      .sort((left, right) => left.localeCompare(right, "zh-CN"));
    const scoreEvidence = evidenceScore(profile);
    const source = record(company.source);
    const sourceLevel = text(source.level, 80);
    const sourceUrl = text(source.url, 1200);
    const capitalMarkets = rows(profile.capitalMarkets);

    let readinessScore = 0;
    const signals: string[] = [];
    const gaps: string[] = [];

    if (lateStageRounds.length) {
      readinessScore += 35;
      signals.push("已识别 D/E/Pre-IPO/Growth 等成熟期融资信号");
    } else {
      gaps.push("尚缺 D/E/Pre-IPO 等成熟期融资轮次的可核对证据");
    }
    if (institutionBackers.length) {
      readinessScore += 18;
      signals.push("命中已纳管硬科技投资机构的公开投资组合");
    } else {
      gaps.push("当前机构目录尚未形成可核对的投资组合连接");
    }
    if (scoreEvidence >= 80) readinessScore += 15;
    else if (scoreEvidence >= 60) readinessScore += 10;
    else if (scoreEvidence >= 40) readinessScore += 5;

    if (["官方披露", "监管文件", "交易所公告"].includes(sourceLevel)) {
      readinessScore += 12;
      signals.push("公司身份和主营方向具备一级公开来源");
    } else {
      gaps.push("公司一级来源仍需补强");
    }
    if (stage === "成长期") readinessScore += 8;
    if (capitalMarkets.length) {
      readinessScore += 12;
      signals.push("已有资本市场公开事件");
    }

    readinessScore = Math.min(100, readinessScore);
    const readinessBand: InnovationOpportunity["readinessBand"] =
      readinessScore >= 65 ? "重点复核"
        : readinessScore >= 40 ? "持续跟踪"
          : "资料补全";

    result.push({
      slug,
      name,
      sector,
      stage,
      headquarters: text(company.headquarters, 120),
      policyThemes,
      latestRound: text(capital.latestRound, 80),
      latestDate: text(capital.latestDate, 40),
      lateStageRounds,
      institutionBackers,
      evidenceScore: scoreEvidence,
      readinessScore,
      readinessBand,
      sourceUrl,
      signals,
      gaps,
    });
  }

  return result.sort((left, right) =>
    Number(right.lateStageRounds.length > 0) - Number(left.lateStageRounds.length > 0)
    || Number(right.institutionBackers.length > 0) - Number(left.institutionBackers.length > 0)
    || right.readinessScore - left.readinessScore
    || left.name.localeCompare(right.name, "zh-CN"));
}
