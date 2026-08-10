import rawTrackingConfig from "@/config/user_tracking.json";
import { ipoCompanies } from "@/lib/catalog-data";
import { normalizeMarketTicker } from "@/lib/listed-company-identity";

export const TRACKING_REPOSITORY = "VCIQ/VCIQ.github.io";
export const TRACKING_BRANCH = "main";
export const TRACKING_CONFIG_PATH = "config/user_tracking.json";
export const TRACKING_OWNER = "VCIQ";

export type TrackingRegion = "中国" | "美国" | "全球";
export type TrackingSourceType = "rss" | "listing-search" | "sec";
export type TrackingSourceCategory = "company" | "media" | "person";
export type TrackingMarket = "A股" | "港股" | "美股";

export type TrackingTrack = {
  slug: string;
  name: string;
  enabled: boolean;
  custom: boolean;
  keywords: string[];
  people: string[];
  sampleCompanies: string[];
};

export type TrackingListedCompany = {
  id: string;
  name: string;
  ticker: string;
  market: TrackingMarket;
  sector: string;
  enabled: boolean;
  custom: boolean;
  catalogSlug?: string;
};

export type TrackingSource = {
  id: string;
  name: string;
  url: string;
  sourceType: TrackingSourceType;
  sourceCategory: TrackingSourceCategory;
  region: TrackingRegion;
  sector: string;
  company: string;
  ticker: string;
  keywords: string[];
  enabled: boolean;
  listedCompanyId?: string;
};

export type UserTrackingConfig = {
  schemaVersion: 1;
  tracks: TrackingTrack[];
  listedCompanies: TrackingListedCompany[];
  sources: TrackingSource[];
};

export type PersonLabelValidation = {
  valid: boolean;
  normalized: string;
  displayName: string;
  handle: string;
  searchTerms: string[];
  xEnabled: boolean;
  message: string;
};

export type TrackingKeywordValidation = {
  valid: boolean;
  normalized: string;
  level: "good" | "warning" | "error";
  message: string;
};

const REGIONS: TrackingRegion[] = ["中国", "美国", "全球"];
const MARKETS: TrackingMarket[] = ["A股", "港股", "美股"];
const SOURCE_TYPES: TrackingSourceType[] = ["rss", "listing-search", "sec"];
const SOURCE_CATEGORIES: TrackingSourceCategory[] = ["company", "media", "person"];
const GENERIC_PERSON_LABELS = new Set([
  "人物",
  "专家",
  "研究员",
  "科学家",
  "创始人",
  "创业者",
  "投资人",
  "ceo",
  "cto",
  "founder",
  "researcher",
  "scientist",
]);
const GENERIC_TRACKING_KEYWORDS = new Set([
  "ai",
  "ml",
  "人工智能",
  "技术",
  "科技",
  "公司",
  "企业",
  "行业",
  "产业",
  "研究",
  "论文",
  "新闻",
  "资讯",
  "产品",
  "项目",
  "模型",
  "系统",
  "平台",
  "创新",
  "投资",
  "融资",
  "上市",
  "发布",
  "突破",
  "发展",
  "市场",
  "应用",
  "机器人",
  "半导体",
  "新能源",
  "生物科技",
  "量子计算",
  "商业航天",
  "web3",
  "新材料",
  "智能制造",
  "tech",
  "technology",
  "company",
  "industry",
  "research",
  "paper",
  "news",
  "product",
  "project",
  "model",
  "system",
  "platform",
  "innovation",
  "investment",
  "funding",
  "launch",
  "update",
]);

function cleanText(value: unknown, maxLength = 120): string {
  return typeof value === "string"
    ? value.replace(/\s+/g, " ").trim().slice(0, maxLength)
    : "";
}

function uniqueStrings(value: unknown, maxItems = 80): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = cleanText(raw);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= maxItems) break;
  }
  return result;
}

