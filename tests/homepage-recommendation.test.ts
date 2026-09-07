import assert from "node:assert/strict";
import test from "node:test";
import type { FavoriteItem } from "@/lib/favorites";
import type { HomepagePreferenceState } from "@/lib/homepage-preferences";
import {
  baseHomepageRecommendationScore,
  homepageEventKey,
  homepageFeedFavoriteInput,
  homepageRecommendationReasons,
  isHomepageEventDismissed,
  matchesHomepageFollowChannel,
  personalizedHomepageRecommendationScore,
} from "@/lib/homepage-recommendation";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

const item: LiveIntelligenceEvent = {
  id: "event-1",
  eventClusterId: "cluster-1",
  title: "HBM capacity expands",
  summary: "A representative HBM supply-chain event.",
  type: "技术突破",
  region: "全球",
  sector: "HBM",
  company: "Example Semiconductor",
  publishedAt: "2026-09-07T03:00:00.000Z",
  importance: 94,
  source: {
    name: "Example Official",
    url: "https://example.com/news/hbm",
    level: "官方披露",
  },
  qualityScore: 92,
  qualityStatus: "高可信",
  duplicateCount: 3,
  matchedTrackingTerms: ["HBM", "高带宽内存"],
};

const emptyPreferences: HomepagePreferenceState = {
  schemaVersion: 1,
  followedSectors: [],
  dismissedEventIds: [],
  sectorDislikes: {},
};

const favorite: FavoriteItem = {
  id: "other-favorite",
  href: "https://another.example/hbm",
  title: "Saved HBM note",
  summary: "",
  channel: "technology",
  channelLabel: "核心赛道",
  keywords: ["HBM"],
  sectors: ["HBM"],
  sources: [{ name: "Another", url: "https://another.example/hbm" }],
  company: "Another Company",
  savedAt: "2026-09-07T01:00:00.000Z",
};

test("explicit follows and saved-topic affinity increase homepage recommendation score", () => {
  const followed: HomepagePreferenceState = {
    ...emptyPreferences,
    followedSectors: ["HBM"],
  };
  const base = baseHomepageRecommendationScore(item);
  const personalized = personalizedHomepageRecommendationScore(item, followed, [favorite]);

  assert.ok(personalized > base + 15);
  assert.equal(matchesHomepageFollowChannel(item, followed), true);
  assert.match(homepageRecommendationReasons(item, followed, [favorite]).join(" | "), /关注「HBM」/);
  assert.match(homepageRecommendationReasons(item, followed, [favorite]).join(" | "), /稍后读过「HBM」/);
});

test("negative sector feedback is bounded and exact dismissed events are filtered", () => {
  const disliked: HomepagePreferenceState = {
    ...emptyPreferences,
    dismissedEventIds: [homepageEventKey(item)],
    sectorDislikes: { HBM: 4 },
  };

  assert.equal(isHomepageEventDismissed(item, disliked), true);
  assert.ok(
    personalizedHomepageRecommendationScore(item, disliked, []) <
      baseHomepageRecommendationScore(item),
  );
});

test("later-read favorite payload reuses the existing event favorite identity", () => {
  const payload = homepageFeedFavoriteInput(item);

  assert.equal(payload.id, "daily-brief:event:cluster-1");
  assert.deepEqual(payload.sectors, ["HBM"]);
  assert.equal(payload.company, "Example Semiconductor");
  assert.equal(payload.importance, 94);
  assert.equal(payload.publishedAt, "2026-09-07");
  assert.equal(payload.sources?.[0]?.url, item.source.url);
});
