import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeTaxonomyTerm,
  trackNameAliases,
  uniqueIdentityTermsByTrack,
} from "../lib/tracking-taxonomy";
import { userTrackingConfig, type TrackingTrack } from "../lib/user-tracking";

function track(
  slug: string,
  name: string,
  keywords: string[],
): TrackingTrack {
  return {
    slug,
    name,
    enabled: true,
    custom: false,
    keywords,
    people: [],
    sampleCompanies: [],
  };
}

test("dynamic keywords cannot steal another track's canonical identity", () => {
  const tracks = [
    track("ai", "AI / AGI", ["大模型", "Agent"]),
    track("biotech", "生物科技", ["AI / AGI", "AI", "biotech"]),
  ];
  const terms = uniqueIdentityTermsByTrack(tracks);
  const aiTerms = new Set(
    (terms.get("ai") ?? []).map(normalizeTaxonomyTerm),
  );
  const biotechTerms = new Set(
    (terms.get("biotech") ?? []).map(normalizeTaxonomyTerm),
  );

  assert.ok(aiTerms.has(normalizeTaxonomyTerm("AI / AGI")));
  assert.ok(aiTerms.has(normalizeTaxonomyTerm("AI")));
  assert.equal(biotechTerms.has(normalizeTaxonomyTerm("AI / AGI")), false);
  assert.equal(biotechTerms.has(normalizeTaxonomyTerm("AI")), false);
  assert.ok(biotechTerms.has(normalizeTaxonomyTerm("biotech")));
});

test("current enabled tracking config has one owner for every canonical name alias", () => {
  const activeTracks = userTrackingConfig.tracks.filter((item) => item.enabled);
  const terms = uniqueIdentityTermsByTrack(activeTracks);

  for (const canonicalTrack of activeTracks) {
    const canonicalKeys = new Set(
      trackNameAliases(canonicalTrack.name).map(normalizeTaxonomyTerm),
    );
    for (const otherTrack of activeTracks) {
      if (otherTrack.slug === canonicalTrack.slug) continue;
      const stolen = (terms.get(otherTrack.slug) ?? []).filter((value) =>
        canonicalKeys.has(normalizeTaxonomyTerm(value)),
      );
      assert.deepEqual(
        stolen,
        [],
        `${otherTrack.name} must not own canonical aliases of ${canonicalTrack.name}`,
      );
    }
  }
});
