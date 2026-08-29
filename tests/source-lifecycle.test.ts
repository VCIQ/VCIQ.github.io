import assert from "node:assert/strict";
import test from "node:test";

import {
  evaluateSourcePromotion,
  type SourceCoreReview,
  type SourceLifecyclePolicy,
  type SourcePromotionMetrics,
} from "../lib/source-lifecycle";

const policy: SourceLifecyclePolicy = {
  requiresManualApproval: true,
  coreMinRuns: 5,
  coreMinScanned: 20,
  coreMinAvailabilityRate: 0.9,
  coreMinValidYieldRate: 0.5,
  coreMinObservedDays: 7,
  coreMinReviewedRecords: 20,
  coreMaxMisattributionRate: 0.05,
  requireActiveCollection: true,
  requirePublicationEligible: true,
  disallowPerformanceReviewRequired: true,
};

const passingMetrics: SourcePromotionMetrics = {
  runs: 8,
  observedDays: 8,
  scanned: 80,
  availabilityRate: 1,
  validYieldRate: 0.6,
  activeCollection: true,
  publicationEligible: true,
  performanceReviewRequired: false,
  reviewedRecords: 20,
  misattributionRate: 0.05,
  evidenceSourceId: "runtime-source",
};

const approval: SourceCoreReview = {
  sourceId: "publisher:example",
  decision: "approve_core",
  reviewedAt: "2026-08-29T00:00:00Z",
  reviewer: "research-review",
  note: "Evidence inspected and approved.",
};

test("a publisher without a sustainable collection endpoint remains candidate", () => {
  const result = evaluateSourcePromotion({
    trackingEligible: false,
    metrics: passingMetrics,
    review: approval,
    policy,
  });
  assert.equal(result.lifecycle, "candidate");
  assert.equal(result.state, "candidate");
});

test("manual approval cannot bypass missing cross-run evidence", () => {
  const result = evaluateSourcePromotion({
    trackingEligible: true,
    review: approval,
    policy,
  });
  assert.equal(result.lifecycle, "tracked");
  assert.equal(result.state, "evidence_pending");
  assert.equal(result.coreReadyByMetrics, false);
  assert.ok(result.reasons.some((reason) => reason.includes("跨日观测不足")));
});

test("passing metrics without explicit approval stop at review pending", () => {
  const result = evaluateSourcePromotion({
    trackingEligible: true,
    metrics: passingMetrics,
    policy,
  });
  assert.equal(result.lifecycle, "tracked");
  assert.equal(result.state, "review_pending");
  assert.equal(result.coreReadyByMetrics, true);
  assert.equal(result.manualDecision, "pending");
});

test("passing metrics plus explicit approval promote a publisher to core", () => {
  const result = evaluateSourcePromotion({
    trackingEligible: true,
    metrics: passingMetrics,
    review: approval,
    policy,
  });
  assert.equal(result.lifecycle, "core");
  assert.equal(result.state, "core");
  assert.equal(result.coreReadyByMetrics, true);
  assert.equal(result.manualDecision, "approved");
});

test("an explicit rejection blocks core even when metrics pass", () => {
  const result = evaluateSourcePromotion({
    trackingEligible: true,
    metrics: passingMetrics,
    review: { ...approval, decision: "reject_core" },
    policy,
  });
  assert.equal(result.lifecycle, "tracked");
  assert.equal(result.state, "blocked");
  assert.equal(result.manualDecision, "rejected");
});

test("manual quality sampling is part of the quantitative core gate", () => {
  const result = evaluateSourcePromotion({
    trackingEligible: true,
    metrics: { ...passingMetrics, reviewedRecords: 0, misattributionRate: undefined },
    review: approval,
    policy,
  });
  assert.equal(result.state, "evidence_pending");
  assert.ok(result.reasons.some((reason) => reason.includes("人工抽查样本不足")));
  assert.ok(result.reasons.some((reason) => reason.includes("误归属率")));
});
