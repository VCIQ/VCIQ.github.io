import type {
  ArticlePayload,
  EventType,
  LiveIntelligenceEvent,
} from "@/lib/use-articles";

export const RANKED_INTELLIGENCE_SOURCE = "google-alerts-rss" as const;
export const RANKED_INTELLIGENCE_PLATFORM = "Google Alerts RSS";
export const RANKED_INTELLIGENCE_MAX_ITEMS = 24;
export const RANKED_INTELLIGENCE_FALLBACK_SECTOR = "跨赛道精选";

export type RankedIntelligenceEntity = {
  objectType: "company" | "person" | "technology";
  name: string;
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
    ? value.trim().replace(/\s+/g, " ").slice(0, limit)
    : "";
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
  };
}

function urlKey(value: string): string {
  try {
    const parsed = new URL(value);
    parsed.hash = "";
    return parsed.toString().toLocaleLowerCase("en-US");
  } catch {
    return value.trim().toLocaleLowerCase("en-US");
  }
}

function mergeStrings(left: string[] | undefined, right: string[] | undefined): string[] | undefined {
  const values = unique([...(left ?? []), ...(right ?? [])]);
  return values.length ? values : undefined;
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
    const existingIndex = articleIndex.get(key);
    if (existingIndex === undefined) {
      articleIndex.set(key, articles.length);
      articles.push(projected);
      continue;
    }

    const existing = articles[existingIndex];
    articles[existingIndex] = {
      ...existing,
      importance: Math.max(existing.importance, projected.importance),
      curated: true,
      mentionedCompanies: mergeStrings(existing.mentionedCompanies, projected.mentionedCompanies),
      mentionedPeople: mergeStrings(existing.mentionedPeople, projected.mentionedPeople),
      matchedTrackingTerms: mergeStrings(existing.matchedTrackingTerms, projected.matchedTrackingTerms),
    };
  }

  return {
    ...payload,
    articleCount: articles.length,
    articles,
  };
}
