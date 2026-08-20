import { inventoryCompoundTrackingEntities } from "@/lib/tracking-compound-entity-inventory";
import {
  validateTrackingKeyword,
  type TrackingTrack,
  type UserTrackingConfig,
} from "@/lib/user-tracking";

export type TrackingCompoundRepairRule = {
  entityType: "company" | "person";
  value: string;
  expectedTrackSlugs: string[];
  replacements: string[];
  keywordTransfers: string[];
  rationale: string;
};

export type TrackingCompoundRepairChange = {
  trackSlug: string;
  trackName: string;
  entityType: "company" | "person";
  value: string;
  replacements: string[];
  keywordTransfers: string[];
};

export type TrackingCompoundRepairPlanAudit = {
  mode: "read-only-repair-plan";
  beforeOccurrences: number;
  beforeUniqueValues: number;
  afterOccurrences: number;
  afterUniqueValues: number;
  appliedRuleCount: number;
  repairedOccurrenceCount: number;
  affectedTrackCount: number;
  changes: TrackingCompoundRepairChange[];
};

const INVESTOR_LIST =
  "Aliya Capital Partners、Atreides Management、Artisan Partners、Battery Ventures、Diagonal Capital、Intel Capital、Key1 Capital";
const PERSON_PAIR = "王慧文、陈天桥、";
const PERSON_RESEARCH = "Jeff Dean、陶哲轩、李飞飞、Dawn Song、Oriol Vinyals";
const PERSON_GOOGLE = "Quoc Le、Jeff Dean、Sanjay Ghemawat、Quoc Le、Oriol Vinyals";

export const CURRENT_COMPOUND_REPAIR_RULES: TrackingCompoundRepairRule[] = [
  {
    entityType: "company",
    value: "阿里云 / Qwen",
    expectedTrackSlugs: ["ai"],
    replacements: ["阿里云"],
    keywordTransfers: ["Qwen"],
    rationale: "阿里云保留为公司；Qwen 是模型品牌，转入关键词以保留原追踪意图。",
  },
  {
    entityType: "company",
    value: "腾讯 / 元宝",
    expectedTrackSlugs: ["ai"],
    replacements: ["腾讯"],
    keywordTransfers: ["元宝"],
    rationale: "腾讯保留为公司；元宝是产品，转入关键词以保留原追踪意图。",
  },
  {
    entityType: "company",
    value: INVESTOR_LIST,
    expectedTrackSlugs: ["semiconductor"],
    replacements: [
      "Aliya Capital Partners",
      "Atreides Management",
      "Artisan Partners",
      "Battery Ventures",
      "Diagonal Capital",
      "Intel Capital",
      "Key1 Capital",
    ],
    keywordTransfers: [],
    rationale: "七个独立投资机构被写成一个 company 值，按原顺序拆分。",
  },
  {
    entityType: "person",
    value: PERSON_PAIR,
    expectedTrackSlugs: ["track-1ccjq49"],
    replacements: ["王慧文", "陈天桥"],
    keywordTransfers: [],
    rationale: "两个独立人物被合并，拆为两个原子人物。",
  },
  {
    entityType: "person",
    value: PERSON_RESEARCH,
    expectedTrackSlugs: ["robotics", "ai-2"],
    replacements: ["Jeff Dean", "陶哲轩", "李飞飞", "Dawn Song", "Oriol Vinyals"],
    keywordTransfers: [],
    rationale: "五个独立人物被合并，按原顺序拆分。",
  },
  {
    entityType: "person",
    value: PERSON_GOOGLE,
    expectedTrackSlugs: ["robotics", "ai-2"],
    replacements: ["Quoc Le", "Jeff Dean", "Sanjay Ghemawat", "Oriol Vinyals"],
    keywordTransfers: [],
    rationale: "原值包含五段人物且 Quoc Le 重复；拆分时去重。",
  },
];

function normalizeKey(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .toLocaleLowerCase("zh-CN");
}

function ruleKey(entityType: "company" | "person", value: string): string {
  return `${entityType}:${normalizeKey(value)}`;
}

