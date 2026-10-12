import assert from "node:assert/strict";
import test from "node:test";
import registry from "../config/innovation_investor_registry_v2.json";
import identities from "../config/innovation_investor_project_identities.json";
import { investorEvidenceRecords } from "../lib/innovation-investor-research";
import {
  buildInvestorIntelligence,
  investorIntelligenceCoverage,
} from "../lib/innovation-investor-intelligence";

test("task 5 preserves every reviewed record and canonical institution identity", () => {
  const rows = buildInvestorIntelligence();
  assert.equal(rows.length, registry.institutions.length);
  assert.equal(new Set(rows.map(row => row.institutionId)).size, rows.length);
  assert.equal(rows.reduce((sum, row) => sum + row.reviewedEvidenceCount, 0), investorEvidenceRecords.length);
  assert.deepEqual(
    new Set(rows.flatMap(row => row.events.map(event => event.evidenceId))),
    new Set(investorEvidenceRecords.map(record => record.id)),
  );
  assert.ok(rows.every(row => row.realizedReturn === "unknown" && row.sampleOnly));
});

test("task 5 never constructs a project ID by guessing from a name", () => {
  const rows = buildInvestorIntelligence();
  const approvedIds = new Set(identities.projects.map(project => project.id));
  assert.ok(rows.flatMap(row => row.events).every(event =>
    event.projectId === null || approvedIds.has(event.projectId)));
  assert.throws(() => buildInvestorIntelligence([{
    ...investorEvidenceRecords[0],
    id: "unreviewed-project-fixture",
    project: "A completely unreviewed company",
  }]), /lacks canonical identity/);
});

test("task 5 timeline is deterministic and preserves per-record attribution", () => {
  const rows = buildInvestorIntelligence();
  for (const row of rows) {
    assert.deepEqual(row.events.map(event => event.evidenceId),
      [...row.events].sort((a, b) =>
        b.date.localeCompare(a.date) || a.evidenceId.localeCompare(b.evidenceId),
      ).map(event => event.evidenceId));
    assert.ok(row.events.every(event => event.sourceUrl.startsWith("https://")));
  }
  const summary = investorIntelligenceCoverage(rows);
  assert.equal(summary.registeredInstitutions, registry.institutions.length);
  assert.equal(summary.reviewedEvidenceRecords, investorEvidenceRecords.length);
  assert.equal(summary.reviewedCanonicalProjects, identities.projects.length);
  assert.equal(summary.status, "reviewed-sample-only");
});
