import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import identities from "../config/innovation_investor_project_identities.json";
import {
  buildCanonicalInvestorProjectGraph,
  investorProjectCoverageMatrix,
  validateInvestorProjectIdentities,
  type ProjectIdentity,
} from "../lib/innovation-investor-project-graph";
import { investorEvidenceRecords, type InvestorEvidenceRecord } from "../lib/innovation-investor-research";

const read = (path: string) => fs.readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("every current project observation has one explicit, source-backed canonical identity", () => {
  assert.equal(identities.projects.length, 32);
  assert.deepEqual(validateInvestorProjectIdentities(), []);
  const names = investorEvidenceRecords.filter((row) => row.project).map((row) => row.project);
  assert.equal(new Set(names).size, 32);
  assert.deepEqual(new Set(identities.projects.flatMap((row) => row.observedNames)), new Set(names));
});

test("32 projects are 33 institution links, preserving cross-firm isolation", () => {
  const graph = buildCanonicalInvestorProjectGraph();
  assert.equal(graph.length, 32);
  assert.equal(graph.reduce((n, project) => n + project.institutions.length, 0), 33);
  const shared = graph.filter((p) => p.institutions.length > 1);
  assert.deepEqual(shared.map((p) => p.projectId), ["physical-intelligence"]);
  const pi = shared[0];
  assert.equal(pi.distinctSourceCount, 3);
  assert.equal(pi.coInvestmentRound, "not-assessed");
  assert.equal(pi.identityEvidenceUrls.length, 2);
  const sequoia = pi.institutions.find((r) => r.institutionId === "sequoia")!;
  const lux = pi.institutions.find((r) => r.institutionId === "lux")!;
  assert.equal(sequoia.portfolioRelationshipCount, 1);
  assert.equal(sequoia.investmentDisclosures.length, 0);
  assert.equal(sequoia.personAttributions[0]?.name, "Alfred Lin");
  assert.equal(sequoia.personAttributions[0]?.type, "portfolio-listed-partner");
  assert.equal(lux.portfolioRelationshipCount, 0);
  assert.equal(lux.investmentDisclosures.length, 1);
  assert.equal(lux.investmentDisclosures[0]?.announcedDate, "2024");
  assert.equal(lux.investmentDisclosures[0]?.round, null);
  assert.ok(lux.personAttributions.some((p) => p.name === "Josh Wolfe" && p.type === "article-attributed-viewpoint"));
  assert.equal(pi.reportedInvestmentEvents, 1);
  assert.equal(sequoia.realizedFundReturn, "unknown");
  assert.equal(lux.realizedFundReturn, "unknown");
});

test("30-firm matrix separates missing reviewed samples from real-world zero activity", () => {
  const matrix = investorProjectCoverageMatrix();
  assert.equal(matrix.length, 30);
  assert.equal(matrix.filter((r) => r.state === "partial-project-samples").length, 0);
  assert.equal(matrix.filter((r) => r.state === "no-project-evidence").length, 20);
  assert.equal(matrix.filter((r) => r.state === "sample-count-target-met").length, 10);
  assert.equal(matrix.reduce((n, r) => n + r.reviewedProjectCount, 0), 33);
  assert.equal(matrix.reduce((n, r) => n + r.disclosedInvestmentEvents, 0), 31);
  assert.equal(matrix.reduce((n, r) => n + r.observedOutcomeRecords, 0), 3);
  assert.equal(matrix.reduce((n, r) => n + r.evidenceRecordCount, 0), 56);
  assert.equal(matrix.filter((r) => r.reviewedProjectCount === 2).length, 0);
  assert.equal(matrix.filter((r) => r.reviewedProjectCount === 1).length, 0);
  assert.equal(matrix.filter((r) => r.reviewedProjectCount === 0).every((r) =>
    r.gapToThreeProjects === 3 && r.disclosedInvestmentEvents === 0), true);
  assert.equal(matrix.find((r) => r.institutionId === "a16z")?.evidenceRecordCount, 8);
  // The a16z Machine Age Fund is a fund/thematic announcement, not a project.
});

test("each of the first ten firms has at least three evidenced companies, not three disclosed investments", () => {
  const matrix = investorProjectCoverageMatrix();
  const withSamples = matrix.filter((row) => row.reviewedProjectCount > 0);
  assert.equal(withSamples.length, 10);
  assert.ok(withSamples.every((row) => row.reviewedProjectCount >= 3 && row.gapToThreeProjects === 0));
  assert.equal(withSamples.filter((row) => row.reviewedProjectCount === 4).length, 3);
  assert.equal(matrix.filter((row) => row.state === "no-project-evidence").length, 20);
  const utec = matrix.find((row) => row.institutionId === "utec")!;
  assert.equal(utec.reviewedProjectCount, 3);
  assert.equal(utec.disclosedInvestmentEvents, 1);
  // The dated UTEC anniversary report proves portfolio membership, NOT investment dates or rounds.
  const japan = buildCanonicalInvestorProjectGraph().filter((row) => ["eureka-robotics", "triorb"].includes(row.projectId));
  assert.equal(japan.length, 2);
  assert.ok(japan.every((row) => row.institutions[0].portfolioRelationshipCount === 1));
  assert.ok(japan.every((row) => row.institutions[0].investmentDisclosures.length === 0));
  assert.ok(japan.every((row) => row.earliestEvidenceDate === "2024-05-31"));
});

