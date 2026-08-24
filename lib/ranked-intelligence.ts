import type {
  ArticlePayload,
  EventType,
  LiveIntelligenceEvent,
  RelatedArticleSource,
} from "@/lib/use-articles";

export const RANKED_INTELLIGENCE_SOURCE = "google-alerts-rss" as const;
export const RANKED_INTELLIGENCE_PLATFORM = "Google Alerts RSS";
export const RANKED_INTELLIGENCE_MAX_ITEMS = 24;
export const RANKED_INTELLIGENCE_FALLBACK_SECTOR = "跨赛道精选";
const EVENT_WINDOW_MS = 48 * 60 * 60 * 1000;
const GENERIC_LATIN_TOKENS = new Set([
  "openai", "chatgpt", "news", "update", "launch", "launches", "released", "release",
  "announces", "announced", "official", "product", "products", "feature", "features", "version",
]);
const TITLE_IDENTITY_STOPWORDS = new Set([
  "news", "update", "launch", "launches", "released", "release", "announces", "announced",
  "official", "product", "products", "feature", "features", "version", "with", "from", "about",
  "after", "before", "into", "more", "new", "for", "the", "and",
]);
const GENERIC_CJK_BIGRAMS = new Set([
  "发布", "推出", "上线", "正式", "最新", "新增", "产品", "版本", "功能", "公司", "宣布",
  "今日", "消息", "相关", "进行", "应用", "使用", "视频", "媒体", "报道",
]);
const GENERIC_CJK_TRIGRAMS = new Set([
  "人工智能", "有限公司", "最新消息", "正式发布", "正式推出", "公司宣布", "相关消息",
  "媒体报道", "今日消息", "产品发布", "功能更新", "用户使用", "技术发展",
]);
const GENERIC_EVENT_ANCHORS = new Set(["ai", "agi", "aiagi", "人工智能", "全球", "美国", "中国"]);
const ROUNDUP_TITLE_RE = /(?:早报|晚报|日报|周报|月报|晨报|要闻|盘点|速览|一览|汇总|热点|简报)/u;
const SEMANTIC_EVENT_CONCEPTS: Array<[string, RegExp]> = [
  ["audience:minor", /(?:青少年|少年版|青春版|未成年(?:人)?|儿童|孩子|年轻用户|teen(?:s|ager|agers)?|adolescent(?:s)?|minor(?:s)?|young users?|under\s*(?:13|18)|13岁以下|18岁以下)/iu],
  ["control:parental", /(?:家长|父母|监护|家长控制|parent(?:s|al)?|guardian(?:s)?)/iu],
  ["safety:minor", /(?:安全防护|安全措施|安全保护|未成年人保护|age[- ]appropriate|safety|safeguard(?:s|ing)?|protection)/iu],
  ["mode:study", /(?:学习模式|学习引导|学习辅导|study mode|learning mode)/iu],
  ["restriction:age", /(?:年龄限制|年龄门槛|限制使用|禁用|under\s*(?:13|18)|age restriction(?:s)?|13岁以下|18岁以下)/iu],
  ["feature:voice", /(?:实时语音|语音模式|voice mode|voice feature|voice translation)/iu],
  ["feature:translation", /(?:实时翻译|语音翻译|translation|translate)/iu],
];
const HIGH_SIGNAL_EVENT_CONCEPTS = new Set(["audience:minor"]);

export type RankedIntelligenceEntity = {
  objectType: "company" | "person" | "technology";
  name: string;
};

export type RankedIntelligenceRelatedSource = {
  source: string;
  href: string;
  title: string;
  publishedAt: string;
};

export type RankedIntelligenceProjectionItem = {
  id: string;
  title: string;
  summary: string;
  href: string;
  source: string;
  publishedAt: string;
  priority: "P0" | "P1" | "P2";
  score: number;
  eventTypes: string[];
  entities: RankedIntelligenceEntity[];
  tracks: string[];
  eventClusterId: string;
  duplicateCount: number;
  relatedSources: RankedIntelligenceRelatedSource[];
};

export type RankedIntelligenceProjection = {
  schemaVersion: 1;
  generatedAt: string;
  source: typeof RANKED_INTELLIGENCE_SOURCE;
  contentHash: string;
  items: RankedIntelligenceProjectionItem[];
};

