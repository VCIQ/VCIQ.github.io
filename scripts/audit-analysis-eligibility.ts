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
const correctedHighConfidenceIds = new Set(
  population
    .filter(
      (entry) =>
        entry.status === "canonical-corrected" && highConfidenceIds.has(entry.item.id),
    )
    .map((entry) => entry.item.id),
);
const remainingHighConfidenceCount =
  highConfidenceIds.size - correctedHighConfidenceIds.size;

const invalidWeights = population.filter(
  (entry) =>
    !Number.isFinite(entry.sectorWeight) ||
    !Number.isFinite(entry.topicWeight) ||
    entry.sectorWeight < 0 ||
    entry.sectorWeight > 1 ||
    entry.topicWeight < 0 ||
    entry.topicWeight > 1,
);
const invalidContentWeights = population.filter(
  (entry) =>
    entry.contentWeight === undefined ||
    ![0.25, 0.5, 1].includes(entry.contentWeight) ||
    (entry.contentRelevanceStatus === "priority-topic" && entry.contentWeight !== 1) ||
    (entry.contentRelevanceStatus === "usable" && entry.contentWeight !== 1) ||
    (entry.contentRelevanceStatus === "partial-evidence" && entry.contentWeight !== 0.5) ||
    (entry.contentRelevanceStatus === "weak-evidence" && entry.contentWeight !== 0.25),
);
const invalidSemanticRescue = population.filter((entry) => {
  const multiplier = entry.trackSemanticRescueMultiplier;
  const status = entry.trackSemanticRescueStatus;
  if (multiplier === undefined || ![1, 1.5, 2].includes(multiplier)) return true;
  if (multiplier === 1) return status !== "none";
  if (
    entry.contentRelevanceStatus !== "weak-evidence" ||
    entry.analysisTopicSlugs.length > 0
  ) {
    return true;
  }
  if (status === "title-rescue") {
    return multiplier !== 2 || !(entry.trackSemanticTitleAnchors?.length ?? 0);
  }
  if (status === "summary-rescue") {
    return (
      multiplier !== 1.5 ||
      (entry.trackSemanticTitleAnchors?.length ?? 0) > 0 ||
      new Set(entry.trackSemanticSummaryAnchors ?? []).size < 2
    );
  }
  return true;
});
const invalidSourceTrackWeights = population.filter(
  (entry) =>
    entry.sourceTrackWeight === undefined ||
    ![0.5, 0.75, 1].includes(entry.sourceTrackWeight) ||
    (entry.sourceTrackRelevanceStatus === "severe-downweight" &&
      entry.sourceTrackWeight !== 0.5) ||
    (entry.sourceTrackRelevanceStatus === "moderate-downweight" &&
      entry.sourceTrackWeight !== 0.75) ||
    (["bypass-strong-evidence", "normal", "provisional", "insufficient"].includes(
      entry.sourceTrackRelevanceStatus ?? "",
    ) &&
      entry.sourceTrackWeight !== 1),
);
const sourceTrackStrongEvidenceViolations = population.filter(
  (entry) =>
    (entry.sourceTrackWeight ?? 1) < 1 &&
    ((entry.item.topicSlugs?.length ?? 0) > 0 ||
      entry.contentRelevanceStatus === "usable" ||
      entry.status === "canonical-corrected"),
);

function baseSectorWeight(status: (typeof population)[number]["status"]) {
  if (status === "sector-excluded" || status === "unscoped") return 0;
  if (status === "downweighted") return 0.5;
  return 1;
}

function baseTopicWeight(entry: (typeof population)[number]) {
  if (!entry.analysisTopicSlugs.length) return 0;
  return entry.status === "downweighted" ? 0.75 : 1;
}

const compositionViolations = population.filter((entry) => {
  const expectedSector =
    baseSectorWeight(entry.status) *
    (entry.contentWeight ?? 1) *
    (entry.trackSemanticRescueMultiplier ?? 1) *
    (entry.sourceTrackWeight ?? 1);
  const expectedTopic = baseTopicWeight(entry) * (entry.contentWeight ?? 1);
  return (
    Math.abs(entry.sectorWeight - expectedSector) > 1e-9 ||
    Math.abs(entry.topicWeight - expectedTopic) > 1e-9
  );
});

