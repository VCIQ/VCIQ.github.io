import type { SourceRole } from "@/lib/core-sources";

export type SourceGovernanceMode = "core_candidate" | "discovery_only";

export type SourceGovernancePolicy = {
  schemaVersion: number;
  coreEligibleRoles: SourceRole[];
  discoveryOnlyRoles: SourceRole[];
  unstableEndpointCyclesBeforePause: number;
  requireFreshSnapshotBeforeBulkDisable: boolean;
};

export const SOURCE_GOVERNANCE_POLICY: SourceGovernancePolicy = {
  schemaVersion: 1,
  coreEligibleRoles: ["primary", "corroboration"],
  discoveryOnlyRoles: ["discovery"],
  unstableEndpointCyclesBeforePause: 3,
  requireFreshSnapshotBeforeBulkDisable: true,
};

type SourceWithRole = {
  sourceRole: SourceRole;
};

export function sourceGovernanceMode(source: SourceWithRole): SourceGovernanceMode {
  return SOURCE_GOVERNANCE_POLICY.coreEligibleRoles.includes(source.sourceRole)
    ? "core_candidate"
    : "discovery_only";
}

export function sourceCoreEligible(source: SourceWithRole): boolean {
  return sourceGovernanceMode(source) === "core_candidate";
}

export function sourceCoreEligibilityReason(source: SourceWithRole): string {
  if (source.sourceRole === "primary") {
    return "默认作为 Primary / Core 候选；仍须通过量化证据门和显式人工审批。";
  }
  if (source.sourceRole === "corroboration") {
    return "默认用于独立交叉验证；证据成熟后可进入 Core 候选队列。";
  }
  return "默认仅作为 Discovery 使用，不进入 Core 晋级或 Core QA 队列；重要结论必须回溯 Primary / Corroboration。";
}

export function sourceRolePriority(source: SourceWithRole): number {
  if (source.sourceRole === "primary") return 0;
  if (source.sourceRole === "corroboration") return 1;
  return 2;
}
