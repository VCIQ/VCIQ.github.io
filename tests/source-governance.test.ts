import assert from "node:assert/strict";
import test from "node:test";
import {
  SOURCE_GOVERNANCE_POLICY,
  sourceCoreEligibilityReason,
  sourceCoreEligible,
  sourceGovernanceMode,
  sourceRolePriority,
} from "@/lib/source-governance";

test("default role governance keeps Discovery sources outside the Core queue", () => {
  const primary = { sourceRole: "primary" as const };
  const corroboration = { sourceRole: "corroboration" as const };
  const discovery = { sourceRole: "discovery" as const };

  assert.equal(sourceCoreEligible(primary), true);
  assert.equal(sourceCoreEligible(corroboration), true);
  assert.equal(sourceCoreEligible(discovery), false);
  assert.equal(sourceGovernanceMode(discovery), "discovery_only");
  assert.match(sourceCoreEligibilityReason(discovery), /不进入 Core 晋级/);
});

test("default governance records pause and bulk-disable guardrails", () => {
  assert.equal(SOURCE_GOVERNANCE_POLICY.unstableEndpointCyclesBeforePause, 3);
  assert.equal(SOURCE_GOVERNANCE_POLICY.requireFreshSnapshotBeforeBulkDisable, true);
  assert.deepEqual(SOURCE_GOVERNANCE_POLICY.coreEligibleRoles, ["primary", "corroboration"]);
  assert.deepEqual(SOURCE_GOVERNANCE_POLICY.discoveryOnlyRoles, ["discovery"]);
});

test("Core queue tie-breaks prioritize Primary before Corroboration and Discovery", () => {
  assert.ok(sourceRolePriority({ sourceRole: "primary" }) < sourceRolePriority({ sourceRole: "corroboration" }));
  assert.ok(sourceRolePriority({ sourceRole: "corroboration" }) < sourceRolePriority({ sourceRole: "discovery" }));
});
