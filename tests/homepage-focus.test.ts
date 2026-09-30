import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { buildHomepageFocusSelection, HOMEPAGE_FOCUS_POLICY } from "../lib/homepage-focus";
import type { FavoriteItem } from "../lib/favorites";
import type { HotnessItem } from "../lib/hotness";
import type { HomepagePreferenceState } from "../lib/homepage-preferences";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const now = Date.parse("2026-09-29T12:00:00Z");
const preferences: HomepagePreferenceState = { schemaVersion: 1, followedSectors: [], dismissedEventIds: [], sectorDislikes: {} };
const event = (extra: Partial<LiveIntelligenceEvent> = {}): LiveIntelligenceEvent => ({ id: "amd-news", title: "AMD announces an AI acquisition", summary: "AMD has signed an agreement; closing is pending.", type: "并购", region: "美国", sector: "半导体", company: "AMD", importance: 89, publishedAt: "2026-09-28", source: { name: "AMD Newsroom", url: "https://newsroom.amd.com/news/agreement/", level: "官方披露" }, ...extra });
const share: HotnessItem = { key: "share-1", id: "share-1", href: "https://example.com/amd-prior", title: "AMD strategy", summary: "AMD AI strategy", shares: 1, opens: 1, favorite: false, firstSeenAt: "2026-09-20", updatedAt: "2026-09-20", lastSharedAt: "2026-09-20" };
const favorite: FavoriteItem = { id: "favorite-1", href: "https://example.com/amd-saved", title: "AMD research", summary: "", channel: "companies", channelLabel: "公司", keywords: ["AMD", "并购", "美国"], sectors: ["半导体"], sources: [], company: "AMD", savedAt: "2026-09-21" };

test("focus requires a personal signal; many opens or high importance alone are insufficient", () => {
  const rows = [event({ importance: 100 })];
  assert.equal(buildHomepageFocusSelection(rows, preferences, [], [{ ...share, shares: 0, opens: 100000 }], now).items.length, 0);
});
test("focus reuses tracking > share > favorite without frequency amplification", () => {
  const rows = [event()];
  assert.equal(buildHomepageFocusSelection(rows, preferences, [favorite], [], now).decisions.get("amd-news")?.signal, "favorite");
  const shared = buildHomepageFocusSelection(rows, preferences, [favorite], [share, { ...share, shares: 9999 }], now);
  assert.equal(shared.decisions.get("amd-news")?.signal, "share"); assert.equal(shared.distinctSharedTargets, 1);
  assert.equal(buildHomepageFocusSelection(rows, { ...preferences, followedSectors: ["半导体"] }, [favorite], [share], now).decisions.get("amd-news")?.signal, "tracking");
});
test("focus cannot resurrect a dismissed event through a second feed or tracked topic", () => {
  const a = event(); const b = event({ id: "other-feed", eventClusterId: "same-event" });
  const result = buildHomepageFocusSelection([a, b], { ...preferences, followedSectors: ["半导体"], dismissedEventIds: [a.id] }, [favorite], [share], now);
  assert.equal(result.items.length, 0); assert.equal(result.decisions.get(b.id)?.exclusion, "dismissed");
});
test("stale or low-quality updates are not promoted by repeated sharing", () => {
  const rows = [event({ id: "old", publishedAt: "2026-08-01" }), event({ id: "bad", qualityStatus: "低可信" })];
  assert.equal(buildHomepageFocusSelection(rows, { ...preferences, followedSectors: ["半导体"] }, [favorite], [share], now).items.length, 0);
});
test("a new material update does not inherit a dismissal from a background reference", () => {
  const old = event({ id: "earlier-agreement" });
  const update = event({ id: "later-approval", title: "AMD acquisition approval update", source: { ...old.source, url: "https://newsroom.amd.com/news/approval/" }, relatedSources: [{ ...old.source, platform: "官方网站", title: old.title, publishedAt: old.publishedAt }] });
  const selected = buildHomepageFocusSelection([old, update], { ...preferences, followedSectors: ["半导体"], dismissedEventIds: [old.id] }, [], [], now);
  assert.deepEqual(selected.items.map((item) => item.id), [update.id]);
});
test("generic event-type, region and source-host affinity cannot admit unrelated stories", () => {
  const unrelated = event({ company: "OtherCo", title: "OtherCo AI acquisition", summary: "OtherCo buys a company" });
  const generic = { ...favorite, company: "科技产业", keywords: ["并购", "美国", "AI"], sources: [{ name: "AMD Newsroom", url: unrelated.source.url }] };
  assert.equal(buildHomepageFocusSelection([unrelated], preferences, [generic], [share], now).items.length, 0);
});
test("removed favorites and expired shares stop contributing, no profile is written", () => {
  const rows = [event()]; const snapshot = JSON.stringify({ preferences, share, favorite });
  assert.equal(buildHomepageFocusSelection(rows, preferences, [], [{ ...share, lastSharedAt: "2025-01-01" }], now).items.length, 0);
  assert.equal(JSON.stringify({ preferences, share, favorite }), snapshot);
});
test("material URL identity preserves Unicode path semantics", () => {
  const rows = [event(), event({ id: "second", source: { ...event().source, url: "https://newsroom.amd.com/news/other/" } })];
  assert.equal(buildHomepageFocusSelection(rows, { ...preferences, followedSectors: ["半导体"] }, [], [], now).items.length, 2);
});
test("focus tab is between follow and recommend, and fresh-only research does not create broken event links", () => {
  const source = readFileSync(new URL("../components/homepage-news-feed.tsx", import.meta.url), "utf8");
  assert.match(source, /\{ id: "follow", label: "关注流" \},\s*\{ id: "focus", label: "重点" \},\s*\{ id: "recommend", label: "推荐" \}/u);
  assert.match(source, /usePriorityIntelligence\(channel === "focus"\)/u);
  assert.match(source, /channel === "focus" \? buildHomepageFocusSelection/u);
  assert.match(source, /canonicalResearchReady/u);
  assert.match(source, /增量待归档后可深研/u);
  assert.match(source, /按发布时间倒序/u);
});

