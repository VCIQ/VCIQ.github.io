import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import approved from "../config/listed_innovation_companies.json";
import pending from "../config/listed_innovation_candidates.json";
import registry from "../config/company_registry.json";
import sources from "../config/official_company_sources.json";
import { listedInnovationCompanies } from "../lib/listed-innovation-companies";
import { buildHomepageInnovationCapitalIndex, buildInnovationCapitalFeedProjection,
  homepageInnovationCapitalAnnotation, matchesHomepageInnovationCapitalChannel } from "../lib/homepage-innovation-capital-channel";
import { buildHomepageFocusSelection } from "../lib/homepage-focus";
import { groupDisclosurePlanAttachments, projectHomepageCompanyDisclosureEvents } from "../lib/homepage-company-disclosure-events";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const emptyIndex = buildHomepageInnovationCapitalIndex({ items: [] });
function event(overrides: Partial<LiveIntelligenceEvent> = {}): LiveIntelligenceEvent {
  return { id: "p1-test", title: "AMD announces an AI acquisition", summary: "AMD signed an agreement. Closing is pending.",
    company: "AMD", sector: "半导体", type: "并购", region: "美国", importance: 89,
    publishedAt: "2026-09-28", source: { name: "AMD", url: "https://ir.amd.com/news-events/press-releases/test", level: "官方披露" }, ...overrides };
}

test("P1 is exactly 40 issuers, P2 exactly 50 pending candidates, without overlap", () => {
  assert.equal(approved.companies.length, 40);
  assert.equal(pending.candidates.length, 50);
  assert.equal(pending.decision, "pending");
  assert.equal(new Set(approved.companies.map((row) => row.companySlug)).size, 40);
  const p1 = new Set(approved.companies.map((row) => row.id));
  assert.ok(pending.candidates.every((row) => !p1.has(row.id)));
  assert.deepEqual(["美股", "A股", "港股"].map((market) => approved.companies.filter((row) => row.primaryMarket === market).length), [14, 15, 11]);
});

test("all approved companies use one canonical profile and matching official-source metadata", () => {
  const profiles = new Map(registry.companies.map((row) => [row.slug, row]));
  const official = new Map(sources.companies.map((row) => [row.slug, row]));
  assert.equal(profiles.size, registry.companies.length);
  assert.equal(official.size, sources.companies.length);
  assert.deepEqual([...profiles.keys()].sort(), [...official.keys()].sort());
  assert.equal(approved.companies.filter((row) => profiles.get(row.companySlug)?.registrySource === "owner-approved-listed-p1").length, 26);
  for (const row of approved.companies) {
    const profile = profiles.get(row.companySlug);
    const source = official.get(row.companySlug);
    assert.ok(profile && source, row.companySlug);
    assert.equal(profile.status, "已上市");
    assert.deepEqual([source.name, source.region, source.sector], [profile.name, profile.region, profile.sector]);
  }
});

