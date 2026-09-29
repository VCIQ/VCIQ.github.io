import assert from "node:assert/strict";
import test from "node:test";
import { buildSourceCollectionAudit } from "../lib/source-collection-audit.mjs";

test("directory coverage counts exact runtime IDs, not source entity names", () => {
  const health = { generatedAt: "2026-09-29T19:33:31Z", sources: {
    one: { lastStatus: "ok", name: "Same name" },
    two: { lastStatus: "empty", name: "Same name" },
    old: { lastStatus: "error", missingFromCurrentRun: true },
  } };
  const audit = buildSourceCollectionAudit({ health, directory: [
    { endpoints: [{ sourceIds: ["one", "one"] }] },
  ] });
  assert.equal(audit.available, true);
  assert.equal(audit.retainedRuntimeChannels, 3);
  assert.equal(audit.currentRuntimeChannels, 2);
  assert.equal(audit.historicalRuntimeChannels, 1);
  assert.equal(audit.representedRuntimeChannels, 1);
  assert.equal(audit.unrepresentedRuntimeChannels, 1);
  assert.equal(audit.statuses.empty, 1);
  assert.equal(audit.statuses.error, 0);
  assert.equal(audit.observedAt, health.generatedAt);
});

test("missing health stays unavailable and zero publication is not an error", () => {
  assert.equal(buildSourceCollectionAudit().available, false);
  assert.equal(buildSourceCollectionAudit({ health: { sources: [] } }).available, false);
  const audit = buildSourceCollectionAudit({ health: { sources: {} }, articleSourceStatus: [
    { accepted: 1, publishedCount: 0 },
    { accepted: 1 },
    { accepted: 0, publishedCount: 0 },
  ] });
  assert.equal(audit.available, true);
  assert.equal(audit.acceptedWithoutPublication, 1);
  assert.equal(audit.observedAt, null);
});

test("public audit exposes no feed URLs or preferences and bounds examples", () => {
  const sources = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [String(i), {
    name: "Source", lastStatus: "ok", feedUrl: "PRIVATE_FEED", token: "PRIVATE_TOKEN", queries: ["PRIVATE_QUERY"],
  }]));
  const audit = buildSourceCollectionAudit({ health: { sources } });
  assert.equal(audit.unrepresentedRuntimeChannels, 20);
  assert.equal(audit.examples.length, 12);
  assert.doesNotMatch(JSON.stringify(audit), /PRIVATE_/);
});
