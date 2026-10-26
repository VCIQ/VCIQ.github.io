import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  applyCompanyTechnologyEvidenceReview as review,
  getCompanyVentureProfile,
  type CompanyVentureProfile,
} from "../lib/venture-profile-data";

function fixture(): CompanyVentureProfile {
  return {
    slug: "smic", name: "中芯国际", updatedAt: "2026-10-02T07:00:18Z", status: "ok",
    background: "已有概览不因技术字段复核而改写。",
    technology: "SMIC DOCUMENT DISTRIBUTION PLATFORM Documents and Downloads Login 文件下载登陆",
    researchTechnology: "SMIC DOCUMENT DISTRIBUTION PLATFORM Documents and Downloads Login",
    products: ["晶圆制造", "工艺平台", "SMIC Document Distribution Platform SMIC文件外发平台", "供应商平台", "文档分发平台"],
    technologyProducts: [
      { name: "晶圆制造", description: "已有技术产品记录。", sourceUrl: "https://www.smics.com/site/technology" },
      { name: "文档分发平台", description: "误提取的登录门户。" },
      { name: "错误来源产品", description: "只有登录页作为来源。", sourceUrl: "http://service.smics.com/ddplatform/" },
    ],
    team: [], financing: [], capitalMarkets: [], evidenceScore: 87,
    sources: [{ name: "中芯国际", url: "http://service.smics.com/ddplatform/", level: "官方披露", section: "technology", title: "SMIC DOCUMENT DISTRIBUTION PLATFORM" }],
  };
}

test("known company portal noise is withheld without inventing replacement technology", () => {
  const raw = fixture(); const before = JSON.stringify(raw); const result = review(raw);
  assert.equal(JSON.stringify(raw), before);
  assert.match(result.technology, /待补充可核验资料/u);
  assert.match(result.researchTechnology!, /待补充可核验资料/u);
  assert.doesNotMatch(result.technology, /DOCUMENT DISTRIBUTION|Login/iu);
  assert.deepEqual(result.products, ["晶圆制造", "工艺平台"]);
  assert.deepEqual(result.technologyProducts?.map((p) => p.name), ["晶圆制造"]);
  assert.equal(result.background, raw.background);
  assert.equal(result.updatedAt, raw.updatedAt);
  assert.deepEqual(result.team, raw.team);
  assert.deepEqual(result.capitalMarkets, raw.capitalMarkets);
});

test("raw source link remains available but cannot support an unchanged completeness score", () => {
  const raw = fixture(); const result = review(raw);
  assert.equal(result.sources[0].url, raw.sources[0].url);
  assert.equal(result.sources[0].level, raw.sources[0].level);
  assert.equal(result.sources[0].title, raw.sources[0].title);
  assert.match(result.sources[0].section!, /非技术证据/u);
  assert.equal(result.evidenceScore, undefined);
  assert.equal(result.evidenceReviewRequired, true);
  assert.equal(result.status, "partial");
  assert.equal(review(result), result);
});

test("other issuers and non-matching source hosts are not changed", () => {
  for (const raw of [
    { ...fixture(), slug: "document-software-company" },
    { ...fixture(), sources: [] },
    { ...fixture(), sources: [{ ...fixture().sources[0], url: "https://service.smics.com.evil.example/ddplatform/" }] },
    { ...fixture(), sources: [{ ...fixture().sources[0], url: "https://www.smics.com/site/news_read/3722" }] },
  ]) assert.equal(review(raw), raw);
});

test("a later clean profile is not permanently pinned to pending review", () => {
  const raw = { ...fixture(), technology: "后续有独立技术资料支持的描述。", researchTechnology: "后续可核验的技术说明。",
    products: ["晶圆制造"], technologyProducts: [fixture().technologyProducts![0]] };
  assert.equal(review(raw), raw);
  assert.equal(review(raw).evidenceScore, 87);
});

test("a separately sourced product is not removed merely for a matching name", () => {
  const raw = fixture();
  raw.technologyProducts!.push({ name: "供应商平台", description: "具有独立详情来源。", sourceUrl: "https://www.smics.com/site/product/verified" });
  assert.ok(review(raw).technologyProducts!.some((p) => p.sourceUrl?.endsWith("/verified")));
  assert.ok(review(raw).products.includes("供应商平台"));
});

test("the shared company reader applies the review before rendering", () => {
  const current = getCompanyVentureProfile("smic");
  assert.ok(current);
  assert.doesNotMatch(`${current.technology} ${current.researchTechnology ?? ""}`, /SMIC DOCUMENT DISTRIBUTION PLATFORM|Documents and Downloads Login/iu);
  const page = readFileSync(new URL("../app/companies/[slug]/page.tsx", import.meta.url), "utf8");
  assert.match(page, /venture\.evidenceReviewRequired/u);
  assert.match(page, /技术资料及完整度评分待复核/u);
});
