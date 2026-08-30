import rawVentureProfiles from "@/public/data/venture_profiles.json";

export type VentureSource = {
  name: string;
  url: string;
  level: "官方披露" | "原始材料" | "监管文件" | "媒体报道" | "数据库记录" | "待交叉验证";
  section?: string;
  title?: string;
  publishedAt?: string;
};

export type VentureTeamMember = {
  name: string;
  role?: string;
  summary?: string;
  background?: string;
  previousExperience?: string;
  sourceUrl?: string;
};

export type VentureCapitalEvent = {
  date?: string;
  type: string;
  title: string;
  summary: string;
  amount?: string;
  round?: string;
  investors?: string[];
  sourceUrl?: string;
};

export type VenturePortfolioCase = {
  name: string;
  companySlug?: string;
  date?: string;
  round?: string;
  summary: string;
  sourceUrl?: string;
};

export type VentureClassicCase = {
  name: string;
  companySlug?: string;
  investmentLogic?: string;
  followOnPerformance?: string;
  exitPerformance?: string;
  analysis: string;
  sourceUrl?: string;
};

export type VentureProjectBackground = {
  summary: string;
  problemSolved?: string;
  marketOpportunity?: string;
};

export type VentureTechnologyProduct = {
  name: string;
  category?: string;
  description: string;
  technicalHighlights?: string[];
  sourceUrl?: string;
};

export type VentureCapitalSummary = {
  eventCount: number;
  disclosedAmounts: string[];
  rounds: string[];
  majorInvestors: string[];
  latestDate?: string;
  latestRound?: string;
  summary: string;
};

export type VentureExitPerformance = {
  status: string;
  latestDate?: string;
  latestEvent?: string;
  summary: string;
  sourceUrl?: string;
};

export type VentureRecentYearSummary = {
  periodStart: string;
  periodEnd: string;
  investmentCount: number;
  companies: string[];
  sectors: string[];
  rounds: string[];
  summary: string;
};

export type CompanyVentureProfile = {
  slug: string;
  name: string;
  updatedAt: string;
  status: "ok" | "partial" | "retained" | "fallback";
  background: string;
  projectBackground?: VentureProjectBackground;
  technology: string;
  researchTechnology?: string;
  products: string[];
  technologyProducts?: VentureTechnologyProduct[];
  team: VentureTeamMember[];
  financing: VentureCapitalEvent[];
  capitalSummary?: VentureCapitalSummary;
  capitalMarkets: VentureCapitalEvent[];
  exitPerformance?: VentureExitPerformance;
  researchModelVersion?: number;
  sources: VentureSource[];
  warnings?: string[];
  evidenceScore?: number;
};

export type InstitutionVentureProfile = {
  slug: string;
  name: string;
  updatedAt: string;
  status: "ok" | "partial" | "retained" | "fallback";
  overview: string;
  strategy: string;
  team: VentureTeamMember[];
  recentInvestments: VenturePortfolioCase[];
  recentYearSummary?: VentureRecentYearSummary;
  portfolio: VenturePortfolioCase[];
  classicCases: VentureClassicCase[];
  researchModelVersion?: number;
  sources: VentureSource[];
  warnings?: string[];
  evidenceScore?: number;
};

type VentureProfileSnapshot = {
  schemaVersion: number;
  researchModelVersion?: number;
  generatedAt: string;
  companies?: Record<string, CompanyVentureProfile>;
  institutions?: Record<string, InstitutionVentureProfile>;
  sourceStatus?: {
    kind: "company" | "institution";
    slug: string;
    name: string;
    status: string;
    fetchedPages: number;
    acceptedSections: number;
    retainedPrevious?: boolean;
    error?: string;
  }[];
  qualityGate?: {
    passed: boolean;
    checks: Record<string, { actual: number; required: number; passed: boolean }>;
  };
};

const VALID_SOURCE_LEVELS = new Set([
  "官方披露",
  "原始材料",
  "监管文件",
  "媒体报道",
  "数据库记录",
  "待交叉验证",
]);

const NAVIGATION_TERMS = [
  "products",
  "solutions",
  "research",
  "policy",
  "commitments",
  "learn",
  "news",
  "insights",
  "investments",
  "projects",
  "careers",
  "contact",
  "portfolio",
  "companies",
  "产品资料与下载",
  "产品资料",
  "数据服务",
  "解决方案",
  "新闻资讯",
  "加入我们",
  "联系我们",
  "投资组合",
  "被投企业",
  "投资项目",
] as const;

