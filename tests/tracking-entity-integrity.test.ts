import assert from "node:assert/strict";
import test from "node:test";

import {
  assertNoNewCompoundTrackingEntities,
  findNewCompoundTrackingEntities,
  splitCompoundTrackingEntityName,
} from "../lib/tracking-entity-integrity";
import type { UserTrackingConfig } from "../lib/user-tracking";

function config(): UserTrackingConfig {
  return {
    schemaVersion: 1,
    tracks: [
      {
        slug: "ai",
        name: "AI / AGI",
        enabled: true,
        custom: false,
        keywords: [],
        people: ["Quoc Le、Jeff Dean"],
        sampleCompanies: ["腾讯 / 元宝"],
      },
    ],
    listedCompanies: [],
    sources: [],
  };
}

function clone(value: UserTrackingConfig): UserTrackingConfig {
  return JSON.parse(JSON.stringify(value)) as UserTrackingConfig;
}

test("compound entity splitter catches high-confidence person and company lists", () => {
  assert.deepEqual(splitCompoundTrackingEntityName("Sam Altman、Demis Hassabis"), [
    "Sam Altman",
    "Demis Hassabis",
  ]);
  assert.deepEqual(splitCompoundTrackingEntityName("OpenAI，Anthropic"), [
    "OpenAI",
    "Anthropic",
  ]);
  assert.deepEqual(splitCompoundTrackingEntityName("腾讯 / 元宝"), ["腾讯", "元宝"]);
  assert.deepEqual(splitCompoundTrackingEntityName("OpenAI 与 Anthropic"), [
    "OpenAI",
    "Anthropic",
  ]);
});

test("single legal-looking names are not split", () => {
  assert.deepEqual(splitCompoundTrackingEntityName("Procter & Gamble"), []);
  assert.deepEqual(splitCompoundTrackingEntityName("Pony.ai, Inc."), []);
  assert.deepEqual(splitCompoundTrackingEntityName("A/B Test Labs"), []);
});

test("historical compound entities are grandfathered and do not block unrelated saves", () => {
  const previous = config();
  const next = clone(previous);
  next.tracks[0].people.push("Sam Altman");
  next.tracks[0].sampleCompanies.push("OpenAI");

  assert.deepEqual(findNewCompoundTrackingEntities(previous, next), []);
  assert.doesNotThrow(() => assertNoNewCompoundTrackingEntities(previous, next));
});

test("new compound people and companies are blocked before persistence", () => {
  const previous = config();
  const next = clone(previous);
  next.tracks[0].people.push("Sam Altman、Demis Hassabis");
  next.tracks[0].sampleCompanies.push("OpenAI，Anthropic");

  const issues = findNewCompoundTrackingEntities(previous, next);
  assert.equal(issues.length, 2);
  assert.deepEqual(
    issues.map((issue) => [issue.entityType, issue.value]),
    [
      ["person", "Sam Altman、Demis Hassabis"],
      ["company", "OpenAI，Anthropic"],
    ],
  );
  assert.throws(
    () => assertNoNewCompoundTrackingEntities(previous, next),
    /已阻止写入 user_tracking\.json.*请拆分为独立实体/,
  );
});

test("moving a historical compound value into another track is treated as new pollution", () => {
  const previous = config();
  const next = clone(previous);
  next.tracks.push({
    slug: "robotics",
    name: "机器人",
    enabled: true,
    custom: false,
    keywords: [],
    people: ["Quoc Le、Jeff Dean"],
    sampleCompanies: [],
  });

  const issues = findNewCompoundTrackingEntities(previous, next);
  assert.equal(issues.length, 1);
  assert.equal(issues[0].trackSlug, "robotics");
  assert.equal(issues[0].entityType, "person");
});
