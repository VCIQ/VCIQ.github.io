import { splitCompoundTrackingEntityName } from "@/lib/tracking-entity-integrity";
import type { UserTrackingConfig } from "@/lib/user-tracking";

export type TrackingCompoundInventoryEntityType = "company" | "person";

export type TrackingCompoundInventoryOccurrence = {
  trackSlug: string;
  trackName: string;
  entityType: TrackingCompoundInventoryEntityType;
  value: string;
  parts: string[];
};

export type TrackingCompoundInventoryUniqueValue = {
  entityType: TrackingCompoundInventoryEntityType;
  value: string;
  parts: string[];
  occurrenceCount: number;
  trackSlugs: string[];
  trackNames: string[];
};

export type TrackingCompoundInventoryReport = {
  mode: "read-only-inventory";
  occurrenceCount: number;
  uniqueValueCount: number;
  personOccurrenceCount: number;
  companyOccurrenceCount: number;
  affectedTrackCount: number;
  occurrences: TrackingCompoundInventoryOccurrence[];
  uniqueValues: TrackingCompoundInventoryUniqueValue[];
};

function normalizedIdentity(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .toLocaleLowerCase("zh-CN");
}

export function inventoryCompoundTrackingEntities(
  config: UserTrackingConfig,
): TrackingCompoundInventoryReport {
  const occurrences: TrackingCompoundInventoryOccurrence[] = [];

  for (const track of config.tracks) {
    const fields = [
      { values: track.people, entityType: "person" as const },
      { values: track.sampleCompanies, entityType: "company" as const },
    ];

    for (const { values, entityType } of fields) {
      for (const value of values) {
        const parts = splitCompoundTrackingEntityName(value);
        if (parts.length < 2) continue;
        occurrences.push({
          trackSlug: track.slug,
          trackName: track.name,
          entityType,
          value,
          parts,
        });
      }
    }
  }

  occurrences.sort(
    (left, right) =>
      left.entityType.localeCompare(right.entityType) ||
      left.value.localeCompare(right.value, "zh-CN") ||
      left.trackSlug.localeCompare(right.trackSlug),
  );

  const grouped = new Map<
    string,
    {
      entityType: TrackingCompoundInventoryEntityType;
      value: string;
      parts: string[];
      trackSlugs: Set<string>;
      trackNames: Set<string>;
      occurrenceCount: number;
    }
  >();

  for (const occurrence of occurrences) {
    const key = `${occurrence.entityType}:${normalizedIdentity(occurrence.value)}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.occurrenceCount += 1;
      existing.trackSlugs.add(occurrence.trackSlug);
      existing.trackNames.add(occurrence.trackName);
      continue;
    }
    grouped.set(key, {
      entityType: occurrence.entityType,
      value: occurrence.value,
      parts: [...occurrence.parts],
      trackSlugs: new Set([occurrence.trackSlug]),
      trackNames: new Set([occurrence.trackName]),
      occurrenceCount: 1,
    });
  }

  const uniqueValues: TrackingCompoundInventoryUniqueValue[] = [...grouped.values()]
    .map((row) => ({
      entityType: row.entityType,
      value: row.value,
      parts: row.parts,
      occurrenceCount: row.occurrenceCount,
      trackSlugs: [...row.trackSlugs].sort(),
      trackNames: [...row.trackNames].sort((left, right) => left.localeCompare(right, "zh-CN")),
    }))
    .sort(
      (left, right) =>
        left.entityType.localeCompare(right.entityType) ||
        left.value.localeCompare(right.value, "zh-CN"),
    );

  return {
    mode: "read-only-inventory",
    occurrenceCount: occurrences.length,
    uniqueValueCount: uniqueValues.length,
    personOccurrenceCount: occurrences.filter((row) => row.entityType === "person").length,
    companyOccurrenceCount: occurrences.filter((row) => row.entityType === "company").length,
    affectedTrackCount: new Set(occurrences.map((row) => row.trackSlug)).size,
    occurrences,
    uniqueValues,
  };
}