function trimPersonSeparators(value: string): string {
  return value
    .replace(/^[\s|｜·•:：,，;；/\\\-—–()（）\[\]【】]+/, "")
    .replace(/[\s|｜·•:：,，;；/\\\-—–()（）\[\]【】]+$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function validateTrackingKeyword(value: unknown): TrackingKeywordValidation {
  const raw = cleanText(value, 80)
    .normalize("NFKC")
    .replace(/^["'“”‘’`]+|["'“”‘’`]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const invalid = (message: string): TrackingKeywordValidation => ({
    valid: false,
    normalized: "",
    level: "error",
    message,
  });

  if (!raw) return invalid("关键词不能为空。");
  if (raw.length > 40) return invalid("关键词过长，请保留核心技术、产品或事件术语。");
  if (/^https?:\/\//i.test(raw) || /\b(?:www\.)?[^\s]+\.(?:com|cn|org|net)\b/i.test(raw)) {
    return invalid("这里填写搜索关键词，不要粘贴网页地址。");
  }
  if (/@/.test(raw)) return invalid("账号应添加到“关键人物 / 关键账号”，不要作为关键词保存。");
  if (/^site\s*:/i.test(raw) || /(^|\s)(?:AND|OR|NOT)(\s|$)/i.test(raw)) {
    return invalid("不要填写 site:、AND、OR 等搜索语法，系统会自动构造查询。");
  }
  if (!/[A-Za-z0-9\u3400-\u9fff]/.test(raw)) {
    return invalid("关键词至少需要包含中文、英文或数字。");
  }

  const normalizedKey = raw.toLocaleLowerCase("zh-CN");
  if (GENERIC_TRACKING_KEYWORDS.has(normalizedKey)) {
    return invalid(`“${raw}”范围过宽。请改为更具体的技术、产品、公司动作或研究术语。`);
  }

  const cjkCount = (raw.match(/[\u3400-\u9fff]/g) ?? []).length;
  const alphanumericCount = (raw.match(/[A-Za-z0-9]/g) ?? []).length;
  const symbolicLanguage = /^(?:c(?:\+\+|#)?|r)$/i.test(raw);
  if (cjkCount === 1 && alphanumericCount === 0) {
    return invalid("单个汉字无法形成稳定搜索条件，请使用更具体的词组。");
  }
  if (cjkCount === 0 && alphanumericCount < 2 && !symbolicLanguage) {
    return invalid("英文或数字关键词至少需要两个有效字符。");
  }

  const shortTerm =
    (cjkCount > 0 && cjkCount <= 2 && alphanumericCount === 0) ||
    (cjkCount === 0 && alphanumericCount <= 2);
  return {
    valid: true,
    normalized: raw,
    level: shortTerm ? "warning" : "good",
    message: shortTerm
      ? "关键词可用，但较短，可能产生较多噪声；可考虑补充更具体的限定词。"
      : "关键词具体且可用于新闻、论文和公开网页筛选。",
  };
}

function uniqueTrackingKeywords(value: unknown, maxItems = 80): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const parsed = validateTrackingKeyword(raw);
    if (!parsed.valid) continue;
    const key = parsed.normalized.toLocaleLowerCase("zh-CN");
    if (seen.has(key)) continue;
    result.push(parsed.normalized);
    seen.add(key);
    if (result.length >= maxItems) break;
  }
  return result;
}

export function validatePersonLabel(value: unknown): PersonLabelValidation {
  const raw = cleanText(value, 100).replace(/＠/g, "@");
  const invalid = (message: string): PersonLabelValidation => ({
    valid: false,
    normalized: "",
    displayName: "",
    handle: "",
    searchTerms: [],
    xEnabled: false,
    message,
  });

  if (!raw) return invalid("人物或账号标签不能为空。");
  if (/^https?:\/\//i.test(raw) || /(?:x|twitter)\.com\//i.test(raw)) {
    return invalid("请填写“显示名 @handle”，不要直接粘贴 X 链接。");
  }

  const atCount = (raw.match(/@/g) ?? []).length;
  const handleMatch = raw.match(/@([A-Za-z0-9_]{1,15})(?![A-Za-z0-9_])/);
  if (atCount > 1) return invalid("一个标签只能包含一个 X handle。");
  if (atCount === 1 && !handleMatch) {
    return invalid("X handle 只能包含 1–15 位英文字母、数字或下划线。");
  }

  if (handleMatch) {
    const handle = handleMatch[1];
    const displayName = trimPersonSeparators(raw.replace(handleMatch[0], ""));
    if (displayName && !/[A-Za-z0-9\u3400-\u9fff]/.test(displayName)) {
      return invalid("显示名至少需要包含一个中文、英文或数字字符。");
    }
    const normalized = displayName ? `${displayName} @${handle}` : `@${handle}`;
    const searchTerms = [...new Set([displayName, handle, `@${handle}`].filter(Boolean))];
    return {
      valid: true,
      normalized,
      displayName,
      handle,
      searchTerms,
      xEnabled: true,
      message: "格式有效：会抓取该 X 账号，并将显示名和 handle 分别用于公开搜索。",
    };
  }

  const displayName = trimPersonSeparators(raw);
  if (
    displayName.length < 2 ||
    !/[A-Za-z0-9\u3400-\u9fff]/.test(displayName) ||
    GENERIC_PERSON_LABELS.has(displayName.toLocaleLowerCase("zh-CN"))
  ) {
    return invalid("标签过于宽泛。请填写具体姓名、组织名，最好补充 @handle。");
  }

  return {
    valid: true,
    normalized: displayName,
    displayName,
    handle: "",
    searchTerms: [displayName],
    xEnabled: false,
    message: "标签有效，但没有 @handle，只会参与新闻、论文和公开网页搜索。",
  };
}

function uniquePeople(value: unknown, maxItems = 40): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const parsed = validatePersonLabel(raw);
    if (!parsed.valid) continue;
    const key = parsed.normalized.toLocaleLowerCase("zh-CN");
    if (seen.has(key)) continue;
    result.push(parsed.normalized);
    seen.add(key);
    if (result.length >= maxItems) break;
  }
  return result;
}

function stableHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

export function slugifyTrack(value: string): string {
  const ascii = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return ascii || `track-${stableHash(value)}`;
}

function normalizeTrack(value: unknown, index: number): TrackingTrack | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 60);
  if (!name) return null;
  const custom = raw.custom === true;
  const suppliedSlug = cleanText(raw.slug, 60);
  return {
    slug: custom
      ? slugifyTrack(suppliedSlug || name)
      : suppliedSlug || `${slugifyTrack(name)}-${index + 1}`,
    name,
    enabled: raw.enabled !== false,
    custom,
    keywords: uniqueTrackingKeywords(raw.keywords),
    people: uniquePeople(raw.people),
    sampleCompanies: uniqueStrings(raw.sampleCompanies),
  };
}

function normalizeListedCompany(
  value: unknown,
  index: number,
): TrackingListedCompany | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 80);
  const market = MARKETS.includes(raw.market as TrackingMarket)
    ? (raw.market as TrackingMarket)
    : null;
  if (!name || !market) return null;
  const ticker = normalizeMarketTicker(market, cleanText(raw.ticker, 30));
  if (!ticker) return null;
  const catalogSlug = cleanText(raw.catalogSlug, 80);
  return {
    id:
      cleanText(raw.id, 100) ||
      `listed-${market}-${slugifyTrack(ticker || name)}-${index + 1}`,
    name,
    ticker,
    market,
    sector: cleanText(raw.sector, 60) || "未分类",
    enabled: raw.enabled !== false,
    custom: raw.custom === true || !catalogSlug,
    ...(catalogSlug ? { catalogSlug } : {}),
  };
}

function inferSourceCategory(
  raw: Record<string, unknown>,
  sourceType: TrackingSourceType,
): TrackingSourceCategory {
  const explicit = raw.sourceCategory as TrackingSourceCategory;
  if (SOURCE_CATEGORIES.includes(explicit)) return explicit;
  if (
    sourceType === "sec" ||
    cleanText(raw.ticker, 30) ||
    cleanText(raw.listedCompanyId, 100)
  ) {
    return "company";
  }
  return "media";
}

