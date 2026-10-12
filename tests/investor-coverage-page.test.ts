import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  buildInvestorCoverageDirectory,
} from "../lib/innovation-investor-coverage";
import {
  investorEvidenceRecords,
  type InvestorEvidenceRecord,
} from "../lib/innovation-investor-research";
import { innovationInvestorRegistryV2 } from "../lib/innovation-investor-registry-v2";

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("coverage page uses canonical distinct count, with transparent overlapping cohorts", () => {
  const {rows, summary} = buildInvestorCoverageDirectory();
  assert.equal(summary.uniqueInstitutions, innovationInvestorRegistryV2.length);
  assert.equal(summary.uniqueInstitutions, 35);
  assert.equal(summary.globalCore, 30);
  assert.equal(summary.chinaFocus, 13);
  assert.equal(summary.overlap, 8);
  assert.equal(summary.withVerifiedEvidence, rows.filter((x) => x.reviewedEvidenceCount > 0).length);
  assert.equal(summary.reviewedEvidenceRecords, investorEvidenceRecords.length);
  assert.equal(summary.registeredHomepages + summary.pendingOfficialSources, rows.length);
  assert.equal(rows.reduce((sum, item) => sum + item.reviewedEvidenceCount, 0), investorEvidenceRecords.length);
  assert.ok(rows.every((row) => row.coverageScore === null && row.lastScoutAt === null));
});

test("Index Oratomic and Sequoia TypeSafe/Catalyst map to unchanged source-backed research", () => {
  const {rows} = buildInvestorCoverageDirectory();
  const byId = new Map(rows.map((row) => [row.id, row]));
  assert.equal(byId.get("index")?.lastReviewedInvestment?.company, "Oratomic");
  assert.ok(byId.get("index")?.lastReviewedInvestment?.sourceUrl.includes("indexventures.com"));
  assert.ok((byId.get("sequoia")?.reviewedCompanyCount ?? 0) >= 2);
  assert.ok((byId.get("sequoia")?.investmentDisclosureCount ?? 0) >= 2);
  assert.equal(byId.get("hongshan")?.id, "hongshan");
  for (const id of ["five-years", "northern-light", "shunwei"]) {
    const row = byId.get(id)!;
    assert.equal(row.officialHomepage, null);
    assert.equal(row.lastScoutAt, null);
    assert.equal(row.coverageScore, null);
  }
});

test("adding a source-backed sample updates one firm without inventing source health", () => {
  const source = investorEvidenceRecords.find((x) => x.id === "sequoia-catalyst-seed-20261008")!;
  assert.ok(source);
  const synthetic = {
    ...source,
    id: "fixture-only-china-institution",
    institutionId: "gaorong",
    project: "Fixture-only Company",
    date: "2026-10-11",
    source: {...source.source, url: "https://www.gaorongcapital.com/fixture-only"},
  } as InvestorEvidenceRecord;
  const before = buildInvestorCoverageDirectory().rows.find((x) => x.id === "gaorong")!;
  const after = buildInvestorCoverageDirectory(undefined, [...investorEvidenceRecords, synthetic])
    .rows.find((x) => x.id === "gaorong")!;
  assert.equal(after.reviewedEvidenceCount, before.reviewedEvidenceCount + 1);
  assert.equal(after.investmentDisclosureCount, before.investmentDisclosureCount + 1);
  assert.equal(after.lastReviewedInvestment?.company, "Fixture-only Company");
  assert.equal(after.coverageScore, null);
  assert.equal(after.lastScoutAt, null);
});

test("coverage has a discoverable public route but does not alter home feed/focus logic", () => {
  const page = read("app/innovation-capital/coverage/page.tsx");
  const card = read("app/innovation-capital/coverage/coverage-directory.tsx");
  const innovation = read("components/innovation-global-investors.tsx");
  const sitemap = read("app/sitemap.ts");
  assert.match(page, /buildInvestorCoverageDirectory/);
  assert.match(page, /investorRegistryV2Errors/);
  assert.match(innovation, /\/innovation-capital\/coverage\//);
  assert.match(sitemap, /\/innovation-capital\/coverage/);
  assert.match(card, /china-focus/);
  assert.match(card, /pending-official-source/);
  assert.doesNotMatch(page, /fetch\(|setInterval\(|tracking-admin\/v1/);
  assert.doesNotMatch(card, /fetch\(|setInterval\(/);
});
