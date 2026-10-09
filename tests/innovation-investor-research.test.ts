import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {
  globalInnovationInvestors, investorEvidenceRecords, investorEvidenceSummary,
  validateInvestorResearch, investorReturnLabel, investorProjectEvidenceTimelines,
  type InvestorEvidenceRecord,
} from "../lib/innovation-investor-research";

const source = (path: string) => fs.readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("30 curated institutions have unique identities and validated primary-source entry points", () => {
  assert.equal(globalInnovationInvestors.length, 30);
  assert.equal(new Set(globalInnovationInvestors.map((row) => row.id)).size, 30);
  assert.deepEqual(validateInvestorResearch(), []);
  assert.equal(new Set(globalInnovationInvestors.map((row) => row.regionGroup)).size, 4);
  const sequoia = globalInnovationInvestors.find((row) => row.id === "sequoia")!;
  const hongshan = globalInnovationInvestors.find((row) => row.id === "hongshan")!;
  assert.notEqual(sequoia.officialUrl, hongshan.officialUrl);
  assert.notEqual(sequoia.id, hongshan.id);
  assert.match(globalInnovationInvestors.find((row) => row.id === "vertex-sea-india")!.officialUrl, /vertexventures\.sg/);
});

test("coverage reports six source-backed institutions, not complete coverage of thirty", () => {
  const summary = investorEvidenceSummary();
  assert.equal(summary.registeredInstitutions, 30);
  assert.equal(summary.evidenceCoveredInstitutions, 6);
  assert.equal(summary.reviewedRecords, 14);
  assert.equal(summary.disclosedInvestmentEvents, 5);
  assert.equal(summary.outcomeMilestones, 1);
  assert.equal(summary.returnStatus, "unknown");
});

test("round total is not an investor cheque and acquisition is not realized investor return", () => {
  const tars = investorEvidenceRecords.find((row) => row.id === "qiming-tars-angel-2025")!;
  assert.equal(tars.roundAmount?.value, 120_000_000);
  assert.equal(tars.investorAmount, null);
  assert.equal(tars.participation, "co-lead");
  const graphcore = investorEvidenceRecords.find((row) => row.id === "graphcore-acquisition-2024")!;
  assert.equal(graphcore.resultStatus, "acquired");
  assert.equal(graphcore.realizedProceeds, null);
  assert.match(investorReturnLabel(graphcore), /实际回报未知/);
  const fund = investorEvidenceRecords.find((row) => row.kind === "fund-announcement")!;
  assert.equal(fund.project, null);
  assert.equal(fund.investorAmount, null);
});

test("coarse dates and portfolio partner labels never fabricate deal details", () => {
  const partner = investorEvidenceRecords.find((row) => row.id === "sequoia-physical-intelligence-partner")!;
  assert.equal(partner.date, "2024");
  assert.equal(partner.datePrecision, "year");
  assert.equal(partner.linkedPerson?.name, "Alfred Lin");
  assert.equal(partner.participation, null);
  assert.equal(partner.speakers.length, 0);
  const oqc = investorEvidenceRecords.find((row) => row.id === "utec-oqc-investment-2022")!;
  assert.equal(oqc.date, "2022-06");
  assert.equal(oqc.datePrecision, "month");
});

test("invalid records fail closed instead of promoting statements into investments", () => {
  const original = investorEvidenceRecords[0];
  const tampered = {...original, kind:"viewpoint", investorAmount:{value:1,currency:"USD"}} as InvestorEvidenceRecord;
  assert.ok(validateInvestorResearch(globalInnovationInvestors, [tampered]).some((error) => error.includes("non-investment")));
  assert.ok(validateInvestorResearch([...globalInnovationInvestors, globalInnovationInvestors[0]]).some((error) => error.includes("duplicate institution")));
  const badSource = {...original, source:{...original.source, url:"https://user:pass@example.com/"}} as InvestorEvidenceRecord;
  assert.ok(validateInvestorResearch(globalInnovationInvestors, [badSource]).some((error) => error.includes("missing evidence")));
  const inventedReturn = {...original, realizedProceeds:500} as unknown as InvestorEvidenceRecord;
  assert.ok(validateInvestorResearch(globalInnovationInvestors, [inventedReturn]).some((error) => error.includes("unsupported realized")));
});

