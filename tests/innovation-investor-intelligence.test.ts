import assert from "node:assert/strict";
import test from "node:test";
import registry from "../config/innovation_investor_registry_v2.json";
import identities from "../config/innovation_investor_project_identities.json";
import { investorEvidenceRecords } from "../lib/innovation-investor-research";
import {
  buildInvestorIntelligence,
  investorIntelligenceCoverage,
  investorEvidenceDateLabel,
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

test("fund notices, portfolio links and company milestones never prove cash fundraising or exits", () => {
  const rows = buildInvestorIntelligence();
  assert.ok(rows.every(row => row.activityEvidence.registration.status === "unknown"));
  assert.ok(rows.every(row => row.activityEvidence.fundraising.status === "unknown"));
  assert.ok(rows.every(row => row.activityEvidence.exit.status === "unknown"));
  const notice = investorEvidenceRecords.find(record => record.kind === "fund-announcement")!;
  const noticeRow = buildInvestorIntelligence([notice]).find(row => row.institutionId === notice.institutionId)!;
  assert.equal(noticeRow.fundAnnouncementCount, 1);
  assert.equal(noticeRow.activityEvidence.investment.status, "unknown");
  for (const record of investorEvidenceRecords.filter(record => record.kind === "outcome" || record.kind === "portfolio-relationship")) {
    const row = buildInvestorIntelligence([record]).find(row => row.institutionId === record.institutionId)!;
    assert.equal(row.activityEvidence.investment.status, "unknown");
    assert.equal(row.activityEvidence.exit.status, "unknown");
  }
  const investment = investorEvidenceRecords.find(record => record.kind === "investment")!;
  const observed = buildInvestorIntelligence([investment]).find(row => row.institutionId === investment.institutionId)!;
  assert.equal(observed.activityEvidence.investment.status, "observed");
  assert.deepEqual(observed.activityEvidence.investment.evidenceIds, [investment.id]);
});

test("evidence summaries and original source dates survive the intelligence projection", () => {
  const originals = new Map(investorEvidenceRecords.map(record => [record.id,record]));
  for (const event of buildInvestorIntelligence().flatMap(row => row.events)) {
    const original = originals.get(event.evidenceId)!;
    assert.equal(event.summary, original.summary);
    assert.equal(event.sourcePublishedAt, original.source.publishedAt);
    assert.equal(event.sourceLocator, original.source.locator);
    assert.equal(event.sourceTitle, original.source.title);
    assert.deepEqual(event.roundAmount, original.roundAmount);
    assert.deepEqual(event.investorAmount, original.investorAmount);
  }
  assert.equal(investorEvidenceDateLabel("2024","year"), "2024（仅年份）");
  assert.equal(investorEvidenceDateLabel("2022-06","month"), "2022-06（仅月份）");
  assert.throws(() => buildInvestorIntelligence([investorEvidenceRecords[0],investorEvidenceRecords[0]]), /duplicate evidence ID/);
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

