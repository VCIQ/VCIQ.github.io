import {
  findCompoundTrackingEntities,
  type TrackingCompoundEntityIssue,
} from "@/lib/tracking-entity-integrity";
import type { UserTrackingConfig } from "@/lib/user-tracking";

export type HistoricalCompoundEntityRepairRule = {
  entityType: "company" | "person";
  value: string;
  expectedTrackSlugs: string[];
  replacements: string[];
  droppedParts: string[];
  rationale: string;
};

export type HistoricalCompoundEntityRepairAudit = {
  detectedOccurrences: number;
  appliedRules: number;
  repairedOccurrences: number;
  droppedParts: Array<{
    entityType: "company" | "person";
    value: string;
    parts: string[];
    rationale: string;
  }>;
};

export const HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES: HistoricalCompoundEntityRepairRule[] = [
  {
    entityType: "person",
    value: "王慧文、陈天桥、",
    expectedTrackSlugs: ["ai", "track-1ccjq49"],
    replacements: ["王慧文", "陈天桥"],
    droppedParts: [],
    rationale: "两个独立人物被中文顿号合并，尾部分隔符不承载实体语义。",
  },
  {
    entityType: "person",
    value: "Quoc Le、Jeff Dean、Sanjay Ghemawat、Quoc Le、Oriol Vinyals",
    expectedTrackSlugs: ["ai", "robotics", "ai-2"],
    replacements: ["Quoc Le", "Jeff Dean", "Sanjay Ghemawat", "Oriol Vinyals"],
    droppedParts: [],
    rationale: "五段均为人物，其中 Quoc Le 在原复合值内重复一次；恢复时去重。",
  },
  {
    entityType: "person",
    value: "Jeff Dean、陶哲轩、李飞飞、Dawn Song、Oriol Vinyals",
    expectedTrackSlugs: ["ai", "robotics", "ai-2"],
    replacements: ["Jeff Dean", "陶哲轩", "李飞飞", "Dawn Song", "Oriol Vinyals"],
    droppedParts: [],
    rationale: "五段均为独立人物，按原顺序恢复为原子实体。",
  },
  {
    entityType: "company",
    value: "Aliya Capital Partners、Atreides Management、Artisan Partners、Battery Ventures、Diagonal Capital、Intel Capital、Key1 Capital",
    expectedTrackSlugs: ["semiconductor", "track-1ccjq49"],
    replacements: [
      "Aliya Capital Partners",
      "Atreides Management",
      "Artisan Partners",
      "Battery Ventures",
      "Diagonal Capital",
      "Intel Capital",
      "Key1 Capital",
    ],
    droppedParts: [],
    rationale: "七个独立投资机构被作为一个公司字段值写入，按原顺序拆分。",
  },
  {
    entityType: "company",
    value: "腾讯 / 元宝",
    expectedTrackSlugs: ["ai"],
    replacements: ["腾讯"],
    droppedParts: ["元宝"],
    rationale: "腾讯是公司，元宝是产品；本次只恢复公司字段，不把产品继续伪装成公司。",
  },
  {
    entityType: "company",
    value: "阿里云 / Qwen",
    expectedTrackSlugs: ["ai"],
    replacements: ["阿里云"],
    droppedParts: ["Qwen"],
    rationale: "阿里云是公司/业务主体，Qwen 是模型品牌；本次只恢复公司字段。",
  },
];

function normalizeKey(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .toLocaleLowerCase("zh-CN");
}

function repairRuleKey(
  entityType: "company" | "person",
  value: string,
): string {
  return `${entityType}:${normalizeKey(value)}`;
}

function sorted(values: string[]): string[] {
  return [...values].sort((a, b) => a.localeCompare(b));
}

function sameStrings(left: string[], right: string[]): boolean {
  const a = sorted(left);
  const b = sorted(right);
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function stableUnique(values: string[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const normalized = value.normalize("NFKC").replace(/\s+/gu, " ").trim();
    const key = normalizeKey(normalized);
    if (!normalized || seen.has(key)) continue;
    seen.add(key);
    result.push(normalized);
  }
  return result;
}

function validateRepairPlan(issues: TrackingCompoundEntityIssue[]): void {
  const rules = new Map(
    HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES.map((rule) => [
      repairRuleKey(rule.entityType, rule.value),
      rule,
    ]),
  );

  for (const issue of issues) {
    const key = repairRuleKey(issue.entityType, issue.value);
    if (!rules.has(key)) {
      throw new Error(
        `发现未在历史修复白名单中的复合实体：${issue.trackSlug}/${issue.entityType}/${issue.value}`,
      );
    }
  }

  for (const rule of HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES) {
    const key = repairRuleKey(rule.entityType, rule.value);
    const actualTrackSlugs = issues
      .filter((issue) => repairRuleKey(issue.entityType, issue.value) === key)
      .map((issue) => issue.trackSlug);
    if (!sameStrings(actualTrackSlugs, rule.expectedTrackSlugs)) {
      throw new Error(
        `历史复合实体分布已漂移：${rule.value}；预期 ${rule.expectedTrackSlugs.join(", ")}；实际 ${actualTrackSlugs.join(", ") || "无"}`,
      );
    }
  }
}

export function repairHistoricalCompoundTrackingEntities(
  config: UserTrackingConfig,
): { config: UserTrackingConfig; audit: HistoricalCompoundEntityRepairAudit } {
  const issues = findCompoundTrackingEntities(config);
  if (!issues.length) {
    return {
      config: structuredClone(config),
      audit: {
        detectedOccurrences: 0,
        appliedRules: 0,
        repairedOccurrences: 0,
        droppedParts: [],
      },
    };
  }

  validateRepairPlan(issues);
  const rules = new Map(
    HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES.map((rule) => [
      repairRuleKey(rule.entityType, rule.value),
      rule,
    ]),
  );
  const next = structuredClone(config);
  let repairedOccurrences = 0;

  for (const track of next.tracks) {
    const fields = [
      { field: "people" as const, entityType: "person" as const },
      { field: "sampleCompanies" as const, entityType: "company" as const },
    ];

    for (const { field, entityType } of fields) {
      const rebuilt: string[] = [];
      for (const value of track[field]) {
        const rule = rules.get(repairRuleKey(entityType, value));
        if (!rule) {
          rebuilt.push(value);
          continue;
        }
        rebuilt.push(...rule.replacements);
        repairedOccurrences += 1;
      }
      track[field] = stableUnique(rebuilt);
    }
  }

  const remaining = findCompoundTrackingEntities(next);
  if (remaining.length) {
    throw new Error(
      `历史复合实体修复后仍有 ${remaining.length} 个复合值，拒绝生成迁移结果。`,
    );
  }

  return {
    config: next,
    audit: {
      detectedOccurrences: issues.length,
      appliedRules: HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES.length,
      repairedOccurrences,
      droppedParts: HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES.filter(
        (rule) => rule.droppedParts.length > 0,
      ).map((rule) => ({
        entityType: rule.entityType,
        value: rule.value,
        parts: [...rule.droppedParts],
        rationale: rule.rationale,
      })),
    },
  };
}
