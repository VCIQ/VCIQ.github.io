import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import type { SourceDirectoryEntry } from "@/lib/source-directory";
import {
  buildSourceCoverageRows,
  sourceFreshness,
  sourceNeedsAction,
  sourceReadinessDistance,
} from "@/lib/source-decision-dashboard";

function source(overrides: Partial<SourceDirectoryEntry> & Pick<SourceDirectoryEntry, "id" | "name">): SourceDirectoryEntry {
  return {
    id: overrides.id,
    name: overrides.name,
    kind: "媒体 / 研究",
    platform: "Web",
    sourceLevel: "待交叉验证",
    sourceRole: "corroboration",
    region: "全球",
    sectors: [],
    keywords: [],
    companies: [],
    people: [],
    lifecycle: "tracked",
    healthStatus: "ok",
    endpoints: [],
    ...overrides,
  } as SourceDirectoryEntry;
}

test("coverage matrix exposes role gaps instead of only counting total sources", () => {
  const rows = buildSourceCoverageRows([
    source({ id: "p1", name: "P1", sourceRole: "primary", sectors: ["量子计算"] }),
    source({ id: "c1", name: "C1", sourceRole: "corroboration", sectors: ["量子计算"] }),
    source({ id: "d1", name: "D1", sourceRole: "discovery", sectors: ["量子计算"] }),
  ]);

  assert.equal(rows.length, 1);
  assert.equal(rows[0].sector, "量子计算");
  assert.equal(rows[0].primary, 1);
  assert.equal(rows[0].corroboration, 1);
  assert.equal(rows[0].discovery, 1);
  assert.equal(rows[0].state, "watch");
  assert.deepEqual(rows[0].gaps, ["Primary 缺 1", "Corroboration 缺 1"]);
});

test("coverage matrix marks missing primary evidence as a critical gap", () => {
  const rows = buildSourceCoverageRows([
    source({ id: "c1", name: "C1", sourceRole: "corroboration", sectors: ["商业航天"] }),
    source({ id: "d1", name: "D1", sourceRole: "discovery", sectors: ["商业航天"] }),
  ]);

  assert.equal(rows[0].state, "gap");
  assert.ok(rows[0].gaps.some((item) => item.startsWith("Primary 缺")));
});

test("freshness is based on successful endpoint observation rather than snapshot date", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const fresh = source({
    id: "fresh",
    name: "Fresh",
    healthUpdatedAt: "2026-09-02T12:00:00Z",
    endpoints: [{
      id: "endpoint:fresh",
      label: "官网",
      platform: "Web",
      status: "ok",
      scanned: 1,
      accepted: 1,
      lastSuccessAt: "2026-09-02T06:00:00Z",
      sourceIds: ["fresh"],
    }],
  });
  const stale = source({
    id: "stale",
    name: "Stale",
    healthUpdatedAt: "2026-09-02T12:00:00Z",
    endpoints: [{
      id: "endpoint:stale",
      label: "官网",
      platform: "Web",
      status: "error",
      scanned: 0,
      accepted: 0,
      lastSuccessAt: "2026-08-30T00:00:00Z",
      sourceIds: ["stale"],
    }],
  });

  assert.equal(sourceFreshness(fresh, now).state, "fresh");
  assert.equal(sourceFreshness(stale, now).state, "stale");
  assert.equal(sourceNeedsAction(stale, now), true);
});

test("unobserved endpoints stay distinct from source research role", () => {
  const item = source({
    id: "unobserved",
    name: "Unobserved",
    sourceRole: "primary",
    healthStatus: "unknown",
    endpoints: [{
      id: "endpoint:unobserved",
      label: "官网",
      platform: "Web",
      status: "unknown",
      scanned: 0,
      accepted: 0,
      sourceIds: [],
    }],
  });

  assert.equal(item.sourceRole, "primary");
  assert.equal(sourceFreshness(item, new Date("2026-09-02T12:00:00Z")).state, "unobserved");
});

test("Core readiness queue ranks review-pending ahead of evidence-pending", () => {
  const ready = source({
    id: "ready",
    name: "Ready",
    promotion: {
      lifecycle: "tracked",
      state: "review_pending",
      coreReadyByMetrics: true,
      manualDecision: "pending",
      reasons: ["量化门槛已满足，等待显式人工 Core 审批"],
    },
  });
  const pending = source({
    id: "pending",
    name: "Pending",
    promotion: {
      lifecycle: "tracked",
      state: "evidence_pending",
      coreReadyByMetrics: false,
      manualDecision: "pending",
      reasons: ["运行样本不足（4/5）", "人工抽查样本不足（10/20）"],
    },
  });

  assert.ok(sourceReadinessDistance(ready) < sourceReadinessDistance(pending));
});

test("Sources v2 renders decision queues and separates evidence role from collector health", async () => {
  const client = await readFile(new URL("../app/sources/source-operations-client.tsx", import.meta.url), "utf8");
  const page = await readFile(new URL("../app/sources/page.tsx", import.meta.url), "utf8");

  assert.match(client, /COVERAGE \/ GAP MATRIX/);
  assert.match(client, /需要处理/);
  assert.match(client, /最接近 Core/);
  assert.match(client, /Coverage 缺口/);
  assert.match(client, /Unobserved/);
  assert.match(client, /EVIDENCE ROLE/);
  assert.match(client, /COLLECTOR HEALTH/);
  assert.match(client, /CORE READINESS/);
  assert.match(client, /SOURCE_FRESHNESS_POLICY\.freshHours/);
  assert.match(client, /SOURCE_FRESHNESS_POLICY\.staleHours/);
  assert.match(page, /SourceOperationsClient/);
  assert.doesNotMatch(page, /groups\.map/);
});