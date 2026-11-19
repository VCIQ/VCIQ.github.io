import assert from "node:assert/strict";
import test from "node:test";
import {
  getArticleInstitutionRelations,
  getSectorInstitutionRelations,
  institutionDirectoryHref,
  normalizeInstitutionTerm,
} from "../lib/institution-activity";
import type { IntelligenceEvent } from "../lib/intelligence-data";
import { institutionDirectory } from "../lib/institution-ranking-data";

function event(
  overrides: Partial<IntelligenceEvent> & Pick<IntelligenceEvent, "id" | "title">,
): IntelligenceEvent {
  return {
    id: overrides.id,
    title: overrides.title,
    summary: overrides.summary ?? "测试公开事件",
    type: overrides.type ?? "融资",
    region: overrides.region ?? "中国",
    sector: overrides.sector ?? "AI / AGI",
    company: overrides.company ?? "测试公司",
    companySlug: overrides.companySlug,
    institutions: overrides.institutions,
    publishedAt: overrides.publishedAt ?? "2026-07-29",
    importance: overrides.importance ?? 80,
    source: overrides.source ?? {
      name: "测试来源",
      url: `https://example.com/${overrides.id}`,
      level: "官方披露",
    },
  };
}

test("institution identity normalization joins spacing and punctuation variants", () => {
  assert.equal(normalizeInstitutionTerm("IDG 资本"), normalizeInstitutionTerm("IDG资本"));
  assert.equal(normalizeInstitutionTerm("HongShan（红杉中国）"), "hongshan红杉中国");
});

test("explicit institution metadata activates the matching directory institution", () => {
  const relations = getArticleInstitutionRelations([
    event({
      id: "idg-round",
      title: "某公司完成新一轮融资",
      institutions: ["IDG 资本"],
    }),
  ]);
  const idg = relations.find((relation) => relation.institution.name === "IDG资本");
  assert.ok(idg);
  assert.equal(idg.active, true);
  assert.equal(idg.directEvents.length, 1);
  assert.equal(idg.portfolioEvents.length, 0);
});

test("relation queries recalculate event text when the event is revised", () => {
  const item = event({
    id: "mutable-research-note",
    title: "某公司公开技术动态",
    company: "测试公司",
    institutions: [],
  });
  assert.equal(
    getArticleInstitutionRelations([item]).some(
      (relation) => relation.institution.name === "IDG资本",
    ),
    false,
  );
  item.institutions = ["IDG 资本"];
  const updated = getArticleInstitutionRelations([item]).find(
    (relation) => relation.institution.name === "IDG资本",
  );
  assert.ok(updated);
  assert.deepEqual(updated.directEvents.map((row) => row.id), [item.id]);
  assert.equal(updated.portfolioEvents.length, 0);
});

test("portfolio company activity creates a relation without pretending it is a direct investment", () => {
  const relations = getArticleInstitutionRelations([
    event({
      id: "harvey-product",
      title: "Harvey 发布企业法律 AI 产品",
      type: "产品发布",
      company: "Harvey",
      companySlug: "harvey",
      institutions: [],
    }),
  ]);
  const sequoia = relations.find(
    (relation) => relation.institution.name === "Sequoia Capital",
  );
  assert.ok(sequoia);
  assert.equal(sequoia.active, false);
  assert.equal(sequoia.directEvents.length, 0);
  assert.equal(sequoia.portfolioEvents.length, 1);
});

test("technology tracks do not absorb ranking-only institutions through broad technology labels", () => {
  const relations = getSectorInstitutionRelations(
    {
      slug: "ai",
      name: "AI / AGI",
      aliases: ["人工智能", "大模型"],
      keywords: ["AI", "智能体"],
    },
    [],
  );
  assert.equal(
    relations.some((relation) => relation.institution.name === "中科创星"),
    false,
  );
  assert.equal(
    relations.some((relation) => relation.institution.name === "Sequoia Capital"),
    true,
  );
});

test("venture-capital tracks activate institutions from matching audited ranking categories", () => {
  const relations = getSectorInstitutionRelations(
    {
      slug: "venture-capital",
      name: "风险投资",
      aliases: ["创业投资", "VC"],
    },
    [],
  );
  const active = relations.filter((relation) => relation.active);
  assert.ok(active.length >= 40);
  assert.ok(active.some((relation) => relation.institution.name === "IDG资本"));
  assert.ok(active.some((relation) => relation.institution.name === "真格基金"));
});

test("directory href opens a profile when available and a focused directory result otherwise", () => {
  const sequoia = institutionDirectory.find((item) => item.name === "Sequoia Capital");
  const zhongke = institutionDirectory.find((item) => item.name === "中科创星");
  assert.ok(sequoia);
  assert.ok(zhongke);
  assert.equal(institutionDirectoryHref(sequoia), "/institutions/sequoia-capital");
  assert.equal(
    institutionDirectoryHref(zhongke),
    `/institutions?institution=${encodeURIComponent("中科创星")}`,
  );
});
