import type { SourceDirectoryEntry } from "@/lib/source-directory";
import type { SourceLifecyclePolicy } from "@/lib/source-lifecycle";

export type SourceQaTier = "qa-now" | "qa-next" | "defer";

export type SourceQaQueueRow = {
  sourceId: string;
  name: string;
  kind: SourceDirectoryEntry["kind"];
  sourceRole: SourceDirectoryEntry["sourceRole"];
  healthStatus: SourceDirectoryEntry["healthStatus"];
  reviewedRecords: number;
  requiredReviewedRecords: number;
  reviewGap: number;
  misattributionRate: number | null;
  misattributionEvidenceMissing: boolean;
  qaBlockers: string[];
  otherBlockers: string[];
  tier: SourceQaTier;
  tierLabel: string;
  rationale: string;
};

function isQaResolvableReason(reason: string): boolean {
  return reason.startsWith("人工抽查样本不足")
    || reason === "人工误归属率尚无可审计数据";
}

function tierFor(input: {
  reviewGap: number;
  misattributionEvidenceMissing: boolean;
  otherBlockers: string[];
  healthStatus: SourceDirectoryEntry["healthStatus"];
}): Pick<SourceQaQueueRow, "tier" | "tierLabel" | "rationale"> {
  if (input.otherBlockers.length === 0) {
    return {
      tier: "qa-now",
      tierLabel: "NOW",
      rationale: input.reviewGap > 0
        ? "当前量化阻塞只剩人工抽查 / 误归属审计；优先补齐可最快形成 Core Ready 候选。"
        : "抽查数量已够，但误归属率证据尚未落账；优先补齐审计结果。",
    };
  }

  if (input.otherBlockers.length <= 2 && input.healthStatus === "ok") {
    return {
      tier: "qa-next",
      tierLabel: "NEXT",
      rationale: "除人工 QA 外只剩少量 Gate，且采集健康；可与剩余证据并行补齐。",
    };
  }

  return {
    tier: "defer",
    tierLabel: "DEFER",
    rationale: "仍有较多非 QA Gate 或采集不健康；先修技术 / 样本问题，避免浪费人工抽查预算。",
  };
}

export function buildSourceQaQueue(
  sources: SourceDirectoryEntry[],
  policy: SourceLifecyclePolicy,
): SourceQaQueueRow[] {
  const rows: SourceQaQueueRow[] = [];

  for (const source of sources) {
    if (source.lifecycle !== "tracked" || source.promotion?.state !== "evidence_pending") continue;

    const evidence = source.promotion.evidence;
    const reviewedRecords = evidence?.reviewedRecords ?? 0;
    const reviewGap = Math.max(0, policy.coreMinReviewedRecords - reviewedRecords);
    const misattributionRate = typeof evidence?.misattributionRate === "number"
      ? evidence.misattributionRate
      : null;
    const misattributionEvidenceMissing = misattributionRate === null;
    const reasons = source.promotion.reasons;
    const qaBlockers = reasons.filter(isQaResolvableReason);
    const otherBlockers = reasons.filter((reason) => !isQaResolvableReason(reason));

    if (reviewGap === 0 && !misattributionEvidenceMissing && qaBlockers.length === 0) continue;

    rows.push({
      sourceId: source.id,
      name: source.name,
      kind: source.kind,
      sourceRole: source.sourceRole,
      healthStatus: source.healthStatus,
      reviewedRecords,
      requiredReviewedRecords: policy.coreMinReviewedRecords,
      reviewGap,
      misattributionRate,
      misattributionEvidenceMissing,
      qaBlockers,
      otherBlockers,
      ...tierFor({
        reviewGap,
        misattributionEvidenceMissing,
        otherBlockers,
        healthStatus: source.healthStatus,
      }),
    });
  }

  const tierRank: Record<SourceQaTier, number> = {
    "qa-now": 0,
    "qa-next": 1,
    defer: 2,
  };

  return rows.sort((left, right) =>
    tierRank[left.tier] - tierRank[right.tier]
    || left.otherBlockers.length - right.otherBlockers.length
    || left.reviewGap - right.reviewGap
    || left.name.localeCompare(right.name, "zh-CN")
  );
}

export function summarizeSourceQaQueue(rows: SourceQaQueueRow[]) {
  return {
    total: rows.length,
    now: rows.filter((row) => row.tier === "qa-now").length,
    next: rows.filter((row) => row.tier === "qa-next").length,
    deferred: rows.filter((row) => row.tier === "defer").length,
  };
}
