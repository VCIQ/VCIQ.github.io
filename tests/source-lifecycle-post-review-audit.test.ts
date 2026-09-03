import assert from "node:assert/strict";
import test from "node:test";

import sourceLifecyclePolicy from "@/config/source_lifecycle_policy.json";
import { sourceDirectory, type SourceDirectoryEntry } from "@/lib/source-directory";
import {
  SOURCE_GOVERNANCE_POLICY,
  sourceCoreEligible,
  sourceGovernanceMode,
} from "@/lib/source-governance";

type Category =
  | "primary_official"
  | "primary_regulatory"
  | "primary_research"
  | "corroboration_media"
  | "discovery_wechat"
  | "discovery_x"
  | "other";

type MetricKey =
  | "runs"
  | "observedDays"
  | "scanned"
  | "availabilityRate"
  | "validYieldRate"
  | "reviewedRecords"
  | "misattributionRate"
  | "activeCollection"
  | "publicationEligible"
  | "performanceReviewRequired";

type NumericMetricKey =
  | "runs"
  | "observedDays"
  | "scanned"
  | "availabilityRate"
  | "validYieldRate"
  | "reviewedRecords"
  | "misattributionRate";

const policy = sourceLifecyclePolicy;

const metricKeys: MetricKey[] = [
  "runs",
  "observedDays",
  "scanned",
  "availabilityRate",
  "validYieldRate",
  "reviewedRecords",
  "misattributionRate",
  "activeCollection",
  "publicationEligible",
  "performanceReviewRequired",
];

function categoryOf(source: SourceDirectoryEntry): Category {
  if (source.kind === "论文 / 原始研究") return "primary_research";
  if (source.kind === "X / 发现") return "discovery_x";
  if (source.kind === "微信公众号") return "discovery_wechat";
  if (source.sourceRole === "corroboration") return "corroboration_media";
  if (source.sourceRole === "primary" && source.platform === "监管机构") return "primary_regulatory";
  if (source.sourceRole === "primary") return "primary_official";
  return "other";
}

function trackingEligible(source: SourceDirectoryEntry): boolean {
  return Boolean(source.promotion) && source.promotion?.state !== "candidate";
}

