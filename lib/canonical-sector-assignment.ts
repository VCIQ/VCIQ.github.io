import rawConfig from "@/config/canonical_sector_assignments.json";
import type { ChannelUpdateItem } from "@/lib/channel-updates";
import { userTrackingConfig } from "@/lib/user-tracking";

export type CanonicalSectorAssignmentMode = "replace" | "augment";

export type CanonicalSectorAssignmentRecord = {
  id: string;
  expectedObservedTrack: string;
  canonicalTracks: string[];
  mode: CanonicalSectorAssignmentMode;
  reviewedAt: string;
  reason: string;
  evidence?: string[];
};

type CanonicalSectorAssignmentConfig = {
  version: number;
  updatedAt: string;
  assignments: CanonicalSectorAssignmentRecord[];
};

const config = rawConfig as CanonicalSectorAssignmentConfig;
const assignmentById = new Map(config.assignments.map((assignment) => [assignment.id, assignment]));
const activeTrackNames = new Set(
  userTrackingConfig.tracks.filter((track) => track.enabled).map((track) => track.name),
);

function unique(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

export const canonicalSectorAssignmentVersion = config.version;
export const canonicalSectorAssignmentUpdatedAt = config.updatedAt;
export const canonicalSectorAssignments = config.assignments;

export function getCanonicalSectorAssignment(id: string) {
  return assignmentById.get(id);
}

export function canonicalTracksForItem(item: ChannelUpdateItem) {
  const observedTrack = item.track?.trim() || "";
  const assignment = getCanonicalSectorAssignment(item.id);
  if (!assignment) {
    return {
      assignment: undefined,
      observedTrack,
      canonicalTracks: observedTrack ? [observedTrack] : [],
      applied: false,
    };
  }

  if (assignment.expectedObservedTrack !== observedTrack) {
    return {
      assignment,
      observedTrack,
      canonicalTracks: observedTrack ? [observedTrack] : [],
      applied: false,
    };
  }

  const reviewedTracks = unique(assignment.canonicalTracks).filter((track) =>
    activeTrackNames.has(track),
  );
  const canonicalTracks =
    assignment.mode === "augment"
      ? unique([observedTrack, ...reviewedTracks])
      : reviewedTracks;

  return {
    assignment,
    observedTrack,
    canonicalTracks,
    applied: canonicalTracks.length > 0,
  };
}
