import assert from "node:assert/strict";
import test from "node:test";
import { coreTechnologyEntities } from "../lib/core-research-objects";
import { technologyTopicsForEntity } from "../lib/technology-topics";

test("public core technologies are classified and evidence-backed", () => {
  for (const entity of coreTechnologyEntities) {
    const evidenceCount = entity.captureCount + entity.articleCount;
    assert.ok(technologyTopicsForEntity(entity).length > 0, `${entity.name} is unclassified`);
    assert.ok(
      evidenceCount >= 2 ||
        entity.captureCount > 0 ||
        entity.priority > 0 ||
        entity.analystNotes.length > 0,
      `${entity.name} lacks the public evidence threshold`,
    );
    assert.ok(!entity.trackNames.includes("待归类"));
  }
});
