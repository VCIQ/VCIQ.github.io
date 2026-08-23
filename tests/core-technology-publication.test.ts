import assert from "node:assert/strict";
import test from "node:test";
import {
  CORE_TECHNOLOGY_EXCLUDED_NAMES,
  coreTechnologyEntities,
} from "../lib/core-research-objects";
import { technologyTopicsForCoreEntity } from "../lib/technology-topics";

function normalizeName(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

test("public core technologies are classified and evidence-backed", () => {
  for (const entity of coreTechnologyEntities) {
    const evidenceCount = entity.captureCount + entity.articleCount;
    assert.ok(
      technologyTopicsForCoreEntity(entity).length > 0,
      `${entity.name} is unclassified`,
    );
    assert.ok(
      evidenceCount >= 2 ||
        entity.priority > 0 ||
        entity.researchThesis.trim().length > 0 ||
        entity.analystNotes.length > 0,
      `${entity.name} lacks the public evidence threshold`,
    );
    assert.ok(!entity.trackNames.includes("待归类"));
  }
});

test("single manual captures do not bypass the core publication threshold", () => {
  assert.equal(
    coreTechnologyEntities.some(
      (entity) =>
        entity.captureCount + entity.articleCount < 2 &&
        entity.priority === 0 &&
        entity.researchThesis.trim().length === 0 &&
        entity.analystNotes.length === 0,
    ),
    false,
  );
});

test("broad topics organizations projects and collision-prone names stay out of L3", () => {
  const publishedKeys = new Set(
    coreTechnologyEntities.flatMap((entity) =>
      [entity.name, ...entity.aliases].map(normalizeName),
    ),
  );
  for (const name of CORE_TECHNOLOGY_EXCLUDED_NAMES) {
    assert.equal(publishedKeys.has(normalizeName(name)), false, `${name} leaked into L3`);
  }
});

test("public model names and agent topic overrides remain explicit", () => {
  const byName = new Map(coreTechnologyEntities.map((entity) => [entity.name, entity]));
  assert.ok(byName.has("Claude Opus"));
  assert.ok(byName.has("Claude Sonnet"));
  assert.equal(byName.has("Opus"), false);
  assert.equal(byName.has("Sonnet"), false);

  for (const name of ["Claude Code", "Codex", "Agent OS"]) {
    const entity = byName.get(name);
    assert.ok(entity, `${name} is missing from the core directory`);
    const topics = technologyTopicsForCoreEntity(entity).map((topic) => topic.name);
    assert.ok(topics.includes("AI 智能体"), `${name} is missing the AI agent topic`);
  }
});
