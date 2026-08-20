import assert from "node:assert/strict";
import test from "node:test";

import rawTrackingConfig from "../config/user_tracking.json";
import { inventoryCompoundTrackingEntities } from "../lib/tracking-compound-entity-inventory";
import { normalizeTrackingConfig, type UserTrackingConfig } from "../lib/user-tracking";

function fixture(): UserTrackingConfig {
  return {
    schemaVersion: 1,
    tracks: [
      {
        slug: "ai",
        name: "AI / AGI",
        enabled: true,
        custom: false,
        keywords: [],
        people: ["Sam Altman、Demis Hassabis", "Alice"],
        sampleCompanies: ["OpenAI，Anthropic", "Pony.ai, Inc."],
      },
      {
        slug: "robotics",
        name: "机器人",
        enabled: true,
        custom: false,
        keywords: [],
        people: ["Sam Altman、Demis Hassabis"],
        sampleCompanies: ["A/B Test Labs"],
      },
    ],
    listedCompanies: [],
    sources: [],
  };
}

test("inventory reports compound occurrences without treating legal names as lists", () => {
  const report = inventoryCompoundTrackingEntities(fixture());

  assert.equal(report.mode, "read-only-inventory");
  assert.equal(report.occurrenceCount, 3);
  assert.equal(report.uniqueValueCount, 2);
  assert.equal(report.personOccurrenceCount, 2);
  assert.equal(report.companyOccurrenceCount, 1);
  assert.equal(report.affectedTrackCount, 2);
  assert.deepEqual(
    report.uniqueValues.map((row) => [row.entityType, row.value, row.occurrenceCount]),
    [
      ["company", "OpenAI，Anthropic", 1],
      ["person", "Sam Altman、Demis Hassabis", 2],
    ],
  );
});

test("current production inventory is read-only and internally accounted", () => {
  const config = normalizeTrackingConfig(rawTrackingConfig);
  const before = JSON.stringify(config);
  const report = inventoryCompoundTrackingEntities(config);

  assert.equal(JSON.stringify(config), before);
  assert.equal(report.occurrenceCount, report.occurrences.length);
  assert.equal(report.uniqueValueCount, report.uniqueValues.length);
  assert.equal(
    report.personOccurrenceCount + report.companyOccurrenceCount,
    report.occurrenceCount,
  );
  assert.equal(
    report.uniqueValues.reduce((total, row) => total + row.occurrenceCount, 0),
    report.occurrenceCount,
  );
  assert.equal(
    new Set(report.occurrences.map((row) => row.trackSlug)).size,
    report.affectedTrackCount,
  );

  console.log(
    "TRACKING_COMPOUND_ENTITY_INVENTORY=" + JSON.stringify(report),
  );
});
