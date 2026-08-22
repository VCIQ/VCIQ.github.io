import {
  canonicalSectorAssignments,
  canonicalSectorAssignmentUpdatedAt,
  canonicalSectorAssignmentVersion,
  canonicalTracksForItem,
} from "@/lib/canonical-sector-assignment";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import { buildSectorQualityReviewQueue } from "@/lib/sector-quality-audit";
import { userTrackingConfig } from "@/lib/user-tracking";

const directory = getChannelUpdateDirectory("technology");
const eventById = new Map(directory.items.map((item) => [item.id, item]));
const activeTrackNames = new Set(
  userTrackingConfig.tracks.filter((track) => track.enabled).map((track) => track.name),
);
const reviewById = new Map(
  buildSectorQualityReviewQueue(directory.items).map((finding) => [finding.id, finding]),
);

const ids = canonicalSectorAssignments.map((assignment) => assignment.id);
const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
const invalidTargets = canonicalSectorAssignments.flatMap((assignment) =>
  assignment.canonicalTracks
    .filter((track) => !activeTrackNames.has(track))
    .map((track) => ({ id: assignment.id, track })),
);
const invalidReviewDates = canonicalSectorAssignments.filter((assignment) =>
  Number.isNaN(new Date(assignment.reviewedAt).getTime()),
);
const emptyReasons = canonicalSectorAssignments.filter(
  (assignment) => assignment.reason.trim().length < 8,
);
const emptyTargets = canonicalSectorAssignments.filter(
  (assignment) => assignment.canonicalTracks.length === 0,
);
const missingEvents = canonicalSectorAssignments.filter(
  (assignment) => !eventById.has(assignment.id),
);
const observedTrackMismatches = canonicalSectorAssignments.flatMap((assignment) => {
  const item = eventById.get(assignment.id);
  if (!item) return [];
  const observedTrack = item.track?.trim() || "";
  return observedTrack === assignment.expectedObservedTrack
    ? []
    : [{ id: assignment.id, expected: assignment.expectedObservedTrack, actual: observedTrack }];
});
const noOpReplacements = canonicalSectorAssignments.filter(
  (assignment) =>
    assignment.mode === "replace" &&
    assignment.canonicalTracks.length === 1 &&
    assignment.canonicalTracks[0] === assignment.expectedObservedTrack,
);
const unappliedPresentAssignments = canonicalSectorAssignments.flatMap((assignment) => {
  const item = eventById.get(assignment.id);
  if (!item) return [];
  const resolution = canonicalTracksForItem(item);
  return resolution.applied ? [] : [{ id: assignment.id, title: item.title }];
});
const recommendationDivergence = canonicalSectorAssignments.flatMap((assignment) => {
  const finding = reviewById.get(assignment.id);
  if (!finding || finding.category !== "high-confidence-misclassification") return [];
  const overlapsSuggestion = assignment.canonicalTracks.some((track) =>
    finding.recommendedTracks.includes(track),
  );
  return overlapsSuggestion
    ? []
    : [{
        id: assignment.id,
        title: finding.title,
        reviewed: assignment.canonicalTracks,
        suggested: finding.recommendedTracks,
      }];
});

const applied = canonicalSectorAssignments.filter((assignment) => {
  const item = eventById.get(assignment.id);
  return item ? canonicalTracksForItem(item).applied : false;
});
const highConfidence = [...reviewById.values()].filter(
  (finding) => finding.category === "high-confidence-misclassification",
);
const correctedHighConfidenceIds = new Set(
  applied
    .filter((assignment) =>
      highConfidence.some((finding) => finding.id === assignment.id),
    )
    .map((assignment) => assignment.id),
);
const remainingHighConfidence = highConfidence.filter(
  (finding) => !correctedHighConfidenceIds.has(finding.id),
);

const audit = {
  version: canonicalSectorAssignmentVersion,
  updatedAt: canonicalSectorAssignmentUpdatedAt,
  eventCount: directory.items.length,
  assignmentCount: canonicalSectorAssignments.length,
  appliedAssignmentCount: applied.length,
  missingEventCount: missingEvents.length,
  highConfidenceBeforeCanonicalReview: highConfidence.length,
  correctedHighConfidenceCount: correctedHighConfidenceIds.size,
  remainingHighConfidenceCount: remainingHighConfidence.length,
  recommendationDivergenceCount: recommendationDivergence.length,
};

console.log(`CANONICAL_SECTOR_ASSIGNMENT_AUDIT=${JSON.stringify(audit)}`);

if (missingEvents.length) {
  console.warn(
    `CANONICAL_SECTOR_ASSIGNMENT_WARNING: ${missingEvents.length} reviewed assignments are not present in the current public event window; provenance is retained in the registry`,
  );
}
if (recommendationDivergence.length) {
  console.warn(
    `CANONICAL_SECTOR_ASSIGNMENT_WARNING: ${recommendationDivergence.length} human-reviewed assignments differ from the current automatic recommendation`,
  );
  console.log(
    `CANONICAL_SECTOR_ASSIGNMENT_DIVERGENCE_SAMPLES=${JSON.stringify(recommendationDivergence.slice(0, 12))}`,
  );
}
if (remainingHighConfidence.length) {
  console.log(
    `CANONICAL_SECTOR_ASSIGNMENT_REVIEW_QUEUE=${JSON.stringify(
      remainingHighConfidence.slice(0, 20).map((finding) => ({
        id: finding.id,
        title: finding.title,
        observedTrack: finding.currentTrack,
        recommendedTracks: finding.recommendedTracks,
        topics: finding.incompatibleTopics,
        sourceGrade: finding.sourceGrade,
      })),
    )}`,
  );
}

const hardFailures = [
  canonicalSectorAssignmentVersion !== 1
    ? `unsupported canonical sector assignment version ${canonicalSectorAssignmentVersion}`
    : "",
  duplicateIds.length ? `${duplicateIds.length} duplicate assignment ids` : "",
  invalidTargets.length ? `${invalidTargets.length} assignment targets are not active tracks` : "",
  invalidReviewDates.length ? `${invalidReviewDates.length} assignments have invalid reviewedAt dates` : "",
  emptyReasons.length ? `${emptyReasons.length} assignments do not contain an auditable review reason` : "",
  emptyTargets.length ? `${emptyTargets.length} assignments contain no canonical target track` : "",
  observedTrackMismatches.length
    ? `${observedTrackMismatches.length} present assignments no longer match their expected observed track`
    : "",
  noOpReplacements.length ? `${noOpReplacements.length} replace assignments are no-ops` : "",
  unappliedPresentAssignments.length
    ? `${unappliedPresentAssignments.length} present reviewed assignments failed to apply`
    : "",
].filter(Boolean);

if (hardFailures.length) {
  for (const failure of hardFailures) {
    console.error(`CANONICAL_SECTOR_ASSIGNMENT_AUDIT_ERROR: ${failure}`);
  }
  process.exitCode = 1;
}
