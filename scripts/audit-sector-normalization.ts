import rawArticles from "@/public/data/articles.json";
import rawCanonicalAssignments from "@/config/canonical_sector_assignments.json";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import { userTrackingConfig } from "@/lib/user-tracking";

type RawArticle = {
  id: string;
  title: string;
  sector: string;
};

type RawArticlePayload = {
  articles: RawArticle[];
};

type CanonicalAssignmentPayload = {
  assignments: Array<{
    id: string;
    expectedObservedTrack: string;
    canonicalTracks: string[];
  }>;
};

function normalize(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

const activeTracks = userTrackingConfig.tracks.filter((track) => track.enabled);
const canonicalNameByKey = new Map(
  activeTracks.map((track) => [normalize(track.name), track.name] as const),
);
const rawById = new Map(
  (rawArticles as RawArticlePayload).articles.map((article) => [article.id, article]),
);
const channelItems = getChannelUpdateDirectory("technology").items.filter(
  (item) => Boolean(item.track),
);

const canonicalNameOverrideViolations = channelItems.flatMap((item) => {
  const raw = rawById.get(item.id);
  if (!raw) return [];
  const canonicalRawTrack = canonicalNameByKey.get(normalize(raw.sector));
  if (!canonicalRawTrack || canonicalRawTrack === item.track) return [];
  return [
    {
      id: item.id,
      title: item.title,
      rawSector: raw.sector,
      expectedCanonicalTrack: canonicalRawTrack,
      channelTrack: item.track,
    },
  ];
});

const registryCompensatingForNormalization = (
  rawCanonicalAssignments as CanonicalAssignmentPayload
).assignments.flatMap((assignment) => {
  const raw = rawById.get(assignment.id);
  if (!raw) return [];
  const canonicalRawTrack = canonicalNameByKey.get(normalize(raw.sector));
  if (!canonicalRawTrack || canonicalRawTrack === assignment.expectedObservedTrack) {
    return [];
  }
  return [
    {
      id: assignment.id,
      title: raw.title,
      rawSector: raw.sector,
      expectedObservedTrack: assignment.expectedObservedTrack,
      canonicalTargets: assignment.canonicalTracks,
    },
  ];
});

const rawCanonicalTrackCount = [...rawById.values()].filter((article) =>
  canonicalNameByKey.has(normalize(article.sector)),
).length;

const audit = {
  rawArticleCount: rawById.size,
  technologyChannelEventCount: channelItems.length,
  activeTrackCount: activeTracks.length,
  rawCanonicalTrackCount,
  canonicalNameOverrideViolationCount: canonicalNameOverrideViolations.length,
  canonicalRegistryNormalizationCompensationCount:
    registryCompensatingForNormalization.length,
};

console.log(`SECTOR_NORMALIZATION_AUDIT=${JSON.stringify(audit)}`);

if (canonicalNameOverrideViolations.length) {
  console.warn(
    `SECTOR_NORMALIZATION_WARNING: ${canonicalNameOverrideViolations.length} events already carry an active canonical raw sector but are rewritten to another channel track`,
  );
  console.log(
    `SECTOR_NORMALIZATION_OVERRIDE_SAMPLES=${JSON.stringify(canonicalNameOverrideViolations.slice(0, 30))}`,
  );
}

if (registryCompensatingForNormalization.length) {
  console.warn(
    `SECTOR_NORMALIZATION_WARNING: ${registryCompensatingForNormalization.length} reviewed canonical assignments appear to compensate for downstream sector normalization instead of raw-sector errors`,
  );
  console.log(
    `SECTOR_NORMALIZATION_REGISTRY_COMPENSATION=${JSON.stringify(registryCompensatingForNormalization.slice(0, 30))}`,
  );
}

// Baseline mode for the first diagnostic PR. After the resolver is fixed this
// audit becomes a hard gate: an explicit active canonical raw sector must never
// be overwritten by a dynamic alias.
