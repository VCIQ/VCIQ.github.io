import assert from "node:assert/strict";
import test from "node:test";

import type {
  ResearchAgentChange,
  ResearchAgentEvidence,
  ResearchAgentReport,
} from "../lib/research-agent-data";
import {
  buildResearchAgentViewModel,
  uniqueResearchEvidence,
} from "../lib/research-agent-view-model";

function change(
  id: string,
  dataset: string,
  overrides: Partial<ResearchAgentChange> & { publicationTier?: string } = {},
): ResearchAgentChange {
  return {
    id,
    dataset,
    entityType: dataset,
    entityId: id,
    entityName: `对象 ${id}`,
    action: "updated",
    changedFields: ["summary"],
    summary: `变化 ${id}`,
    importance: 60,
    before: null,
    after: null,
    evidenceIds: [`E-${id}`],
    ...overrides,
  };
}

function evidence(id: string): ResearchAgentEvidence {
  return {
    id,
    changeId: id.replace(/^E-/, ""),
    entityName: `对象 ${id}`,
    claim: `主张 ${id}`,
    sourceName: "测试来源",
    title: `证据 ${id}`,
    url: `https://example.com/${id}`,
    publishedAt: "2026-08-30",
    evidenceGrade: "A级",
  };
}

function report(
  changes: ResearchAgentChange[],
  overrides: Partial<ResearchAgentReport> & { reviewStatus?: string } = {},
): ResearchAgentReport {
  return {
    schemaVersion: 1,
    generatedAt: "2026-08-30T00:00:00Z",
    asOfDate: "2026-08-30",
    runStatus: "model",
    baselineSource: "test",
    model: {
      provider: "test",
      name: "test",
      baseUrl: "",
      reasoningEffort: "medium",
      used: true,
    },
    changeSummary: {
      totalDetected: changes.length,
      total: changes.length,
      byDataset: {
        person: 999,
        ventureCompany: 999,
        marketCompany: 999,
        intelligenceEvent: 999,
      },
      byChangeType: { external_event: changes.length },
      highestImportance: 60,
    },
    researchScope: {
      technology: { label: "核心技术", status: "pending-artifact", count: null, note: "" },
      track: { label: "核心赛道", status: "pending-artifact", count: null, note: "" },
      person: { label: "核心人物", status: "active", count: 23, note: "" },
      ventureCompany: { label: "核心公司", status: "active", count: 31, note: "" },
    },
    pipelineHealth: {
      overallStatus: "stale",
      healthyJobs: 7,
      jobCount: 9,
      issueJobs: [],
    },
    analysis: {
      executiveSummary: "test",
      keyDevelopments: Array.from({ length: 5 }, (_, index) => ({
        title: `重点 ${index}`,
        assessment: "test",
        importance: 60,
        confidence: "medium" as const,
        entities: [],
        evidenceIds: [],
      })),
      thesisUpdates: [],
      watchlist: [],
      risks: [],
      methodologyNote: "test",
    },
    changes,
    evidence: changes.flatMap((item) => item.evidenceIds.map(evidence)),
    methodology: { stages: [], fallbackReason: "", disclaimer: "test" },
    history: [],
    ...overrides,
  } as ResearchAgentReport;
}

test("legacy quality contract derives formal, candidate and external counts from changes", () => {
  const fixture = report([
    change("formal", "person", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
    }),
    change("ineligible", "ventureCompany", {
      changeType: "external_event",
      eligibleForKeyDevelopment: false,
    }),
    change("candidate", "marketCompany", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
    }),
    change("clue", "intelligenceEvent", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
    }),
    change("maintenance", "person", {
      changeType: "data_maintenance",
      eligibleForKeyDevelopment: false,
    }),
  ]);

  const view = buildResearchAgentViewModel(fixture);
  assert.equal(view.metrics.formalChangeCount, 1);
  assert.equal(view.metrics.companyCandidateCount, 1);
  assert.equal(view.metrics.candidateCount, 1);
  assert.equal(view.metrics.externalClueCount, 1);
  assert.equal(view.visibleChanges.length, 3);
  assert.equal(view.metrics.pipelineHealthyCount, 7);
  assert.equal(view.metrics.pipelineJobCount, 9);
  assert.deepEqual(view.coverage, {
    technology: "待接入",
    track: "待接入",
    person: 23,
    ventureCompany: 31,
  });
  assert.equal(view.topDevelopments.length, 3);
  assert.equal(view.hiddenDevelopmentCount, 2);
});

