import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import {
  buildSectorQualityReviewQueue,
  type SectorQualityCategory,
} from "@/lib/sector-quality-audit";
import { userTrackingConfig } from "@/lib/user-tracking";

const technologyItems = getChannelUpdateDirectory("technology").items.filter(
  (item) => Boolean(item.track),
);
const queue = buildSectorQualityReviewQueue(technologyItems);

const categoryCounts = new Map<SectorQualityCategory, number>([
  ["high-confidence-misclassification", 0],
  ["reasonable-cross-sector", 0],
  ["needs-review", 0],
]);
for (const finding of queue) {
  categoryCounts.set(
    finding.category,
    (categoryCounts.get(finding.category) ?? 0) + 1,
  );
}

function countBy(values: string[]) {
  const counts = new Map<string, number>();
  for (const value of values.filter(Boolean)) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort(
      (left, right) =>
        right.count - left.count || left.name.localeCompare(right.name, "zh-CN"),
    );
}

const activeTrackNames = new Set(
  userTrackingConfig.tracks
    .filter((track) => track.enabled)
    .map((track) => track.name),
);
const invalidRecommendations = queue.flatMap((finding) =>
  finding.recommendedTracks
    .filter((track) => !activeTrackNames.has(track))
    .map((track) => ({ id: finding.id, title: finding.title, track })),
);
const highConfidenceWithoutRecommendation = queue.filter(
  (finding) =>
    finding.category === "high-confidence-misclassification" &&
    finding.recommendedTracks.length === 0,
);
const duplicateIds = [
  ...new Set(
    queue
      .map((finding) => finding.id)
      .filter((id, index, values) => values.indexOf(id) !== index),
  ),
];

const highConfidence = queue.filter(
  (finding) => finding.category === "high-confidence-misclassification",
);
const reasonableCrossSector = queue.filter(
  (finding) => finding.category === "reasonable-cross-sector",
);
const needsReview = queue.filter((finding) => finding.category === "needs-review");

const summary = {
  eventCount: technologyItems.length,
  topicTaggedEventCount: technologyItems.filter(
    (item) => (item.topicSlugs ?? []).length > 0,
  ).length,
  reviewCandidateCount: queue.length,
  highConfidenceMisclassificationCount: highConfidence.length,
  reasonableCrossSectorCount: reasonableCrossSector.length,
  needsReviewCount: needsReview.length,
  suggestedTrendExclusionCount: highConfidence.length,
  structurallyValidRecommendationCount:
    queue.length - invalidRecommendations.length - highConfidenceWithoutRecommendation.length,
  byCurrentTrack: countBy(queue.map((finding) => finding.currentTrack)),
  byRecommendedTrack: countBy(
    queue.flatMap((finding) => finding.recommendedTracks),
  ),
};

console.log(`SECTOR_QUALITY_AUDIT=${JSON.stringify(summary)}`);

function printSamples<T>(label: string, rows: T[]) {
  if (!rows.length) return;
  console.log(`${label}=${JSON.stringify(rows.slice(0, 15))}`);
}

printSamples(
  "SECTOR_QUALITY_HIGH_CONFIDENCE_QUEUE",
  highConfidence.map((finding) => ({
    id: finding.id,
    title: finding.title,
    currentTrack: finding.currentTrack,
    recommendedTracks: finding.recommendedTracks,
    topics: finding.incompatibleTopics,
    sourceGrade: finding.sourceGrade,
  })),
);
printSamples(
  "SECTOR_QUALITY_CROSS_SECTOR_QUEUE",
  reasonableCrossSector.map((finding) => ({
    id: finding.id,
    title: finding.title,
    currentTrack: finding.currentTrack,
    compatibleTopics: finding.compatibleTopics,
    adjacentTopics: finding.incompatibleTopics,
  })),
);
printSamples(
  "SECTOR_QUALITY_NEEDS_REVIEW_QUEUE",
  needsReview.map((finding) => ({
    id: finding.id,
    title: finding.title,
    currentTrack: finding.currentTrack,
    recommendedTracks: finding.recommendedTracks,
    topics: finding.incompatibleTopics,
  })),
);

if (highConfidence.length) {
  console.warn(
    `SECTOR_QUALITY_AUDIT_WARNING: ${highConfidence.length} events are high-confidence sector-misclassification candidates; do not use them for future sector Momentum until reviewed or excluded`,
  );
}
if (reasonableCrossSector.length) {
  console.warn(
    `SECTOR_QUALITY_AUDIT_WARNING: ${reasonableCrossSector.length} events appear legitimately cross-sector and should not be force-moved to a single track`,
  );
}
if (needsReview.length) {
  console.warn(
    `SECTOR_QUALITY_AUDIT_WARNING: ${needsReview.length} events have weak cross-track evidence and require manual review`,
  );
}

const hardFailures = [
  invalidRecommendations.length
    ? `${invalidRecommendations.length} sector recommendations point to inactive tracks`
    : "",
  highConfidenceWithoutRecommendation.length
    ? `${highConfidenceWithoutRecommendation.length} high-confidence findings have no recommended track`
    : "",
  duplicateIds.length
    ? `${duplicateIds.length} duplicate event ids exist in the sector review queue`
    : "",
  queue.length !==
  (categoryCounts.get("high-confidence-misclassification") ?? 0) +
    (categoryCounts.get("reasonable-cross-sector") ?? 0) +
    (categoryCounts.get("needs-review") ?? 0)
    ? "sector review category counts do not reconcile"
    : "",
].filter(Boolean);

if (hardFailures.length) {
  for (const failure of hardFailures) {
    console.error(`SECTOR_QUALITY_AUDIT_ERROR: ${failure}`);
  }
  process.exitCode = 1;
}