test("cross-listings share a company; Alphabet securities do not create a second Google issuer", () => {
  const securities = approved.companies.flatMap((row) => row.securities.map((security) => `${security.exchange}:${security.ticker}`));
  assert.equal(securities.length, 45);
  assert.equal(new Set(securities).size, securities.length);
  for (const row of approved.companies) for (const security of row.securities) {
    assert.match(security.evidenceUrl, /^https:\/\//u);
    if (security.market === "港股") assert.match(security.ticker, /^\d{5}$/u);
    if (security.market === "A股") assert.match(security.ticker, /^\d{6}$/u);
  }
  const google = listedInnovationCompanies.find((row) => row.companySlug === "google")!;
  assert.equal(google.issuerRelationship, "parent");
  assert.equal(google.issuerName, "Alphabet Inc.");
  assert.deepEqual(google.securities.map((row) => row.ticker), ["GOOGL", "GOOG"]);
  assert.deepEqual(listedInnovationCompanies.find((row) => row.companySlug === "edge-medical")?.lifecycleProjectIds, ["citic-jingfeng"]);
  assert.notEqual(listedInnovationCompanies.find((row) => row.companySlug === "tsmc")?.region, "美国");
  assert.notEqual(listedInnovationCompanies.find((row) => row.companySlug === "asml")?.region, "美国");
});

test("approved material English and Chinese updates qualify without mutating events", () => {
  for (const row of [event(), event({ title: "NVIDIA releases a new GPU", company: "NVIDIA", type: "产品发布" }),
    event({ title: "宁德时代发布新一代储能电池并启动量产", company: "宁德时代", type: "产品发布" })]) {
    const before = JSON.stringify(row);
    const annotation = homepageInnovationCapitalAnnotation(row, emptyIndex);
    assert.ok(annotation);
    assert.ok(annotation.reasonCodes.includes("LISTED_COMPANY"));
    assert.equal(JSON.stringify(row), before);
  }
});

test("approval does not admit routine governance, price stories, promotions or P2", () => {
  for (const row of [
    event({ title: "宁德时代员工持股计划草案", company: "宁德时代", summary: "电池企业公布员工计划。" }),
    event({ title: "腾讯发布优惠券促销", company: "腾讯", summary: "AI推荐购物。" }),
    event({ title: "Microsoft declares a dividend", company: "Microsoft", summary: "Cloud AI company." }),
    event({ title: "Arm launches a new AI chip", company: "Arm", summary: "New chip launch." }),
    event({ title: "OtherCo launches new GPU", company: "OtherCo", summary: "NVIDIA is a historical reference." }),
    event({ title: "Camden launches new AI system", company: "Camden", summary: "No registered company is involved." }),
    event({ title: "AMD has not launched a GPU", summary: "No acquisition occurred." }),
    event({ title: "AMD日常动态", summary: "公司没有融资或收购，也没有发布新芯片。" }),
    event({ title: "Tencent invests in a coffee chain", company: "Tencent", summary: "A beverage investment." }),
  ]) assert.equal(matchesHomepageInnovationCapitalChannel(row, emptyIndex), false, row.title);
});

test("listed approval is not a personal-interest signal or a new publication date", () => {
  const row = event();
  assert.equal(matchesHomepageInnovationCapitalChannel(row, emptyIndex), true);
  const selected = buildHomepageFocusSelection([row],
    { schemaVersion: 1, followedSectors: [], dismissedEventIds: [], sectorDislikes: {} }, [], [], Date.parse("2026-10-01T12:00:00Z"));
  assert.equal(selected.items.length, 0);
  assert.equal(row.matchedTrackingTerms, undefined);
  assert.equal(homepageInnovationCapitalAnnotation(row, emptyIndex)?.publishedAt, "2026-09-28");
  assert.equal(matchesHomepageInnovationCapitalChannel(event({ publishedAt: "" }), emptyIndex), false);
});

test("the persisted projection and live-increment matcher agree on approved company events", () => {
  const row = event();
  const projected = buildInnovationCapitalFeedProjection({ articlesPayload: { generatedAt: "2026-10-01", articles: [row] },
    rankedPayload: {}, watchlistPayload: {}, lifecyclePayload: {}, maturePayload: {}, trackingSeedsPayload: {} });
  assert.equal(projected.eventCount, 1);
  const parsed = homepageInnovationCapitalAnnotation(row, buildHomepageInnovationCapitalIndex(projected));
  assert.ok(parsed?.matchedObjects.some((item) => item.type === "listed-company"));
  assert.deepEqual(parsed?.reasonCodes, homepageInnovationCapitalAnnotation(row, emptyIndex)?.reasonCodes);
});

test("both channels and company detail expose shared securities without rewriting IPO pool counters", () => {
  const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
  assert.match(read("../app/innovation-capital/page.tsx"), /ListedInnovationDirectory/u);
  assert.match(read("../app/companies/page.tsx"), /listedInnovationCompanies/u);
  assert.match(read("../app/companies/[slug]/page.tsx"), /ListedInnovationSecurities/u);
  assert.match(read("../app/companies/[slug]/page.tsx"), /conflictingExitSummary/u);
  assert.doesNotMatch(read("../lib/listed-innovation-companies.ts"), /listed_innovation_candidates/u);
});

test("same-plan attachments group without losing evidence or merging later milestones", () => {
  const rows = [
    event({ id: "draft", companySlug: "catl", title: "2026年A股第二期员工持股计划（草案）" }),
    event({ id: "summary", companySlug: "catl", title: "2026年A股第二期员工持股计划（草案）摘要", source: { ...event().source, url: "https://example.com/summary" } }),
    event({ id: "later", companySlug: "catl", title: "2026年A股第二期员工持股计划获批", publishedAt: "2026-09-29", source: { ...event().source, url: "https://example.com/approval" } }),
  ];
  const before = JSON.stringify(rows);
  const result = groupDisclosurePlanAttachments(rows);
  assert.equal(result.length, 2);
  assert.equal(result[0].relatedSources?.length, 1);
  assert.equal(result[0].relatedSources?.[0].url, "https://example.com/summary");
  assert.equal(result[1].id, "later");
  assert.equal(JSON.stringify(rows), before);
  const sameDayApproval = { ...rows[2], publishedAt: rows[0].publishedAt };
  assert.equal(groupDisclosurePlanAttachments([rows[0], rows[1], sameDayApproval]).length, 2);
  assert.ok(projectHomepageCompanyDisclosureEvents(48).every((row) => !/an announcement has just been published/iu.test(row.title)));
});
