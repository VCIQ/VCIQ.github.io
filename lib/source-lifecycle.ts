export type SourceLifecycle = "candidate" | "tracked" | "core";

export type SourcePromotionState =
  | "candidate"
  | "evidence_pending"
  | "review_pending"
  | "blocked"
  | "core";

export type SourceCoreDecision = "approve_core" | "reject_core" | "pending";

export type SourceLifecyclePolicy = {
  requiresManualApproval: boolean;
  coreMinRuns: number;
  coreMinScanned: number;
  coreMinAvailabilityRate: number;
  coreMinValidYieldRate: number;
  coreMinObservedDays: number;
  coreMinReviewedRecords: number;
  coreMaxMisattributionRate: number;
  requireActiveCollection: boolean;
  requirePublicationEligible: boolean;
  disallowPerformanceReviewRequired: boolean;
};

export type SourcePromotionMetrics = {
  runs?: number;
  observedDays?: number;
  scanned?: number;
  availabilityRate?: number;
  validYieldRate?: number;
  activeCollection?: boolean;
  publicationEligible?: boolean;
  performanceReviewRequired?: boolean;
  reviewedRecords?: number;
  misattributionRate?: number;
  evidenceSourceId?: string;
};

export type SourceCoreReview = {
  sourceId: string;
  decision: Exclude<SourceCoreDecision, "pending">;
  reviewedAt: string;
  reviewer: string;
  note: string;
};

export type SourcePromotionEvaluation = {
  lifecycle: SourceLifecycle;
  state: SourcePromotionState;
  coreReadyByMetrics: boolean;
  manualDecision: "approved" | "rejected" | "pending";
  reasons: string[];
  evidence?: SourcePromotionMetrics;
};

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function nonNegativeInteger(value: unknown): number | undefined {
  const numeric = finiteNumber(value);
  return numeric !== undefined && numeric >= 0 ? Math.floor(numeric) : undefined;
}

function rate(value: unknown): number | undefined {
  const numeric = finiteNumber(value);
  return numeric !== undefined && numeric >= 0 && numeric <= 1 ? numeric : undefined;
}

function normalizedMetrics(metrics?: SourcePromotionMetrics): SourcePromotionMetrics | undefined {
  if (!metrics) return undefined;
  return {
    runs: nonNegativeInteger(metrics.runs),
    observedDays: nonNegativeInteger(metrics.observedDays),
    scanned: nonNegativeInteger(metrics.scanned),
    availabilityRate: rate(metrics.availabilityRate),
    validYieldRate: rate(metrics.validYieldRate),
    activeCollection: typeof metrics.activeCollection === "boolean" ? metrics.activeCollection : undefined,
    publicationEligible: typeof metrics.publicationEligible === "boolean" ? metrics.publicationEligible : undefined,
    performanceReviewRequired: typeof metrics.performanceReviewRequired === "boolean"
      ? metrics.performanceReviewRequired
      : undefined,
    reviewedRecords: nonNegativeInteger(metrics.reviewedRecords),
    misattributionRate: rate(metrics.misattributionRate),
    evidenceSourceId: typeof metrics.evidenceSourceId === "string" && metrics.evidenceSourceId.trim()
      ? metrics.evidenceSourceId.trim()
      : undefined,
  };
}

function manualDecision(review?: SourceCoreReview): "approved" | "rejected" | "pending" {
  if (review?.decision === "approve_core") return "approved";
  if (review?.decision === "reject_core") return "rejected";
  return "pending";
}

export function evaluateSourcePromotion(input: {
  trackingEligible: boolean;
  metrics?: SourcePromotionMetrics;
  review?: SourceCoreReview;
  policy: SourceLifecyclePolicy;
}): SourcePromotionEvaluation {
  const { trackingEligible, review, policy } = input;
  const evidence = normalizedMetrics(input.metrics);
  const decision = manualDecision(review);

  if (!trackingEligible) {
    return {
      lifecycle: "candidate",
      state: "candidate",
      coreReadyByMetrics: false,
      manualDecision: decision,
      reasons: ["尚未配置可持续采集入口"],
      evidence,
    };
  }

  const reasons: string[] = [];
  const runs = evidence?.runs;
  const observedDays = evidence?.observedDays;
  const scanned = evidence?.scanned;
  const availabilityRate = evidence?.availabilityRate;
  const validYieldRate = evidence?.validYieldRate;
  const reviewedRecords = evidence?.reviewedRecords;
  const misattributionRate = evidence?.misattributionRate;

  if (runs === undefined || runs < policy.coreMinRuns) {
    reasons.push(`运行样本不足（${runs ?? 0}/${policy.coreMinRuns}）`);
  }
  if (observedDays === undefined || observedDays < policy.coreMinObservedDays) {
    reasons.push(`跨日观测不足（${observedDays ?? 0}/${policy.coreMinObservedDays}）`);
  }
  if (scanned === undefined || scanned < policy.coreMinScanned) {
    reasons.push(`扫描样本不足（${scanned ?? 0}/${policy.coreMinScanned}）`);
  }
  if (availabilityRate === undefined || availabilityRate < policy.coreMinAvailabilityRate) {
    reasons.push(`可用率不足（${availabilityRate === undefined ? "无数据" : availabilityRate.toFixed(2)}）`);
  }
  if (validYieldRate === undefined || validYieldRate < policy.coreMinValidYieldRate) {
    reasons.push(`有效产出率不足（${validYieldRate === undefined ? "无数据" : validYieldRate.toFixed(2)}）`);
  }
  if (reviewedRecords === undefined || reviewedRecords < policy.coreMinReviewedRecords) {
    reasons.push(`人工抽查样本不足（${reviewedRecords ?? 0}/${policy.coreMinReviewedRecords}）`);
  }
  if (misattributionRate === undefined) {
    reasons.push("人工误归属率尚无可审计数据");
  } else if (misattributionRate > policy.coreMaxMisattributionRate) {
    reasons.push(`人工误归属率过高（${misattributionRate.toFixed(2)}）`);
  }
  if (policy.requireActiveCollection && evidence?.activeCollection !== true) {
    reasons.push("采集通道当前未处于 active 状态");
  }
  if (policy.requirePublicationEligible && evidence?.publicationEligible !== true) {
    reasons.push("当前采集证据不满足 publication eligible");
  }
  if (policy.disallowPerformanceReviewRequired && evidence?.performanceReviewRequired !== false) {
    reasons.push(
      evidence?.performanceReviewRequired === true
        ? "滚动性能指标仍触发人工审查"
        : "滚动性能审查状态尚无明确证据",
    );
  }

  const coreReadyByMetrics = reasons.length === 0;

  if (decision === "rejected") {
    return {
      lifecycle: "tracked",
      state: "blocked",
      coreReadyByMetrics,
      manualDecision: decision,
      reasons: ["人工 Core 审核已拒绝", ...reasons],
      evidence,
    };
  }

  if (!coreReadyByMetrics) {
    return {
      lifecycle: "tracked",
      state: "evidence_pending",
      coreReadyByMetrics: false,
      manualDecision: decision,
      reasons,
      evidence,
    };
  }

  if (policy.requiresManualApproval && decision !== "approved") {
    return {
      lifecycle: "tracked",
      state: "review_pending",
      coreReadyByMetrics: true,
      manualDecision: decision,
      reasons: ["量化门槛已满足，等待显式人工 Core 审批"],
      evidence,
    };
  }

  return {
    lifecycle: "core",
    state: "core",
    coreReadyByMetrics: true,
    manualDecision: decision,
    reasons: [],
    evidence,
  };
}
