import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { normalizeHomepagePreferenceCloudState } from "@/lib/homepage-preference-sync";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("homepage cloud state normalizes actor-scoped preference projection", () => {
  const state = normalizeHomepagePreferenceCloudState({
    available: true,
    followedSectors: ["HBM", " HBM ", "具身智能"],
    dismissedEventIds: ["e1", "e1", "e2"],
    dismissedEvents: [
      { eventId: "e1", sector: "HBM" },
      { eventId: "e1", sector: "HBM" },
      { eventId: "e2", sector: "具身智能" },
    ],
    sectorDislikes: { HBM: 99, "具身智能": 2, invalid: 0 },
    updatedAt: "2026-09-07T05:00:00Z",
  }, 200);

  assert.equal(state.available, true);
  assert.deepEqual(state.followedSectors, ["HBM", "具身智能"]);
  assert.deepEqual(state.dismissedEventIds, ["e1", "e2"]);
  assert.deepEqual(state.dismissedEvents, [
    { eventId: "e1", sector: "HBM" },
    { eventId: "e2", sector: "具身智能" },
  ]);
  assert.equal(state.sectorDislikes.HBM, 4);
  assert.equal(state.sectorDislikes["具身智能"], 2);
  assert.equal(state.authRequired, false);
});

test("homepage cloud read failures remain unavailable instead of fabricating empty success", () => {
  const state = normalizeHomepagePreferenceCloudState({}, 403);
  assert.equal(state.available, false);
  assert.equal(state.authRequired, true);
  assert.deepEqual(state.followedSectors, []);
});

test("explicit homepage actions mirror to cloud while the hook performs account hydration", async () => {
  const preferences = await source("lib/homepage-preferences.ts");
  const hook = await source("components/use-homepage-preferences.ts");
  const bootstrap = await source("lib/homepage-preference-cloud-bootstrap.ts");

  assert.match(preferences, /syncHomepagePreference\(\{ action: followed \? "follow" : "unfollow", sector \}\)/);
  assert.match(preferences, /syncHomepagePreference\(\{ action: "dismiss", eventId, sector \}\)/);
  assert.match(preferences, /syncHomepagePreference\(\{ action: "restore", eventId, sector \}\)/);
  assert.match(hook, /ensureHomepagePreferenceCloudHydrated\(\)/);
  assert.match(bootstrap, /bootstrapHomepagePreferenceHistory/);
  assert.match(bootstrap, /flushPendingHomepagePreferences/);
  assert.match(bootstrap, /fetchHomepagePreferenceCloudState/);
  assert.match(bootstrap, /LEGACY_DISMISSED_SECTOR = "__legacy__"/);
});
