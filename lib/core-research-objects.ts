import { companies } from "@/lib/catalog-data";
import { researchPeople } from "@/lib/people-data";
import { publishedTrackingResearchEntities } from "@/lib/published-tracking-entity-research";
import { technologyTopicDefinitions } from "@/lib/technology-topics";
import { trackedSectors } from "@/lib/tracked-sectors";

function normalizeResearchObjectName(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

const trackIdentityKeys = new Set(
  trackedSectors.flatMap((sector) =>
    [sector.name, ...(sector.aliases ?? [])]
      .map(normalizeResearchObjectName)
      .filter(Boolean),
  ),
);

/**
 * Core technologies are substantive public topic entities that are more
 * specific than the configured track taxonomy. Broad domains such as AI or
 * semiconductors remain in the track directory; concrete technologies and
 * technical systems are exposed here.
 */
export const coreTechnologyEntities = publishedTrackingResearchEntities
  .filter((entity) => entity.entityType === "topic")
  .filter(
    (entity) =>
      ![entity.name, ...entity.aliases]
        .map(normalizeResearchObjectName)
        .some((key) => key && trackIdentityKeys.has(key)),
  )
  .sort(
    (left, right) =>
      right.priority - left.priority ||
      right.captureCount + right.articleCount -
        (left.captureCount + left.articleCount) ||
      right.lastActivityAt.localeCompare(left.lastActivityAt) ||
      left.name.localeCompare(right.name, "zh-CN"),
  );

export const coreResearchObjectStats = {
  technologyCount: coreTechnologyEntities.length,
  topicCount: technologyTopicDefinitions.length,
  trackCount: trackedSectors.length,
  personCount: researchPeople.length,
  companyCount: companies.length,
};
