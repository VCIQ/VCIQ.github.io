import type {
  ChannelUpdateItem,
  SourceEvidenceGrade,
} from "./channel-updates";

export const ALL_CHANNEL_UPDATE_KEYWORDS = "全部";
export const ALL_CHANNEL_UPDATE_CLASSIFICATIONS = "全部分类";
export const ALL_CHANNEL_UPDATE_TRACKS = "全部赛道";
export const ALL_CHANNEL_UPDATE_TOPICS = "全部主题";
export const ALL_CHANNEL_UPDATE_REGIONS = "全部地区";
export const ALL_CHANNEL_UPDATE_EVIDENCE = "全部等级";

export type ChannelUpdateSortOrder = "newest" | "oldest";

export type ChannelUpdateKeywordOption = {
  keyword: string;
  count: number;
};

function normalizeKeyword(value: string) {
  return value.trim().toLocaleLowerCase("zh-CN");
}

function snapshotDate(generatedAt: string) {
  const value = generatedAt.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/u.test(value) ? value : "";
}

export function countChannelUpdatesForSnapshotDay(
  items: ChannelUpdateItem[],
  generatedAt: string,
) {
  const date = snapshotDate(generatedAt);
  if (!date) return 0;

  return items.filter(
    (item) =>
      item.datePrecision !== "undated" &&
      item.sortAt.slice(0, 10) === date,
  ).length;
}

export function countChannelUpdatesFirstSeenForSnapshotDay(
  items: ChannelUpdateItem[],
  generatedAt: string,
) {
  const date = snapshotDate(generatedAt);
  if (!date) return 0;

  return items.filter(
    (item) =>
      Boolean(item.firstSeenAt) &&
      item.firstSeenEstimated !== true &&
      item.firstSeenAt?.slice(0, 10) === date,
  ).length;
}

function collectOptions(valuesByItem: string[][]): ChannelUpdateKeywordOption[] {
  const counts = new Map<string, { keyword: string; count: number }>();

  for (const values of valuesByItem) {
    const seenForItem = new Set<string>();
    for (const rawKeyword of values) {
      const keyword = rawKeyword.trim();
      const normalized = normalizeKeyword(keyword);
      if (!normalized || seenForItem.has(normalized)) continue;
      seenForItem.add(normalized);
      const current = counts.get(normalized);
      counts.set(normalized, {
        keyword: current?.keyword ?? keyword,
        count: (current?.count ?? 0) + 1,
      });
    }
  }

  return [...counts.values()].sort(
    (left, right) =>
      right.count - left.count || left.keyword.localeCompare(right.keyword, "zh-CN"),
  );
}

export function collectChannelUpdateKeywords(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  return collectOptions(items.map((item) => item.keywords));
}

export function collectChannelUpdateClassifications(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  return collectOptions(items.map((item) => item.classifications ?? []));
}

export function collectChannelUpdateTracks(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  return collectOptions(items.map((item) => (item.track ? [item.track] : [])));
}

export function collectChannelUpdateTopics(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  return collectOptions(items.map((item) => item.topicNames ?? []));
}

export function collectChannelUpdateRegions(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  return collectOptions(items.map((item) => (item.region ? [item.region] : [])));
}

export function collectChannelUpdateEvidenceGrades(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  const options = collectOptions(
    items.map((item) => (item.sourceGrade ? [item.sourceGrade] : [])),
  );
  const order: SourceEvidenceGrade[] = ["A", "B", "C", "D"];
  return options.sort(
    (left, right) =>
      order.indexOf(left.keyword as SourceEvidenceGrade) -
      order.indexOf(right.keyword as SourceEvidenceGrade),
  );
}

export function filterAndSortChannelUpdates({
  items,
  keyword,
  classification = ALL_CHANNEL_UPDATE_CLASSIFICATIONS,
  track = ALL_CHANNEL_UPDATE_TRACKS,
  topic = ALL_CHANNEL_UPDATE_TOPICS,
  region = ALL_CHANNEL_UPDATE_REGIONS,
  evidence = ALL_CHANNEL_UPDATE_EVIDENCE,
  sortOrder,
}: {
  items: ChannelUpdateItem[];
  keyword: string;
  classification?: string;
  track?: string;
  topic?: string;
  region?: string;
  evidence?: string;
  sortOrder: ChannelUpdateSortOrder;
}) {
  const normalizedKeyword = normalizeKeyword(keyword);
  const normalizedClassification = normalizeKeyword(classification);
  const normalizedTrack = normalizeKeyword(track);
  const normalizedTopic = normalizeKeyword(topic);
  const normalizedRegion = normalizeKeyword(region);
  const filtered = items.filter((item) => {
    const keywordMatches =
      keyword === ALL_CHANNEL_UPDATE_KEYWORDS ||
      item.keywords.some(
        (itemKeyword) => normalizeKeyword(itemKeyword) === normalizedKeyword,
      );
    const classificationMatches =
      classification === ALL_CHANNEL_UPDATE_CLASSIFICATIONS ||
      (item.classifications ?? []).some(
        (itemClassification) =>
          normalizeKeyword(itemClassification) === normalizedClassification,
      );
    const trackMatches =
      track === ALL_CHANNEL_UPDATE_TRACKS ||
      (item.track ? normalizeKeyword(item.track) === normalizedTrack : false);
    const topicMatches =
      topic === ALL_CHANNEL_UPDATE_TOPICS ||
      (item.topicNames ?? []).some(
        (itemTopic) => normalizeKeyword(itemTopic) === normalizedTopic,
      );
    const regionMatches =
      region === ALL_CHANNEL_UPDATE_REGIONS ||
      (item.region ? normalizeKeyword(item.region) === normalizedRegion : false);
    const evidenceMatches =
      evidence === ALL_CHANNEL_UPDATE_EVIDENCE || item.sourceGrade === evidence;

    return (
      keywordMatches &&
      classificationMatches &&
      trackMatches &&
      topicMatches &&
      regionMatches &&
      evidenceMatches
    );
  });

  return filtered.sort((left, right) => {
    const dateComparison =
      sortOrder === "newest"
        ? right.sortAt.localeCompare(left.sortAt) || right.date.localeCompare(left.date)
        : left.sortAt.localeCompare(right.sortAt) || left.date.localeCompare(right.date);
    return dateComparison || left.title.localeCompare(right.title, "zh-CN");
  });
}