const PRODUCT_NOISE_TERMS = [
  "terms of service",
  "data processing agreement",
  "privacy policy",
  "cookie policy",
  "responsible scaling policy",
  "press release",
  "white paper",
  "case study",
  "introducing ",
  "announcing ",
  "k-12",
  "careers",
  "jobs",
  "manual",
  "documentation",
  "download",
  "support",
  "产品手册",
  "产品资料",
  "资料下载",
  "售后",
  "用户协议",
  "服务条款",
  "隐私政策",
  "数据处理协议",
  "白皮书",
  "大赛",
  "赛事",
  "峰会",
  "论坛",
  "发布会",
  "展会",
  "新闻",
  "资讯",
  "招聘",
] as const;

const PERSON_NAME_NOISE = [
  "关于",
  "新闻",
  "资讯",
  "生产力",
  "营销",
  "联席",
  "产品",
  "技术",
  "公司",
  "集团",
  "智能",
  "解决方案",
  "业务",
  "研发",
  "服务",
  "平台",
  "团队",
  "联系",
  "加入",
  "招聘",
  "官网",
  "中心",
  "部门",
  "事业部",
  "办公室",
  "委员会",
  "研究院",
  "高级",
  "副总",
  "总裁",
  "经理",
  "总监",
  "主管",
  "首席",
  "负责人",
  "董事会",
] as const;

const FINANCING_ACTION_RE = /\b(?:rais(?:e|ed|es|ing)|funding round|financing round|series\s+[a-z0-9]+|seed round|pre-seed|backed by|led by|investment from|invested in|secured)\b|(?:完成|获得|宣布|获).{0,28}(?:融资|投资)|(?:融资|募资|领投|跟投|战略投资|估值)/iu;
const CAPITAL_ACTION_RE = /\b(?:ipo|listed|listing|went public|acquired|acquisition|merger|nasdaq|nyse|hkex|stock exchange)\b|(?:上市|挂牌|并购|收购|退出|退市|交易所|公开市场)/iu;
const DATE_LIKE_RE = /\b20\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b/iu;

