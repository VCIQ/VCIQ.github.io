type JsonRecord = Record<string, unknown>;

export type InnovationCapitalObjectType =
  | "project"
  | "lifecycle-project"
  | "broker"
  | "institution"
  | "mature-candidate"
  | "discovered-company";

export type InnovationCapitalMatchedObject = {
  type: InnovationCapitalObjectType;
  name: string;
  broker?: string;
  stage?: string;
};

export type InnovationCapitalFeedItem = {
  eventId: string;
  sourceUrl: string;
  publishedAt: string;
  eventClusterId: string;
  matchedObjects: InnovationCapitalMatchedObject[];
  reasonCodes: string[];
  evidenceTier: "primary" | "trusted" | "discovery";
  innovationPriority: number;
};

export type InnovationCapitalFeedProjection = {
  schemaVersion: 1;
  generatedAt: string;
  universeAsOf: string;
  eventCount: number;
  items: InnovationCapitalFeedItem[];
};

export type HomepageInnovationEvent = {
  id: string;
  title: string;
  summary: string;
  type?: string;
  sector?: string;
  company?: string;
  sourceId?: string;
  publishedAt?: string;
  importance?: number;
  eventClusterId?: string;
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  matchedTrackingTerms?: string[];
  source: {
    name?: string;
    url: string;
    level?: string;
    platform?: string;
  };
};

type UniverseObject = InnovationCapitalMatchedObject & {
  aliases: string[];
};

export type HomepageInnovationCapitalIndex = {
  byId: Map<string, InnovationCapitalFeedItem>;
  byUrl: Map<string, InnovationCapitalFeedItem>;
  byCluster: Map<string, InnovationCapitalFeedItem>;
};

const LISTING_RE =
  /辅导|IPO|上市|科创板|创业板|受理|问询|注册(?:稿|阶段)?|发行|招股|保荐|港交所|H股|A\+H|18C/iu;
const FUNDING_RE =
  /融资|募资|领投|跟投|增资|投资|D\+?\+?轮|E\+?\+?轮|F轮|Pre[- ]?IPO|Growth|战略融资|战略投资/iu;
const TECHNOLOGY_RE =
  /发布|推出|量产|订单|中标|签约|商业化|产能|技术突破|芯片|GPU|机器人|具身智能|火箭|卫星|脑机|6G|新药|细胞治疗|储能|固态电池|新材料|量子|高端装备/iu;
const POLICY_RE = /十五五|监管|政策|规则|指引|审核标准|上市标准/iu;

const PRIMARY_LEVELS = new Set([
  "监管文件",
  "交易所公告",
  "官方披露",
  "原始材料",
  "券商官方",
  "投资机构官方",
  "公司官方",
]);

const REASON_LABELS: Record<string, string> = {
  TRACKED_PROJECT: "已追踪科创项目",
  LIFECYCLE_PROJECT: "上市生命周期项目",
  TARGET_BROKER: "五大券商",
  CAPITAL_INSTITUTION: "硬科技投资机构",
  MATURE_CANDIDATE: "成熟期潜在项目",
  DISCOVERED_COMPANY: "科创发现候选",
  LISTING_EVENT: "辅导 / 上市事件",
  FUNDING_EVENT: "融资 / 投资事件",
  TECHNOLOGY_EVENT: "技术 / 商业化事件",
  POLICY_EVENT: "科创政策事件",
  PRIMARY_EVIDENCE: "一级公开证据",
  TRUSTED_EVIDENCE: "可信公开来源",
  INNOVATION_DISCOVERY_SOURCE: "科创专用发现源",
};

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function text(value: unknown, limit = 1_600): string {
  return typeof value === "string"
    ? value.trim().replace(/\s+/gu, " ").slice(0, limit)
    : "";
}

function normalize(value: unknown): string {
  return text(value, 500)
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function unique(values: string[], limit = 40): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = text(raw, 300);
    const key = normalize(value);
    if (!value || !key || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
    if (result.length >= limit) break;
  }
  return result;
}

function urlKey(value: unknown): string {
  const raw = text(value, 1_600);
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    parsed.hash = "";
    for (const key of [...parsed.searchParams.keys()]) {
      const lower = key.toLocaleLowerCase("en-US");
      if (lower.startsWith("utm_") || ["gclid", "fbclid", "mc_cid", "mc_eid"].includes(lower)) {
        parsed.searchParams.delete(key);
      }
    }
    return parsed.toString().replace(/\/$/u, "").toLocaleLowerCase("en-US");
  } catch {
    return raw.toLocaleLowerCase("en-US");
  }
}

