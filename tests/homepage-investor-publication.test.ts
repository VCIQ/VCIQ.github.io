import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import manifest from "../config/innovation_investor_homepage_publications.json";
import evidence from "../config/innovation_investor_evidence.json";
import roster from "../config/innovation_global_investors.json";
import identities from "../config/innovation_investor_project_identities.json";
import {
  buildInvestorHomepageEvents,
  mergeInvestorHomepageEvents,
  withInvestorHomepageInnovationProjection,
} from "../lib/homepage-investor-publication";
import {
  buildHomepageInnovationCapitalIndex,
  matchesHomepageInnovationCapitalChannel,
} from "../lib/homepage-innovation-capital-channel";
import { buildHomepageFocusSelection } from "../lib/homepage-focus";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const now = new Date("2026-10-10T12:00:00Z");
const build = () => buildInvestorHomepageEvents(manifest, evidence.records, roster.institutions, identities.projects, now);

test("publication requires two explicit first-party investments and exact original article day, not crawler appearance", () => {
  assert.equal(manifest.selections.length, 2);
  const published = build();
  assert.equal(published.length, 2);
  assert.deepEqual(published.map((x) => x.company).sort(), ["Oxide", "TypeSafe AI"]);
  assert.ok(published.every((x) => x.publishedAt === "2026-10-09"));
  assert.ok(published.every((x) => x.publicationTimePrecision === "day"));
  assert.ok(published.every((x) => x.source.level === "官方披露"));
  assert.ok(published.every((x) => x.type === "产业投资" && x.importance >= 85));
  assert.ok(published.every((x) => x.matchedTrackingTerms?.length === 0));
  assert.ok(published.every((x) => !x.summary.includes("基金已经兑现")));
  assert.ok(published.every((x) => x.source.url.startsWith("https://")));
  assert.ok(published.every((x) => x.source.url !== "https://vciq.github.io/"));
  const oxide = published.find((x) => x.company === "Oxide")!;
  assert.match(oxide.summary, /4\.45亿美元.*整轮融资额/);
  assert.match(oxide.summary, /单家出资额|Eclipse独家出资额/);
  assert.equal(oxide.mentionedPeople?.[0], "Seth Winterroth");
  const typesafe = published.find((x) => x.company === "TypeSafe AI")!;
  assert.equal(typesafe.mentionedPeople?.length, 5);
  assert.match(typesafe.summary, /署名不证明个人交易签约责任/);
});

test("reviewed source homepage projection admits 科创 but never requires fake company master approval", () => {
  const published = build();
  const projection = withInvestorHomepageInnovationProjection({
    schemaVersion: 1, generatedAt: "2026-10-09", universeAsOf: "2026-10-09",
    eventCount: 0, items: [],
  }, published);
  const index = buildHomepageInnovationCapitalIndex(projection);
  assert.equal(projection.eventCount, 2);
  assert.ok(published.every((event) => matchesHomepageInnovationCapitalChannel(event, index)));
  assert.ok(projection.items.every((item) => item.evidenceTier === "primary"));
  assert.ok(projection.items.every((item) => item.reasonCodes.includes("FUNDING_EVENT")));
  assert.ok(projection.items.every((item) => item.matchedObjects.some((x) => x.type === "institution")));
  assert.ok(projection.items.every((item) => item.matchedObjects.some((x) => x.type === "discovered-company")));
});

test("browser refresh retains approved official events while collapsing same URL crawler copies", () => {
  const original = build();
  const crawler: LiveIntelligenceEvent[] = [{
    ...original[0],
    id: "unreviewed-news-clone",
    title: "Other title inferred by crawler",
    source: {...original[0].source, url: original[0].source.url + "?utm_source=alerts"},
    qualityStatus: "低可信",
    curated: false,
  }, {
    ...original[1],
    id: "generic-other-event",
    company: "OtherCompany",
    source: {...original[1].source, url: "https://example.org/other-update"},
    curated: false,
  }];
  const frozen = JSON.stringify(crawler);
  const merged = mergeInvestorHomepageEvents(crawler, original);
  assert.equal(JSON.stringify(crawler), frozen);
  assert.equal(merged.length, 3);
  assert.deepEqual(merged.filter((x) => x.id.startsWith("investor-original-source:")).map((x) => x.id),
    original.map((x) => x.id));
  assert.equal(merged.some((x) => x.id === "unreviewed-news-clone"), false);
  assert.equal(merged.some((x) => x.id === "generic-other-event"), true);
});

