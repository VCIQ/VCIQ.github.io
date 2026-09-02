import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import type { SourceDirectoryEntry } from "@/lib/source-directory";
import type { SourceLifecyclePolicy } from "@/lib/source-lifecycle";
import { buildSourceQaQueue } from "@/lib/source-qa-queue";

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

function source(input: {
  id: string;
  name: string;
  reviewedRecords?: number;
  misattributionRate?: number;
  reasons: string[];
  healthStatus?: SourceDirectoryEntry["healthStatus"];
  sourceRole?: SourceDirectoryEntry["sourceRole"];
}): SourceDirectoryEntry {
  return {
    id: input.id,
    name: input.name,
    kind: "媒体 / 研究",
    platform: "Web",
    sourceLevel: "待交叉验证",
    sourceRole: input.sourceRole ?? "corroboration",
    region: "全球",
    sectors: ["AI / AGI"],
    keywords: [],
    companies: [],
    people: [],
    lifecycle: "tracked",
    healthStatus: input.healthStatus ?? "ok",
    endpoints: [],
    promotion: {
      lifecycle: "tracked",
      state: "evidence_pending",
      coreReadyByMetrics: false,
      manualDecision: "pending",
      reasons: input.reasons,
      evidence: {
        reviewedRecords: input.reviewedRecords,
        misattributionRate: input.misattributionRate,
      },
    },
  } as SourceDirectoryEntry;
}

test("QA-only blockers rank ahead of sources with technical blockers", () => {
  const rows = buildSourceQaQueue([
    source({
      id: "qa-only",
      name: "QA Only",
      reviewedRecords: 18,
      reasons: ["人工抽查样本不足（18/20）", "人工误归属率尚无可审计数据"],
    }),
    source({
      id: "technical",
      name: "Technical",
      reviewedRecords: 10,
      reasons: ["人工抽查样本不足（10/20）", "扫描样本不足（8/20）", "有效产出率不足（0.30）"],
    }),
  ], policy);

  assert.equal(rows[0].sourceId, "qa-only");
  assert.equal(rows[0].tier, "qa-now");
  assert.equal(rows[0].reviewGap, 2);
  assert.equal(rows[0].otherBlockers.length, 0);
  assert.equal(rows[1].tier, "qa-next");
});

test("unhealthy sources with many non-QA blockers are deferred", () => {
  const rows = buildSourceQaQueue([
    source({
      id: "defer",
      name: "Defer",
      reviewedRecords: 0,
      healthStatus: "error",
      reasons: [
        "运行样本不足（1/5）",
        "扫描样本不足（2/20）",
        "有效产出率不足（0.10）",
        "人工抽查样本不足（0/20）",
        "人工误归属率尚无可审计数据",
      ],
    }),
  ], policy);

  assert.equal(rows[0].tier, "defer");
  assert.equal(rows[0].reviewGap, 20);
  assert.equal(rows[0].otherBlockers.length, 3);
});

test("sources without QA evidence gaps are excluded from the queue", () => {
  const rows = buildSourceQaQueue([
    source({
      id: "done",
      name: "Done",
      reviewedRecords: 20,
      misattributionRate: 0.02,
      reasons: ["跨日观测不足（5/7）"],
    }),
  ], policy);

  assert.equal(rows.length, 0);
});

test("Discovery-only sources never consume Core QA budget", () => {
  const rows = buildSourceQaQueue([
    source({
      id: "discovery",
      name: "Discovery",
      sourceRole: "discovery",
      reviewedRecords: 0,
      reasons: ["人工抽查样本不足（0/20）", "人工误归属率尚无可审计数据"],
    }),
    source({
      id: "primary",
      name: "Primary",
      sourceRole: "primary",
      reviewedRecords: 0,
      reasons: ["人工抽查样本不足（0/20）", "人工误归属率尚无可审计数据"],
    }),
  ], policy);

  assert.deepEqual(rows.map((row) => row.sourceId), ["primary"]);
});

test("Sources page renders Core-candidate QA queue before lifecycle methodology", async () => {
  const page = await readFile(new URL("../app/sources/page.tsx", import.meta.url), "utf8");
  const qa = await readFile(new URL("../app/sources/source-qa-queue.tsx", import.meta.url), "utf8");

  assert.match(page, /SourceQaQueue/);
  assert.ok(page.indexOf("<SourceQaQueue") < page.indexOf("<details className={styles.lifecycle}>") );
  assert.match(qa, /SOURCE QA QUEUE/);
  assert.match(qa, /人工抽查目标/);
  assert.match(qa, /Discovery-only 不消耗 Core QA 预算/);
  assert.match(qa, /MISATTRIBUTION/);
  assert.match(qa, /OTHER GATES/);
  assert.match(qa, /NOW/);
  assert.match(qa, /NEXT/);
  assert.match(qa, /DEFER/);
});