function aliasesFrom(row: JsonRecord, canonicalField: string): string[] {
  return unique([
    text(row[canonicalField], 240),
    ...list(row.aliases).map((value) => text(value, 240)),
  ], 20);
}

function objectKey(value: InnovationCapitalMatchedObject): string {
  return `${value.type}:${normalize(value.name)}`;
}

function buildUniverse(input: {
  watchlistPayload: unknown;
  lifecyclePayload: unknown;
  maturePayload: unknown;
  trackingSeedsPayload: unknown;
}): UniverseObject[] {
  const watchlist = record(input.watchlistPayload);
  const lifecycle = record(input.lifecyclePayload);
  const mature = record(input.maturePayload);
  const seeds = record(input.trackingSeedsPayload);
  const result = new Map<string, UniverseObject>();

  const add = (value: UniverseObject) => {
    const key = objectKey(value);
    if (!normalize(value.name) || result.has(key)) return;
    result.set(key, {
      ...value,
      aliases: unique([value.name, ...value.aliases], 30),
    });
  };

  for (const raw of list(watchlist.projects)) {
    const row = record(raw);
    const name = text(row.company, 240);
    if (!name) continue;
    add({
      type: "project",
      name,
      broker: text(row.broker, 160),
      stage: text(row.stage, 120),
      aliases: aliasesFrom(row, "company"),
    });
  }

  for (const raw of list(lifecycle.projects)) {
    const row = record(raw);
    const name = text(row.company, 240);
    if (!name) continue;
    add({
      type: "lifecycle-project",
      name,
      broker: text(row.broker, 160),
      stage: text(row.stage, 120),
      aliases: aliasesFrom(row, "company"),
    });
  }

  for (const raw of list(mature.candidates)) {
    const row = record(raw);
    const name = text(row.name, 240);
    if (!name) continue;
    add({
      type: "mature-candidate",
      name,
      aliases: aliasesFrom(row, "name"),
      stage: text(row.financingRound, 120) || "成熟期融资候选",
    });
  }

  const seedBrokers = list(seeds.brokers).map(record);
  if (seedBrokers.length) {
    for (const row of seedBrokers) {
      const name = text(row.name, 160);
      if (!name) continue;
      add({
        type: "broker",
        name,
        aliases: aliasesFrom(row, "name"),
      });
    }
  } else {
    for (const broker of list(watchlist.brokers)) {
      const name = text(broker, 160);
      if (!name) continue;
      add({ type: "broker", name, aliases: [name] });
    }
  }

  for (const raw of list(seeds.institutions)) {
    const row = record(raw);
    const name = text(row.name, 240);
    if (!name) continue;
    add({
      type: "institution",
      name,
      aliases: aliasesFrom(row, "name"),
    });
  }

  return [...result.values()];
}

function structuredValues(event: HomepageInnovationEvent): string[] {
  return unique([
    event.company ?? "",
    ...(event.mentionedCompanies ?? []),
    ...(event.mentionedPeople ?? []),
    ...(event.matchedTrackingTerms ?? []),
  ], 40);
}

function aliasMatches(
  alias: string,
  structured: string[],
  haystack: string,
): boolean {
  const key = normalize(alias);
  if (!key) return false;
  if (structured.some((value) => normalize(value) === key)) return true;
  if (key.length < 2) return false;
  const normalizedHaystack = normalize(haystack);
  if (!normalizedHaystack.includes(key)) return false;
  if (/^[a-z0-9]+$/u.test(key) && key.length < 4) return false;
  return true;
}

function matchedObjectsForEvent(
  event: HomepageInnovationEvent,
  universe: UniverseObject[],
): InnovationCapitalMatchedObject[] {
  const structured = structuredValues(event);
  const haystack = [
    event.title,
    event.summary,
    event.company,
    event.sector,
    ...(event.mentionedCompanies ?? []),
    ...(event.matchedTrackingTerms ?? []),
  ].filter(Boolean).join(" ");

  const matched = new Map<string, InnovationCapitalMatchedObject>();
  for (const object of universe) {
    if (!object.aliases.some((alias) => aliasMatches(alias, structured, haystack))) continue;
    const compact: InnovationCapitalMatchedObject = {
      type: object.type,
      name: object.name,
      ...(object.broker ? { broker: object.broker } : {}),
      ...(object.stage ? { stage: object.stage } : {}),
    };
    matched.set(objectKey(compact), compact);
  }

  return [...matched.values()]
    .sort((left, right) => {
      const weight = (type: InnovationCapitalObjectType) =>
        type === "lifecycle-project" ? 5
          : type === "project" ? 4
            : type === "mature-candidate" ? 3
              : type === "institution" ? 2
                : type === "broker" ? 1
                  : 0;
      return weight(right.type) - weight(left.type)
        || left.name.localeCompare(right.name, "zh-CN");
    })
    .slice(0, 8);
}

