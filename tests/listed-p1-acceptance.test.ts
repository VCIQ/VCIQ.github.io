import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { applyArticleMetadataReview } from "../lib/article-metadata-reviews";
import { isActionableCompanySignal } from "../lib/company-update-curation";

const manifest = JSON.parse(readFileSync(new URL("../config/article_metadata_reviews.json", import.meta.url), "utf8"));
const review = manifest.reviews.find((row: { id: string }) => row.id === "resonac-sic-not-nvidia");
function fixture() {
  return {
    id: review.articleId, sourceId: review.sourceId, title: review.expectedTitle,
    summary: "半导体材料制造商 Resonac Holdings 开发出300毫米SiC衬底。",
    company: "英伟达", companySlug: "nvidia", companySlugs: ["nvidia"],
    companyMatch: { slug: "nvidia", method: "structured-company", confidence: 0.97 },
    companyMatches: [{ slug: "nvidia", method: "structured-company", confidence: 0.97 }],
    companyCandidateSlugs: ["nvidia"], mentionedCompanies: ["英伟达"],
    publishedAt: "2026-09-29", importance: 82, qualityScore: 25, qualityStatus: "低可信",
    sector: "半导体", type: "产品发布",
    source: { url: review.sourceUrl, name: "半导体行业观察", level: "媒体报道" },
  };
}

test("review removes all stale Nvidia bindings without adding a new company profile", () => {
  const raw = fixture();
  const before = JSON.stringify(raw);
  const result = applyArticleMetadataReview(raw);
  assert.equal(result.company, "Resonac Holdings");
  for (const key of ["companySlug", "companySlugs", "companyMatch", "companyMatches", "companyCandidateSlugs"]) {
    assert.equal(key in result, false, key);
  }
  assert.deepEqual(result.mentionedCompanies, ["Resonac Holdings"]);
  assert.equal(JSON.stringify(raw), before);
  assert.equal(applyArticleMetadataReview(result), result);
});

test("subject correction cannot raise confidence, importance or refresh publication time", () => {
  const raw = fixture(); const result = applyArticleMetadataReview(raw);
  assert.deepEqual(result.source, raw.source);
  for (const key of ["publishedAt", "importance", "qualityScore", "qualityStatus"] as const) {
    assert.equal(result[key], raw[key]);
  }
});

test("subject review requires exact identity and supporting summary, and respects a later correction", () => {
  for (const change of [
    { id: "other" }, { sourceId: "other" }, { title: "other" },
    { summary: "不同主体发布其他消息" }, { source: { ...fixture().source, url: "https://example.org/other" } },
    { company: "Another reviewed company" },
  ]) {
    const raw = { ...fixture(), ...change };
    assert.equal(applyArticleMetadataReview(raw), raw);
  }
});

test("review only removes the explicitly rejected entity, not unrelated retained bindings", () => {
  const raw = fixture();
  raw.companySlugs.push("another-company");
  raw.companyMatches.push({ slug: "another-company", method: "official-domain", confidence: 0.99 });
  raw.mentionedCompanies.push("Another company");
  const result = applyArticleMetadataReview(raw);
  assert.deepEqual(result.companySlugs, ["another-company"]);
  assert.equal(result.companyMatches[0].slug, "another-company");
  assert.deepEqual(result.mentionedCompanies, ["Another company", "Resonac Holdings"]);
});

test("company latest-change selection rejects low-quality records even with an actionable headline", () => {
  const base = { title: "Company launches chip", summary: "New chip released", label: "产品发布", sourceLevel: "媒体报道" };
  assert.equal(isActionableCompanySignal({ ...base, qualityStatus: "低可信" }), false);
  assert.equal(isActionableCompanySignal({ ...base, qualityScore: 25 }), false);
  assert.equal(isActionableCompanySignal({ ...base, qualityScore: 75 }), true);
  assert.equal(isActionableCompanySignal(base), true);
  const code = readFileSync(new URL("../lib/company-research.ts", import.meta.url), "utf8");
  assert.match(code, /qualityScore: event\.qualityScore/);
  assert.match(code, /qualityStatus: event\.qualityStatus/);
  const staticReader = readFileSync(new URL("../lib/intelligence-data.ts", import.meta.url), "utf8");
  assert.match(staticReader, /snapshot\.articles\.map\(applyArticleMetadataReview\)/);
});