test("new project evidence retains official dates, deal roles and authorship limits", () => {
  const pref = investorEvidenceRecords.find((row) => row.id === "a16z-preference-model-investment-2026")!;
  assert.equal(pref.date, "2026-10-07");
  assert.equal(pref.kind, "investment");
  assert.equal(pref.round, null);
  assert.equal(pref.participation, "disclosed-investor");
  assert.equal(pref.investorAmount, null);
  const jennifer = investorEvidenceRecords.find((row) => row.id === "a16z-preference-model-thesis-2026")!;
  assert.equal(jennifer.speakers[0]?.name, "Jennifer Li");
  assert.match(jennifer.speakers[0]?.projectResponsibility ?? "", /不单凭署名/);
  const ricursive = investorEvidenceRecords.find((row) => row.id === "lightspeed-ricursive-series-a-2026")!;
  assert.equal(ricursive.participation, "lead");
  assert.equal(ricursive.round, "Series A");
  assert.equal(ricursive.roundAmount, null);
  assert.equal(ricursive.investorAmount, null);
  const thesis = investorEvidenceRecords.find((row) => row.id === "lightspeed-ricursive-ai-chip-thesis-2026")!;
  assert.deepEqual(thesis.speakers.map((row) => row.name), ["Guru Chahal", "Ravi Mhatre", "Jonah Cader"]);
  assert.ok(thesis.speakers.every((row) => row.attribution === "paraphrase"));
  const oris = investorEvidenceRecords.find((row) => row.id === "earlybird-oris-portfolio-relation-2026")!;
  assert.equal(oris.kind, "portfolio-relationship");
  assert.equal(oris.participation, null);
  assert.equal(oris.investorAmount, null);
  const orisView = investorEvidenceRecords.find((row) => row.id === "earlybird-oris-space-energy-thesis-2026")!;
  assert.deepEqual(orisView.speakers, []);
  assert.ok(investorEvidenceRecords.every((row) => row.realizedProceeds === null));
});

test("one publication can support a deal and a viewpoint, without counting two investments", () => {
  const projects = investorProjectEvidenceTimelines();
  assert.equal(projects.length, 8);
  const pref = projects.find((row) => row.project === "Preference Model")!;
  assert.equal(pref.investmentDisclosures, 1);
  assert.equal(pref.viewpointDisclosures, 1);
  assert.equal(pref.sourceCount, 1);
  assert.equal(pref.returnStatus, "unknown");
  const lightspeed = projects.find((row) => row.project === "Ricursive Intelligence")!;
  assert.equal(lightspeed.investmentDisclosures, 1);
  assert.equal(lightspeed.sourceCount, 1);
  const oris = projects.find((row) => row.project === "ORiS")!;
  assert.equal(oris.investmentDisclosures, 0);
  assert.equal(oris.portfolioRelationships, 1);
  assert.equal(oris.outcomeMilestones, 0);
  assert.equal(oris.returnStatus, "unknown");
  assert.ok(projects.every((row) => row.project !== "The Machine Age Fund"));
});

test("Graphcore chronology sorts the old investment before the 2024 acquisition, without return inference", () => {
  const graphcore = investorProjectEvidenceTimelines().find((row) => row.project === "Graphcore")!;
  assert.equal(graphcore.earliestEvidenceDate, "2017-11-13");
  assert.equal(graphcore.latestEvidenceDate, "2024-07-11");
  assert.equal(graphcore.sourceCount, 2);
  assert.equal(graphcore.investmentDisclosures, 1);
  assert.equal(graphcore.outcomeMilestones, 1);
  assert.equal(graphcore.entries.at(-1)?.kind, "outcome");
  assert.equal(graphcore.returnStatus, "unknown");
});

test("duplicate investment rows fail closed, but a same-day authored viewpoint may coexist", () => {
  const ricursive = investorEvidenceRecords.find((row) => row.id === "lightspeed-ricursive-series-a-2026")!;
  const viewpoint = investorEvidenceRecords.find((row) => row.id === "lightspeed-ricursive-ai-chip-thesis-2026")!;
  assert.deepEqual(validateInvestorResearch(globalInnovationInvestors, [ricursive, viewpoint]), []);
  const duplicate = {...ricursive, id:"copied-investment"} as InvestorEvidenceRecord;
  assert.ok(validateInvestorResearch(globalInnovationInvestors, [ricursive, duplicate]).some((error) => error.includes("duplicate investment disclosure")));
});

test("institution research remains a nested evidence view and projects precede listed benchmarks", () => {
  const page = source("app/innovation-capital/page.tsx");
  assert.ok(page.indexOf("<InnovationDirectory") < page.indexOf("<ListedInnovationDirectory"));
  assert.match(page, /<InnovationGlobalInvestors/);
  assert.match(page, /不是今天的采集成功时间/);
  assert.match(source("app/sitemap.ts"), /\/innovation-capital\/investors/);
  const client = source("app/innovation-capital/investors/research-directory.tsx");
  assert.match(client, /import type/);
  assert.doesNotMatch(client, /fetch\(|setInterval\(|tracking-admin\/v1/);
  assert.match(client, /无记录/);
  const chronology = source("app/innovation-capital/investors/project-evidence-timelines.tsx");
  assert.match(chronology, /不从日期推定交易交割/);
  assert.match(chronology, /基金现金收益仍未知/);
  assert.match(source("app/innovation-capital/investors/page.tsx"), /<ProjectEvidenceTimelines/);
});