function evidenceTier(event: HomepageInnovationEvent): InnovationCapitalFeedItem["evidenceTier"] {
  const level = text(event.source.level, 80);
  if (PRIMARY_LEVELS.has(level)) return "primary";
  if (level && !/待交叉验证|低可信|未知/u.test(level)) return "trusted";
  return "discovery";
}

function materialSignalText(event: HomepageInnovationEvent): string {
  const raw = [
    event.title,
    event.summary,
    event.type,
    event.sector,
  ].filter(Boolean).join(" ");

  // Discovery summaries often explicitly say that a financing/listing event did
  // not occur. Remove the whole negated clause before event classification so
  // strings such as “没有投资、融资或上市事件” cannot become positive signals.
  return raw
    .replace(
      /(?:没有|并无|未发生|不存在|尚无|未有|尚未发生|并未发生)[^。；;！？!?]{0,48}(?:。|；|;|！|!|？|\?|$)/giu,
      " ",
    )
    .replace(/\s+/gu, " ")
    .trim();
}

function reasonCodes(
  event: HomepageInnovationEvent,
  matched: InnovationCapitalMatchedObject[],
): string[] {
  const haystack = materialSignalText(event);
  const result: string[] = [];

  if (matched.some((item) => item.type === "project")) result.push("TRACKED_PROJECT");
  if (matched.some((item) => item.type === "lifecycle-project")) result.push("LIFECYCLE_PROJECT");
  if (matched.some((item) => item.type === "broker")) result.push("TARGET_BROKER");
  if (matched.some((item) => item.type === "institution")) result.push("CAPITAL_INSTITUTION");
  if (matched.some((item) => item.type === "mature-candidate")) result.push("MATURE_CANDIDATE");
  if (matched.some((item) => item.type === "discovered-company")) result.push("DISCOVERED_COMPANY");
  if (LISTING_RE.test(haystack)) result.push("LISTING_EVENT");
  if (FUNDING_RE.test(haystack)) result.push("FUNDING_EVENT");
  if (TECHNOLOGY_RE.test(haystack)) result.push("TECHNOLOGY_EVENT");
  if (POLICY_RE.test(haystack)) result.push("POLICY_EVENT");

  const tier = evidenceTier(event);
  if (tier === "primary") result.push("PRIMARY_EVIDENCE");
  else if (tier === "trusted") result.push("TRUSTED_EVIDENCE");

  if (
    text(event.sourceId, 240).startsWith("innovation-listing-")
    || text(event.sourceId, 240).startsWith("innovation-capital-portfolio-")
  ) {
    result.push("INNOVATION_DISCOVERY_SOURCE");
  }
  return unique(result, 16);
}

function qualifies(
  event: HomepageInnovationEvent,
  matched: InnovationCapitalMatchedObject[],
  reasons: string[],
): boolean {
  const directProject = matched.some((item) =>
    ["project", "lifecycle-project", "mature-candidate"].includes(item.type));
  const institution = matched.some((item) => item.type === "institution");
  const broker = matched.some((item) => item.type === "broker");
  const listing = reasons.includes("LISTING_EVENT");
  const funding = reasons.includes("FUNDING_EVENT");
  const technology = reasons.includes("TECHNOLOGY_EVENT");
  const policy = reasons.includes("POLICY_EVENT");
  const discoverySource = reasons.includes("INNOVATION_DISCOVERY_SOURCE");
  if (directProject && (listing || funding || technology || policy || discoverySource)) return true;
  if (institution && (listing || funding)) return true;
  if (broker && (listing || funding)) return true;
  if (discoverySource && (listing || funding)) return true;
  return false;
}

function innovationPriority(
  event: HomepageInnovationEvent,
  matched: InnovationCapitalMatchedObject[],
  reasons: string[],
): number {
  let score = 0;
  if (reasons.includes("LIFECYCLE_PROJECT")) score += 30;
  else if (reasons.includes("TRACKED_PROJECT")) score += 25;
  else if (reasons.includes("MATURE_CANDIDATE")) score += 20;
  if (reasons.includes("CAPITAL_INSTITUTION")) score += 12;
  if (reasons.includes("TARGET_BROKER")) score += 10;
  if (reasons.includes("LISTING_EVENT")) score += 30;
  if (reasons.includes("FUNDING_EVENT")) score += 25;
  if (reasons.includes("TECHNOLOGY_EVENT")) score += 12;
  if (reasons.includes("POLICY_EVENT")) score += 10;
  if (reasons.includes("PRIMARY_EVIDENCE")) score += 15;
  else if (reasons.includes("TRUSTED_EVIDENCE")) score += 7;
  if (reasons.includes("INNOVATION_DISCOVERY_SOURCE")) score += 8;
  score += Math.min(5, Math.max(0, Math.floor(Number(event.importance ?? 0) / 20)));
  score += Math.min(5, matched.length);
  return Math.min(100, score);
}

