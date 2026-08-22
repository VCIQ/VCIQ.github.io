import rawArticles from "@/public/data/articles.json";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import { contentRelevanceForItem } from "@/lib/content-relevance";

type RawArticle = {
  id: string;
  sourceId?: string;
  qualityStatus?: string;
  qualitySignals?: string[];
  sourceRole?: string;
  companyMatch?: { confidence?: number };
  companyMatches?: Array<{ confidence?: number }>;
  matchedTrackingTerms?: string[];
  source?: {
    name?: string;
    platform?: string;
    level?: string;
    sourceRole?: string;
  };
};

type RawArticlePayload = {
  articles: RawArticle[];
};

type PairStats = {
  source: string;
  track: string;
  count: number;
  topicBacked: number;
  crawlerUsable: number;
  partialEvidence: number;
  weakEvidence: number;
  primaryEvidence: number;
  companyEvidence: number;
  trackingTermEvidence: number;
  samples: string[];
};

const rawById = new Map(
  (rawArticles as RawArticlePayload).articles.map((article) => [article.id, article]),
);
const directory = getChannelUpdateDirectory("technology");

function sourceIdentity(itemId: string, fallback: string) {
  const raw = rawById.get(itemId);
  const sourceName = raw?.source?.name?.trim();
  if (sourceName) return sourceName;
  const platform = raw?.source?.platform?.trim();
  if (platform && platform !== "官方网站" && platform !== "专业媒体") return platform;
  return fallback.trim() || raw?.sourceId || "未知来源";
}

function hasPrimaryEvidence(raw: RawArticle | undefined) {
  if (!raw) return false;
  if (raw.sourceRole === "primary" || raw.source?.sourceRole === "primary") return true;
  return ["官方披露", "原始材料", "监管文件"].includes(raw.source?.level ?? "");
}

function hasCompanyEvidence(raw: RawArticle | undefined) {
  if (!raw) return false;
  if ((raw.companyMatch?.confidence ?? 0) >= 0.9) return true;
  return (raw.companyMatches ?? []).some((match) => (match.confidence ?? 0) >= 0.9);
}

const pairs = new Map<string, PairStats>();
const tracksBySource = new Map<string, Set<string>>();
const totalBySource = new Map<string, number>();

for (const item of directory.items) {
  const track = item.track?.trim() || "未归类";
  const source = sourceIdentity(item.id, item.source);
  const raw = rawById.get(item.id);
  const relevance = contentRelevanceForItem(item);
  const key = `${source}\u0000${track}`;
  const stats = pairs.get(key) ?? {
    source,
    track,
    count: 0,
    topicBacked: 0,
    crawlerUsable: 0,
    partialEvidence: 0,
    weakEvidence: 0,
    primaryEvidence: 0,
    companyEvidence: 0,
    trackingTermEvidence: 0,
    samples: [],
  };

  stats.count += 1;
  if ((item.topicSlugs?.length ?? 0) > 0) stats.topicBacked += 1;
  if (relevance.status === "usable") stats.crawlerUsable += 1;
  if (relevance.status === "partial-evidence") stats.partialEvidence += 1;
  if (relevance.status === "weak-evidence") stats.weakEvidence += 1;
  if (hasPrimaryEvidence(raw)) stats.primaryEvidence += 1;
  if (hasCompanyEvidence(raw)) stats.companyEvidence += 1;
  if ((raw?.matchedTrackingTerms?.length ?? 0) > 0) stats.trackingTermEvidence += 1;
  if (stats.samples.length < 4) stats.samples.push(item.title);
  pairs.set(key, stats);

  const tracks = tracksBySource.get(source) ?? new Set<string>();
  tracks.add(track);
  tracksBySource.set(source, tracks);
  totalBySource.set(source, (totalBySource.get(source) ?? 0) + 1);
}

function roundedRate(value: number, total: number) {
  if (!total) return 0;
  return Math.round((value / total) * 1000) / 1000;
}

const pairRows = [...pairs.values()].map((stats) => {
  const directEvidence = Math.min(
    stats.count,
    stats.topicBacked + stats.crawlerUsable + stats.primaryEvidence + stats.companyEvidence,
  );
  const sourceTrackCount = tracksBySource.get(stats.source)?.size ?? 0;
  const sourceEventCount = totalBySource.get(stats.source) ?? 0;
  const broadSource = sourceEventCount >= 8 && sourceTrackCount >= 3;
  const weakRate = roundedRate(stats.weakEvidence, stats.count);
  const directEvidenceRate = roundedRate(directEvidence, stats.count);
  const severeCandidate =
    broadSource && stats.count >= 5 && weakRate >= 0.7 && directEvidenceRate < 0.3;
  const moderateCandidate =
    !severeCandidate &&
    broadSource &&
    stats.count >= 4 &&
    weakRate >= 0.5 &&
    directEvidenceRate < 0.5;

  return {
    ...stats,
    sourceEventCount,
    sourceTrackCount,
    broadSource,
    weakRate,
    directEvidenceRate,
    severeCandidate,
    moderateCandidate,
  };
});

const severe = pairRows
  .filter((row) => row.severeCandidate)
  .sort((a, b) => b.weakEvidence - a.weakEvidence || b.count - a.count);
const moderate = pairRows
  .filter((row) => row.moderateCandidate)
  .sort((a, b) => b.weakEvidence - a.weakEvidence || b.count - a.count);
const broadSources = [...tracksBySource.entries()]
  .map(([source, tracks]) => ({
    source,
    eventCount: totalBySource.get(source) ?? 0,
    trackCount: tracks.size,
  }))
  .filter((row) => row.eventCount >= 8 && row.trackCount >= 3)
  .sort((a, b) => b.eventCount - a.eventCount || b.trackCount - a.trackCount);

const audit = {
  eventCount: directory.items.length,
  sourceCount: totalBySource.size,
  sourceTrackPairCount: pairRows.length,
  broadSourceCount: broadSources.length,
  severeCandidatePairCount: severe.length,
  moderateCandidatePairCount: moderate.length,
  severeCandidateEventCount: severe.reduce((sum, row) => sum + row.count, 0),
  moderateCandidateEventCount: moderate.reduce((sum, row) => sum + row.count, 0),
};

console.log(`SOURCE_TRACK_RELEVANCE_AUDIT=${JSON.stringify(audit)}`);
console.log(
  `SOURCE_TRACK_RELEVANCE_BROAD_SOURCES=${JSON.stringify(broadSources.slice(0, 30))}`,
);
console.log(
  `SOURCE_TRACK_RELEVANCE_SEVERE=${JSON.stringify(severe.slice(0, 30))}`,
);
console.log(
  `SOURCE_TRACK_RELEVANCE_MODERATE=${JSON.stringify(moderate.slice(0, 30))}`,
);

if (severe.length) {
  console.warn(
    `SOURCE_TRACK_RELEVANCE_WARNING: ${severe.length} broad-source × track pairs have >=70% weak evidence and <30% direct evidence; inspect before allowing full source-track weight`,
  );
}
if (moderate.length) {
  console.warn(
    `SOURCE_TRACK_RELEVANCE_NOTICE: ${moderate.length} additional source-track pairs have mixed topical precision and may merit conservative weighting`,
  );
}
