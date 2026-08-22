import { buildTechnologyAnalysisPopulation } from "@/lib/analysis-eligibility";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import { buildSectorQualityReviewQueue } from "@/lib/sector-quality-audit";
import { buildTechnologyAnalysisSnapshot } from "@/lib/technology-momentum";
import { technologyTopicDefinitions } from "@/lib/technology-topics";
import { userTrackingConfig } from "@/lib/user-tracking";

const directory = getChannelUpdateDirectory("technology");
const population = buildTechnologyAnalysisPopulation(directory.items);
const snapshot = buildTechnologyAnalysisSnapshot(directory);
const reviewQueue = buildSectorQualityReviewQueue(directory.items);
const activeTrackNames = new Set(
  userTrackingConfig.tracks.filter((track) => track.enabled).map((track) => track.name),
);

const highConfidenceIds = new Set(
  reviewQueue
    .filter((finding) => finding.category === "high-confidence-misclassification")
    .map((finding) => finding.id),
);

const invalidWeights = population.filter(
  (entry) =>
    !Number.isFinite(entry.sectorWeight) ||
    !Number.isFinite(entry.topicWeight) ||
    entry.sectorWeight < 0 ||
    entry.sectorWeight > 1 ||
    entry.topicWeight < 0 ||
    entry.topicWeight > 1,
);
const invalidTrackTargets = population.flatMap((entry) =>
  entry.analysisTracks
    .filter((track) => !activeTrackNames.has(track))
    .map((track) => ({ id: entry.item.id, title: entry.item.title, track })),
);
const leakedHighConfidence = population.filter(
  (entry) => highConfidenceIds.has(entry.item.id) && entry.sectorWeight > 0,
);
const lostHighConfidenceTopics = population.filter(
  (entry) =>
    highConfidenceIds.has(entry.item.id) &&
    (entry.item.topicSlugs ?? []).length > 0 &&
    entry.topicWeight <= 0,
);
const downweightedPolicyViolations = population.filter(
  (entry) =>
    entry.status === "downweighted" &&
    (entry.sectorWeight !== 0.5 || entry.topicWeight !== 0.75),
);
const crossSectorPolicyViolations = population.filter(
  (entry) =>
    entry.status === "cross-sector" &&
    (entry.sectorWeight !== 1 || entry.analysisTracks.length < 2),
);

function invalidWindow(value: {
  currentWeightedEvents: number;
  previousWeightedEvents: number;
  deltaWeightedEvents: number;
}) {
  return (
    !Number.isFinite(value.currentWeightedEvents) ||
    !Number.isFinite(value.previousWeightedEvents) ||
    !Number.isFinite(value.deltaWeightedEvents) ||
    value.currentWeightedEvents < 0 ||
    value.previousWeightedEvents < 0
  );
}

const invalidMomentumRows = [
  ...snapshot.tracks.flatMap((track) =>
    [track.sevenDayTrend, track.thirtyDayMomentum]
      .filter(invalidWindow)
      .map(() => ({ kind: "track", name: track.name })),
  ),
  ...snapshot.topics.flatMap((topic) =>
    [topic.sevenDayTrend, topic.thirtyDayMomentum]
      .filter(invalidWindow)
      .map(() => ({ kind: "topic", name: topic.name })),
  ),
];

const readinessViolations = [
  ...snapshot.tracks.flatMap((track) => [
    { name: track.name, kind: "track-7d", window: track.sevenDayTrend, ready: snapshot.coverage.sevenDayComparisonReady },
    { name: track.name, kind: "track-30d", window: track.thirtyDayMomentum, ready: snapshot.coverage.thirtyDayComparisonReady },
  ]),
  ...snapshot.topics.flatMap((topic) => [
    { name: topic.name, kind: "topic-7d", window: topic.sevenDayTrend, ready: snapshot.coverage.sevenDayComparisonReady },
    { name: topic.name, kind: "topic-30d", window: topic.thirtyDayMomentum, ready: snapshot.coverage.thirtyDayComparisonReady },
  ]),
].filter(({ window, ready }) =>
  ready
    ? !window.comparisonReady || window.direction === "insufficient"
    : window.comparisonReady || window.direction !== "insufficient" || window.growthPct !== null,
);

const populationCount =
  snapshot.population.included +
  snapshot.population.crossSector +
  snapshot.population.downweighted +
  snapshot.population.sectorExcluded +
  snapshot.population.unscoped;

const risingTracks = snapshot.tracks
  .filter(
    (track) =>
      track.thirtyDayMomentum.comparisonReady &&
      ["up", "new"].includes(track.thirtyDayMomentum.direction),
  )
  .sort(
    (left, right) =>
      right.thirtyDayMomentum.deltaWeightedEvents -
      left.thirtyDayMomentum.deltaWeightedEvents,
  )
  .slice(0, 8)
  .map((track) => ({
    name: track.name,
    direction: track.thirtyDayMomentum.direction,
    current: track.thirtyDayMomentum.currentWeightedEvents,
    previous: track.thirtyDayMomentum.previousWeightedEvents,
    growthPct: track.thirtyDayMomentum.growthPct,
  }));