function articleEvents(payload: unknown): HomepageInnovationEvent[] {
  return list(record(payload).articles).map((raw) => {
    const row = record(raw);
    const source = record(row.source);
    return {
      id: text(row.id, 260),
      title: text(row.title, 600),
      summary: text(row.summary, 1_600),
      type: text(row.type, 120),
      sector: text(row.sector, 160),
      company: text(row.company, 240),
      sourceId: text(row.sourceId, 240),
      publishedAt: text(row.publishedAt, 80),
      importance: Number(row.importance) || 0,
      eventClusterId: text(row.eventClusterId, 240),
      mentionedCompanies: list(row.mentionedCompanies).map((value) => text(value, 240)).filter(Boolean),
      mentionedPeople: list(row.mentionedPeople).map((value) => text(value, 240)).filter(Boolean),
      matchedTrackingTerms: list(row.matchedTrackingTerms).map((value) => text(value, 240)).filter(Boolean),
      source: {
        name: text(source.name, 240),
        url: text(source.url, 1_600),
        level: text(source.level, 80),
        platform: text(source.platform, 120),
      },
    };
  }).filter((item) => item.id && item.source.url);
}

function rankedEvents(payload: unknown): HomepageInnovationEvent[] {
  return list(record(payload).items).map((raw) => {
    const row = record(raw);
    const entities = list(row.entities).map(record);
    const companies = entities
      .filter((entity) => text(entity.objectType, 40) === "company")
      .map((entity) => text(entity.name, 240))
      .filter(Boolean);
    const people = entities
      .filter((entity) => text(entity.objectType, 40) === "person")
      .map((entity) => text(entity.name, 240))
      .filter(Boolean);
    return {
      id: `ranked-intelligence:${text(row.id, 240)}`,
      title: text(row.title, 600),
      summary: text(row.summary, 1_600),
      type: list(row.eventTypes).map((value) => text(value, 80)).filter(Boolean).join(" / "),
      sector: text(list(row.tracks)[0], 160),
      company: companies[0] ?? "",
      sourceId: "ranked-intelligence",
      publishedAt: text(row.publishedAt, 80),
      importance: Number(row.score) || 0,
      eventClusterId: text(row.eventClusterId, 240),
      mentionedCompanies: companies,
      mentionedPeople: people,
      matchedTrackingTerms: list(row.tracks).map((value) => text(value, 160)).filter(Boolean),
      source: {
        name: text(row.source, 240),
        url: text(row.href, 1_600),
        level: "待交叉验证",
        platform: "Ranked Intelligence",
      },
    };
  }).filter((item) => item.id !== "ranked-intelligence:" && item.source.url);
}

function generatedAt(input: { articlesPayload: unknown; rankedPayload: unknown }): string {
  const values = [
    text(record(input.articlesPayload).generatedAt, 80),
    text(record(input.rankedPayload).generatedAt, 80),
  ].filter(Boolean);
  return values.sort().at(-1) ?? "";
}

export function buildInnovationCapitalFeedProjection(input: {
  articlesPayload: unknown;
  rankedPayload: unknown;
  watchlistPayload: unknown;
  lifecyclePayload: unknown;
  maturePayload: unknown;
  trackingSeedsPayload: unknown;
}): InnovationCapitalFeedProjection {
  const universe = buildUniverse(input);
  const events = [
    ...articleEvents(input.articlesPayload),
    ...rankedEvents(input.rankedPayload),
  ];
  const items: InnovationCapitalFeedItem[] = [];

  for (const event of events) {
    let matched = matchedObjectsForEvent(event, universe);
    const sourceId = text(event.sourceId, 240);
    const discoverySource =
      sourceId.startsWith("innovation-listing-")
      || sourceId.startsWith("innovation-capital-portfolio-");

    if (!matched.length && discoverySource && event.company) {
      matched = [{
        type: "discovered-company",
        name: text(event.company, 240),
      }];
    }

    const reasons = reasonCodes(event, matched);
    if (!qualifies(event, matched, reasons)) continue;

    items.push({
      eventId: event.id,
      sourceUrl: event.source.url,
      publishedAt: event.publishedAt ?? "",
      eventClusterId: event.eventClusterId ?? "",
      matchedObjects: matched,
      reasonCodes: reasons,
      evidenceTier: evidenceTier(event),
      innovationPriority: innovationPriority(event, matched, reasons),
    });
  }

  const deduped = new Map<string, InnovationCapitalFeedItem>();
  for (const item of items) {
    const key = item.eventId || urlKey(item.sourceUrl);
    const existing = deduped.get(key);
    if (!existing || item.innovationPriority > existing.innovationPriority) {
      deduped.set(key, item);
    }
  }

  const output = [...deduped.values()]
    .sort((left, right) =>
      right.publishedAt.localeCompare(left.publishedAt)
      || right.innovationPriority - left.innovationPriority
      || left.eventId.localeCompare(right.eventId))
    .slice(0, 240);

  return {
    schemaVersion: 1,
    generatedAt: generatedAt(input),
    universeAsOf: text(record(input.watchlistPayload).asOf, 40),
    eventCount: output.length,
    items: output,
  };
}

