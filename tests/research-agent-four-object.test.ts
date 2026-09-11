import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import test from "node:test";

import { coreTechnologyEntities } from "../lib/core-research-objects";
import type { ResearchAgentChange, ResearchAgentReport } from "../lib/research-agent-data";
import { buildResearchAgentViewModel } from "../lib/research-agent-view-model";
import { trackedSectors } from "../lib/tracked-sectors";

const root = resolve(import.meta.dirname, "..");

function change(id: string, dataset: string): ResearchAgentChange {
  return {
    id,
    dataset,
    entityType: dataset === "technology" ? "核心技术" : "核心赛道",
    entityId: id,
    entityName: id,
    action: "updated",
    changedFields: ["latestEvents"],
    summary: `${id} 新增事件`,
    importance: 90,
    before: null,
    after: null,
    evidenceIds: [`E-${id}`],
    changeType: "external_event",
    eligibleForKeyDevelopment: true,
    publicationTier: "verified_change",
  };
}

function report(changes: ResearchAgentChange[]): ResearchAgentReport {
  return {
    schemaVersion: 1,
    generatedAt: "2026-09-11T00:00:00Z",
    asOfDate: "2026-09-11",
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
      byDataset: { technology: 1, track: 1 },
      byChangeType: { external_event: changes.length },
      highestImportance: 90,
      verifiedChangeTotal: changes.length,
      candidateTotal: 0,
      auxiliaryLeadTotal: 0,
      rejectedTotal: 0,
    },
    researchScope: {
      technology: { label: "核心技术", status: "active", count: 7, note: "" },
      track: { label: "核心赛道", status: "active", count: 23, note: "" },
      person: { label: "核心人物", status: "active", count: 1, note: "" },
      ventureCompany: { label: "核心公司", status: "active", count: 1, note: "" },
    },
    analysis: {
      executiveSummary: "test",
      keyDevelopments: [],
      thesisUpdates: [],
      watchlist: [],
      risks: [],
      methodologyNote: "test",
    },
    changes,
    evidence: changes.map((item) => ({
      id: item.evidenceIds[0],
      changeId: item.id,
      entityName: item.entityName,
      claim: item.summary,
      sourceName: "Official",
      title: item.summary,
      url: `https://example.com/${item.id}`,
      publishedAt: "2026-09-11",
      evidenceGrade: "官方披露",
      qualityStatus: "passed",
      supportStatus: "supports",
      publicationTier: "verified_change",
    })),
    methodology: { stages: [], fallbackReason: "", disclaimer: "" },
    history: [],
  };
}

test("canonical object exporter matches the public Track and Technology directories", () => {
  const directory = mkdtempSync(join(tmpdir(), "research-agent-objects-"));
  const output = join(directory, "objects.json");
  try {
    execFileSync(
      process.execPath,
      ["--import", "tsx", "scripts/build-research-agent-object-snapshot.ts"],
      {
        cwd: root,
        env: {
          ...process.env,
          RESEARCH_AGENT_OBJECT_SNAPSHOT_PATH: output,
        },
        stdio: "pipe",
      },
    );
    const payload = JSON.parse(readFileSync(output, "utf8")) as {
      counts: { track: number; technology: number };
      tracks: Record<string, unknown>;
      technologies: Record<string, unknown>;
    };
    assert.equal(payload.counts.track, trackedSectors.length);
    assert.equal(payload.counts.technology, coreTechnologyEntities.length);
    assert.equal(Object.keys(payload.tracks).length, trackedSectors.length);
    assert.equal(Object.keys(payload.technologies).length, coreTechnologyEntities.length);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("verified Technology and Track changes are first-class core changes", () => {
  const fixture = report([
    change("technology-codex", "technology"),
    change("track-ai", "track"),
  ]);
  const view = buildResearchAgentViewModel(fixture);
  assert.equal(view.metrics.formalChangeCount, 2);
  assert.equal(view.visibleMetrics.formalChangeCount, 2);
  assert.deepEqual(
    view.formalChanges.map((item) => item.dataset).sort(),
    ["technology", "track"],
  );
  assert.equal(view.coverage.technology, 7);
  assert.equal(view.coverage.track, 23);
});
