import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  buildInvestorHomepagePublication,
  INVESTOR_HOMEPAGE_LOOKBACK_DAYS,
  INVESTOR_HOMEPAGE_MAX_ARTICLES,
} from "../lib/homepage-investor-publication";
import {
  globalInnovationInvestors,
  investorEvidenceRecords,
  type InvestorEvidenceRecord,
} from "../lib/innovation-investor-research";
import {
  buildHomepageInnovationCapitalIndex,
  homepageInnovationCapitalAnnotation,
  matchesHomepageInnovationCapitalChannel,
} from "../lib/homepage-innovation-capital-channel";
import { mergePriorityCandidates } from "../lib/priority-intelligence";
import { buildHomepageFocusSelection } from "../lib/homepage-focus";
import type { HomepagePreferenceState } from "../lib/homepage-preferences";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const now = Date.parse("2026-10-10T12:00:00Z");
const build = (records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords, at = now) =>
  buildInvestorHomepagePublication(records, globalInnovationInvestors, at);
const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("official recent originals, not old case studies, become the limited homepage publication", () => {
  assert.equal(INVESTOR_HOMEPAGE_LOOKBACK_DAYS, 14);
  assert.ok(INVESTOR_HOMEPAGE_MAX_ARTICLES <= 12);
  const output = build();
  assert.ok(output.events.length >= 4, "retain the four independently reviewed recent sources");
  assert.ok(output.events.length <= INVESTOR_HOMEPAGE_MAX_ARTICLES);
  assert.equal(output.events.length, output.innovationItems.length);
  assert.equal(new Set(output.events.map((item) => item.source.url)).size, output.events.length,
    "each original source should yield only one homepage article");
  assert.deepEqual(new Set(output.events.map((item) => item.id)),
    new Set(output.innovationItems.map((item) => item.eventId)));
  // Verify durable original articles in isolation: they must remain publishable
  // even after newer approved stories displace them from the 12-card window.
  const originalSources = [
    "https://a16z.com/announcement/investing-in-preference-model/",
    "https://a16z.com/announcement/investing-in-typesafe-ai/",
    "https://eclipse.capital/blog/built-for-the-compute-ownership-era",
    "https://sequoiacap.com/article/partnering-with-catalyst-turning-ideas-into-trades",
  ];
  const originalRecords = investorEvidenceRecords.filter((item) => originalSources.includes(item.source.url));
  for (const url of originalSources) {
    const isolated = build(originalRecords.filter((item) => item.source.url === url));
    assert.equal(isolated.events.length, 1, `one article for known original: ${url}`);
    assert.equal(isolated.events[0].source.url, url);
  }
  assert.ok(output.events.every((item) =>
    item.source.level === "官方披露" &&
    item.qualityStatus === "可用" &&
    item.publicationTimePrecision === "day" &&
    !("realizedProceeds" in item) &&
    item.matchedTrackingTerms?.length === 0,
  ));
  assert.ok(output.events.every((item) => !("curated" in item)));
  assert.equal(build(investorEvidenceRecords.filter((item) => [
    "https://a16z.com/announcement/investing-in-preference-model/",
    "https://a16z.com/announcement/investing-in-typesafe-ai/",
    "https://eclipse.capital/blog/built-for-the-compute-ownership-era",
    "https://sequoiacap.com/article/partnering-with-catalyst-turning-ideas-into-trades",
  ].includes(item.source.url)), Date.parse("2026-11-01T12:00:00Z")).events.length, 0,
    "expired originals must not be relabelled as new publications");
});

test("multiple descriptions of the same source yield one news card, but preserve speaker attribution", () => {
  const {events} = build(investorEvidenceRecords.filter((row) =>
    row.source.url.includes("investing-in-typesafe-ai") ||
    row.source.url.includes("built-for-the-compute-ownership-era")));
  const typesafe = events.find((item) => item.company === "TypeSafe AI")!;
  const oxide = events.find((item) => item.company === "Oxide")!;
  assert.equal(typesafe.type, "产业投资");
  assert.equal(typesafe.publishedAt, "2026-10-09");
  assert.match(typesafe.title, /领投/);
  assert.equal(typesafe.mentionedPeople?.length, 5);
  assert.equal(oxide.type, "产业投资");
  assert.equal(oxide.mentionedPeople?.[0], "Seth Winterroth");
  assert.match(oxide.summary, /4\.45亿美元/);
  assert.match(oxide.summary, /未披露的部分不能推断/);
  assert.equal(events.filter((item) => item.source.url.includes("typesafe-ai")).length, 1);
  assert.equal(events.filter((item) => item.source.url.includes("built-for-the-compute")).length, 1);
});

