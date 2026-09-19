import { institutionTrackingMatches } from "@/lib/institution-tracking-identity";
import rawDecisions from "@/config/entity_resolution_decisions.json";
import { people as catalogPeople } from "@/lib/catalog-data";
import { companyRegistryEntries } from "@/lib/company-registry";
import { userTrackingConfig } from "@/lib/user-tracking";

export type EntityResolutionEntityType = "company" | "person" | "topic";
export type EntityResolutionStatus = "resolved" | "review" | "rejected";
export type EntityResolutionConfidence = "verified" | "high" | "medium" | "low";
export type EntityResolutionSource =
  | "human-decision"
  | "company-registry"
  | "institution-directory"
  | "people-registry"
  | "tracking-taxonomy"
  | "source-context"
  | "explicit-type"
  | "unresolved";

export type EntityResolutionDecision = {
  status: EntityResolutionStatus;
  requestedType: EntityResolutionEntityType;
  entityType: EntityResolutionEntityType;
  canonicalName: string;
  targetId: string;
  aliases: string[];
  confidence: EntityResolutionConfidence;
  note: string;
  reviewedBy: string;
  reviewedAt: string;
};

export type EntityResolutionManifest = {
  schemaVersion: 1;
  generatedAt: string;
  decisions: Record<string, EntityResolutionDecision>;
};

export type EntityResolutionSourceContext = {
  title?: string;
  summary?: string;
  sourceName?: string;
  channel?: string;
  channelLabel?: string;
  eventType?: string;
  url?: string;
};

export type TrackingEntityResolution = {
  status: EntityResolutionStatus;
  requestedType: EntityResolutionEntityType;
  entityType: EntityResolutionEntityType;
  canonicalName: string;
  targetId: string;
  confidence: EntityResolutionConfidence;
  source: EntityResolutionSource;
  reason: string;
  decisionKey: string;
  reclassified: boolean;
};

export type ResolveTrackingEntityInput = {
  requestedType: EntityResolutionEntityType;
  name: string;
  source?: EntityResolutionSourceContext;
  manifest?: EntityResolutionManifest;
};

const ENTITY_TYPES: EntityResolutionEntityType[] = ["company", "person", "topic"];
const STATUSES: EntityResolutionStatus[] = ["resolved", "review", "rejected"];
const CONFIDENCES: EntityResolutionConfidence[] = ["verified", "high", "medium", "low"];

