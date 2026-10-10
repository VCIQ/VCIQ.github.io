import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  projectReviewedInvestorHomepageEvents,
  withReviewedInvestorInnovationProjection,
} from "../lib/homepage-investor-reviewed-events";
import {
  mergeReviewedInvestorHomepageEvents,
  REVIEWED_INVESTOR_SOURCE_ID,
} from "../lib/homepage-reviewed-investor-merge";
import {
  globalInnovationInvestors, investorEvidenceRecords,
  type InvestorEvidenceRecord,
} from "../lib/innovation-investor-research";
import {
  buildHomepageInnovationCapitalIndex,
  homepageInnovationCapitalAnnotation,
  matchesHomepageInnovationCapitalChannel,
  type InnovationCapitalFeedProjection,
} from "../lib/homepage-innovation-capital-channel";
import { buildHomepageFocusSelection } from "../lib/homepage-focus";
import type { HomepagePreferenceState } from "../lib/homepage-preferences";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const now = Date.parse("2026-10-10T12:00:00Z");
const projected = () => projectReviewedInvestorHomepageEvents(investorEvidenceRecords, globalInnovationInvestors, now);
const preferences: HomepagePreferenceState = {
  schemaVersion: 1, followedSectors: [], dismissedEventIds: [], sectorDislikes: {},
};
const emptyProjection: InnovationCapitalFeedProjection = {
  schemaVersion: 1, generatedAt: "2026-10-10T03:00:00Z",
  universeAsOf: "2026-10-10", eventCount: 0, items: [],
};
const read = (path: string) => readFileSync(new URL("../" + path, import.meta.url), "utf8");

test("recent official investment sources appear once with correct day, type and original URL", () => {
  const items = projected();
  assert.ok(items.length >= 3);
  const typesafe = items.filter((row) => row.source.url === "https://a16z.com/announcement/investing-in-typesafe-ai/");
  const oxide = items.filter((row) => row.source.url === "https://eclipse.capital/blog/built-for-the-compute-ownership-era");
  assert.equal(typesafe.length, 1); // One investment + one thesis, but just one original article.
  assert.equal(oxide.length, 1);
  assert.equal(typesafe[0].id, "reviewed-investor:a16z-typesafe-ai-investment-2026");
  assert.equal(typesafe[0].type, "产业投资");
  assert.equal(typesafe[0].publishedAt, "2026-10-09");
  assert.equal(typesafe[0].publicationTimePrecision, "day");
  assert.equal(typesafe[0].source.level, "官方披露");
  assert.equal(typesafe[0].sourceId, REVIEWED_INVESTOR_SOURCE_ID);
  assert.equal(typesafe[0].authors?.length, 5);
  assert.match(typesafe[0].summary, /署名不能证明个人交易签约责任/);
  assert.equal(oxide[0].company, "Oxide");
  assert.match(oxide[0].summary, /4.45亿美元|4.45亿|4.45/);
  assert.ok(items.every((row) => row.matchedTrackingTerms === undefined));
  assert.ok(items.every((row) => row.curated && row.qualityStatus !== "低可信"));
  assert.ok(items.every((row) => row.publishedAt.length === 10));
});

test("historical/reported investment dates and stale sources never masquerade as news", () => {
  const items = projected();
  assert.ok(!items.some((row) => row.id.includes("qiming-mechmind-a-plus-investment-2019")));
  assert.ok(!items.some((row) => row.id.includes("utec-eureka-portfolio-asof-2024")));
  assert.ok(!items.some((row) => row.publishedAt.startsWith("2024")));
  const later = projectReviewedInvestorHomepageEvents(
    investorEvidenceRecords, globalInnovationInvestors, Date.parse("2026-12-20T12:00:00Z"),
  );
  assert.equal(later.length, 0);
});

test("unsigned, cross-domain or non-investor publication cannot enter reviewed investor feed", () => {
  const original = investorEvidenceRecords.find((r) => r.id === "a16z-typesafe-ai-investment-2026")!;
  const originalThesis = investorEvidenceRecords.find((r) => r.id === "a16z-typesafe-ai-investment-thesis-2026")!;
  const adversarial = [
    {...original, id: "unreviewed-investment", source: {...original.source, kind: "investor-hosted-media-report"}},
    {...original, id: "wrong-origin", source: {...original.source, url: "https://unrelated.example.com/company/funding"}},
    {...original, id: "future-date", source: {...original.source, publishedAt: "2026-12-01"}},
    {...originalThesis, id: "unsigned-statement", speakers: [], source: {...originalThesis.source,
      url: "https://a16z.com/announcement/unsigned-opinion"}},
  ] as InvestorEvidenceRecord[];
  const items = projectReviewedInvestorHomepageEvents(adversarial, globalInnovationInvestors, now);
  assert.equal(items.length, 0);
});