test("new source-backed cards are inside 科创 with source-based annotation, not a new publication writer", () => {
  const {events, innovationItems} = build();
  const index = buildHomepageInnovationCapitalIndex({
    schemaVersion: 1, generatedAt: "2026-10-10T12:00:00Z", universeAsOf: "2026-10-10",
    eventCount: innovationItems.length, items: innovationItems,
  });
  for (const item of events) {
    assert.equal(matchesHomepageInnovationCapitalChannel(item, index), true);
    const annotation = homepageInnovationCapitalAnnotation(item, index)!;
    assert.equal(annotation.evidenceTier, "primary");
    assert.equal(annotation.reasonCodes.includes("INVESTOR_SOURCE_RESEARCH"), true);
    assert.ok(annotation.matchedObjects.some((x) => x.type === "institution"));
    assert.ok(annotation.matchedObjects.some((x) => x.type === "discovered-company"));
  }
  assert.ok(innovationItems.every((item) => item.innovationPriority <= 100));
});

test("reviewed event merges with existing canonical archive without taking over its headline or doubling URL", () => {
  const {events} = build();
  const original = events[0];
  const canonical: LiveIntelligenceEvent = {
    ...original, id: "archive-first", title: "Earlier official archive title",
    importance: 88, qualityStatus: "高可信",
  };
  const merged = mergePriorityCandidates([canonical], events);
  assert.equal(merged.length, events.length);
  const sameSource = merged.filter((item) => item.source.url === original.source.url);
  assert.equal(sameSource.length, 1);
  assert.equal(sameSource[0].id, "archive-first");
  assert.equal(sameSource[0].title, "Earlier official archive title");
});

test("重点 retains explicit preference admission and exclusions; official investor role alone is insufficient", () => {
  const {events} = build();
  const preferences: HomepagePreferenceState = {
    schemaVersion: 1, followedSectors: [], dismissedEventIds: [], sectorDislikes: {},
  };
  const result = buildHomepageFocusSelection(events, preferences, [], [], now);
  assert.equal(result.items.length, 0);
  const follow = buildHomepageFocusSelection(
    events, {...preferences, followedSectors: ["产业投资"]}, [], [], now,
  );
  assert.ok(follow.items.length >= 2);
  assert.ok(follow.items.every((item) => item.type === "产业投资"));
  const id = follow.items[0].id;
  const hidden = buildHomepageFocusSelection(
    events, {...preferences, followedSectors: ["产业投资"], dismissedEventIds: [id]}, [], [], now,
  );
  assert.equal(hidden.items.some((item) => item.id === id), false);
});

test("unreviewed navigation, media republications, estimated timing, and old announcements are rejected", () => {
  const raw = investorEvidenceRecords.find((row) => row.id === "eclipse-oxide-series-d-2026")!;
  const media = {...raw, id: "media-fallback", source: {...raw.source, kind: "investor-hosted-media-report"}} as InvestorEvidenceRecord;
  const yearOnly = {...raw, id: "year-only", date: "2026", datePrecision: "year", source: {...raw.source, publishedAt: null}} as InvestorEvidenceRecord;
  const retrospective = {...raw, id: "retrospective", date: "2019", datePrecision: "year", source: {...raw.source, publishedAt: "2026-10-09"}} as InvestorEvidenceRecord;
  const events = build([media, yearOnly, retrospective]).events;
  assert.equal(events.length, 0);
  assert.throws(() => build([raw, {...raw, id: "duplicate"}]), /duplicate investment disclosure/);
});

test("server first paint and client rehydration use one unified flow and a direct investor dossier link", () => {
  const server = read("app/page.tsx");
  const client = read("components/homepage-news-feed.tsx");
  assert.match(server, /buildInvestorHomepagePublication/);
  assert.match(server, /mergePriorityCandidates\(\s*admitHomepageEvents/);
  assert.match(server, /investorFirstPaint/);
  assert.match(server, /investorChannelEvents=\{investorEvents\}/);
  assert.match(client, /mergePriorityCandidates\(archiveArticles, investorChannelEvents\)/);
  assert.match(client, /\/innovation-capital\/investors\//);
  assert.match(client, /buildHomepageFocusSelection/);
  assert.doesNotMatch(server, /fetch\(["']https:/);
});

test("Catalyst official seed investment and thesis share exactly one 科创 homepage card", () => {
  const {events} = build(investorEvidenceRecords.filter((row) =>
    row.source.url === "https://sequoiacap.com/article/partnering-with-catalyst-turning-ideas-into-trades"));
  const event = events.find((item) => item.company === "Catalyst");
  assert.ok(event);
  assert.equal(event.type, "产业投资");
  assert.equal(event.publishedAt, "2026-10-08");
  assert.match(event.title, /领投/);
  assert.deepEqual(event.mentionedPeople, ["George Robson"]);
  assert.equal(event.source.url, "https://sequoiacap.com/article/partnering-with-catalyst-turning-ideas-into-trades");
  assert.equal(events.filter((item) => item.company === "Catalyst").length, 1);
});