test("focus displays newer favorites before older tracking without changing admission signals", () => {
  const older = event({ id: "older-tracked", publishedAt: "2026-09-28T18:00:00Z", matchedTrackingTerms: ["AMD"], importance: 100 });
  const newer = event({ id: "newer-favorite", publishedAt: "2026-09-29T10:00:00Z", importance: 80,
    source: { ...event().source, url: "https://newsroom.amd.com/news/new-release/" } });
  const inputs = [older, newer];
  const before = JSON.stringify(inputs);
  const result = buildHomepageFocusSelection(inputs, preferences, [favorite], [], now);
  assert.equal(result.decisions.get(older.id)?.signal, "tracking");
  assert.equal(result.decisions.get(newer.id)?.signal, "favorite");
  assert.deepEqual(result.items.map((item) => item.id), [newer.id, older.id]);
  assert.equal(JSON.stringify(inputs), before);
  assert.equal(HOMEPAGE_FOCUS_POLICY.sortOrder, "published-desc");
});

test("focus applies chronological order before its unchanged item cap", () => {
  const old = Array.from({ length: HOMEPAGE_FOCUS_POLICY.maxItems }, (_, index) => event({
    id: `old-${index}`, publishedAt: "2026-09-28", importance: 100, matchedTrackingTerms: ["AMD"],
    source: { ...event().source, url: `https://newsroom.amd.com/news/old-${index}/` },
  }));
  const latest = event({ id: "latest-favorite", publishedAt: "2026-09-29T11:00:00Z", importance: 80 });
  const result = buildHomepageFocusSelection([...old, latest], preferences, [favorite], [], now);
  assert.equal(result.items.length, HOMEPAGE_FOCUS_POLICY.maxItems);
  assert.equal(result.items[0].id, latest.id);
  assert.equal(result.decisions.get(latest.id)?.signal, "favorite");
});

test("focus compares actual timestamp instants across time zones, not text order", () => {
  const earlier = event({ id: "earlier-local", publishedAt: "2026-09-29T12:00:00+08:00", matchedTrackingTerms: ["AMD"] });
  const later = event({ id: "later-utc", publishedAt: "2026-09-29T05:00:00Z", matchedTrackingTerms: ["AMD"],
    source: { ...event().source, url: "https://newsroom.amd.com/news/later/" } });
  assert.deepEqual(buildHomepageFocusSelection([earlier, later], preferences, [], [], now).items.map((item) => item.id), [later.id, earlier.id]);
});

test("equal publication dates retain deterministic ties and never gain invented time precision", () => {
  const a = event({ id: "a", publishedAt: "2026-09-29", matchedTrackingTerms: ["AMD"] });
  const b = event({ id: "b", publishedAt: "2026-09-29", matchedTrackingTerms: ["AMD"],
    source: { ...event().source, url: "https://newsroom.amd.com/news/another/" } });
  const one = buildHomepageFocusSelection([b, a], preferences, [], [], now).items;
  const two = buildHomepageFocusSelection([a, b], preferences, [], [], now).items;
  assert.deepEqual(one.map((item) => item.id), ["a", "b"]);
  assert.deepEqual(one, two);
  assert.ok(one.every((item) => item.publishedAt === "2026-09-29"));
});

test("invalid publication dates stay excluded instead of falling back to collection time", () => {
  const invalid = event({ id: "undated", publishedAt: "unknown", matchedTrackingTerms: ["AMD"] });
  const result = buildHomepageFocusSelection([invalid], preferences, [favorite], [share], now);
  assert.equal(result.items.length, 0);
  assert.equal(result.decisions.get(invalid.id)?.exclusion, "stale");
});