test("published funding totals never become a firm's individual investment amounts", () => {
  const graph = buildCanonicalInvestorProjectGraph();
  const values = [
    ["bayshore", 8000000, "lead", "Seed"],
    ["emerald-ai", 150000000, "co-lead", "Series A"],
    ["callosum", 100000000, "participant", "Seed"],
    ["forsight-robotics", 125000000, "lead", "Series B"],
    ["simbe-robotics", 28000000, "disclosed-investor", "Series B"],
    ["nu-quantum", 60000000, "participant", "Series A"],
    ["synthesized", 20000000, "participant", "Series A"],
  ] as const;
  for (const [key, funding, role, round] of values) {
    const record = graph.find((project) => project.projectId === key)!.institutions[0].investmentDisclosures[0];
    assert.equal(record.roundAmount?.value, funding, key);
    assert.equal(record.investorAmount, null, key);
    assert.equal(record.participation, role, key);
    assert.equal(record.round, round, key);
  }
  const reactor = graph.find((row) => row.projectId === "reactor")!.institutions[0].investmentDisclosures[0];
  assert.equal(reactor.round, "Series A");
  assert.equal(reactor.roundAmount, null); // $59M in official article was Seed + A combined.
  const angel = graph.find((row) => row.projectId === "xinguangjie")!.institutions[0].investmentDisclosures[0];
  assert.equal(angel.roundAmount, null); // '亿元' is not a precise standalone check.
  assert.equal(angel.investorAmount, null);
  assert.equal(angel.participation, "sole-investor");
});

test("same project rounds and a listing milestone remain distinct from realized fund cash", () => {
  const graph = buildCanonicalInvestorProjectGraph();
  const robot = graph.find((p) => p.projectId === "mech-mind")!;
  assert.equal(robot.institutions.length, 1);
  assert.equal(robot.institutions[0].investmentDisclosures.length, 1);
  assert.equal(robot.institutions[0].investmentDisclosures[0].announcedDate, "2019");
  assert.equal(robot.institutions[0].investmentDisclosures[0].datePrecision, "year");
  assert.equal(robot.institutions[0].investmentDisclosures[0].round, "A+");
  assert.equal(robot.institutions[0].outcomes.length, 1);
  assert.equal(robot.institutions[0].outcomes[0].status, "listed");
  assert.equal(robot.institutions[0].outcomes[0].date, "2026-09-01");
  assert.equal(robot.institutions[0].realizedFundReturn, "unknown");
  const orig = investorEvidenceRecords.find((r) => r.id === "qiming-mechmind-a-plus-investment-2019")!;
  assert.equal(orig.source.publishedAt, "2026-09-01");
  assert.equal(orig.date, "2019");
});

test("new daily official articles are separate projects and Oxide has only one dated new Series D", () => {
  const graph = buildCanonicalInvestorProjectGraph();
  const a = graph.find((p) => p.projectId === "typesafe-ai")!;
  const ox = graph.find((p) => p.projectId === "oxide-computer")!;
  assert.equal(a.name, "TypeSafe AI");
  assert.equal(a.institutions[0].institutionId, "a16z");
  assert.equal(a.institutions[0].investmentDisclosures[0].round, null);
  assert.equal(a.institutions[0].investmentDisclosures[0].participation, "lead");
  assert.equal(a.institutions[0].personAttributions.length, 5);
  assert.equal(ox.name, "Oxide");
  assert.equal(ox.institutions[0].institutionId, "eclipse");
  assert.equal(ox.institutions[0].investmentDisclosures.length, 1);
  assert.equal(ox.institutions[0].investmentDisclosures[0].round, "Series D");
  assert.equal(ox.institutions[0].investmentDisclosures[0].roundAmount?.value, 445_000_000);
  assert.equal(ox.institutions[0].investmentDisclosures[0].investorAmount, null);
  assert.equal(ox.institutions[0].confirmedTransactionOwner, false);
  assert.equal(ox.institutions[0].realizedFundReturn, "unknown");
});

