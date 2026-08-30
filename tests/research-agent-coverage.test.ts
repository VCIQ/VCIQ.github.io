import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  researchAgentReport,
  type ResearchScopeEntry,
} from "../lib/research-agent-data";
import { buildResearchAgentViewModel } from "../lib/research-agent-view-model";

test("Research Agent core coverage is never masked by degraded run output", () => {
  const page = readFileSync(
    new URL("../app/research-agent/page.tsx", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(page, /count:\s*suppressLegacyDegradedOutput\s*\?\s*0/);
  assert.match(page, /当前研究对象覆盖/);
  assert.match(page, /只表示本轮增量/);
  assert.match(page, /不会把历史研究对象清零/);
});

test("Research Agent published coverage follows researchScope semantics", () => {
  const scope = researchAgentReport.researchScope;
  assert.ok(scope);
  const coverage = buildResearchAgentViewModel(researchAgentReport).coverage;

  const mappings: Array<[string, keyof typeof coverage]> = [
    ["technology", "technology"],
    ["track", "track"],
    ["person", "person"],
    ["ventureCompany", "ventureCompany"],
  ];

  for (const [scopeKey, coverageKey] of mappings) {
    const entry: ResearchScopeEntry | undefined = scope[scopeKey];
    assert.ok(entry);
    if (entry.status === "active" && typeof entry.count === "number") {
      assert.equal(coverage[coverageKey], entry.count);
    } else {
      assert.equal(coverage[coverageKey], "待接入");
    }
  }
});

test("a zero-delta run does not imply zero active-object coverage", () => {
  if (researchAgentReport.changeSummary.total !== 0) return;

  const scope = researchAgentReport.researchScope;
  assert.ok(scope);
  const coverage = buildResearchAgentViewModel(researchAgentReport).coverage;
  for (const key of ["person", "ventureCompany"] as const) {
    const entry: ResearchScopeEntry | undefined = scope[key];
    if (entry?.status !== "active" || typeof entry.count !== "number") continue;
    assert.equal(coverage[key], entry.count);
    assert.ok(entry.count > 0);
  }
});

test("changeSummary.byDataset remains this-run change volume", () => {
  for (const [dataset, count] of Object.entries(researchAgentReport.changeSummary.byDataset)) {
    assert.equal(
      count,
      researchAgentReport.changes.filter((change) => change.dataset === dataset).length,
    );
  }
});