test("standalone signed investor viewpoints have explicit attribution, not a fictitious investment", () => {
  const original = investorEvidenceRecords.find((r) => r.id === "a16z-typesafe-ai-investment-thesis-2026")!;
  const article = {...original, id: "reviewed-standalone-viewpoint",
    source: {...original.source, url: "https://a16z.com/announcement/ai-research-investor-viewpoint/"}} as InvestorEvidenceRecord;
  const items = projectReviewedInvestorHomepageEvents([article], globalInnovationInvestors, now);
  assert.equal(items.length, 1);
  assert.equal(items[0].type, "人物观点");
  assert.match(items[0].title, /^投资人观点/);
  assert.equal(items[0].importance, 85);
  assert.equal(items[0].mentionedPeople?.length, 5);
  assert.doesNotMatch(items[0].summary, /已确认独家领投/);
});

test("innovation channel annotates only reviewed official sources, including attributed viewpoints", () => {
  const reviewed = projected();
  const projection = withReviewedInvestorInnovationProjection(emptyProjection, reviewed);
  const index = buildHomepageInnovationCapitalIndex(projection);
  const typesafe = reviewed.find((x) => x.company === "TypeSafe AI")!;
  assert.ok(projection.eventCount > 0);
  assert.equal(matchesHomepageInnovationCapitalChannel(typesafe, index), true);
  assert.equal(homepageInnovationCapitalAnnotation(typesafe, index)?.evidenceTier, "primary");
  assert.ok(homepageInnovationCapitalAnnotation(typesafe, index)?.reasonCodes.includes("REVIEWED_INVESTOR_EVIDENCE"));
  // Canonical news ID for the same original URL still matches the 科创 projection.
  const canonical: LiveIntelligenceEvent = {...typesafe, id: "original-canonical-news",
    sourceId: "news-original"};
  assert.equal(matchesHomepageInnovationCapitalChannel(canonical, index), true);
  const forged: LiveIntelligenceEvent = {...typesafe, id: "raw-scout-candidate",
    sourceId: "innovation-investor-unreviewed", source: {...typesafe.source, url: "https://other.example.org/unreviewed"}};
  assert.equal(matchesHomepageInnovationCapitalChannel(forged, index), false);
  const opinionSource = {...typesafe, id: "fake-opinion", type: "人物观点" as const,
    source: {...typesafe.source, url: "https://unrelated.example.com/post"}};
  // Changing the URL alone isn't enough to add an entry to the index.
  assert.equal(matchesHomepageInnovationCapitalChannel(opinionSource, index), false);
});

test("canonical news wins on same URL and reviewed investor items survive live article refresh", () => {
  const reviewed = projected();
  const typesafe = reviewed.find((x) => x.company === "TypeSafe AI")!;
  const archived: LiveIntelligenceEvent = {...typesafe, id: "canonical-news-story",
    sourceId: "publisher-crawler", title: "Original canonical article metadata", curated: false};
  const merged = mergeReviewedInvestorHomepageEvents([archived], reviewed);
  assert.equal(merged.filter(x => x.source.url === typesafe.source.url).length, 1);
  assert.equal(merged.find(x => x.source.url === typesafe.source.url)?.title, archived.title);
  const refreshed = mergeReviewedInvestorHomepageEvents([], reviewed);
  assert.equal(refreshed.length, reviewed.length);
  assert.equal(refreshed.find(x => x.company === "TypeSafe AI")?.id, typesafe.id);
  assert.equal(mergeReviewedInvestorHomepageEvents([], [{...typesafe, sourceId: "raw-unverified"}]).length, 0);
});

test("重点 still requires user interest, can admit fresh official investor news on followed topic", () => {
  const typesafe = projected().find((x) => x.company === "TypeSafe AI")!;
  assert.equal(buildHomepageFocusSelection([typesafe], preferences, [], [], now).items.length, 0);
  const followed = buildHomepageFocusSelection(
    [typesafe], {...preferences, followedSectors: ["科创投资"]}, [], [], now,
  );
  assert.deepEqual(followed.items.map((x) => x.id), [typesafe.id]);
  assert.equal(followed.decisions.get(typesafe.id)?.signal, "tracking");
  const dismissed = buildHomepageFocusSelection(
    [typesafe], {...preferences, followedSectors: ["科创投资"], dismissedEventIds: [typesafe.id]}, [], [], now,
  );
  assert.equal(dismissed.items.length, 0);
});

test("homepage first paint and refreshed client feed use the same approved projection", () => {
  const page = read("app/page.tsx");
  const component = read("components/homepage-news-feed.tsx");
  assert.match(page, /projectReviewedInvestorHomepageEvents\(\)/);
  assert.match(page, /withReviewedInvestorInnovationProjection/);
  assert.match(page, /reviewedInvestorEvents=\{reviewedInvestorEvents\}/);
  assert.match(component, /mergeReviewedInvestorHomepageEvents\(articles, reviewedInvestorEvents\)/);
  assert.match(component, /mergePriorityCandidates\(\s*combinedArticles/);
  assert.match(component, /item\.sourceId !== REVIEWED_INVESTOR_SOURCE_ID/);
  assert.match(component, /\/innovation-capital\/investors\//);
  assert.doesNotMatch(page, /innovation-investor-source-scout.json/);
  assert.doesNotMatch(page, /innovation-investor-change-report.json/);
});
