import rawArticles from "@/public/data/articles.json";
import type { ChannelUpdateItem } from "@/lib/channel-updates";
import {
  contentRelevanceForItem,
  type ContentRelevanceStatus,
} from "@/lib/content-relevance";

export type SourceTrackProfileStatus =
  | "severe"
  | "moderate"
  | "normal"
  | "insufficient";

export type SourceTrackRelevanceStatus =
  | "bypass-strong-evidence"
  | "severe-downweight"
  | "moderate-downweight"
  | "normal"
  | "insufficient";

export type SourceTrackProfile = {
  key: string;
  source: string;
  track: string;
  status: SourceTrackProfileStatus;
  pairCount: number;
  sourceEventCount: number;
  sourceTrackCount: number;
  broadSource: boolean;
  topicBackedCount: number;
  crawlerUsableCount: number;
  partialEvidenceCount: number;
  weakEvidenceCount: number;
  primaryEvidenceCount: number;
  companyEvidenceCount: number;
  trackingTermEvidenceCount: number;
  directEvidenceCount: number;
  weakRate: number;
  directEvidenceRate: number;
  samples: string[];
};

export type SourceTrackRelevanceAssessment = {
  source: string;
  track: string;
  profileStatus: SourceTrackProfileStatus;
  status: SourceTrackRelevanceStatus;
  weight: number;
  reason: string;
};

type RawArticleEvidence = {
  id: string;
  sourceId?: string;
  sourceRole?: string;
  matchedTrackingTerms?: string[];
  companyMatch?: { confidence?: number };
  companyMatches?: Array<{ confidence?: number }>;
  source?: {
    name?: string;
    platform?: string;
    level?: string;
    sourceRole?: string;
  };
};

type RawArticlePayload = {
  articles: RawArticleEvidence[];
};

type PairAccumulator = {
  source: string;
  track: string;
  pairCount: number;
  topicBackedCount: number;
  crawlerUsableCount: number;
  partialEvidenceCount: number;
  weakEvidenceCount: number;
  primaryEvidenceCount: number;
  companyEvidenceCount: number;
  trackingTermEvidenceCount: number;
  directEvidenceCount: number;
  samples: string[];
};

const rawById = new Map(
  (rawArticles as RawArticlePayload).articles.map((article) => [article.id, article]),
);

function roundedRate(value: number, total: number) {
  if (!total) return 0;
  return Math.round((value / total) * 1000) / 1000;
}

export function sourceTrackProfileKey(source: string, track: string) {
  return `${source.trim()}\u0000${track.trim()}`;
}

export function sourceIdentityForItem(item: ChannelUpdateItem) {
  const raw = rawById.get(item.id);
  const sourceName = raw?.source?.name?.trim();
  if (sourceName) return sourceName;
  const platform = raw?.source?.platform?.trim();
  if (platform && !["官方网站", "专业媒体", "媒体报道"].includes(platform)) {
    return platform;
  }
  return item.source.trim() || raw?.sourceId || "未知来源";
}

export function rawSourceEvidenceForItem(item: ChannelUpdateItem) {
  const raw = rawById.get(item.id);
  const primaryEvidence = Boolean(
    raw &&
      (raw.sourceRole === "primary" ||
        raw.source?.sourceRole === "primary" ||
        ["官方披露", "原始材料", "监管文件"].includes(raw.source?.level ?? "")),
  );
  const companyEvidence = Boolean(
    raw &&
      ((raw.companyMatch?.confidence ?? 0) >= 0.9 ||
        (raw.companyMatches ?? []).some((match) => (match.confidence ?? 0) >= 0.9)),
  );
  const trackingTermEvidence = Boolean(raw?.matchedTrackingTerms?.length);
  return { primaryEvidence, companyEvidence, trackingTermEvidence };
}

export function classifySourceTrackProfile(input: {
  sourceEventCount: number;
  sourceTrackCount: number;
  pairCount: number;
  weakEvidenceCount: number;
  directEvidenceCount: number;
}): SourceTrackProfileStatus {
  const broadSource = input.sourceEventCount >= 8 && input.sourceTrackCount >= 3;
  if (!broadSource || input.pairCount < 4) return "insufficient";

  const weakRate = input.weakEvidenceCount / input.pairCount;
  const directEvidenceRate = input.directEvidenceCount / input.pairCount;
  if (
    input.pairCount >= 5 &&
    weakRate >= 0.7 &&
    directEvidenceRate < 0.3
  ) {
    return "severe";
  }
  if (weakRate >= 0.5 && directEvidenceRate < 0.5) {
    return "moderate";
  }
  return "normal";
}

