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

test("evidence samples now span ten institutions, without implying complete portfolio coverage", () => {
  const summary = investorEvidenceSummary();
  assert.equal(summary.registeredInstitutions, 30);
  assert.equal(summary.evidenceCoveredInstitutions, 10);
  assert.equal(summary.reviewedRecords, 25);
  assert.equal(summary.disclosedInvestmentEvents, 11);
  assert.equal(summary.outcomeMilestones, 2);
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
  assert.equal(projects.length, 12);
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

test("Lux Physical Intelligence keeps its dated memo separate from year-only investment milestone", () => {
  const group = investorProjectEvidenceTimelines().find((x) => x.institutionId === "lux" && x.project === "Physical Intelligence")!;
  assert.equal(group.investmentDisclosures, 1);
  assert.equal(group.viewpointDisclosures, 1);
  assert.equal(group.sourceCount, 2);
  assert.equal(group.earliestEvidenceDate, "2024");
  assert.equal(group.latestEvidenceDate, "2024-05-19");
  const deal = group.entries.find((x) => x.kind === "investment")!;
  assert.equal(deal.datePrecision, "year");
  assert.equal(deal.source.publishedAt, null);
  assert.equal(deal.round, null);
  assert.equal(deal.investorAmount, null);
  const speaker = group.entries.find((x) => x.kind === "viewpoint")!.speakers[0];
  assert.equal(speaker.name, "Josh Wolfe");
  assert.match(speaker.projectResponsibility, /没有独立轮次决策/);
});

test("DCVC disclosed Series C funding is the whole round, not DCVC's personal cheque", () => {
  const investment = investorEvidenceRecords.find((r) => r.id === "dcvc-quantum-motion-series-c-2026")!;
  assert.equal(investment.institutionId, "dcvc");
  assert.equal(investment.round, "Series C");
  assert.equal(investment.participation, "lead");
  assert.equal(investment.roundAmount?.value, 160_000_000);
  assert.equal(investment.investorAmount, null);
  const thesis = investorEvidenceRecords.find((r) => r.id === "dcvc-quantum-motion-silicon-thesis-2026")!;
  assert.equal(thesis.speakers[0]?.name, "Dr. Prineha Narang");
  assert.match(thesis.speakers[0]?.roleAtPublication ?? "", /Operating Partner/);
  assert.equal(thesis.speakers[0]?.attribution, "paraphrase");
  assert.equal(thesis.investorAmount, null);
  assert.equal(investorProjectEvidenceTimelines().find((x) => x.project === "Quantum Motion")?.sourceCount, 1);
});

test("Eclipse's two rounds in Foxglove stay separate and no claim creates a realized return", () => {
  const g = investorProjectEvidenceTimelines().find((x) => x.project === "Foxglove")!;
  assert.equal(g.investmentDisclosures, 2);
  assert.equal(g.sourceCount, 2);
  assert.equal(g.viewpointDisclosures, 1);
  assert.equal(g.earliestEvidenceDate, "2022-10-11");
  assert.equal(g.latestEvidenceDate, "2025-11-12");
  assert.deepEqual(g.entries.filter((x) => x.kind === "investment").map((x) => [x.round, x.roundAmount?.value, x.participation]), [
    ["Series A", 15_000_000, "lead"], ["Series B", 40_000_000, "participant"],
  ]);
  assert.ok(g.entries.every((x) => x.investorAmount === null && x.realizedProceeds === null));
  assert.match(g.entries.find((x) => x.kind === "viewpoint")!.speakers[0]?.projectResponsibility ?? "", /不由此推断/);
});

test("IQ Capital Nyobolt includes follow-on investment and only company-reported commercial progress", () => {
  const g = investorProjectEvidenceTimelines().find((x) => x.institutionId === "iq-capital" && x.project === "Nyobolt")!;
  assert.equal(g.investmentDisclosures, 2);
  assert.equal(g.outcomeMilestones, 1);
  assert.equal(g.viewpointDisclosures, 1);
  assert.equal(g.sourceCount, 2);
  const deals = g.entries.filter((x) => x.kind === "investment");
  assert.deepEqual(deals.map((x) => [x.round, x.roundAmount?.value, x.participation]), [
    [null, 30_000_000, "co-lead"], ["Series C", 60_000_000, "participant"],
  ]);
  const outcome = g.entries.find((x) => x.kind === "outcome")!;
  assert.equal(outcome.resultStatus, "company-reported-commercial-update");
  assert.equal(outcome.source.kind, "investor-hosted-company-release");
  assert.match(outcome.summary, /尚非独立财务审计/);
  assert.equal(outcome.realizedProceeds, null);
  const tampered = {...outcome, source: {...outcome.source, kind:"investor-official"}} as InvestorEvidenceRecord;
  assert.ok(validateInvestorResearch(globalInnovationInvestors, [tampered]).some((error) =>
    error.includes("company-reported outcome lacks company disclosure source"),
  ));
  const speaker = g.entries.find((x) => x.kind === "viewpoint")!.speakers[0];
  assert.equal(speaker.name, "Max Bautin");
  assert.match(speaker.roleAtPublication, /Managing Partner/);
  assert.equal(g.returnStatus, "unknown");
});

test("new observed company updates cannot be interpreted as audited investment profits", () => {
  const sampled = investorEvidenceRecords.filter((r) => ["lux", "dcvc", "eclipse", "iq-capital"].includes(r.institutionId));
  assert.equal(sampled.length, 11);
  assert.ok(sampled.every((r) => r.investorAmount === null && r.realizedProceeds === null));
  const noUnsignedSpeaker = sampled.filter((r) => r.speakers.length).every((r) =>
    r.speakers.every((person) => person.attribution === "paraphrase" && person.projectResponsibility.length > 15),
  );
  assert.equal(noUnsignedSpeaker, true);
  assert.deepEqual(validateInvestorResearch(), []);
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
  assert.match(client, /公司披露的商业化进展（尚无独立财务或工程验收）/);
  const chronology = source("app/innovation-capital/investors/project-evidence-timelines.tsx");
  assert.match(chronology, /不从日期推定交易交割/);
  assert.match(chronology, /基金现金收益仍未知/);
  assert.match(source("app/innovation-capital/investors/page.tsx"), /<ProjectEvidenceTimelines/);
});