function text(value: unknown, limit = 1_200) {
  return String(value ?? "").normalize("NFKC").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function unique(values: unknown, limit = 40) {
  if (!Array.isArray(values)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = text(raw, 240);
    const key = normalizeEntityResolutionIdentity(value);
    if (!value || !key || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

export function normalizeEntityResolutionIdentity(value: unknown) {
  return text(value, 300)
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function normalizeDecision(value: unknown): EntityResolutionDecision | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const status = STATUSES.includes(row.status as EntityResolutionStatus)
    ? (row.status as EntityResolutionStatus)
    : null;
  const requestedType = ENTITY_TYPES.includes(row.requestedType as EntityResolutionEntityType)
    ? (row.requestedType as EntityResolutionEntityType)
    : "company";
  const entityType = ENTITY_TYPES.includes(row.entityType as EntityResolutionEntityType)
    ? (row.entityType as EntityResolutionEntityType)
    : requestedType;
  const canonicalName = text(row.canonicalName, 160);
  if (!status || !canonicalName) return null;
  return {
    status,
    requestedType,
    entityType,
    canonicalName,
    targetId: text(row.targetId, 240),
    aliases: unique(row.aliases, 30),
    confidence: CONFIDENCES.includes(row.confidence as EntityResolutionConfidence)
      ? (row.confidence as EntityResolutionConfidence)
      : status === "resolved"
        ? "verified"
        : "low",
    note: text(row.note, 600),
    reviewedBy: text(row.reviewedBy, 120),
    reviewedAt: text(row.reviewedAt, 80),
  };
}

export function normalizeEntityResolutionManifest(value: unknown): EntityResolutionManifest {
  const row = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const rawDecisions = row.decisions && typeof row.decisions === "object"
    ? (row.decisions as Record<string, unknown>)
    : {};
  const decisions: Record<string, EntityResolutionDecision> = {};
  for (const [rawKey, rawValue] of Object.entries(rawDecisions)) {
    const decision = normalizeDecision(rawValue);
    const key = normalizeEntityResolutionIdentity(rawKey || decision?.canonicalName);
    if (!key || !decision) continue;
    decisions[key] = decision;
  }
  return {
    schemaVersion: 1,
    generatedAt: text(row.generatedAt, 80),
    decisions,
  };
}

export const entityResolutionDecisionManifest = normalizeEntityResolutionManifest(rawDecisions);

function addIndex<T>(index: Map<string, T[]>, alias: string, value: T) {
  const key = normalizeEntityResolutionIdentity(alias);
  if (!key) return;
  const values = index.get(key) ?? [];
  if (!values.includes(value)) index.set(key, [...values, value]);
}

const companyIndex = new Map<string, typeof companyRegistryEntries>();
for (const company of companyRegistryEntries) {
  for (const alias of [company.name, company.englishName ?? "", company.slug, ...company.aliases]) {
    addIndex(companyIndex, alias, company);
  }
}

type ResolutionPerson = {
  slug: string;
  name: string;
  englishName?: string;
  aliases?: string[];
};

function configuredPersonName(raw: string) {
  const value = text(raw, 160);
  const base = text(value.replace(/\s+@[A-Za-z0-9_]+$/u, ""), 160);
  if (!base || base.startsWith("The ")) return "";
  if (/[\u3400-\u9fff]/u.test(base)) {
    return /^[\u3400-\u9fff·•]{2,8}$/u.test(base) ? base : "";
  }
  const parts = base.split(/\s+/u);
  if (parts.length < 2 || parts.length > 5) return "";
  return parts.every((part) => /^[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)*$/u.test(part))
    ? base
    : "";
}

const personIndex = new Map<string, ResolutionPerson[]>();
for (const person of catalogPeople) {
  for (const alias of [person.name, person.englishName, person.slug]) {
    addIndex(personIndex, alias, person);
  }
}
for (const track of userTrackingConfig.tracks) {
  for (const rawName of track.people) {
    const canonicalName = configuredPersonName(rawName);
    const key = normalizeEntityResolutionIdentity(canonicalName);
    if (!canonicalName || !key || personIndex.has(key)) continue;
    const person: ResolutionPerson = {
      slug: key,
      name: canonicalName,
      englishName: canonicalName,
      aliases: [rawName],
    };
    for (const alias of [canonicalName, rawName]) {
      addIndex(personIndex, alias, person);
    }
  }
}

const topicIndex = new Map<string, string[]>();
for (const track of userTrackingConfig.tracks) {
  for (const alias of [track.name, ...track.keywords]) {
    const value = text(alias, 160);
    if (!value) continue;
    addIndex(topicIndex, value, value);
  }
}

function decisionIndex(manifest: EntityResolutionManifest) {
  const index = new Map<string, EntityResolutionDecision>();
  for (const [key, decision] of Object.entries(manifest.decisions)) {
    index.set(key, decision);
    for (const alias of [decision.canonicalName, ...decision.aliases]) {
      const aliasKey = normalizeEntityResolutionIdentity(alias);
      if (aliasKey) index.set(aliasKey, decision);
    }
  }
  return index;
}

function sourceText(source: EntityResolutionSourceContext | undefined) {
  if (!source) return "";
  return text(
    [
      source.title,
      source.summary,
      source.eventType,
      source.sourceName,
      source.channel,
      source.channelLabel,
      source.url,
    ].join(" "),
    4_000,
  );
}

function contextWindow(context: string, name: string) {
  const normalizedContext = context.toLocaleLowerCase("zh-CN");
  const normalizedName = text(name, 200).toLocaleLowerCase("zh-CN");
  const index = normalizedContext.indexOf(normalizedName);
  if (index < 0) return "";
  return context.slice(Math.max(0, index - 90), Math.min(context.length, index + normalizedName.length + 90));
}

const COMPANY_CUES = /公司|企业|集团|平台|实验室|研究院|基金|资本|创投|startup|company|platform|labs?\b|technolog(?:y|ies)\b|systems?\b|capital\b|ventures?\b|foundation\b|inc\.?\b|corp(?:oration)?\b|ltd\.?\b/iu;
const PERSON_CUES = /创始人|联合创始人|CEO|CTO|CFO|董事|高管|教授|研究员|工程师|作者|大佬|先锋|先生|女士|founder|executive|professor|researcher|engineer|author/iu;
const TOPIC_CUES = /编程语言|语言|框架|协议|标准|技术|算法|模型|芯片架构|数据库|开源项目|软件包|工具链|programming language|framework|protocol|standard|technology|algorithm|model|library|package|toolchain/iu;
const COMPANY_NAME_CUES = /(?:\b(?:Inc|Corp|Corporation|Ltd|LLC|Labs|Technologies|Systems|Capital|Ventures|Foundation)\b|公司|集团|资本|基金|科技)$/iu;

function result(
  input: ResolveTrackingEntityInput,
  patch: Omit<TrackingEntityResolution, "requestedType" | "decisionKey" | "reclassified">,
): TrackingEntityResolution {
  const decisionKey = normalizeEntityResolutionIdentity(input.name);
  return {
    ...patch,
    requestedType: input.requestedType,
    decisionKey,
    reclassified: patch.entityType !== input.requestedType,
  };
}

export function resolveTrackingEntity(input: ResolveTrackingEntityInput): TrackingEntityResolution {
  const requestedType = ENTITY_TYPES.includes(input.requestedType) ? input.requestedType : "company";
  const name = text(input.name, 160);
  const normalizedInput = { ...input, requestedType, name };
  const key = normalizeEntityResolutionIdentity(name);
  if (!key) {
    return result(normalizedInput, {
      status: "rejected",
      entityType: requestedType,
      canonicalName: name,
      targetId: "",
      confidence: "low",
      source: "unresolved",
      reason: "名称为空或无法形成稳定实体键。",
    });
  }

  const manifest = input.manifest ?? entityResolutionDecisionManifest;
  const reviewed = decisionIndex(manifest).get(key);
  if (reviewed) {
    return result(normalizedInput, {
      status: reviewed.status,
      entityType: reviewed.entityType,
      canonicalName: reviewed.canonicalName,
      targetId: reviewed.targetId,
      confidence: reviewed.confidence,
      source: "human-decision",
      reason: reviewed.note || "复用版本化人工解析决定。",
    });
  }

  const companies = companyIndex.get(key) ?? [];
  if (companies.length === 1) {
    const company = companies[0];
    return result(normalizedInput, {
      status: "resolved",
      entityType: "company",
      canonicalName: company.name,
      targetId: `company:${company.slug}`,
      confidence: "verified",
      source: "company-registry",
      reason: "名称唯一命中正式公司注册表。",
    });
  }
  if (companies.length > 1) {
    return result(normalizedInput, {
      status: "review",
      entityType: requestedType,
      canonicalName: name,
      targetId: "",
      confidence: "low",
      source: "company-registry",
      reason: "名称同时命中多个正式公司别名，需要人工消歧。",
    });
  }

  const persons = personIndex.get(key) ?? [];
  if (persons.length === 1) {
    const person = persons[0];
    return result(normalizedInput, {
      status: "resolved",
      entityType: "person",
      canonicalName: person.name,
      targetId: `person:${person.slug}`,
      confidence: "high",
      source: "people-registry",
      reason: "名称唯一命中正式人物目录。",
    });
  }
  if (persons.length > 1) {
    return result(normalizedInput, {
      status: "review",
      entityType: requestedType,
      canonicalName: name,
      targetId: "",
      confidence: "low",
      source: "people-registry",
      reason: "名称同时命中多个人物别名，需要人工消歧。",
    });
  }

  if (requestedType === "company") {
    const matches = institutionTrackingMatches(name);
    if (matches.length) {
      const unique = matches.length === 1;
      return result(normalizedInput, {
        status: unique ? "resolved" : "review", entityType: "company",
        canonicalName: unique ? matches[0].name : name,
        targetId: unique ? matches[0].targetId : "", confidence: unique ? "verified" : "low",
        source: "institution-directory",
        reason: unique ? "名称唯一命中已核验投资机构目录；仅解析机构身份，不代表公司档案发布。" : "名称命中多个投资机构，需要人工消歧。",
      });
    }
  }
  const topics = topicIndex.get(key) ?? [];
  if (topics.length === 1) {
    return result(normalizedInput, {
      status: "resolved",
      entityType: "topic",
      canonicalName: topics[0],
      targetId: `topic:${key}`,
      confidence: "high",
      source: "tracking-taxonomy",
      reason: "名称唯一命中已审核追踪赛道或关键词。",
    });
  }

  if (requestedType === "person" || requestedType === "topic") {
    return result(normalizedInput, {
      status: "resolved",
      entityType: requestedType,
      canonicalName: name,
      targetId: `${requestedType}:${key}`,
      confidence: "medium",
      source: "explicit-type",
      reason: `管理员显式选择“${requestedType === "person" ? "人物" : "技术／主题"}”，且未与正式目录冲突。`,
    });
  }

  const context = sourceText(input.source);
  const local = contextWindow(context, name);
  if (PERSON_CUES.test(local) || TOPIC_CUES.test(local)) {
    return result(normalizedInput, {
      status: "review",
      entityType: requestedType,
      canonicalName: name,
      targetId: "",
      confidence: "low",
      source: "source-context",
      reason: PERSON_CUES.test(local)
        ? "原文邻近语境更像人物，不能直接作为公司写入。"
        : "原文邻近语境更像技术、项目或工具，不能直接作为公司写入。",
    });
  }
  if (COMPANY_CUES.test(local) || COMPANY_NAME_CUES.test(name)) {
    return result(normalizedInput, {
      status: "resolved",
      entityType: "company",
      canonicalName: name,
      targetId: `company-candidate:${key}`,
      confidence: "medium",
      source: "source-context",
      reason: "原文邻近语境存在公司、企业或平台表述，可进入候选审核。",
    });
  }

  return result(normalizedInput, {
    status: "review",
    entityType: requestedType,
    canonicalName: name,
    targetId: "",
    confidence: "low",
    source: "unresolved",
    reason: "缺少正式目录命中或明确公司语境，暂存到实体解析审核队列。",
  });
}

export function normalizeTrackingEntityResolution(value: unknown): TrackingEntityResolution | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const status = STATUSES.includes(row.status as EntityResolutionStatus)
    ? (row.status as EntityResolutionStatus)
    : null;
  const requestedType = ENTITY_TYPES.includes(row.requestedType as EntityResolutionEntityType)
    ? (row.requestedType as EntityResolutionEntityType)
    : null;
  const entityType = ENTITY_TYPES.includes(row.entityType as EntityResolutionEntityType)
    ? (row.entityType as EntityResolutionEntityType)
    : null;
  const canonicalName = text(row.canonicalName, 160);
  if (!status || !requestedType || !entityType || !canonicalName) return undefined;
  return {
    status,
    requestedType,
    entityType,
    canonicalName,
    targetId: text(row.targetId, 240),
    confidence: CONFIDENCES.includes(row.confidence as EntityResolutionConfidence)
      ? (row.confidence as EntityResolutionConfidence)
      : "low",
    source: [
      "human-decision",
      "company-registry",
      "institution-directory",
      "people-registry",
      "tracking-taxonomy",
      "source-context",
      "explicit-type",
      "unresolved",
    ].includes(String(row.source))
      ? (row.source as EntityResolutionSource)
      : "unresolved",
    reason: text(row.reason, 600),
    decisionKey: normalizeEntityResolutionIdentity(row.decisionKey || canonicalName),
    reclassified: Boolean(row.reclassified ?? entityType !== requestedType),
  };
}