const risingTopics = snapshot.topics
  .filter(
    (topic) =>
      topic.thirtyDayMomentum.comparisonReady &&
      ["up", "new"].includes(topic.thirtyDayMomentum.direction),
  )
  .sort(
    (left, right) =>
      right.thirtyDayMomentum.deltaWeightedEvents -
      left.thirtyDayMomentum.deltaWeightedEvents,
  )
  .slice(0, 8)
  .map((topic) => ({
    name: topic.name,
    direction: topic.thirtyDayMomentum.direction,
    current: topic.thirtyDayMomentum.currentWeightedEvents,
    previous: topic.thirtyDayMomentum.previousWeightedEvents,
    growthPct: topic.thirtyDayMomentum.growthPct,
  }));
const currentThirtyDayTrackActivity = snapshot.tracks
  .sort(
    (left, right) =>
      right.thirtyDayMomentum.currentWeightedEvents -
      left.thirtyDayMomentum.currentWeightedEvents,
  )
  .slice(0, 8)
  .map((track) => ({
    name: track.name,
    current: track.thirtyDayMomentum.currentWeightedEvents,
  }));
const currentThirtyDayTopicActivity = snapshot.topics
  .sort(
    (left, right) =>
      right.thirtyDayMomentum.currentWeightedEvents -
      left.thirtyDayMomentum.currentWeightedEvents,
  )
  .slice(0, 8)
  .map((topic) => ({
    name: topic.name,
    current: topic.thirtyDayMomentum.currentWeightedEvents,
  }));

const audit = {
  asOf: snapshot.asOf,
  coverage: snapshot.coverage,
  totalEvents: snapshot.population.totalEvents,
  included: snapshot.population.included,
  crossSector: snapshot.population.crossSector,
  downweighted: snapshot.population.downweighted,
  sectorExcluded: snapshot.population.sectorExcluded,
  unscoped: snapshot.population.unscoped,
  datedForTrend: snapshot.population.datedForTrend,
  highConfidenceSectorFindings: highConfidenceIds.size,
  activeTracks: snapshot.tracks.length,
  technologyTopics: snapshot.topics.length,
  risingTracks,
  risingTopics,
  currentThirtyDayTrackActivity,
  currentThirtyDayTopicActivity,
};

console.log(`ANALYSIS_ELIGIBILITY_AUDIT=${JSON.stringify(audit)}`);

if (snapshot.population.sectorExcluded) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_WARNING: ${snapshot.population.sectorExcluded} high-confidence sector candidates are excluded from sector Momentum until reviewed`,
  );
}
if (snapshot.population.downweighted) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_WARNING: ${snapshot.population.downweighted} uncertain sector assignments are retained at 0.5 sector weight / 0.75 topic weight`,
  );
}
if (!snapshot.coverage.sevenDayComparisonReady || !snapshot.coverage.thirtyDayComparisonReady) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_WARNING: observation history is ${snapshot.coverage.observedDays ?? "unknown"} days; 7D/30D growth remains suppressed until 14/60 reliable first-seen days are available`,
  );
}

const hardFailures = [
  populationCount !== snapshot.population.totalEvents
    ? `population status counts (${populationCount}) do not reconcile to total (${snapshot.population.totalEvents})`
    : "",
  snapshot.population.sectorExcluded !== highConfidenceIds.size
    ? `sector-excluded count (${snapshot.population.sectorExcluded}) does not match high-confidence sector findings (${highConfidenceIds.size})`
    : "",
  invalidWeights.length ? `${invalidWeights.length} analysis entries have invalid weights` : "",
  invalidTrackTargets.length
    ? `${invalidTrackTargets.length} analysis entries point to inactive tracks`
    : "",
  leakedHighConfidence.length
    ? `${leakedHighConfidence.length} high-confidence sector findings leaked into sector Momentum`
    : "",
  lostHighConfidenceTopics.length
    ? `${lostHighConfidenceTopics.length} high-confidence sector findings incorrectly lost valid topic evidence`
    : "",
  downweightedPolicyViolations.length
    ? `${downweightedPolicyViolations.length} needs-review entries violate conservative weights`
    : "",
  crossSectorPolicyViolations.length
    ? `${crossSectorPolicyViolations.length} cross-sector entries violate multi-track policy`
    : "",
  invalidMomentumRows.length
    ? `${invalidMomentumRows.length} track/topic momentum rows contain invalid window values`
    : "",
  readinessViolations.length
    ? `${readinessViolations.length} momentum rows violate the global observation-coverage gate`
    : "",
  snapshot.tracks.length !== activeTrackNames.size
    ? `expected ${activeTrackNames.size} active track momentum rows, got ${snapshot.tracks.length}`
    : "",
  snapshot.topics.length !== technologyTopicDefinitions.length
    ? `expected ${technologyTopicDefinitions.length} topic momentum rows, got ${snapshot.topics.length}`
    : "",
].filter(Boolean);

if (hardFailures.length) {
  for (const failure of hardFailures) {
    console.error(`ANALYSIS_ELIGIBILITY_AUDIT_ERROR: ${failure}`);
  }
  process.exitCode = 1;
}