test("publication tier contract is authoritative and rejected rows stay private", () => {
  const fixture = report([
    change("formal", "person", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
      publicationTier: "verified_change",
    }),
    change("candidate", "marketCompany", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
      publicationTier: "candidate",
    }),
    change("clue", "intelligenceEvent", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
      publicationTier: "external_clue",
    }),
    change("rejected", "marketCompany", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
      publicationTier: "rejected",
    }),
    change("malformed-formal", "intelligenceEvent", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
      publicationTier: "verified_change",
    }),
    change("malformed-candidate", "institution", {
      changeType: "external_event",
      eligibleForKeyDevelopment: true,
      publicationTier: "candidate",
    }),
  ], { reviewStatus: "automated_unreviewed" });

  const view = buildResearchAgentViewModel(fixture);
  assert.equal(view.hasPublicationTierContract, true);
  assert.equal(view.metrics.formalChangeCount, 1);
  assert.equal(view.metrics.companyCandidateCount, 1);
  assert.equal(view.metrics.candidateCount, 2);
  assert.equal(view.metrics.externalClueCount, 1);
  assert.deepEqual(view.visibleChanges.map((item) => item.id), [
    "formal",
    "candidate",
    "clue",
    "malformed-candidate",
  ]);
  assert.deepEqual(view.otherCandidateChanges.map((item) => item.id), ["malformed-candidate"]);
  assert.equal(view.reviewStatus, "automated_unreviewed");
});

test("new tier totals identify a healthy empty report as new-schema output", () => {
  const fixture = report([], {
    changeSummary: {
      totalDetected: 0,
      total: 0,
      byDataset: {},
      byChangeType: {},
      highestImportance: 0,
      verifiedChangeTotal: 0,
      candidateTotal: 0,
      auxiliaryLeadTotal: 0,
      rejectedTotal: 0,
    } as ResearchAgentReport["changeSummary"],
  });

  const view = buildResearchAgentViewModel(fixture);
  assert.equal(view.hasPublicationTierContract, true);
  assert.equal(view.metrics.formalChangeCount, 0);
  assert.equal(view.metrics.companyCandidateCount, 0);
  assert.equal(view.metrics.candidateCount, 0);
  assert.equal(view.metrics.externalClueCount, 0);
});

test("pre-contract JSON remains readable but a degraded legacy run is isolated", () => {
  const oldChanges = [
    change("formal", "person"),
    change("candidate", "marketCompany"),
    change("clue", "intelligenceEvent"),
  ];
  const oldReport = report(oldChanges, {
    changeSummary: {
      totalDetected: 3,
      total: 3,
      byDataset: {},
      highestImportance: 60,
    },
    researchScope: undefined,
  });

  const visible = buildResearchAgentViewModel(oldReport);
  assert.equal(visible.hasEvidenceQualityContract, false);
  assert.equal(visible.metrics.formalChangeCount, 1);
  assert.equal(visible.metrics.companyCandidateCount, 1);
  assert.equal(visible.metrics.candidateCount, 1);
  assert.equal(visible.metrics.externalClueCount, 1);
  assert.deepEqual(visible.coverage, {
    technology: "待同步",
    track: "待同步",
    person: "待同步",
    ventureCompany: "待同步",
  });

  const degraded = buildResearchAgentViewModel({ ...oldReport, runStatus: "api-fallback" });
  assert.equal(degraded.suppressLegacyDegradedOutput, true);
  assert.equal(degraded.visibleChanges.length, 0);
  assert.equal(degraded.visibleEvidence.length, 0);
  assert.equal(degraded.topDevelopments.length, 0);
  assert.equal(degraded.thesisUpdates.length, 0);
  assert.equal(degraded.watchlist.length, 0);
  assert.equal(degraded.risks.length, 0);
});

test("evidence ledger de-duplicates repeated evidence IDs", () => {
  const first = evidence("E-1");
  const unique = uniqueResearchEvidence([first, { ...first }, evidence("E-2")]);
  assert.deepEqual(unique.map((item) => item.id), ["E-1", "E-2"]);
});
