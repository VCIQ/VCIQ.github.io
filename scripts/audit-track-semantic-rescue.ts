import { buildTechnologyAnalysisPopulation } from "@/lib/analysis-eligibility";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";

const directory = getChannelUpdateDirectory("technology");
const population = buildTechnologyAnalysisPopulation(directory.items);

const rescued = population.filter(
  (entry) => (entry.trackSemanticRescueMultiplier ?? 1) > 1,
);
const titleRescued = rescued.filter(
  (entry) => entry.trackSemanticRescueStatus === "title-rescue",
);
const summaryRescued = rescued.filter(
  (entry) => entry.trackSemanticRescueStatus === "summary-rescue",
);

const invalid = rescued.filter(
  (entry) =>
    entry.contentRelevanceStatus !== "weak-evidence" ||
    entry.analysisTopicSlugs.length > 0 ||
    !entry.observedTrack ||
    ![1.5, 2].includes(entry.trackSemanticRescueMultiplier ?? 1) ||
    (entry.trackSemanticRescueStatus === "title-rescue" &&
      !(entry.trackSemanticTitleAnchors?.length ?? 0)) ||
    (entry.trackSemanticRescueStatus === "summary-rescue" &&
      new Set(entry.trackSemanticSummaryAnchors ?? []).size < 2),
);

const byTrack = [...new Set(rescued.map((entry) => entry.observedTrack ?? "未归类"))]
  .map((track) => ({
    track,
    count: rescued.filter((entry) => (entry.observedTrack ?? "未归类") === track).length,
    titleRescued: titleRescued.filter(
      (entry) => (entry.observedTrack ?? "未归类") === track,
    ).length,
    summaryRescued: summaryRescued.filter(
      (entry) => (entry.observedTrack ?? "未归类") === track,
    ).length,
  }))
  .sort((left, right) => right.count - left.count || left.track.localeCompare(right.track, "zh-CN"));

const samples = rescued.slice(0, 40).map((entry) => ({
  id: entry.item.id,
  title: entry.item.title,
  track: entry.observedTrack,
  status: entry.trackSemanticRescueStatus,
  multiplier: entry.trackSemanticRescueMultiplier,
  titleAnchors: entry.trackSemanticTitleAnchors,
  summaryAnchors: entry.trackSemanticSummaryAnchors,
  source: entry.item.source,
  sourceTrackStatus: entry.sourceTrackRelevanceStatus,
  finalSectorWeight: entry.sectorWeight,
}));

const audit = {
  eventCount: population.length,
  rescuedCount: rescued.length,
  titleRescuedCount: titleRescued.length,
  summaryRescuedCount: summaryRescued.length,
  invalidRescueCount: invalid.length,
  byTrack,
};

console.log(`TRACK_SEMANTIC_RESCUE_AUDIT=${JSON.stringify(audit)}`);
console.log(`TRACK_SEMANTIC_RESCUE_SAMPLES=${JSON.stringify(samples)}`);

if (rescued.length) {
  console.warn(
    `TRACK_SEMANTIC_RESCUE_NOTICE: ${rescued.length} weak, untagged events receive limited sector-only semantic rescue; raw evidence and topic Momentum remain unchanged`,
  );
}
if (invalid.length) {
  console.error(
    `TRACK_SEMANTIC_RESCUE_AUDIT_ERROR: ${invalid.length} rescue entries violate weak/untagged/anchor constraints`,
  );
  process.exitCode = 1;
}