function clean(value: unknown, limit = 600) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function compact(value: unknown) {
  return clean(value, 1000).toLocaleLowerCase("zh-CN").replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function cleanList(values: unknown, limit = 20, itemLimit = 220) {
  if (!Array.isArray(values)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const item = clean(value, itemLimit);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function validUrl(value: unknown) {
  const text = clean(value, 1000);
  return /^https?:\/\//iu.test(text) ? text : "";
}

function looksLikeNavigation(text: string) {
  const lowered = text.toLocaleLowerCase("zh-CN");
  const hits = NAVIGATION_TERMS.filter((term) => lowered.includes(term.toLocaleLowerCase("zh-CN")));
  if (/all rights reserved|cookie settings|版权所有|备案号/iu.test(text)) return true;
  if (hits.length >= 4) return true;
  if ((text.includes("\\") || text.includes("|") || text.includes("｜")) && hits.length >= 2) {
    return true;
  }
  return text.length >= 220 && hits.length >= 3;
}

export function sanitizeVentureNarrative(value: unknown, limit = 900) {
  const text = clean(value, 5000);
  if (!text) return "";
  const clauses = text
    .split(/[。！？!?；;\n]+|(?<=\.)\s+(?=[A-Z\u3400-\u9fff])/u)
    .map((item) => clean(item, 700).replace(/^[ .。|｜\\-]+|[ .。|｜\\-]+$/gu, ""))
    .filter((item) => item.length >= 18 && !looksLikeNavigation(item));
  const selected: string[] = [];
  const seen: string[] = [];
  let total = 0;
  for (const clause of clauses) {
    const key = compact(clause);
    if (!key) continue;
    if (
      seen.some(
        (previous) =>
          previous === key ||
          (previous.length >= 40 && key.length >= 40 && (previous.includes(key) || key.includes(previous))),
      )
    ) {
      continue;
    }
    if (total + clause.length > limit && selected.length) continue;
    selected.push(clause);
    seen.push(key);
    total += clause.length;
    if (selected.length >= 4 || total >= limit) break;
  }
  if (!selected.length) return "";
  const cjkCount = selected.join("").match(/[\u3400-\u9fff]/gu)?.length ?? 0;
  const joined = cjkCount / Math.max(1, selected.join("").length) >= 0.18
    ? `${selected.map((item) => item.replace(/。$/u, "")).join("。")}。`
    : `${selected.map((item) => item.replace(/\.$/u, "")).join(". ")}.`;
  return clean(joined, limit);
}

export function sanitizeVentureProducts(values: unknown) {
  return cleanList(values, 30, 240).filter((item) => {
    const lowered = item.toLocaleLowerCase("zh-CN");
    if (item.includes("|") || item.includes("｜")) return false;
    if (PRODUCT_NOISE_TERMS.some((term) => lowered.includes(term.toLocaleLowerCase("zh-CN")))) {
      return false;
    }
    if (DATE_LIKE_RE.test(item) && /introducing|announcing|新闻|资讯|发布/iu.test(item)) {
      return false;
    }
    return true;
  }).slice(0, 16);
}

function matchesEntityAlias(name: string, aliases: string[]) {
  const nameKey = compact(name);
  if (nameKey.length < 2) return false;
  return aliases.some((alias) => {
    const aliasKey = compact(alias);
    return aliasKey.length >= 2 && (aliasKey.includes(nameKey) || nameKey.includes(aliasKey));
  });
}

function validPersonName(name: string) {
  if (!name || name.length < 2 || name.length > 80 || /\d|https?:\/\/|@/u.test(name)) return false;
  if (PERSON_NAME_NOISE.some((term) => name.includes(term))) return false;
  if (/^[\u3400-\u9fff·]{2,6}$/u.test(name)) return true;
  return /^[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){1,3}$/u.test(name);
}

function safeHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function normalizeSources(values: unknown): VentureSource[] {
  if (!Array.isArray(values)) return [];
  const result: VentureSource[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const url = validUrl(row.url);
    if (!url || seen.has(url)) continue;
    const level = clean(row.level, 20);
    result.push({
      name: clean(row.name, 120) || safeHostname(url) || url,
      url,
      level: VALID_SOURCE_LEVELS.has(level)
        ? (level as VentureSource["level"])
        : "官方披露",
      section: clean(row.section, 60) || undefined,
      title: clean(row.title, 200) || undefined,
      publishedAt: clean(row.publishedAt, 20) || undefined,
    });
    seen.add(url);
    if (result.length >= 30) break;
  }
  return result;
}

function normalizeTeam(values: unknown, aliases: string[] = []): VentureTeamMember[] {
  if (!Array.isArray(values)) return [];
  const result: VentureTeamMember[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 100).replace(/^[ ,，:：;；|｜-]+|[ ,，:：;；|｜-]+$/gu, "");
    const key = name.toLocaleLowerCase("zh-CN");
    if (!validPersonName(name) || matchesEntityAlias(name, aliases) || seen.has(key)) continue;
    result.push({
      name,
      role: clean(row.role, 120) || undefined,
      summary: clean(row.summary, 360) || undefined,
      background: clean(row.background, 360) || undefined,
      previousExperience: clean(row.previousExperience, 360) || undefined,
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(key);
    if (result.length >= 20) break;
  }
  return result;
}

function normalizeCapitalEvents(values: unknown, capitalMarket = false): VentureCapitalEvent[] {
  if (!Array.isArray(values)) return [];
  const result: VentureCapitalEvent[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const title = clean(row.title, 220);
    const summary = clean(row.summary, 520);
    const amount = clean(row.amount, 80);
    const round = clean(row.round, 80);
    const sourceUrl = validUrl(row.sourceUrl);
    const evidence = `${title} ${summary}`;
    if (!title && !summary) continue;
    if (!sourceUrl) continue;
    if (capitalMarket ? !CAPITAL_ACTION_RE.test(evidence) : !(amount || round || FINANCING_ACTION_RE.test(evidence))) {
      continue;
    }
    const key = `${clean(row.date, 20)}|${title}|${summary}`.toLocaleLowerCase("zh-CN");
    if (seen.has(key)) continue;
    result.push({
      date: clean(row.date, 20) || undefined,
      type: clean(row.type, 60) || (capitalMarket ? "资本市场" : "融资"),
      title: title || summary.slice(0, 80),
      summary: summary || title,
      amount: amount || undefined,
      round: round || undefined,
      investors: cleanList(row.investors, 12, 100),
      sourceUrl,
    });
    seen.add(key);
    if (result.length >= 20) break;
  }
  return result;
}

function normalizePortfolio(values: unknown): VenturePortfolioCase[] {
  if (!Array.isArray(values)) return [];
  const result: VenturePortfolioCase[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 120);
    const date = clean(row.date, 20);
    const key = `${name.toLocaleLowerCase("zh-CN")}|${date}`;
    if (!name || seen.has(key)) continue;
    result.push({
      name,
      companySlug: clean(row.companySlug, 100) || undefined,
      date: date || undefined,
      round: clean(row.round, 80) || undefined,
      summary: clean(row.summary, 420) || "公开组合记录。",
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(key);
    if (result.length >= 40) break;
  }
  return result;
}

function normalizeClassicCases(values: unknown): VentureClassicCase[] {
  if (!Array.isArray(values)) return [];
  const result: VentureClassicCase[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 120);
    const analysis = clean(row.analysis, 760);
    if (!name || !analysis || seen.has(name.toLocaleLowerCase("zh-CN"))) continue;
    result.push({
      name,
      companySlug: clean(row.companySlug, 100) || undefined,
      investmentLogic: clean(row.investmentLogic, 520) || undefined,
      followOnPerformance: clean(row.followOnPerformance, 520) || undefined,
      exitPerformance: clean(row.exitPerformance, 520) || undefined,
      analysis,
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(name.toLocaleLowerCase("zh-CN"));
    if (result.length >= 8) break;
  }
  return result;
}

function normalizeProjectBackground(value: unknown): VentureProjectBackground | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const summary = sanitizeVentureNarrative(row.summary, 900);
  if (!summary) return undefined;
  return {
    summary,
    problemSolved: sanitizeVentureNarrative(row.problemSolved, 520) || undefined,
    marketOpportunity: sanitizeVentureNarrative(row.marketOpportunity, 520) || undefined,
  };
}

function normalizeTechnologyProducts(values: unknown): VentureTechnologyProduct[] {
  if (!Array.isArray(values)) return [];
  const result: VentureTechnologyProduct[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const name = clean(row.name, 160);
    const description = clean(row.description, 520);
    const key = name.toLocaleLowerCase("zh-CN");
    if (!name || !description || seen.has(key)) continue;
    result.push({
      name,
      category: clean(row.category, 80) || undefined,
      description,
      technicalHighlights: cleanList(row.technicalHighlights, 6, 260),
      sourceUrl: validUrl(row.sourceUrl) || undefined,
    });
    seen.add(key);
    if (result.length >= 12) break;
  }
  return result;
}

function normalizeCapitalSummary(value: unknown): VentureCapitalSummary | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  return {
    eventCount: Math.max(0, Number(row.eventCount) || 0),
    disclosedAmounts: cleanList(row.disclosedAmounts, 12, 80),
    rounds: cleanList(row.rounds, 12, 80),
    majorInvestors: cleanList(row.majorInvestors, 20, 120),
    latestDate: clean(row.latestDate, 20) || undefined,
    latestRound: clean(row.latestRound, 80) || undefined,
    summary: clean(row.summary, 520) || "当前未识别到可核对的融资汇总。",
  };
}

function normalizeExitPerformance(value: unknown): VentureExitPerformance | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const status = clean(row.status, 100);
  const summary = clean(row.summary, 520);
  if (!status && !summary) return undefined;
  return {
    status: status || "暂无公开退出信息",
    latestDate: clean(row.latestDate, 20) || undefined,
    latestEvent: clean(row.latestEvent, 220) || undefined,
    summary: summary || "当前未识别到可核对的上市、并购或退出记录。",
    sourceUrl: validUrl(row.sourceUrl) || undefined,
  };
}

function normalizeRecentYearSummary(value: unknown): VentureRecentYearSummary | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const periodStart = clean(row.periodStart, 20);
  const periodEnd = clean(row.periodEnd, 20);
  if (!periodStart || !periodEnd) return undefined;
  return {
    periodStart,
    periodEnd,
    investmentCount: Math.max(0, Number(row.investmentCount) || 0),
    companies: cleanList(row.companies, 30, 120),
    sectors: cleanList(row.sectors, 12, 100),
    rounds: cleanList(row.rounds, 12, 80),
    summary: clean(row.summary, 520) || "最近一年暂无可核对投资记录。",
  };
}

function normalizeCompanyProfile(raw: CompanyVentureProfile): CompanyVentureProfile {
  const fallbackBackground = sanitizeVentureNarrative(raw.background, 900);
  const projectBackground =
    normalizeProjectBackground(raw.projectBackground) ??
    (Number(raw.researchModelVersion) >= 2
      ? {
          summary:
            fallbackBackground ||
            "当前公开来源未提供可核对的项目背景说明。",
        }
      : undefined);
  return {
    slug: clean(raw.slug, 100),
    name: clean(raw.name, 120),
    updatedAt: clean(raw.updatedAt, 40),
    status: raw.status || "fallback",
    background: fallbackBackground,
    projectBackground,
    technology: sanitizeVentureNarrative(raw.technology, 900),
    researchTechnology: sanitizeVentureNarrative(raw.researchTechnology, 900) || undefined,
    products: sanitizeVentureProducts(raw.products),
    technologyProducts: normalizeTechnologyProducts(raw.technologyProducts),
    team: normalizeTeam(raw.team, [raw.name, raw.slug]),
    financing: normalizeCapitalEvents(raw.financing),
    capitalSummary: normalizeCapitalSummary(raw.capitalSummary),
    capitalMarkets: normalizeCapitalEvents(raw.capitalMarkets, true),
    exitPerformance: normalizeExitPerformance(raw.exitPerformance),
    researchModelVersion: Number(raw.researchModelVersion) || undefined,
    sources: normalizeSources(raw.sources),
    warnings: cleanList(raw.warnings, 12, 220),
    evidenceScore: Number.isFinite(Number(raw.evidenceScore))
      ? Number(raw.evidenceScore)
      : undefined,
  };
}

function normalizeInstitutionProfile(raw: InstitutionVentureProfile): InstitutionVentureProfile {
  return {
    slug: clean(raw.slug, 100),
    name: clean(raw.name, 120),
    updatedAt: clean(raw.updatedAt, 40),
    status: raw.status || "fallback",
    overview: sanitizeVentureNarrative(raw.overview, 900),
    strategy: sanitizeVentureNarrative(raw.strategy, 900),
    team: normalizeTeam(raw.team, [raw.name, raw.slug]),
    recentInvestments: normalizePortfolio(raw.recentInvestments),
    recentYearSummary: normalizeRecentYearSummary(raw.recentYearSummary),
    portfolio: normalizePortfolio(raw.portfolio),
    classicCases: normalizeClassicCases(raw.classicCases),
    researchModelVersion: Number(raw.researchModelVersion) || undefined,
    sources: normalizeSources(raw.sources),
    warnings: cleanList(raw.warnings, 12, 220),
    evidenceScore: Number.isFinite(Number(raw.evidenceScore))
      ? Number(raw.evidenceScore)
      : undefined,
  };
}

const snapshot = rawVentureProfiles as VentureProfileSnapshot;

export const ventureProfileGeneratedAt = clean(snapshot.generatedAt, 40);
export const ventureResearchModelVersion = Number(snapshot.researchModelVersion) || 1;
export const companyVentureProfiles = Object.fromEntries(
  Object.entries(snapshot.companies ?? {}).map(([slug, profile]) => [
    slug,
    normalizeCompanyProfile(profile),
  ]),
) as Record<string, CompanyVentureProfile>;
export const institutionVentureProfiles = Object.fromEntries(
  Object.entries(snapshot.institutions ?? {}).map(([slug, profile]) => [
    slug,
    normalizeInstitutionProfile(profile),
  ]),
) as Record<string, InstitutionVentureProfile>;
export const ventureProfileSourceStatus = snapshot.sourceStatus ?? [];
export const ventureProfileQualityGate = snapshot.qualityGate;

export function getCompanyVentureProfile(slug: string) {
  return companyVentureProfiles[slug];
}

export function getInstitutionVentureProfile(slug: string) {
  return institutionVentureProfiles[slug];
}
