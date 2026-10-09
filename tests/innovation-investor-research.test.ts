import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {
  globalInnovationInvestors, investorEvidenceRecords, investorEvidenceSummary,
  validateInvestorResearch, investorReturnLabel, type InvestorEvidenceRecord,
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

test("coverage reports four sampled institutions, not complete coverage of thirty", () => {
  const summary = investorEvidenceSummary();
  assert.equal(summary.registeredInstitutions, 30);
  assert.equal(summary.evidenceCoveredInstitutions, 4);
  assert.equal(summary.reviewedRecords, 8);
  assert.equal(summary.disclosedInvestmentEvents, 3);
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
});