function stableUnique(values: string[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw.normalize("NFKC").replace(/\s+/gu, " ").trim();
    const key = normalizeKey(value);
    if (!value || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result;
}

function sorted(values: string[]): string[] {
  return [...values].sort((left, right) => left.localeCompare(right));
}

function sameSet(left: string[], right: string[]): boolean {
  const a = sorted(left);
  const b = sorted(right);
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function validateRules(config: UserTrackingConfig): void {
  const inventory = inventoryCompoundTrackingEntities(config);
  const rules = new Map(
    CURRENT_COMPOUND_REPAIR_RULES.map((rule) => [ruleKey(rule.entityType, rule.value), rule]),
  );

  for (const row of inventory.uniqueValues) {
    const key = ruleKey(row.entityType, row.value);
    const rule = rules.get(key);
    if (!rule) {
      throw new Error(`当前 inventory 出现未审核复合值：${row.entityType}/${row.value}`);
    }
    if (!sameSet(row.trackSlugs, rule.expectedTrackSlugs)) {
      throw new Error(
        `复合值分布已漂移：${row.value}；预期 ${rule.expectedTrackSlugs.join(", ")}；实际 ${row.trackSlugs.join(", ")}`,
      );
    }
  }

  for (const rule of CURRENT_COMPOUND_REPAIR_RULES) {
    const exists = inventory.uniqueValues.some(
      (row) => ruleKey(row.entityType, row.value) === ruleKey(rule.entityType, rule.value),
    );
    if (!exists) {
      throw new Error(`审核规则已过期或 inventory 已变化：${rule.entityType}/${rule.value}`);
    }
    for (const keyword of rule.keywordTransfers) {
      const parsed = validateTrackingKeyword(keyword);
      if (!parsed.valid) {
        throw new Error(`迁移关键词无效：${keyword}；${parsed.message}`);
      }
    }
  }
}

function rebuildField(
  track: TrackingTrack,
  field: "people" | "sampleCompanies",
  entityType: "person" | "company",
  ruleMap: Map<string, TrackingCompoundRepairRule>,
  changes: TrackingCompoundRepairChange[],
): { values: string[]; keywordTransfers: string[] } {
  const rebuilt: string[] = [];
  const keywordTransfers: string[] = [];

  for (const value of track[field]) {
    const rule = ruleMap.get(ruleKey(entityType, value));
    if (!rule) {
      rebuilt.push(value);
      continue;
    }
    rebuilt.push(...rule.replacements);
    keywordTransfers.push(...rule.keywordTransfers);
    changes.push({
      trackSlug: track.slug,
      trackName: track.name,
      entityType,
      value,
      replacements: [...rule.replacements],
      keywordTransfers: [...rule.keywordTransfers],
    });
  }

  return { values: stableUnique(rebuilt), keywordTransfers: stableUnique(keywordTransfers) };
}

export function buildCurrentCompoundTrackingRepairPlan(
  config: UserTrackingConfig,
): { config: UserTrackingConfig; audit: TrackingCompoundRepairPlanAudit } {
  validateRules(config);
  const before = inventoryCompoundTrackingEntities(config);
  const next = structuredClone(config);
  const ruleMap = new Map(
    CURRENT_COMPOUND_REPAIR_RULES.map((rule) => [ruleKey(rule.entityType, rule.value), rule]),
  );
  const changes: TrackingCompoundRepairChange[] = [];

  for (const track of next.tracks) {
    const people = rebuildField(track, "people", "person", ruleMap, changes);
    const companies = rebuildField(track, "sampleCompanies", "company", ruleMap, changes);
    track.people = people.values;
    track.sampleCompanies = companies.values;
    track.keywords = stableUnique([
      ...track.keywords,
      ...people.keywordTransfers,
      ...companies.keywordTransfers,
    ]);
  }

  const after = inventoryCompoundTrackingEntities(next);
  if (after.occurrenceCount !== 0) {
    throw new Error(`迁移计划执行后仍有 ${after.occurrenceCount} 个复合实体，拒绝生成计划。`);
  }

  return {
    config: next,
    audit: {
      mode: "read-only-repair-plan",
      beforeOccurrences: before.occurrenceCount,
      beforeUniqueValues: before.uniqueValueCount,
      afterOccurrences: after.occurrenceCount,
      afterUniqueValues: after.uniqueValueCount,
      appliedRuleCount: CURRENT_COMPOUND_REPAIR_RULES.length,
      repairedOccurrenceCount: changes.length,
      affectedTrackCount: new Set(changes.map((row) => row.trackSlug)).size,
      changes,
    },
  };
}