export const emptyRankedIntelligenceProjection: RankedIntelligenceProjection = {
  schemaVersion: 1,
  generatedAt: "",
  source: RANKED_INTELLIGENCE_SOURCE,
  contentHash: "",
  items: [],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function text(value: unknown, limit: number): string {
  return typeof value === "string"
    ? value.normalize("NFKC").trim().replace(/\s+/g, " ").slice(0, limit)
    : "";
}

function normalizedText(value: unknown, limit = 800): string {
  return text(value, limit).toLocaleLowerCase("en-US").replace(/[^a-z0-9\u3400-\u9fff]+/g, "");
}

function stringList(value: unknown, limit: number): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = text(raw, 160);
    const key = item.normalize("NFKC").toLocaleLowerCase("en-US");
    if (!item || !key || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function safeHttpUrl(value: unknown): string {
  const candidate = text(value, 1600);
  if (!candidate) return "";
  try {
    const parsed = new URL(candidate);
    if (!/^https?:$/.test(parsed.protocol) || parsed.username || parsed.password) return "";
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return "";
  }
}

function normalizeEntity(value: unknown): RankedIntelligenceEntity | null {
  if (!isRecord(value)) return null;
  const objectType = value.objectType;
  if (objectType !== "company" && objectType !== "person" && objectType !== "technology") {
    return null;
  }
  const name = text(value.name, 160);
  return name ? { objectType, name } : null;
}

function normalizeRelatedSource(
  value: unknown,
  primaryHref: string,
): RankedIntelligenceRelatedSource | null {
  if (!isRecord(value)) return null;
  const href = safeHttpUrl(value.href);
  const publishedAt = text(value.publishedAt, 80);
  const parsedTime = new Date(publishedAt);
  if (!href || href === primaryHref || !publishedAt || Number.isNaN(parsedTime.getTime())) return null;
  return {
    source: text(value.source, 160) || new URL(href).hostname.replace(/^www\./, ""),
    href,
    title: text(value.title, 240),
    publishedAt: parsedTime.toISOString(),
  };
}

function normalizeItem(value: unknown): RankedIntelligenceProjectionItem | null {
  if (!isRecord(value)) return null;
  const href = safeHttpUrl(value.href);
  const title = text(value.title, 240);
  const publishedAt = text(value.publishedAt, 80);
  const parsedTime = new Date(publishedAt);
  if (!href || !title || !publishedAt || Number.isNaN(parsedTime.getTime())) return null;

  const priority = value.priority === "P0" || value.priority === "P1" ? value.priority : "P2";
  const scoreValue = typeof value.score === "number" && Number.isFinite(value.score) ? value.score : 0;
  const score = Math.max(0, Math.min(100, Math.round(scoreValue)));
  const entities = Array.isArray(value.entities)
    ? value.entities.map(normalizeEntity).filter((entity): entity is RankedIntelligenceEntity => Boolean(entity)).slice(0, 8)
    : [];
  const relatedSources = Array.isArray(value.relatedSources)
    ? value.relatedSources
      .map((source) => normalizeRelatedSource(source, href))
      .filter((source): source is RankedIntelligenceRelatedSource => Boolean(source))
      .slice(0, 3)
    : [];
  const duplicateValue = typeof value.duplicateCount === "number" && Number.isFinite(value.duplicateCount)
    ? Math.trunc(value.duplicateCount)
    : 1;

  return {
    id: text(value.id, 240) || href,
    title,
    summary: text(value.summary, 700),
    href,
    source: text(value.source, 160) || new URL(href).hostname.replace(/^www\./, ""),
    publishedAt: parsedTime.toISOString(),
    priority,
    score,
    eventTypes: stringList(value.eventTypes, 6),
    entities,
    tracks: stringList(value.tracks, 4),
    eventClusterId: text(value.eventClusterId, 160),
    duplicateCount: Math.max(1, duplicateValue, relatedSources.length + 1),
    relatedSources,
  };
}

export function parseRankedIntelligenceProjection(value: unknown): RankedIntelligenceProjection {
  if (!isRecord(value)) throw new Error("Ranked intelligence projection is not an object");
  if (value.schemaVersion !== 1) throw new Error("Ranked intelligence projection schemaVersion must be 1");
  if (value.source !== RANKED_INTELLIGENCE_SOURCE) {
    throw new Error("Ranked intelligence projection has an unsupported source");
  }
  if (!Array.isArray(value.items)) throw new Error("Ranked intelligence projection is missing items");

  return {
    schemaVersion: 1,
    generatedAt: text(value.generatedAt, 80),
    source: RANKED_INTELLIGENCE_SOURCE,
    contentHash: text(value.contentHash, 128),
    items: value.items
      .slice(0, RANKED_INTELLIGENCE_MAX_ITEMS)
      .map(normalizeItem)
      .filter((item): item is RankedIntelligenceProjectionItem => Boolean(item)),
  };
}

function mappedEventType(eventTypes: string[]): EventType {
  for (const raw of eventTypes) {
    switch (raw.trim().toLowerCase()) {
      case "funding":
        return "融资";
      case "m&a":
      case "merger":
      case "acquisition":
        return "并购";
      case "ipo":
        return "IPO";
      case "product":
        return "产品发布";
      case "technology":
      case "patent":
        return "技术突破";
      case "research":
        return "论文";
      case "policy":
        return "政策";
      case "personnel":
        return "公司动态";
      case "partnership":
      case "production":
      case "order":
      case "market":
        return "商业进展";
      default:
        break;
    }
  }
  return "公司动态";
}

function unique(values: string[], limit = 12): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw.trim();
    const key = value.normalize("NFKC").toLocaleLowerCase("en-US");
    if (!value || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
    if (result.length >= limit) break;
  }
  return result;
}

function projectedRelatedSource(source: RankedIntelligenceRelatedSource): RelatedArticleSource {
  return {
    name: source.source,
    url: source.href,
    level: "待交叉验证",
    platform: RANKED_INTELLIGENCE_PLATFORM,
    title: source.title,
    publishedAt: source.publishedAt,
  };
}

export function rankedIntelligenceItemToArticle(
  item: RankedIntelligenceProjectionItem,
): LiveIntelligenceEvent {
  const companies = unique(
    item.entities.filter((entity) => entity.objectType === "company").map((entity) => entity.name),
  );
  const people = unique(
    item.entities.filter((entity) => entity.objectType === "person").map((entity) => entity.name),
  );
  const technologies = unique(
    item.entities.filter((entity) => entity.objectType === "technology").map((entity) => entity.name),
  );

  return {
    id: `ranked-intelligence:${item.id}`,
    title: item.title,
    summary: item.summary,
    type: mappedEventType(item.eventTypes),
    region: "全球",
    sector: item.tracks[0] ?? RANKED_INTELLIGENCE_FALLBACK_SECTOR,
    company: companies[0] ?? "",
    sourceId: RANKED_INTELLIGENCE_SOURCE,
    publishedAt: item.publishedAt,
    importance: item.score,
    source: {
      name: item.source,
      url: item.href,
      level: "待交叉验证",
      platform: RANKED_INTELLIGENCE_PLATFORM,
    },
    curated: true,
    mentionedCompanies: companies,
    mentionedPeople: people,
    matchedTrackingTerms: unique([...technologies, ...item.tracks]),
    eventClusterId: item.eventClusterId || undefined,
    duplicateCount: item.duplicateCount,
    relatedSources: item.relatedSources.map(projectedRelatedSource),
  };
}

function urlKey(value: string): string {
  try {
    const parsed = new URL(value);
    parsed.hash = "";
    for (const key of [...parsed.searchParams.keys()]) {
      const lowered = key.toLowerCase();
      if (lowered.startsWith("utm_") || ["gclid", "fbclid", "mc_cid", "mc_eid", "igshid"].includes(lowered)) {
        parsed.searchParams.delete(key);
      }
    }
    if (parsed.pathname.length > 1 && parsed.pathname.endsWith("/")) parsed.pathname = parsed.pathname.replace(/\/+$/, "");
    return parsed.toString().toLocaleLowerCase("en-US");
  } catch {
    return value.trim().toLocaleLowerCase("en-US");
  }
}

function mergeStrings(left: string[] | undefined, right: string[] | undefined): string[] | undefined {
  const values = unique([...(left ?? []), ...(right ?? [])]);
  return values.length ? values : undefined;
}

function eventTimestamp(value: string): number | null {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function cjkRuns(value: string): string[] {
  return text(value, 500).match(/[\u3400-\u9fff]{2,}/g) ?? [];
}

function cjkTrigrams(value: string): Set<string> {
  const result = new Set<string>();
  for (const run of cjkRuns(value)) {
    for (let index = 0; index < run.length - 2; index += 1) {
      const trigram = run.slice(index, index + 3);
      if (!GENERIC_CJK_TRIGRAMS.has(trigram)) result.add(trigram);
    }
  }
  return result;
}

function compoundHomepageEvent(item: LiveIntelligenceEvent): boolean {
  const title = text(item.title, 500);
  if (!title) return false;
  if (ROUNDUP_TITLE_RE.test(title)) return true;
  const hardSeparators = title.match(/[；;｜|]/g)?.length ?? 0;
  return hardSeparators >= 1 && title.length >= 42;
}

function semanticEventConceptKeys(item: LiveIntelligenceEvent): Set<string> {
  const haystack = `${text(item.title, 500)} ${text(item.summary, 1000)}`.normalize("NFKC");
  const result = new Set<string>();
  for (const [concept, pattern] of SEMANTIC_EVENT_CONCEPTS) {
    if (pattern.test(haystack)) result.add(concept);
  }
  return result;
}

function semanticEventEvidence(left: LiveIntelligenceEvent, right: LiveIntelligenceEvent): {
  sharedCount: number;
  highSignal: boolean;
} {
  const a = semanticEventConceptKeys(left);
  const b = semanticEventConceptKeys(right);
  const shared = [...a].filter((concept) => b.has(concept));
  return {
    sharedCount: shared.length,
    highSignal: shared.some((concept) => HIGH_SIGNAL_EVENT_CONCEPTS.has(concept)),
  };
}

function titleIdentityTokens(value: string): Set<string> {
  const result = new Set<string>();
  const normalized = text(value, 500).toLocaleLowerCase("en-US");
  for (const token of normalized.match(/[a-z0-9][a-z0-9.+_-]{2,}/g) ?? []) {
    const cleaned = token.replace(/[^a-z0-9]/g, "");
    if (cleaned.length >= 3 && !TITLE_IDENTITY_STOPWORDS.has(cleaned)) result.add(cleaned);
  }
  return result;
}

function topicTokens(value: string): Set<string> {
  const normalized = text(value, 500).toLocaleLowerCase("en-US");
  const result = new Set<string>();
  for (const token of normalized.match(/[a-z0-9][a-z0-9.+_-]{2,}/g) ?? []) {
    const cleaned = token.replace(/[^a-z0-9]/g, "");
    if (cleaned.length >= 3 && !GENERIC_LATIN_TOKENS.has(cleaned)) result.add(cleaned);
  }
  for (const run of normalized.match(/[\u3400-\u9fff]{2,}/g) ?? []) {
    for (let index = 0; index < run.length - 1; index += 1) {
      const bigram = run.slice(index, index + 2);
      if (!GENERIC_CJK_BIGRAMS.has(bigram)) result.add(bigram);
    }
  }
  return result;
}

function overlapCount(left: Set<string>, right: Set<string>): number {
  let count = 0;
  for (const value of left) if (right.has(value)) count += 1;
  return count;
}

function titleTopicContainment(left: string, right: string): number {
  const a = topicTokens(left);
  const b = topicTokens(right);
  if (!a.size || !b.size) return 0;
  return overlapCount(a, b) / Math.min(a.size, b.size);
}

function sharedSalientPhrases(left: string, right: string): number {
  return overlapCount(cjkTrigrams(left.toLocaleLowerCase("en-US")), cjkTrigrams(right.toLocaleLowerCase("en-US")));
}

function eventAnchors(item: LiveIntelligenceEvent): Set<string> {
  const values = [
    item.company,
    ...(item.mentionedCompanies ?? []),
    ...(item.mentionedPeople ?? []),
    ...(item.matchedTrackingTerms ?? []),
  ];
  const result = new Set<string>();
  for (const value of values) {
    const normalized = normalizedText(value, 160);
    if (!normalized || normalized.length < 3 || GENERIC_EVENT_ANCHORS.has(normalized)) continue;
    result.add(normalized);
  }
  return result;
}

export function areLikelySameHomepageEvent(
  left: LiveIntelligenceEvent,
  right: LiveIntelligenceEvent,
): boolean {
  if (left.eventClusterId && right.eventClusterId && left.eventClusterId === right.eventClusterId) return true;
  if (left.type !== right.type) return false;
  const leftTime = eventTimestamp(left.publishedAt);
  const rightTime = eventTimestamp(right.publishedAt);
  if (leftTime === null || rightTime === null || Math.abs(leftTime - rightTime) > EVENT_WINDOW_MS) return false;

  const leftTitle = normalizedText(left.title, 500);
  const rightTitle = normalizedText(right.title, 500);
  if (leftTitle && rightTitle && leftTitle === rightTitle) return true;

  const anchors = overlapCount(eventAnchors(left), eventAnchors(right));
  const topic = titleTopicContainment(left.title, right.title);
  const contained = Math.min(leftTitle.length, rightTitle.length) >= 10
    && (leftTitle.includes(rightTitle) || rightTitle.includes(leftTitle));
  const salient = sharedSalientPhrases(left.title, right.title);
  const semantic = semanticEventEvidence(left, right);
  const semanticMatch = semantic.highSignal || semantic.sharedCount >= 2;
  const identity = overlapCount(titleIdentityTokens(left.title), titleIdentityTokens(right.title));
  const compound = compoundHomepageEvent(left) || compoundHomepageEvent(right);

  if (compound) {
    if (semantic.highSignal && identity > 0) return true;
    return anchors > 0 && (contained || topic >= 0.56 || salient >= 2);
  }

  if (anchors > 0) {
    return contained
      || topic >= (anchors >= 2 ? 0.24 : 0.38)
      || (semanticMatch && identity > 0);
  }

  // Public projection intentionally omits private Query/category/catalog state. For
  // Catalog-OFF cross-pipeline matching, require a shared title identity plus strong
  // event concepts instead of lowering the generic topic threshold globally.
  return identity > 0 && (semantic.highSignal || semantic.sharedCount >= 2);
}

function asRelatedSource(item: LiveIntelligenceEvent): RelatedArticleSource {
  return {
    name: item.source.name,
    url: item.source.url,
    level: item.source.level,
    platform: item.source.platform ?? "",
    title: item.title,
    publishedAt: item.publishedAt,
  };
}

function mergeRelatedSources(
  primaryUrl: string,
  groups: Array<RelatedArticleSource[] | undefined>,
): RelatedArticleSource[] | undefined {
  const primaryKey = urlKey(primaryUrl);
  const seen = new Set<string>();
  const result: RelatedArticleSource[] = [];
  for (const group of groups) {
    for (const source of group ?? []) {
      const key = urlKey(source.url);
      if (!key || key === primaryKey || seen.has(key)) continue;
      seen.add(key);
      result.push(source);
      if (result.length >= 12) return result;
    }
  }
  return result.length ? result : undefined;
}

function mergeEventArticle(
  existing: LiveIntelligenceEvent,
  projected: LiveIntelligenceEvent,
  includeProjectedPrimary: boolean,
): LiveIntelligenceEvent {
  const promoteProjected = includeProjectedPrimary
    && compoundHomepageEvent(existing)
    && !compoundHomepageEvent(projected);
  const primary = promoteProjected ? projected : existing;
  const secondary = promoteProjected ? existing : projected;
  const secondaryPrimary = includeProjectedPrimary ? [asRelatedSource(secondary)] : [];
  const relatedSources = mergeRelatedSources(primary.source.url, [
    primary.relatedSources,
    secondaryPrimary,
    secondary.relatedSources,
  ]);
  const visibleSourceCount = 1 + (relatedSources?.length ?? 0);
  return {
    ...primary,
    importance: Math.max(existing.importance, projected.importance),
    curated: true,
    eventClusterId: promoteProjected
      ? (projected.eventClusterId || existing.eventClusterId)
      : (existing.eventClusterId || projected.eventClusterId),
    duplicateCount: Math.max(
      existing.duplicateCount ?? 1,
      projected.duplicateCount ?? 1,
      visibleSourceCount,
    ),
    relatedSources,
    mentionedCompanies: mergeStrings(existing.mentionedCompanies, projected.mentionedCompanies),
    mentionedPeople: mergeStrings(existing.mentionedPeople, projected.mentionedPeople),
    matchedTrackingTerms: mergeStrings(existing.matchedTrackingTerms, projected.matchedTrackingTerms),
  };
}

export function mergeRankedIntelligenceIntoArticlePayload(
  payload: ArticlePayload,
  rawProjection: unknown,
): ArticlePayload {
  let projection: RankedIntelligenceProjection;
  try {
    projection = parseRankedIntelligenceProjection(rawProjection);
  } catch {
    return payload;
  }
  if (projection.items.length === 0) return payload;

  const articles = [...payload.articles];
  const articleIndex = new Map<string, number>();
  articles.forEach((article, index) => {
    const key = urlKey(article.source.url);
    if (key && !articleIndex.has(key)) articleIndex.set(key, index);
  });

  for (const item of projection.items) {
    const projected = rankedIntelligenceItemToArticle(item);
    const key = urlKey(projected.source.url);
    let existingIndex = articleIndex.get(key);
    let semanticMatch = false;
    if (existingIndex === undefined) {
      existingIndex = articles.findIndex((article) => areLikelySameHomepageEvent(article, projected));
      semanticMatch = existingIndex >= 0;
    }
    if (existingIndex === undefined || existingIndex < 0) {
      articleIndex.set(key, articles.length);
      articles.push(projected);
      continue;
    }

    const existing = articles[existingIndex];
    articles[existingIndex] = mergeEventArticle(existing, projected, semanticMatch || urlKey(existing.source.url) !== key);
    articleIndex.set(key, existingIndex);
  }

  return {
    ...payload,
    articleCount: articles.length,
    articles,
  };
}