import assert from "node:assert/strict";
import test from "node:test";
import snapshot from "../config/innovation_investor_coverage.json";
import roster from "../config/innovation_global_investors.json";
import evidence from "../config/innovation_investor_evidence.json";
import identities from "../config/innovation_investor_project_identities.json";
import registry from "../config/innovation_investor_registry_v2.json";

test("coverage snapshot reconciles all 35 unique rows with signed evidence counts", () => {
  assert.equal(snapshot.schemaVersion, 1);
  assert.equal(snapshot.status, "initial-observed-evidence-baseline");
  assert.equal(snapshot.institutions.length, registry.institutionCount);
  assert.equal(snapshot.summary.institutions, registry.institutionCount);
  assert.equal(snapshot.summary.globalCore, roster.institutions.length);
  assert.equal(snapshot.summary.chinaFocus, 13);
  assert.equal(snapshot.summary.uniqueCanonicalProjects, identities.projects.length);
  assert.equal(snapshot.summary.reviewedEvidenceRecords, evidence.records.length);
  assert.equal(snapshot.institutions.reduce((sum, row) => sum + row.reviewedEvidenceCount, 0),
    evidence.records.length);
  const observed = new Set(evidence.records.map((row) => row.institutionId));
  assert.equal(snapshot.summary.reviewedInstitutionCount, observed.size);
  assert.equal(snapshot.summary.registeredOfficialHomepages +
    snapshot.summary.missingOfficialHomepages, snapshot.summary.institutions);
  const rows = new Map(snapshot.institutions.map((row) => [row.institutionId, row]));
  for (const entry of registry.institutions) {
    const row = rows.get(entry.id)!;
    assert.ok(row);
    assert.equal(row.reviewedEvidenceCount,
      evidence.records.filter((record) => record.institutionId === entry.id).length);
    assert.equal(row.reviewedInvestmentDisclosureCount,
      evidence.records.filter((record) => record.institutionId === entry.id && record.kind === "investment").length);
    assert.equal(row.distinctEvidenceOriginals,
      new Set(evidence.records.filter((record) => record.institutionId === entry.id).map((record) => record.source.url)).size);
    assert.equal(row.registeredOfficialHomepage, entry.officialSources.homepage);
    assert.deepEqual(row.cohorts, entry.cohorts);
  }
});

test("a sparse or unscanned institution must not be labelled poor-quality or inactive", () => {
  assert.ok(snapshot.institutions.every((row) => row.coverageScore === null));
  assert.ok(snapshot.institutions.every((row) => row.metrics.sourceCompleteness === null &&
    row.metrics.evidenceQuality === null && row.metrics.recentActivity === null &&
    row.metrics.identityCompleteness === null));
  assert.ok(snapshot.institutions.every((row) => row.lastSuccessfulScoutAt === null));
  assert.ok(snapshot.institutions.every((row) => row.scoreStatus === "pending-source-health-baseline"));
  const noHomepage = snapshot.institutions.filter((row) => !row.registeredOfficialHomepage);
  assert.deepEqual(noHomepage.map((row) => row.institutionId).sort(),
    ["five-years", "northern-light", "shunwei"]);
  assert.ok(noHomepage.every((row) => row.sourceStatus === "pending-official-source"));
  assert.ok(snapshot.institutions.some((row) => row.reviewedEvidenceCount === 0 &&
    row.coverageScore === null));
});

test("verified source presence is not confused with scanned source completeness", () => {
  const registered = snapshot.institutions.filter((row) => Boolean(row.registeredOfficialHomepage));
  assert.equal(registered.length, snapshot.summary.registeredOfficialHomepages);
  assert.ok(snapshot.institutions.every((row) => row.sourceStatus !== "pending-official-source" ||
    !row.registeredOfficialHomepage));
  assert.equal(snapshot.summary.pendingScoring, snapshot.institutions.length);
});
