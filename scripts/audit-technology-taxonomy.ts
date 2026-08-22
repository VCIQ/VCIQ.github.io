import rawArticles from "@/public/data/articles.json";
import { getChannelUpdateDirectory, type SourceEvidenceGrade } from "@/lib/channel-updates";
import { technologyTopicDefinitions } from "@/lib/technology-topics";
import { trackedSectors } from "@/lib/tracked-sectors";

type RawArticle = {
  id: string;
  title: string;
  sector: string;
  eventClusterId?: string;
  source: {
    name: string;
    url: string;
    evidenceGrade?: SourceEvidenceGrade;
  };
};

type RawArticlePayload = {
  generatedAt: string;
  articles: RawArticle[];
};

const gradeRank: Record<SourceEvidenceGrade, number> = {
  A: 0,
  B: 1,
  C: 2,
  D: 3,
};

function normalize(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function topicIsCompatibleWithTrack(topicSlug: string, trackName: string) {
  const topic = technologyTopicDefinitions.find((item) => item.slug === topicSlug);
  if (!topic) return false;
  const track = trackedSectors.find(
    (item) =>
      normalize(item.name) === normalize(trackName) ||
      (item.aliases ?? []).some((alias) => normalize(alias) === normalize(trackName)),
  );
  if (!track) return false;
  const trackNames = new Set(
    [track.name, ...(track.aliases ?? [])].map(normalize).filter(Boolean),
  );
  return topic.trackNames.some((name) => trackNames.has(normalize(name)));
}

const directory = getChannelUpdateDirectory("technology");
const items = directory.items.filter((item) => Boolean(item.track));
const topicSlugs = new Set(technologyTopicDefinitions.map((topic) => topic.slug));

const unknownTopicAssignments = items.flatMap((item) =>
  (item.topicSlugs ?? [])
    .filter((slug) => !topicSlugs.has(slug))
    .map((slug) => ({ id: item.id, title: item.title, slug })),
);

const trackTopicMismatches = items.flatMap((item) =>
  (item.topicSlugs ?? [])
    .filter((slug) => !topicIsCompatibleWithTrack(slug, item.track ?? ""))
    .map((slug) => ({
      id: item.id,
      title: item.title,
      track: item.track ?? "",
      topic: technologyTopicDefinitions.find((topic) => topic.slug === slug)?.name ?? slug,
    })),
);

const untagged = items.filter((item) => !(item.topicSlugs ?? []).length);
const heavilyMultiTagged = items.filter((item) => (item.topicSlugs ?? []).length >= 4);
const groupedEvents = items.filter((item) => (item.sourceCount ?? 1) > 1);
const invalidSourceCounts = items.filter(
  (item) => (item.sources?.length ?? 1) !== (item.sourceCount ?? 1),
);

const clusterIds = items.map((item) => item.eventClusterId).filter(Boolean) as string[];
const duplicateClusterIds = [...new Set(clusterIds.filter((id, index) => clusterIds.indexOf(id) !== index))];

const rawPayload = rawArticles as RawArticlePayload;
const rawClusters = new Map<string, RawArticle[]>();
for (const article of rawPayload.articles) {
  if (!article.eventClusterId) continue;
  const rows = rawClusters.get(article.eventClusterId) ?? [];
  rows.push(article);
  rawClusters.set(article.eventClusterId, rows);
}

const primarySourceViolations = items.flatMap((item) => {
  if (!item.eventClusterId || !item.sourceGrade) return [];
  const rawCluster = rawClusters.get(item.eventClusterId) ?? [];
  const grades = rawCluster
    .map((article) => article.source.evidenceGrade)
    .filter(Boolean) as SourceEvidenceGrade[];
  if (!grades.length) return [];
  const bestGrade = grades.sort((left, right) => gradeRank[left] - gradeRank[right])[0];
  if (gradeRank[item.sourceGrade] <= gradeRank[bestGrade]) return [];
  return [{
    id: item.id,
    title: item.title,
    clusterId: item.eventClusterId,
    chosenGrade: item.sourceGrade,
    bestGrade,
  }];
});

const topicStats = technologyTopicDefinitions.map((topic) => {
  const matchingItems = items.filter((item) => item.topicSlugs?.includes(topic.slug));
  const incompatible = matchingItems.filter(
    (item) => !topicIsCompatibleWithTrack(topic.slug, item.track ?? ""),
  );
  return {
    slug: topic.slug,
    name: topic.name,
    count: matchingItems.length,
    incompatibleTrackCount: incompatible.length,
  };
});

const sourceRowsBeforeAggregation = items.reduce(
  (total, item) => total + (item.sourceCount ?? 1),
  0,
);

const audit = {
  generatedAt: rawPayload.generatedAt,
  eventCount: items.length,
  taggedEventCount: items.length - untagged.length,
  untaggedEventCount: untagged.length,
  untaggedRate: items.length ? Number((untagged.length / items.length).toFixed(4)) : 0,
  heavilyMultiTaggedCount: heavilyMultiTagged.length,
  trackTopicMismatchCount: trackTopicMismatches.length,
  unknownTopicAssignmentCount: unknownTopicAssignments.length,
  groupedEventCount: groupedEvents.length,
  sourceRowsBeforeAggregation,
  collapsedSourceRows: Math.max(0, sourceRowsBeforeAggregation - items.length),
  duplicateClusterIdCount: duplicateClusterIds.length,
  invalidSourceCountCount: invalidSourceCounts.length,
  primarySourceViolationCount: primarySourceViolations.length,
  topics: topicStats,
};

console.log(`TECHNOLOGY_TAXONOMY_AUDIT=${JSON.stringify(audit)}`);

function printSamples<T>(label: string, rows: T[]) {
  if (!rows.length) return;
  console.log(`${label}=${JSON.stringify(rows.slice(0, 12))}`);
}

printSamples("TECHNOLOGY_TAXONOMY_MISMATCH_SAMPLES", trackTopicMismatches);
printSamples(
  "TECHNOLOGY_TAXONOMY_UNTAGGED_SAMPLES",
  untagged.map((item) => ({ id: item.id, title: item.title, track: item.track })),
);
printSamples(
  "TECHNOLOGY_TAXONOMY_MULTI_TAG_SAMPLES",
  heavilyMultiTagged.map((item) => ({
    id: item.id,
    title: item.title,
    track: item.track,
    topics: item.topicNames ?? [],
  })),
);
printSamples("TECHNOLOGY_TAXONOMY_PRIMARY_SOURCE_VIOLATIONS", primarySourceViolations);

const hardFailures = [
  technologyTopicDefinitions.length !== 20
    ? `expected 20 technology topics, got ${technologyTopicDefinitions.length}`
    : "",
  unknownTopicAssignments.length
    ? `${unknownTopicAssignments.length} unknown topic assignments`
    : "",
  duplicateClusterIds.length
    ? `${duplicateClusterIds.length} duplicate eventClusterId rows remain after aggregation`
    : "",
  invalidSourceCounts.length
    ? `${invalidSourceCounts.length} aggregated rows have inconsistent sourceCount`
    : "",
  primarySourceViolations.length
    ? `${primarySourceViolations.length} event clusters did not choose the strongest evidence grade`
    : "",
  trackTopicMismatches.length
    ? `${trackTopicMismatches.length} topic assignments conflict with the event track taxonomy`
    : "",
].filter(Boolean);

if (hardFailures.length) {
  for (const failure of hardFailures) {
    console.error(`TECHNOLOGY_TAXONOMY_AUDIT_ERROR: ${failure}`);
  }
  process.exitCode = 1;
}