function normalizeSource(value: unknown, index: number): TrackingSource | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const name = cleanText(raw.name, 80);
  const sourceType = SOURCE_TYPES.includes(raw.sourceType as TrackingSourceType)
    ? (raw.sourceType as TrackingSourceType)
    : "listing-search";
  const sourceCategory = inferSourceCategory(raw, sourceType);
  const ticker = cleanText(raw.ticker, 30).toUpperCase();
  const suppliedUrl = cleanText(raw.url, 500);
  const url =
    sourceType === "sec" && !suppliedUrl
      ? "https://www.sec.gov/edgar/search/"
      : suppliedUrl;
  if (
    !name ||
    !/^https?:\/\//i.test(url) ||
    (sourceType === "sec" && (!ticker || sourceCategory !== "company"))
  ) {
    return null;
  }
  const region = REGIONS.includes(raw.region as TrackingRegion)
    ? (raw.region as TrackingRegion)
    : "全球";
  const listedCompanyId = cleanText(raw.listedCompanyId, 100);
  return {
    id:
      cleanText(raw.id, 80) ||
      `user-source-${slugifyTrack(name)}-${index + 1}`,
    name,
    url,
    sourceType,
    sourceCategory,
    region,
    sector: cleanText(raw.sector, 60) || "AI / AGI",
    company: sourceCategory === "company" ? cleanText(raw.company, 80) : "",
    ticker: sourceCategory === "company" ? ticker : "",
    keywords: uniqueStrings(raw.keywords),
    enabled: raw.enabled !== false,
    ...(sourceCategory === "company" && listedCompanyId ? { listedCompanyId } : {}),
  };
}

function defaultListedCompanies(): TrackingListedCompany[] {
  return ipoCompanies.map((company) => ({
    id: `catalog-${company.slug}`,
    name: company.name,
    ticker:
      normalizeMarketTicker(company.market, company.ticker) || company.ticker,
    market: company.market,
    sector: company.sector,
    enabled: true,
    custom: false,
    catalogSlug: company.slug,
  }));
}

export function normalizeTrackingConfig(value: unknown): UserTrackingConfig {
  const raw =
    value && typeof value === "object"
      ? (value as Record<string, unknown>)
      : {};
  const tracks = Array.isArray(raw.tracks)
    ? raw.tracks
        .map(normalizeTrack)
        .filter((item): item is TrackingTrack => Boolean(item))
    : [];
  const listedCompanies = Array.isArray(raw.listedCompanies)
    ? raw.listedCompanies
        .map(normalizeListedCompany)
        .filter((item): item is TrackingListedCompany => Boolean(item))
    : defaultListedCompanies();
  const sources = Array.isArray(raw.sources)
    ? raw.sources
        .map(normalizeSource)
        .filter((item): item is TrackingSource => Boolean(item))
    : [];

  const uniqueTracks = tracks.filter((track, index) => {
    const normalizedName = track.name.toLocaleLowerCase("zh-CN");
    return (
      tracks.findIndex(
        (candidate) =>
          candidate.slug === track.slug ||
          candidate.name.toLocaleLowerCase("zh-CN") === normalizedName,
      ) === index
    );
  });
  const uniqueListedCompanies = listedCompanies.filter(
    (company, index) =>
      listedCompanies.findIndex(
        (candidate) =>
          candidate.id === company.id ||
          (candidate.market === company.market &&
            candidate.ticker === company.ticker),
      ) === index,
  );
  const uniqueSources = sources.filter(
    (source, index) =>
      sources.findIndex((candidate) => candidate.id === source.id) === index,
  );

  return {
    schemaVersion: 1,
    tracks: uniqueTracks,
    listedCompanies: uniqueListedCompanies,
    sources: uniqueSources,
  };
}

export function cloneTrackingConfig(
  config: UserTrackingConfig,
): UserTrackingConfig {
  return JSON.parse(JSON.stringify(config)) as UserTrackingConfig;
}

export const userTrackingConfig = normalizeTrackingConfig(rawTrackingConfig);