test("priority 重点 requires the user's own follow/favorite/share rather than institution sponsorship", () => {
  const events = build();
  const prefs = {schemaVersion: 1 as const, followedSectors: [], dismissedEventIds: [], sectorDislikes: {}};
  const result = buildHomepageFocusSelection(events, prefs, [], [], now.getTime());
  assert.equal(result.items.length, 0);
  assert.ok(events.every((x) => result.decisions.get(x.id)?.exclusion === "no-personal-signal" ||
    result.decisions.get(x.id)?.exclusion === "entity-unresolved"));
  const followed = buildHomepageFocusSelection(
    events, {...prefs, followedSectors: ["AI / AGI"]}, [], [], now.getTime());
  assert.deepEqual(followed.items.map((x) => x.company), ["TypeSafe AI"]);
  assert.equal(followed.decisions.get(followed.items[0].id)?.signal, "tracking");
});

test("never turn raw scout, company-reported outcomes, undated or off-domain claims into homepage news", () => {
  const bad = structuredClone(manifest) as typeof manifest;
  bad.selections[0].investmentEvidenceId = "eclipse-oxide-compute-thesis-2026";
  assert.throws(() => buildInvestorHomepageEvents(bad, evidence.records, roster.institutions, identities.projects, now), /Unreviewed/);
  const malformed = structuredClone(evidence.records) as typeof evidence.records;
  const chosen = malformed.find((x) => x.id === "a16z-typesafe-ai-investment-2026")!;
  chosen.source.url = "https://unrelated.example.net/claim";
  assert.throws(() => buildInvestorHomepageEvents(manifest, malformed, roster.institutions, identities.projects, now), /official domain/);
  const another = structuredClone(manifest) as typeof manifest;
  another.selections.push({...another.selections[0]});
  assert.throws(() => buildInvestorHomepageEvents(another, evidence.records, roster.institutions, identities.projects, now), /duplicate/);
  assert.deepEqual(buildInvestorHomepageEvents(manifest, evidence.records, roster.institutions, identities.projects,
    new Date("2026-12-01T00:00:00Z")), []);
  assert.throws(() => buildInvestorHomepageEvents(manifest, evidence.records, roster.institutions, identities.projects,
    new Date("2026-10-08T12:00:00Z")), /Invalid publication date/);
});

test("home route merges editorial events into first paint and retains them after useArticles refresh", () => {
  const home = fs.readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
  const feed = fs.readFileSync(new URL("../components/homepage-news-feed.tsx", import.meta.url), "utf8");
  assert.match(home, /buildInvestorHomepageEvents/);
  assert.match(home, /mergeInvestorHomepageEvents\(/);
  assert.match(home, /publishedInnovationProjection/);
  assert.match(home, /investorHomepageEvents=\{investorHomepageEvents\}/);
  assert.match(feed, /useArticles\(initialPayload\)/);
  assert.match(feed, /mergeInvestorHomepageEvents\(fetchedArticles, investorHomepageEvents\)/);
  assert.match(feed, /channel === "focus" \? buildHomepageFocusSelection/);
  assert.match(feed, /matchesHomepageInnovationCapitalChannel\(item, innovationCapital\)/);
  const manifestString = fs.readFileSync(new URL("../config/innovation_investor_homepage_publications.json", import.meta.url), "utf8");
  assert.doesNotMatch(manifestString, /unreviewed-navigation-candidate/);
});
