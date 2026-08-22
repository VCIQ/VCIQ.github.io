import type { ChannelUpdateDirectory, ChannelUpdateItem } from "@/lib/channel-updates";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import {
  buildTechnologyAnalysisPopulation,
  type TechnologyAnalysisEntry,
} from "@/lib/analysis-eligibility";
import { technologyTopicDefinitions } from "@/lib/technology-topics";
import { userTrackingConfig } from "@/lib/user-tracking";

export type MomentumDirection = "up" | "flat" | "down" | "new";

export type MomentumWindowComparison = {
  windowDays: number;
  currentWeightedEvents: number;
  previousWeightedEvents: number;
  deltaWeightedEvents: number;
  growthPct: number | null;
  direction: MomentumDirection;
};

export type TechnologyTrackMomentum = {
  name: string;
  sevenDayTrend: MomentumWindowComparison;
  thirtyDayMomentum: MomentumWindowComparison;
};

export type TechnologyTopicMomentum = {
  slug: string;
  name: string;
  sevenDayTrend: MomentumWindowComparison;
  thirtyDayMomentum: MomentumWindowComparison;
};

export type TechnologyAnalysisSnapshot = {
  asOf: string;
  population: {
    totalEvents: number;
    included: number;
    crossSector: number;
    downweighted: number;
    sectorExcluded: number;
    datedForTrend: number;
  };
  tracks: TechnologyTrackMomentum[];
  topics: TechnologyTopicMomentum[];
};

const DAY_MS = 24 * 60 * 60 * 1000;

function roundWeight(value: number) {
  return Math.round(value * 10) / 10;
}

function validDate(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function resolveAsOf(directory: ChannelUpdateDirectory) {
  const generated = validDate(directory.generatedAt);
  if (generated) return generated;

  const newest = directory.items
    .map((item) => validDate(item.sortAt))
    .filter((value): value is Date => Boolean(value))
    .sort((left, right) => right.getTime() - left.getTime())[0];
  return newest ?? new Date("1970-01-01T00:00:00.000Z");
}

function temporalWeight(item: ChannelUpdateItem) {
  if (item.datePrecision === "exact") return 1;
  if (item.datePrecision === "approximate") return 0.75;
  return 0;
}

function itemTimestamp(item: ChannelUpdateItem) {
  const parsed = validDate(item.sortAt);
  return parsed?.getTime() ?? 0;
}

function windowWeight(
  entries: TechnologyAnalysisEntry[],
  asOf: Date,
  startDaysAgo: number,
  endDaysAgo: number,
  weightForEntry: (entry: TechnologyAnalysisEntry) => number,
) {
  const upper = asOf.getTime() - endDaysAgo * DAY_MS;
  const lower = asOf.getTime() - startDaysAgo * DAY_MS;

  return entries.reduce((sum, entry) => {
    const timestamp = itemTimestamp(entry.item);
    if (!timestamp || timestamp <= lower || timestamp > upper) return sum;
    return sum + weightForEntry(entry) * temporalWeight(entry.item);
  }, 0);
}

function compareWindow(
  entries: TechnologyAnalysisEntry[],
  asOf: Date,
  days: number,
  weightForEntry: (entry: TechnologyAnalysisEntry) => number,
): MomentumWindowComparison {
  const current = windowWeight(entries, asOf, days, 0, weightForEntry);
  const previous = windowWeight(entries, asOf, days * 2, days, weightForEntry);
  const delta = current - previous;
  const growthPct =
    previous >= 0.5 ? Math.round((delta / previous) * 100) : current >= 0.75 ? null : 0;

  let direction: MomentumDirection = "flat";
  if (previous < 0.5 && current >= 0.75) {
    direction = "new";
  } else if (delta >= 1 && current >= previous * 1.2) {
    direction = "up";
  } else if (delta <= -1 && current <= previous * 0.8) {
    direction = "down";
  }

  return {
    windowDays: days,
    currentWeightedEvents: roundWeight(current),
    previousWeightedEvents: roundWeight(previous),
    deltaWeightedEvents: roundWeight(delta),
    growthPct,
    direction,
  };
}

function trackWeight(trackName: string) {
  return (entry: TechnologyAnalysisEntry) =>
    entry.analysisTracks.includes(trackName) ? entry.sectorWeight : 0;
}

function topicWeight(topicSlug: string) {
  return (entry: TechnologyAnalysisEntry) =>
    entry.analysisTopicSlugs.includes(topicSlug) ? entry.topicWeight : 0;
}

export function buildTechnologyAnalysisSnapshot(
  directory: ChannelUpdateDirectory = getChannelUpdateDirectory("technology"),
): TechnologyAnalysisSnapshot {
  const asOf = resolveAsOf(directory);
  const population = buildTechnologyAnalysisPopulation(directory.items);
  const activeTracks = userTrackingConfig.tracks.filter((track) => track.enabled);

  return {
    asOf: asOf.toISOString(),
    population: {
      totalEvents: population.length,
      included: population.filter((entry) => entry.status === "included").length,
      crossSector: population.filter((entry) => entry.status === "cross-sector").length,
      downweighted: population.filter((entry) => entry.status === "downweighted").length,
      sectorExcluded: population.filter((entry) => entry.status === "sector-excluded").length,
      datedForTrend: population.filter((entry) => temporalWeight(entry.item) > 0).length,
    },
    tracks: activeTracks.map((track) => ({
      name: track.name,
      sevenDayTrend: compareWindow(population, asOf, 7, trackWeight(track.name)),
      thirtyDayMomentum: compareWindow(population, asOf, 30, trackWeight(track.name)),
    })),
    topics: technologyTopicDefinitions.map((topic) => ({
      slug: topic.slug,
      name: topic.name,
      sevenDayTrend: compareWindow(population, asOf, 7, topicWeight(topic.slug)),
      thirtyDayMomentum: compareWindow(population, asOf, 30, topicWeight(topic.slug)),
    })),
  };
}
