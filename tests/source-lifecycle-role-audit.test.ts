import assert from "node:assert/strict";
import test from "node:test";

import sourceLifecyclePolicy from "@/config/source_lifecycle_policy.json";
import { sourceDirectory, type SourceDirectoryEntry } from "@/lib/source-directory";

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

const policy = sourceLifecyclePolicy;

function categoryOf(source: SourceDirectoryEntry): Category {
  if (source.kind === "论文 / 原始研究") return "primary_research";
  if (source.kind === "X / 发现") return "discovery_x";
  if (source.kind === "微信公众号") return "discovery_wechat";
  if (source.sourceRole === "corroboration") return "corroboration_media";
  if (source.sourceRole === "primary" && source.platform === "监管机构") return "primary_regulatory";
  if (source.sourceRole === "primary") return "primary_official";
  return "other";
}

function passes(source: SourceDirectoryEntry, key: MetricKey): boolean {
  const evidence = source.promotion?.evidence;
  switch (key) {
    case "runs": return (evidence?.runs ?? -1) >= policy.coreMinRuns;
    case "observedDays": return (evidence?.observedDays ?? -1) >= policy.coreMinObservedDays;
    case "scanned": return (evidence?.scanned ?? -1) >= policy.coreMinScanned;
    case "availabilityRate": return (evidence?.availabilityRate ?? -1) >= policy.coreMinAvailabilityRate;
    case "validYieldRate": return (evidence?.validYieldRate ?? -1) >= policy.coreMinValidYieldRate;
    case "reviewedRecords": return (evidence?.reviewedRecords ?? -1) >= policy.coreMinReviewedRecords;
    case "misattributionRate": return evidence?.misattributionRate !== undefined
      && evidence.misattributionRate <= policy.coreMaxMisattributionRate;
    case "activeCollection": return !policy.requireActiveCollection || evidence?.activeCollection === true;
    case "publicationEligible": return !policy.requirePublicationEligible || evidence?.publicationEligible === true;
    case "performanceReviewRequired": return !policy.disallowPerformanceReviewRequired
      || evidence?.performanceReviewRequired === false;
  }
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function round(value: number | null, digits = 3): number | null {
  return value === null ? null : Number(value.toFixed(digits));
}

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

test("audit lifecycle gate distribution by source role", () => {
  const categories = [...new Set(sourceDirectory.map(categoryOf))].sort();
  const report = Object.fromEntries(categories.map((category) => {
    const all = sourceDirectory.filter((source) => categoryOf(source) === category);
    const eligible = all.filter((source) => source.lifecycle !== "candidate" || source.promotion?.state !== "candidate");
    const withEvidence = eligible.filter((source) => Boolean(source.promotion?.evidence));
    const blockerCounts = Object.fromEntries(metricKeys.map((key) => [
      key,
      eligible.filter((source) => !passes(source, key)).length,
    ]));
    const passRates = Object.fromEntries(metricKeys.map((key) => [
      key,
      eligible.length ? Number((eligible.filter((source) => passes(source, key)).length / eligible.length).toFixed(3)) : null,
    ]));
    const numeric = <K extends "runs" | "observedDays" | "scanned" | "availabilityRate" | "validYieldRate" | "reviewedRecords" | "misattributionRate">(key: K) =>
      withEvidence.flatMap((source) => {
        const value = source.promotion?.evidence?.[key];
        return typeof value === "number" ? [value] : [];
      });
    const singleBlockerCounts = Object.fromEntries(metricKeys.map((key) => [
      key,
      eligible.filter((source) => {
        const failed = metricKeys.filter((metric) => !passes(source, metric));
        return failed.length === 1 && failed[0] === key;
      }).length,
    ]));
    return [category, {
      total: all.length,
      candidate: all.filter((source) => source.promotion?.state === "candidate").length,
      eligible: eligible.length,
      withEvidence: withEvidence.length,
      coreReadyByMetrics: eligible.filter((source) => source.promotion?.coreReadyByMetrics).length,
      reviewPending: eligible.filter((source) => source.promotion?.state === "review_pending").length,
      blockerCounts,
      singleBlockerCounts,
      passRates,
      medians: {
        runs: round(median(numeric("runs"))),
        observedDays: round(median(numeric("observedDays"))),
        scanned: round(median(numeric("scanned"))),
        availabilityRate: round(median(numeric("availabilityRate"))),
        validYieldRate: round(median(numeric("validYieldRate"))),
        reviewedRecords: round(median(numeric("reviewedRecords"))),
        misattributionRate: round(median(numeric("misattributionRate"))),
      },
    }];
  }));

  console.log("SOURCE_LIFECYCLE_ROLE_AUDIT=" + JSON.stringify({
    sourceCount: sourceDirectory.length,
    policy,
    report,
  }));

  assert.ok(sourceDirectory.length > 0);
  assert.ok(Object.keys(report).length >= 5);
});
