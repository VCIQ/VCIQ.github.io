import assert from "node:assert/strict";
import test from "node:test";

import rawTrackingConfig from "../config/user_tracking.json";
import {
  CURRENT_COMPOUND_REPAIR_RULES,
  buildCurrentCompoundTrackingRepairPlan,
} from "../lib/tracking-compound-entity-repair-plan";
import { inventoryCompoundTrackingEntities } from "../lib/tracking-compound-entity-inventory";
import { normalizeTrackingConfig } from "../lib/user-tracking";

test("current reviewed repair plan removes every inventoried compound without mutating input", () => {
  const config = normalizeTrackingConfig(rawTrackingConfig);
  const beforeText = JSON.stringify(config);
  const before = inventoryCompoundTrackingEntities(config);
  const result = buildCurrentCompoundTrackingRepairPlan(config);
  const after = inventoryCompoundTrackingEntities(result.config);

  assert.equal(JSON.stringify(config), beforeText);
  assert.equal(before.occurrenceCount, 8);
  assert.equal(before.uniqueValueCount, 6);
  assert.equal(result.audit.beforeOccurrences, 8);
  assert.equal(result.audit.beforeUniqueValues, 6);
  assert.equal(result.audit.afterOccurrences, 0);
  assert.equal(result.audit.afterUniqueValues, 0);
  assert.equal(after.occurrenceCount, 0);
  assert.equal(result.audit.appliedRuleCount, CURRENT_COMPOUND_REPAIR_RULES.length);
  assert.equal(result.audit.repairedOccurrenceCount, 8);
  assert.equal(result.audit.affectedTrackCount, 5);
});

test("company-product compounds preserve the company field and transfer product names to keywords", () => {
  const config = normalizeTrackingConfig(rawTrackingConfig);
  const { config: next } = buildCurrentCompoundTrackingRepairPlan(config);
  const ai = next.tracks.find((track) => track.slug === "ai");
  assert.ok(ai);

  assert.ok(ai.sampleCompanies.includes("腾讯"));
  assert.ok(ai.sampleCompanies.includes("阿里云"));
  assert.ok(!ai.sampleCompanies.includes("腾讯 / 元宝"));
  assert.ok(!ai.sampleCompanies.includes("阿里云 / Qwen"));
  assert.ok(ai.keywords.includes("元宝"));
  assert.ok(ai.keywords.includes("Qwen"));
});

test("person and institution lists become stable deduplicated atomic entities", () => {
  const config = normalizeTrackingConfig(rawTrackingConfig);
  const { config: next } = buildCurrentCompoundTrackingRepairPlan(config);

  const robotics = next.tracks.find((track) => track.slug === "robotics");
  const aiSafety = next.tracks.find((track) => track.slug === "ai-2");
  const venture = next.tracks.find((track) => track.slug === "track-1ccjq49");
  const semiconductor = next.tracks.find((track) => track.slug === "semiconductor");
  assert.ok(robotics && aiSafety && venture && semiconductor);

  for (const track of [robotics, aiSafety]) {
    for (const person of ["Quoc Le", "Jeff Dean", "Sanjay Ghemawat", "Oriol Vinyals", "陶哲轩", "李飞飞", "Dawn Song"]) {
      assert.equal(track.people.filter((value) => value === person).length, 1, `${track.slug}/${person}`);
    }
  }
  assert.ok(venture.people.includes("王慧文"));
  assert.ok(venture.people.includes("陈天桥"));

  for (const institution of [
    "Aliya Capital Partners",
    "Atreides Management",
    "Artisan Partners",
    "Battery Ventures",
    "Diagonal Capital",
    "Intel Capital",
    "Key1 Capital",
  ]) {
    assert.equal(
      semiconductor.sampleCompanies.filter((value) => value === institution).length,
      1,
      institution,
    );
  }
});

test("repair plan fails closed when the frozen current inventory distribution drifts", () => {
  const config = normalizeTrackingConfig(rawTrackingConfig);
  const changed = structuredClone(config);
  const robotics = changed.tracks.find((track) => track.slug === "robotics");
  assert.ok(robotics);
  robotics.people = robotics.people.filter(
    (value) => value !== "Jeff Dean、陶哲轩、李飞飞、Dawn Song、Oriol Vinyals",
  );

  assert.throws(
    () => buildCurrentCompoundTrackingRepairPlan(changed),
    /复合值分布已漂移/,
  );
});
