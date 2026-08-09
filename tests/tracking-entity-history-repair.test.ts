import assert from "node:assert/strict";
import test from "node:test";

import rawTrackingConfig from "../config/user_tracking.json";
import {
  HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES,
  repairHistoricalCompoundTrackingEntities,
} from "../lib/tracking-entity-history-repair";
import { findCompoundTrackingEntities } from "../lib/tracking-entity-integrity";
import type { UserTrackingConfig } from "../lib/user-tracking";

function currentConfig(): UserTrackingConfig {
  return structuredClone(rawTrackingConfig) as UserTrackingConfig;
}

test("historical compound inventory is frozen to the reviewed repair plan", () => {
  const issues = findCompoundTrackingEntities(currentConfig());
  assert.equal(issues.length, 12);
  assert.equal(issues.filter((issue) => issue.entityType === "person").length, 8);
  assert.equal(issues.filter((issue) => issue.entityType === "company").length, 4);
  assert.equal(
    new Set(issues.map((issue) => `${issue.entityType}:${issue.value}`)).size,
    6,
  );
  assert.equal(HISTORICAL_COMPOUND_ENTITY_REPAIR_RULES.length, 6);
});

test("historical repair removes every reviewed compound occurrence", () => {
  const result = repairHistoricalCompoundTrackingEntities(currentConfig());
  assert.deepEqual(result.audit, {
    detectedOccurrences: 12,
    appliedRules: 6,
    repairedOccurrences: 12,
    droppedParts: [
      {
        entityType: "company",
        value: "腾讯 / 元宝",
        parts: ["元宝"],
        rationale: "腾讯是公司，元宝是产品；本次只恢复公司字段，不把产品继续伪装成公司。",
      },
      {
        entityType: "company",
        value: "阿里云 / Qwen",
        parts: ["Qwen"],
        rationale: "阿里云是公司/业务主体，Qwen 是模型品牌；本次只恢复公司字段。",
      },
    ],
  });
  assert.deepEqual(findCompoundTrackingEntities(result.config), []);

  const ai = result.config.tracks.find((track) => track.slug === "ai");
  assert.ok(ai);
  for (const person of [
    "王慧文",
    "陈天桥",
    "Quoc Le",
    "Jeff Dean",
    "Sanjay Ghemawat",
    "Oriol Vinyals",
    "陶哲轩",
    "李飞飞",
    "Dawn Song",
  ]) {
    assert.ok(ai.people.includes(person), `missing repaired person ${person}`);
  }
  assert.ok(ai.sampleCompanies.includes("腾讯"));
  assert.ok(ai.sampleCompanies.includes("阿里云"));
  assert.ok(!ai.sampleCompanies.includes("元宝"));
  assert.ok(!ai.sampleCompanies.includes("Qwen"));
});

test("historical repair is idempotent after the reviewed migration is clean", () => {
  const first = repairHistoricalCompoundTrackingEntities(currentConfig());
  const second = repairHistoricalCompoundTrackingEntities(first.config);
  assert.deepEqual(second.config, first.config);
  assert.deepEqual(second.audit, {
    detectedOccurrences: 0,
    appliedRules: 0,
    repairedOccurrences: 0,
    droppedParts: [],
  });
});

test("historical repair refuses an unreviewed compound value", () => {
  const config = currentConfig();
  config.tracks[0].people.push("Alice、Bob");
  assert.throws(
    () => repairHistoricalCompoundTrackingEntities(config),
    /未在历史修复白名单中的复合实体/u,
  );
});

test("historical repair refuses reviewed values whose track distribution drifted", () => {
  const config = currentConfig();
  const ai = config.tracks.find((track) => track.slug === "ai");
  assert.ok(ai);
  ai.people = ai.people.filter((value) => value !== "王慧文、陈天桥、");
  assert.throws(
    () => repairHistoricalCompoundTrackingEntities(config),
    /历史复合实体分布已漂移/u,
  );
});