test("project people distinguish authored viewpoints from portfolio partner labels, without invented deal leadership", () => {
  const graph = buildCanonicalInvestorProjectGraph();
  const people = graph.flatMap((p) => p.institutions.flatMap((i) => i.personAttributions));
  assert.ok(people.some((p) => p.name === "Alfred Lin" && p.type === "portfolio-listed-partner"));
  assert.ok(people.some((p) => p.name === "Max Bautin" && p.type === "article-attributed-viewpoint"));
  assert.ok(people.some((p) => p.name === "Dr. Prineha Narang" && p.type === "article-attributed-viewpoint"));
  assert.ok(people.every((p) => p.independentlyConfirmedDealOwner === false));
  assert.ok(people.every((p) => p.originalUrl.startsWith("https://")));
  assert.ok(graph.every((p) => p.institutions.every((i) => i.confirmedTransactionOwner === false)));
});

test("follow-on funding rounds and original commercial claims stay separate without inferred cashflow", () => {
  const graph = buildCanonicalInvestorProjectGraph();
  const foxglove = graph.find((p) => p.projectId === "foxglove")!;
  assert.equal(foxglove.institutions.length, 1);
  assert.deepEqual(foxglove.institutions[0].investmentDisclosures.map((r) => r.round), ["Series A", "Series B"]);
  assert.deepEqual(foxglove.institutions[0].investmentDisclosures.map((r) => r.roundAmount?.value),
    [15_000_000, 40_000_000]);
  assert.ok(foxglove.institutions[0].investmentDisclosures.every((r) => r.investorAmount === null));
  const nyobolt = graph.find((p) => p.projectId === "nyobolt")!;
  assert.equal(nyobolt.institutions[0].investmentDisclosures.length, 2);
  assert.equal(nyobolt.institutions[0].outcomes.length, 1);
  assert.equal(nyobolt.institutions[0].outcomes[0].status, "company-reported-commercial-update");
  assert.equal(nyobolt.institutions[0].outcomes[0].sourceKind, "investor-hosted-company-release");
  assert.equal(nyobolt.institutions[0].realizedFundReturn, "unknown");
});

test("unknown, colliding or unsourced identity mappings fail closed before publication", () => {
  const current: readonly ProjectIdentity[] = identities.projects;
  const badProject = {...investorEvidenceRecords[0], id: "unverified", project: "GraphCoReX"} as InvestorEvidenceRecord;
  assert.ok(validateInvestorProjectIdentities(current, [...investorEvidenceRecords, badProject])
    .some((e) => e.includes("unmapped evidence project")));
  const aliasCollision = [...current, {
    id: "another-physical", name: "Physical Intelligence",
    observedNames: ["Physical Intelligence"], identityEvidenceUrls: [
      "https://www.luxcapital.com/companies/physical-intelligence",
    ],
  }];
  assert.ok(validateInvestorProjectIdentities(aliasCollision).some((e) => e.includes("ambiguous project alias")));
  const badSource = current.map((p) => p.id === "physical-intelligence" ?
    {...p, identityEvidenceUrls: ["https://totally-unreviewed.example.net/projects/p-i"]} : p);
  assert.ok(validateInvestorProjectIdentities(badSource).some((e) => e.includes("identity source not traceable")));
  assert.throws(() => buildCanonicalInvestorProjectGraph(current, [...investorEvidenceRecords, badProject]),
    /Canonical project review required/);
});

test("static research page exposes identity graph and full sample denominator, not new browser network calls", () => {
  const page = read("app/innovation-capital/investors/page.tsx");
  assert.match(page, /validateInvestorProjectIdentities/);
  assert.match(page, /<InvestorProjectEvidenceNetwork/);
  const view = read("app/innovation-capital/investors/project-evidence-network.tsx");
  assert.match(view, /机构—项目证据关系/);
  assert.match(view, /30家机构的项目证据覆盖与缺口/);
  assert.match(view, /不能据此确认独家交易责任/);
  assert.doesNotMatch(view, /fetch\(|setInterval\(|tracking-admin\/v1/);
});

test("Catalyst graph keeps Sequoia's seed disclosure separate from George Robson's viewpoint", () => {
  const catalyst = buildCanonicalInvestorProjectGraph().find((item) => item.projectId === "catalyst-ai-investing");
  assert.ok(catalyst);
  assert.equal(catalyst.name, "Catalyst");
  assert.equal(catalyst.institutions.length, 1);
  const sequoia = catalyst.institutions[0];
  assert.equal(sequoia.institutionId, "sequoia");
  assert.equal(sequoia.investmentDisclosures.length, 1);
  assert.equal(sequoia.investmentDisclosures[0].round, "Seed");
  assert.equal(sequoia.investmentDisclosures[0].investorAmount, null);
  assert.equal(sequoia.viewpointRecordCount, 1);
  assert.equal(sequoia.personAttributions[0]?.name, "George Robson");
  assert.equal(sequoia.confirmedTransactionOwner, false);
  assert.equal(sequoia.realizedFundReturn, "unknown");
});