const invalidTrackTargets = population.flatMap((entry) =>
  entry.analysisTracks
    .filter((track) => !activeTrackNames.has(track))
    .map((track) => ({ id: entry.item.id, title: entry.item.title, track })),
);
const leakedHighConfidence = population.filter(
  (entry) =>
    highConfidenceIds.has(entry.item.id) &&
    entry.sectorWeight > 0 &&
    entry.status !== "canonical-corrected",
);
const invalidCanonicalCorrections = population.filter(
  (entry) =>
    entry.status === "canonical-corrected" &&
    (!entry.canonicalAssignment ||
      entry.analysisTracks.length === 0 ||
      entry.sourceTrackWeight !== 1),
);
const lostHighConfidenceTopics = population.filter(
  (entry) =>
    highConfidenceIds.has(entry.item.id) &&
    (entry.item.topicSlugs ?? []).length > 0 &&
    entry.topicWeight <= 0,
);
const structuralPolicyViolations = population.filter(
  (entry) =>
    (entry.status === "cross-sector" && entry.analysisTracks.length < 2) ||
    (entry.status === "sector-excluded" && entry.analysisTracks.length !== 0) ||
    (entry.status === "unscoped" && entry.analysisTracks.length !== 0),
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
  snapshot.population.canonicalCorrected +
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
  canonicalCorrected: snapshot.population.canonicalCorrected,
  crossSector: snapshot.population.crossSector,
  downweighted: snapshot.population.downweighted,
  sectorExcluded: snapshot.population.sectorExcluded,
  unscoped: snapshot.population.unscoped,
  contentPartialEvidence: snapshot.population.contentPartialEvidence,
  contentWeakEvidence: snapshot.population.contentWeakEvidence,
  semanticTitleRescued: snapshot.population.semanticTitleRescued,
  semanticSummaryRescued: snapshot.population.semanticSummaryRescued,
  sourceTrackSevereDownweighted: snapshot.population.sourceTrackSevereDownweighted,
  sourceTrackModerateDownweighted: snapshot.population.sourceTrackModerateDownweighted,
  sourceTrackProvisional: snapshot.population.sourceTrackProvisional,
  datedForTrend: snapshot.population.datedForTrend,
  highConfidenceSectorFindings: highConfidenceIds.size,
  correctedHighConfidence: correctedHighConfidenceIds.size,
  remainingHighConfidence: remainingHighConfidenceCount,
  activeTracks: snapshot.tracks.length,
  technologyTopics: snapshot.topics.length,
  risingTracks,
  risingTopics,
  currentThirtyDayTrackActivity,
  currentThirtyDayTopicActivity,
};

console.log(`ANALYSIS_ELIGIBILITY_AUDIT=${JSON.stringify(audit)}`);

if (snapshot.population.canonicalCorrected) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_NOTICE: ${snapshot.population.canonicalCorrected} reviewed canonical sector assignments now contribute to sector Momentum while retaining original sector provenance`,
  );
}
if (snapshot.population.sectorExcluded) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_WARNING: ${snapshot.population.sectorExcluded} unreviewed high-confidence sector candidates remain excluded from sector Momentum`,
  );
}
if (snapshot.population.downweighted) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_WARNING: ${snapshot.population.downweighted} uncertain sector assignments retain the base 0.5 sector / 0.75 topic policy before orthogonal relevance weights`,
  );
}
if (snapshot.population.contentPartialEvidence || snapshot.population.contentWeakEvidence) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_NOTICE: content relevance weighting applies to ${snapshot.population.contentPartialEvidence} partial-evidence events at 0.5 and ${snapshot.population.contentWeakEvidence} weak-evidence events at 0.25; no raw events are deleted`,
  );
}
if (snapshot.population.semanticTitleRescued || snapshot.population.semanticSummaryRescued) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_NOTICE: track semantic rescue restores limited sector weight for ${snapshot.population.semanticTitleRescued} direct-title and ${snapshot.population.semanticSummaryRescued} multi-summary weak-evidence events; topic Momentum is unchanged`,
  );
}
if (
  snapshot.population.sourceTrackSevereDownweighted ||
  snapshot.population.sourceTrackModerateDownweighted ||
  snapshot.population.sourceTrackProvisional
) {
  console.warn(
    `ANALYSIS_ELIGIBILITY_NOTICE: source-track relevance applies stable-profile penalties to ${snapshot.population.sourceTrackSevereDownweighted} severe and ${snapshot.population.sourceTrackModerateDownweighted} moderate weak/partial events; ${snapshot.population.sourceTrackProvisional} events are in provisional profiles and receive no extra penalty`,
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
  snapshot.population.sectorExcluded !== remainingHighConfidenceCount
    ? `sector-excluded count (${snapshot.population.sectorExcluded}) does not match unreviewed high-confidence findings (${remainingHighConfidenceCount})`
    : "",
  invalidWeights.length ? `${invalidWeights.length} analysis entries have invalid weights` : "",
  invalidContentWeights.length
    ? `${invalidContentWeights.length} analysis entries violate content relevance weighting policy`
    : "",
  invalidSemanticRescue.length
    ? `${invalidSemanticRescue.length} analysis entries violate track semantic rescue policy`
    : "",
  invalidSourceTrackWeights.length
    ? `${invalidSourceTrackWeights.length} analysis entries violate source-track relevance weighting policy`
    : "",
  sourceTrackStrongEvidenceViolations.length
    ? `${sourceTrackStrongEvidenceViolations.length} strong-evidence events were incorrectly source-track downweighted`
    : "",
  compositionViolations.length
    ? `${compositionViolations.length} analysis entries violate multiplicative sector/content/rescue/source weighting composition`
    : "",
  invalidTrackTargets.length
    ? `${invalidTrackTargets.length} analysis entries point to inactive tracks`
    : "",
  leakedHighConfidence.length
    ? `${leakedHighConfidence.length} unreviewed high-confidence sector findings leaked into sector Momentum`
    : "",
  invalidCanonicalCorrections.length
    ? `${invalidCanonicalCorrections.length} canonical-corrected entries lack a valid reviewed assignment or source-gate bypass`
    : "",
  lostHighConfidenceTopics.length
    ? `${lostHighConfidenceTopics.length} high-confidence sector findings incorrectly lost valid topic evidence`
    : "",
  structuralPolicyViolations.length
    ? `${structuralPolicyViolations.length} analysis entries violate sector status structure`
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
