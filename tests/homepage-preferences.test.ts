import assert from "node:assert/strict";
import test from "node:test";
import {
  EMPTY_HOMEPAGE_PREFERENCES,
  normalizeHomepagePreferenceState,
  parseHomepagePreferenceState,
} from "@/lib/homepage-preferences";

test("homepage preference state deduplicates and bounds explicit signals", () => {
  const state = normalizeHomepagePreferenceState({
    followedSectors: ["HBM", " HBM ", "具身智能"],
    dismissedEventIds: ["event-1", "event-1", "event-2"],
    sectorDislikes: { HBM: 99, "具身智能": 2, invalid: 0 },
  });

  assert.deepEqual(state.followedSectors, ["HBM", "具身智能"]);
  assert.deepEqual(state.dismissedEventIds, ["event-1", "event-2"]);
  assert.equal(state.sectorDislikes.HBM, 4);
  assert.equal(state.sectorDislikes["具身智能"], 2);
  assert.equal(state.sectorDislikes.invalid, undefined);
});

test("invalid serialized homepage preferences fail closed to an empty profile", () => {
  assert.equal(parseHomepagePreferenceState("not-json"), EMPTY_HOMEPAGE_PREFERENCES);
  assert.deepEqual(parseHomepagePreferenceState(null), EMPTY_HOMEPAGE_PREFERENCES);
});