function passes(source: SourceDirectoryEntry, key: MetricKey): boolean {
  const evidence = source.promotion?.evidence;
  switch (key) {
    case "runs":
      return (evidence?.runs ?? -1) >= policy.coreMinRuns;
    case "observedDays":
      return (evidence?.observedDays ?? -1) >= policy.coreMinObservedDays;
    case "scanned":
      return (evidence?.scanned ?? -1) >= policy.coreMinScanned;
    case "availabilityRate":
      return (evidence?.availabilityRate ?? -1) >= policy.coreMinAvailabilityRate;
    case "validYieldRate":
      return (evidence?.validYieldRate ?? -1) >= policy.coreMinValidYieldRate;
    case "reviewedRecords":
      return (evidence?.reviewedRecords ?? -1) >= policy.coreMinReviewedRecords;
    case "misattributionRate":
      return evidence?.misattributionRate !== undefined
        && evidence.misattributionRate <= policy.coreMaxMisattributionRate;
    case "activeCollection":
      return !policy.requireActiveCollection || evidence?.activeCollection === true;
    case "publicationEligible":
      return !policy.requirePublicationEligible || evidence?.publicationEligible === true;
    case "performanceReviewRequired":
      return !policy.disallowPerformanceReviewRequired
        || evidence?.performanceReviewRequired === false;
  }
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

function rounded(value: number | null, digits = 3): number | null {
  return value === null ? null : Number(value.toFixed(digits));
}

function valuesFor(sources: SourceDirectoryEntry[], key: NumericMetricKey): number[] {
  return sources.flatMap((source) => {
    const value = source.promotion?.evidence?.[key];
    return typeof value === "number" ? [value] : [];
  });
}

function mediansFor(sources: SourceDirectoryEntry[]) {
  return {
    runs: rounded(median(valuesFor(sources, "runs"))),
    observedDays: rounded(median(valuesFor(sources, "observedDays"))),
    scanned: rounded(median(valuesFor(sources, "scanned"))),
    availabilityRate: rounded(median(valuesFor(sources, "availabilityRate"))),
    validYieldRate: rounded(median(valuesFor(sources, "validYieldRate"))),
    reviewedRecords: rounded(median(valuesFor(sources, "reviewedRecords"))),
    misattributionRate: rounded(median(valuesFor(sources, "misattributionRate"))),
  };
}

test("audit post-review lifecycle evidence by source role", () => {
  const categories = [...new Set(sourceDirectory.map(categoryOf))].sort();
  const report = Object.fromEntries(categories.map((category) => {
    const all = sourceDirectory.filter((source) => categoryOf(source) === category);
    const tracked = all.filter(trackingEligible);
    const rawWithEvidence = tracked.filter((source) => Boolean(source.promotion?.evidence));
    const coreCohort = tracked.filter(sourceCoreEligible);
    const coreWithEvidence = coreCohort.filter((source) => Boolean(source.promotion?.evidence));

    const failedMetricCounts = Object.fromEntries(metricKeys.map((key) => [
      key,
      coreCohort.filter((source) => !passes(source, key)).length,
    ]));
    const passRates = Object.fromEntries(metricKeys.map((key) => [
      key,
      coreCohort.length
        ? Number((coreCohort.filter((source) => passes(source, key)).length / coreCohort.length).toFixed(3))
        : null,
    ]));
    const singleBlockerSources = Object.fromEntries(metricKeys.map((key) => [
      key,
      coreCohort.filter((source) => {
        const failed = metricKeys.filter((metric) => !passes(source, metric));
        return failed.length === 1 && failed[0] === key;
      }).map((source) => source.id),
    ]));
    const singleBlockerCounts = Object.fromEntries(
      Object.entries(singleBlockerSources).map(([key, sourceIds]) => [key, sourceIds.length]),
    );

    return [category, {
      total: all.length,
      tracked: tracked.length,
      coreEligible: coreCohort.length,
      discoveryOnly: tracked.filter((source) => sourceGovernanceMode(source) === "discovery_only").length,
      withEvidence: rawWithEvidence.length,
      coreWithEvidence: coreWithEvidence.length,
      manualQaEvidence: coreCohort.filter((source) => {
        const evidence = source.promotion?.evidence;
        return typeof evidence?.reviewedRecords === "number"
          && typeof evidence?.misattributionRate === "number";
      }).length,
      qaGatePassed: coreCohort.filter((source) =>
        passes(source, "reviewedRecords") && passes(source, "misattributionRate")
      ).length,
      coreReadyByMetrics: coreCohort.filter((source) => source.promotion?.coreReadyByMetrics).length,
      reviewPending: coreCohort.filter((source) => source.promotion?.state === "review_pending").length,
      core: coreCohort.filter((source) => source.promotion?.state === "core").length,
      failedMetricCounts,
      singleBlockerCounts,
      singleBlockerSources,
      passRates,
      rawMedians: mediansFor(rawWithEvidence),
      coreMedians: mediansFor(coreWithEvidence),
    }];
  }));

  const regulatoryFocus = sourceDirectory
    .filter((source) => categoryOf(source) === "primary_regulatory")
    .map((source) => ({
      id: source.id,
      name: source.name,
      governanceMode: sourceGovernanceMode(source),
      lifecycle: source.lifecycle,
      promotionState: source.promotion?.state,
      coreReadyByMetrics: source.promotion?.coreReadyByMetrics,
      manualDecision: source.promotion?.manualDecision,
      evidence: source.promotion?.evidence,
      failedMetrics: metricKeys.filter((key) => !passes(source, key)),
      reasons: source.promotion?.reasons,
    }));

  const snapshot = {
    auditVersion: "post-review-2026-09-03",
    sourceCount: sourceDirectory.length,
    policy,
    governancePolicy: SOURCE_GOVERNANCE_POLICY,
    governanceCounts: {
      coreCandidate: sourceDirectory.filter(sourceCoreEligible).length,
      discoveryOnly: sourceDirectory.filter(
        (source) => sourceGovernanceMode(source) === "discovery_only",
      ).length,
    },
    report,
    regulatoryFocus,
  };

  console.log("SOURCE_LIFECYCLE_POST_REVIEW_AUDIT=" + JSON.stringify(snapshot));

  assert.ok(sourceDirectory.length > 0);
  assert.ok(Object.keys(report).length >= 5);
  assert.equal(regulatoryFocus.length, 6);
});
