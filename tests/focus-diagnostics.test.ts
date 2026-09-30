import assert from "node:assert/strict";
import test from "node:test";
import { buildHomepageFocusSelection } from "../lib/homepage-focus";
import { focusDisplayDecision, focusQualityMetrics, findFocusCandidates, focusObservationLatency } from "../lib/focus-diagnostics";
import { groupFocusReports, focusPreferenceIdentity } from "../lib/focus-event-groups";
import { parsePriorityIntelligence } from "../lib/priority-intelligence";
import type { HomepagePreferenceState } from "../lib/homepage-preferences";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const now = Date.parse("2026-09-30T02:00:00Z");
const prefs: HomepagePreferenceState = { schemaVersion: 1, followedSectors: ["半导体"], dismissedEventIds: [], sectorDislikes: {} };
const event = (id: string, url = `https://newsroom.amd.com/news/${id}`): LiveIntelligenceEvent => ({
  id, title: "AMD signs acquisition agreement", summary: "World Labs", company: "AMD", sector: "半导体",
  region: "美国", publishedAt: "2026-09-29", importance: 89, type: "并购", source: { name: "AMD", url, level: "官方披露" },
});

test("pagination diagnoses a qualified 25th item rather than truncating it", () => {
  const selection = buildHomepageFocusSelection(Array.from({ length: 40 }, (_, i) => event(`a${String(i).padStart(2, "0")}`)), prefs, [], [], now);
  assert.equal(selection.items.length, 40);
  assert.equal(focusDisplayDecision(selection.items[24].id, selection, selection.items, selection.items.slice(0, 24)).code, "next-page");
  assert.equal(focusDisplayDecision(selection.items[24].id, selection, selection.items, selection.items).code, "displayed");
});
test("absence is not fabricated as never collected and filters are explicit", () => {
  const selection = buildHomepageFocusSelection([event("a")], prefs, [], [], now);
  assert.equal(focusDisplayDecision("missing", selection, [], []).code, "not-observed");
  assert.equal(focusDisplayDecision("a", selection, [], []).code, "view-filter");
  assert.equal(findFocusCandidates("https://newsroom.amd.com/news/a?utm_source=x", selection).length, 1);
});
test("reviewed agreement sources group, but a subsequent approval is separate", () => {
  const rows = [event("media", "https://www.mittrchina.com/news/detail/17028"),
    event("official", "https://newsroom.amd.com/news/amd-acquire-world-labs"), event("later-approval")];
  const grouped = groupFocusReports(rows);
  assert.equal(grouped.items.length, 2);
  assert.equal(grouped.items[0].relatedSources.length, 1);
  assert.equal(grouped.groupedInto.get("official"), "media");
  const selection = buildHomepageFocusSelection(rows, { ...prefs, dismissedEventIds: ["official"] }, [], [], now);
  assert.deepEqual(selection.items.map((x) => x.id), ["later-approval"]);
});
test("equal company names without reviewed event identity never collapse", () => {
  assert.equal(groupFocusReports([event("one"), event("two")]).items.length, 2);
});
test("a reviewed event veto survives the original representative leaving the candidate window", () => {
  const old = event("old", "https://newsroom.amd.com/news/amd-acquire-world-labs");
  const newer = event("newer", "https://www.mittrchina.com/news/detail/17028");
  const selected = buildHomepageFocusSelection([newer], { ...prefs, dismissedEventIds: [focusPreferenceIdentity(old)] }, [], [], now);
  assert.equal(selected.items.length, 0);
});

test("transitive material identity merges once and records the representative", () => {
  const a = event("a"); const b = { ...event("b", a.source.url), eventClusterId: "c" };
  const c = { ...event("c"), eventClusterId: "c" };
  const result = groupFocusReports([a, c, b]);
  assert.equal(result.items.length, 1); assert.equal(result.groupedInto.size, 2);
});
test("unjudged samples never produce invented recall or irrelevance rates", () => {
  assert.equal(focusQualityMetrics(null, {}, ["a"]).recall, null);
  assert.equal(focusQualityMetrics(null, {}, ["a"]).irrelevantRate, null);
  assert.deepEqual(focusQualityMetrics(["a", "b"], { a: true, x: false }, ["a", "x"]), {
    expectedCount: 2, missedCount: 1, recall: 0.5, judgedVisibleCount: 2, irrelevantRate: 0.5,
  });
});
test("latency is computed only with real timestamp precision, never inferred from a date", () => {
  const row = { ...event("a"), firstSeenAt: "2026-09-29T11:10:00Z" };
  assert.equal(focusObservationLatency(row).collectionDelayMinutes, null);
  const precise = { ...row, publishedAt: "2026-09-29T11:00:00Z", publicationTimePrecision: "second" as const };
  assert.equal(focusObservationLatency(precise).collectionDelayMinutes, 10);
  assert.equal(focusObservationLatency(precise).firstExposureDelayMinutes, null);
});

test("wire entity evidence is bounded and must occur in actual public text", () => {
  const row = { ...event("amd-newsroom-test"), sourceId: "amd-newsroom", entityResolutionStatus: "matched",
    entityMentions: [{ id: "company:amd", name: "AMD", kind: "company", field: "title", alias: "AMD" }] };
  const payload = { schemaVersion: 1, policyVersion: "priority-publisher-v1", contentHash: "a".repeat(64), sourceState: "healthy", generatedAt: "2026-09-30T01:00:00Z", items: [row] };
  const parsed = parsePriorityIntelligence(payload, now);
  assert.deepEqual(parsed.items[0].mentionedCompanies, ["AMD"]);
  assert.throws(() => parsePriorityIntelligence({ ...payload, items: [{ ...row, entityMentions: [{ ...row.entityMentions[0], alias: "not present" }] }] }, now));
});