export function parseInnovationCapitalFeedProjection(
  value: unknown,
): InnovationCapitalFeedProjection {
  const root = record(value);
  const items = list(root.items).flatMap((raw): InnovationCapitalFeedItem[] => {
    const row = record(raw);
    const eventId = text(row.eventId, 260);
    const sourceUrl = text(row.sourceUrl, 1_600);
    if (!eventId || !sourceUrl) return [];
    const matchedObjects = list(row.matchedObjects).flatMap((candidate): InnovationCapitalMatchedObject[] => {
      const item = record(candidate);
      const type = text(item.type, 40) as InnovationCapitalObjectType;
      const name = text(item.name, 240);
      if (
        !name
        || ![
          "project",
          "lifecycle-project",
          "broker",
          "institution",
          "mature-candidate",
          "discovered-company",
        ].includes(type)
      ) return [];
      return [{
        type,
        name,
        ...(text(item.broker, 160) ? { broker: text(item.broker, 160) } : {}),
        ...(text(item.stage, 120) ? { stage: text(item.stage, 120) } : {}),
      }];
    });
    return [{
      eventId,
      sourceUrl,
      publishedAt: text(row.publishedAt, 80),
      eventClusterId: text(row.eventClusterId, 240),
      matchedObjects,
      reasonCodes: unique(list(row.reasonCodes).map((item) => text(item, 80)), 20),
      evidenceTier: text(row.evidenceTier, 40) === "primary"
        ? "primary"
        : text(row.evidenceTier, 40) === "trusted"
          ? "trusted"
          : "discovery",
      innovationPriority: Math.max(0, Math.min(100, Math.round(Number(row.innovationPriority) || 0))),
    }];
  });

  return {
    schemaVersion: 1,
    generatedAt: text(root.generatedAt, 80),
    universeAsOf: text(root.universeAsOf, 40),
    eventCount: items.length,
    items,
  };
}

export function buildHomepageInnovationCapitalIndex(
  rawProjection: unknown,
): HomepageInnovationCapitalIndex {
  const projection = parseInnovationCapitalFeedProjection(rawProjection);
  const byId = new Map<string, InnovationCapitalFeedItem>();
  const byUrl = new Map<string, InnovationCapitalFeedItem>();
  const byCluster = new Map<string, InnovationCapitalFeedItem>();
  for (const item of projection.items) {
    byId.set(item.eventId, item);
    const url = urlKey(item.sourceUrl);
    if (url && !byUrl.has(url)) byUrl.set(url, item);
    if (item.eventClusterId && !byCluster.has(item.eventClusterId)) {
      byCluster.set(item.eventClusterId, item);
    }
  }
  return { byId, byUrl, byCluster };
}

export function homepageInnovationCapitalAnnotation(
  event: HomepageInnovationEvent,
  index: HomepageInnovationCapitalIndex,
): InnovationCapitalFeedItem | null {
  return index.byId.get(event.id)
    ?? index.byUrl.get(urlKey(event.source.url))
    ?? (event.eventClusterId ? index.byCluster.get(event.eventClusterId) : undefined)
    ?? null;
}

export function matchesHomepageInnovationCapitalChannel(
  event: HomepageInnovationEvent,
  index: HomepageInnovationCapitalIndex,
): boolean {
  return homepageInnovationCapitalAnnotation(event, index) !== null;
}

export function homepageInnovationReasonLabels(
  item: InnovationCapitalFeedItem,
): string[] {
  return item.reasonCodes
    .map((code) => REASON_LABELS[code] ?? "")
    .filter(Boolean)
    .slice(0, 4);
}