export function buildSourceTrackRelevanceProfiles(items: ChannelUpdateItem[]) {
  const pairs = new Map<string, PairAccumulator>();
  const sourceEventCounts = new Map<string, number>();
  const sourceTracks = new Map<string, Set<string>>();

  for (const item of items) {
    const source = sourceIdentityForItem(item);
    const track = item.track?.trim() || "未归类";
    const key = sourceTrackProfileKey(source, track);
    const content = contentRelevanceForItem(item);
    const rawEvidence = rawSourceEvidenceForItem(item);
    const topicBacked = (item.topicSlugs?.length ?? 0) > 0;
    const crawlerUsable = content.status === "usable";
    const directEvidence =
      topicBacked ||
      crawlerUsable ||
      rawEvidence.primaryEvidence ||
      rawEvidence.companyEvidence;

    const pair = pairs.get(key) ?? {
      source,
      track,
      pairCount: 0,
      topicBackedCount: 0,
      crawlerUsableCount: 0,
      partialEvidenceCount: 0,
      weakEvidenceCount: 0,
      primaryEvidenceCount: 0,
      companyEvidenceCount: 0,
      trackingTermEvidenceCount: 0,
      directEvidenceCount: 0,
      samples: [],
    };
    pair.pairCount += 1;
    if (topicBacked) pair.topicBackedCount += 1;
    if (crawlerUsable) pair.crawlerUsableCount += 1;
    if (content.status === "partial-evidence") pair.partialEvidenceCount += 1;
    if (content.status === "weak-evidence") pair.weakEvidenceCount += 1;
    if (rawEvidence.primaryEvidence) pair.primaryEvidenceCount += 1;
    if (rawEvidence.companyEvidence) pair.companyEvidenceCount += 1;
    if (rawEvidence.trackingTermEvidence) pair.trackingTermEvidenceCount += 1;
    if (directEvidence) pair.directEvidenceCount += 1;
    if (pair.samples.length < 4) pair.samples.push(item.title);
    pairs.set(key, pair);

    sourceEventCounts.set(source, (sourceEventCounts.get(source) ?? 0) + 1);
    const tracks = sourceTracks.get(source) ?? new Set<string>();
    tracks.add(track);
    sourceTracks.set(source, tracks);
  }

  return new Map(
    [...pairs.entries()].map(([key, pair]) => {
      const sourceEventCount = sourceEventCounts.get(pair.source) ?? 0;
      const sourceTrackCount = sourceTracks.get(pair.source)?.size ?? 0;
      const broadSource = sourceEventCount >= 8 && sourceTrackCount >= 3;
      const status = classifySourceTrackProfile({
        sourceEventCount,
        sourceTrackCount,
        pairCount: pair.pairCount,
        weakEvidenceCount: pair.weakEvidenceCount,
        directEvidenceCount: pair.directEvidenceCount,
      });
      const profile: SourceTrackProfile = {
        key,
        ...pair,
        sourceEventCount,
        sourceTrackCount,
        broadSource,
        status,
        weakRate: roundedRate(pair.weakEvidenceCount, pair.pairCount),
        directEvidenceRate: roundedRate(pair.directEvidenceCount, pair.pairCount),
      };
      return [key, profile] as const;
    }),
  );
}

export function sourceTrackWeightForEvidence(input: {
  profileStatus: SourceTrackProfileStatus;
  contentStatus: ContentRelevanceStatus;
  priorityTopic: boolean;
  primaryEvidence: boolean;
  companyEvidence: boolean;
  canonicalReviewed?: boolean;
}): { status: SourceTrackRelevanceStatus; weight: number } {
  const bypass =
    input.canonicalReviewed === true ||
    input.priorityTopic ||
    input.contentStatus === "usable" ||
    input.primaryEvidence ||
    input.companyEvidence;
  if (bypass) return { status: "bypass-strong-evidence", weight: 1 };

  const eligibleForSourcePenalty = ["partial-evidence", "weak-evidence"].includes(
    input.contentStatus,
  );
  if (!eligibleForSourcePenalty) {
    return {
      status: input.profileStatus === "insufficient" ? "insufficient" : "normal",
      weight: 1,
    };
  }

  if (input.profileStatus === "severe") {
    return { status: "severe-downweight", weight: 0.5 };
  }
  if (input.profileStatus === "moderate") {
    return { status: "moderate-downweight", weight: 0.75 };
  }
  return {
    status: input.profileStatus === "insufficient" ? "insufficient" : "normal",
    weight: 1,
  };
}

export function sourceTrackRelevanceForItem(
  item: ChannelUpdateItem,
  profiles: Map<string, SourceTrackProfile>,
  options: { canonicalReviewed?: boolean } = {},
): SourceTrackRelevanceAssessment {
  const source = sourceIdentityForItem(item);
  const track = item.track?.trim() || "未归类";
  const profile = profiles.get(sourceTrackProfileKey(source, track));
  const profileStatus = profile?.status ?? "insufficient";
  const content = contentRelevanceForItem(item);
  const rawEvidence = rawSourceEvidenceForItem(item);
  const result = sourceTrackWeightForEvidence({
    profileStatus,
    contentStatus: content.status,
    priorityTopic: (item.topicSlugs?.length ?? 0) > 0,
    primaryEvidence: rawEvidence.primaryEvidence,
    companyEvidence: rawEvidence.companyEvidence,
    canonicalReviewed: options.canonicalReviewed,
  });

  let reason = "来源—赛道组合没有触发额外相关性降权。";
  if (result.status === "bypass-strong-evidence") {
    reason = "事件已有重点主题、crawler 可用、官方/原始材料、高置信公司或人工规范纠错等强证据，来源—赛道门槛不再处罚。";
  } else if (result.status === "severe-downweight") {
    reason = `宽信源“${source}”在“${track}”样本中弱证据占比较高；本事件缺少强证据，额外按 0.5 来源—赛道权重计入。`;
  } else if (result.status === "moderate-downweight") {
    reason = `宽信源“${source}”在“${track}”样本中精度混合；本事件缺少强证据，额外按 0.75 来源—赛道权重计入。`;
  } else if (result.status === "insufficient") {
    reason = "该来源—赛道组合样本不足或来源不够宽泛，不基于小样本自动处罚。";
  }

  return {
    source,
    track,
    profileStatus,
    status: result.status,
    weight: result.weight,
    reason,
  };
}
