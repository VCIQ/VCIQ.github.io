import { companies } from "@/lib/catalog-data";
import { researchPeople } from "@/lib/people-data";
import { publishedTrackingResearchEntities } from "@/lib/published-tracking-entity-research";
import {
  technologyTopicDefinitions,
  technologyTopicsForCoreEntity,
} from "@/lib/technology-topics";
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

export const CORE_TECHNOLOGY_EXCLUDED_NAMES = [
  "AI agents",
  "具身智能",
  "智能体",
  "世界模型",
  "多模态",
  "数据中心",
  "DeepMind",
  "HuggingFace",
  "Project Panama",
  "Flash",
  "Harness",
] as const;

const excludedCoreTechnologyIdentityKeys = new Set(
  CORE_TECHNOLOGY_EXCLUDED_NAMES.map(normalizeResearchObjectName),
);

const coreTechnologyPublicNames = new Map(
  [
    ["Opus", "Claude Opus"],
    ["Sonnet", "Claude Sonnet"],
  ].map(([source, publicName]) => [normalizeResearchObjectName(source), publicName]),
);

/**
 * Core technologies are substantive public topic entities that are more
 * specific than the configured track taxonomy. Broad domains such as AI or
 * semiconductors remain in the track directory; concrete technologies and
 * technical systems are exposed here.
 */
function unique(values: Iterable<string>) {
  return [...new Set([...values].map((value) => value.trim()).filter(Boolean))];
}

/**
 * The public core directory is deliberately stricter than the provenance
 * registry. A tracked topic remains available on its detail route, but only a
 * classified entity with corroborating evidence (or explicit analyst/manual
 * curation) is promoted to the core technology layer.
 */
export const coreTechnologyEntities = publishedTrackingResearchEntities
  .filter((entity) => entity.entityType === "topic")
  .filter((entity) => {
    const identityKeys = [entity.name, ...entity.aliases]
      .map(normalizeResearchObjectName)
      .filter(Boolean);
    return !identityKeys.some(
      (key) =>
        trackIdentityKeys.has(key) || excludedCoreTechnologyIdentityKeys.has(key),
    );
  })
  .map((entity) => ({
    entity,
    topics: technologyTopicsForCoreEntity(entity),
    evidenceCount: entity.captureCount + entity.articleCount,
  }))
  .filter(({ entity, topics, evidenceCount }) =>
    topics.length > 0 &&
    (
      evidenceCount >= 2 ||
      entity.priority > 0 ||
      entity.researchThesis.trim().length > 0 ||
      entity.analystNotes.length > 0
    ),
  )
  .map(({ entity, topics }) => ({
    ...entity,
    name:
      coreTechnologyPublicNames.get(normalizeResearchObjectName(entity.name)) ??
      entity.name,
    // Do not expose inherited crawler tracks on the curated technology layer.
    // The topic taxonomy is the canonical source for a technology's parents.
    trackNames: unique(topics.flatMap((topic) => topic.trackNames)),
    trackSlugs: unique(
      topics.flatMap((topic) =>
        trackedSectors
          .filter((sector) => topic.trackNames.includes(sector.name))
          .map((sector) => sector.slug),
      ),
    ),
  }))
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
