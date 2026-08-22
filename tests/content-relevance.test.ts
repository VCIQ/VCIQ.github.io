import assert from "node:assert/strict";
import test from "node:test";
import { contentRelevanceForEvidence } from "../lib/content-relevance";

test("priority technology topic evidence always keeps full content weight", () => {
  const result = contentRelevanceForEvidence({
    topicCount: 1,
    qualityStatus: "低可信",
    qualitySignals: ["未命中有效追踪词"],
  });
  assert.equal(result.status, "priority-topic");
  assert.equal(result.weight, 1);
});

test("crawler-usable long-tail events keep full sector weight without a priority topic", () => {
  const result = contentRelevanceForEvidence({
    topicCount: 0,
    qualityStatus: "可用",
    qualitySignals: ["标题命中 2 个追踪词"],
  });
  assert.equal(result.status, "usable");
  assert.equal(result.weight, 1);
});

test("low-confidence untagged events with partial tracking evidence are downweighted, not deleted", () => {
  const result = contentRelevanceForEvidence({
    topicCount: 0,
    qualityStatus: "低可信",
    qualitySignals: ["摘要命中 1 个追踪词"],
  });
  assert.equal(result.status, "partial-evidence");
  assert.equal(result.weight, 0.5);
});

test("untagged events explicitly missing valid tracking terms retain provenance at quarter weight", () => {
  const result = contentRelevanceForEvidence({
    topicCount: 0,
    qualityStatus: "低可信",
    qualitySignals: ["未命中有效追踪词"],
  });
  assert.equal(result.status, "weak-evidence");
  assert.equal(result.weight, 0.25);
});

test("missing quality metadata never causes an automatic relevance penalty", () => {
  const result = contentRelevanceForEvidence({ topicCount: 0 });
  assert.equal(result.status, "unassessed");
  assert.equal(result.weight, 1);
});
