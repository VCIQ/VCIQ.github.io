import assert from "node:assert/strict";
import test from "node:test";
import identities from "../config/innovation_investor_project_identities.json";
import {
  buildCanonicalInvestorProjectGraph,
  investorProjectCoverageMatrix,
  validateInvestorProjectIdentities,
  type ProjectIdentity,
} from "../lib/innovation-investor-project-graph";
import {
  globalInnovationInvestors, investorEvidenceRecords,
  validateInvestorResearch, type InvestorEvidenceRecord,
} from "../lib/innovation-investor-research";
import { buildInvestorHomepagePublication } from "../lib/homepage-investor-publication";

// Synthetic test-only evidence. This is never inserted into config, a news feed,
// a review queue, a PR approval packet, or the production investor registry.
const fixtureProject = "Fixture-only Incremental Venture";
const fixtureUrl = "https://www.balderton.com/stories/test-only-incremental-venture";
const originalInvestment = investorEvidenceRecords.find(
  (row) => row.id === "sequoia-catalyst-seed-20261008",
)!;

function extraRecords(): InvestorEvidenceRecord[] {
  const investment = {
    ...originalInvestment,
    id: "fixture-only-balderton-seed-20261010",
    institutionId: "balderton",
    project: fixtureProject,
    date: "2026-10-10",
    datePrecision: "day",
    title: "Test fixture: official seed financing",
    summary: "Synthetic test record, not a real transaction or public statement.",
    round: "Seed",
    participation: "lead",
    roundAmount: null,
    investorAmount: null,
    speakers: [],
    linkedPerson: null,
    resultStatus: null,
    realizedProceeds: null,
    source: {
      ...originalInvestment.source,
      url: fixtureUrl,
      title: "Test fixture — not a published official article",
      publisher: "Balderton Capital",
      kind: "investor-official",
      publishedAt: "2026-10-10",
      locator: "TEST FIXTURE ONLY: source content is deliberately simulated",
    },
    nextCheck: "Not applicable: test fixture",
  } as InvestorEvidenceRecord;
  const viewpoint = {
    ...investment,
    id: "fixture-only-balderton-thesis-20261010",
    kind: "viewpoint",
    title: "Test fixture: source-attributed research thesis",
    round: null,
    participation: null,
    roundAmount: null,
    investorAmount: null,
    speakers: [{
      name: "Fixture Author",
      roleAtPublication: "Synthetic article author (test only)",
      attribution: "paraphrase",
      projectResponsibility: "Article authorship never proves exclusive investment responsibility",
    }],
  } as InvestorEvidenceRecord;
  return [investment, viewpoint];
}

test("adding a newly reviewed project updates graph and institution coverage without fixed totals", () => {
  const newRows = extraRecords();
  const newIdentity: ProjectIdentity = {
    id: "fixture-only-incremental-venture",
    name: fixtureProject,
    observedNames: [fixtureProject],
    identityEvidenceUrls: [fixtureUrl],
    identityNote: "Synthetic record used solely in regression tests",
  };
  const proposedRecords = [...investorEvidenceRecords, ...newRows];
  const proposedIdentities = [...identities.projects, newIdentity];
  assert.deepEqual(validateInvestorResearch(globalInnovationInvestors, proposedRecords), []);
  assert.deepEqual(validateInvestorProjectIdentities(proposedIdentities, proposedRecords), []);

  const baselineGraph = buildCanonicalInvestorProjectGraph();
  const extendedGraph = buildCanonicalInvestorProjectGraph(proposedIdentities, proposedRecords);
  assert.equal(extendedGraph.length, baselineGraph.length + 1);
  const extra = extendedGraph.find((project) => project.projectId === newIdentity.id);
  assert.ok(extra);
  assert.equal(extra.institutions.length, 1);
  assert.equal(extra.institutions[0].institutionId, "balderton");
  assert.equal(extra.institutions[0].evidenceCount, 2);
  assert.equal(extra.institutions[0].investmentDisclosures.length, 1);
  assert.equal(extra.institutions[0].viewpointRecordCount, 1);
  assert.equal(extra.institutions[0].realizedFundReturn, "unknown");

  const before = investorProjectCoverageMatrix(baselineGraph).find((row) => row.institutionId === "balderton")!;
  const after = investorProjectCoverageMatrix(extendedGraph).find((row) => row.institutionId === "balderton")!;
  assert.equal(after.reviewedProjectCount, before.reviewedProjectCount + 1);
  assert.equal(after.evidenceRecordCount, before.evidenceRecordCount + 2);
  assert.equal(after.disclosedInvestmentEvents, before.disclosedInvestmentEvents + 1);
  assert.equal(after.state, after.reviewedProjectCount < 3 ?
    "partial-project-samples" : "sample-count-target-met");
});

test("one future reviewed original can cover investment plus viewpoint without duplicate homepage cards", () => {
  const {events, innovationItems} = buildInvestorHomepagePublication(
    extraRecords(), globalInnovationInvestors, Date.parse("2026-10-10T12:00:00Z"),
  );
  assert.equal(events.length, 1);
  assert.equal(innovationItems.length, 1);
  assert.equal(events[0].source.url, fixtureUrl);
  assert.equal(events[0].type, "产业投资");
  assert.equal(events[0].publicationTimePrecision, "day");
  assert.deepEqual(events[0].mentionedPeople, ["Fixture Author"]);
  assert.deepEqual(events[0].matchedTrackingTerms, []);
  assert.equal(innovationItems[0].eventId, events[0].id);
});
