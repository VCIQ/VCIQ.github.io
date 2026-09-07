import type { FavoriteInput, FavoriteItem } from "@/lib/favorites";
import type { HomepagePreferenceState } from "@/lib/homepage-preferences";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

function normalized(value: string | undefined) {
  return (value ?? "").normalize("NFKC").trim().toLocaleLowerCase("zh-CN");
}

function sourceHost(value: string | undefined) {
  if (!value) return "";
  try {
    return new URL(value).hostname.replace(/^www\./, "").toLocaleLowerCase("en-US");
  } catch {
    return "";
  }
}

function relatedSourceCount(item: LiveIntelligenceEvent) {
  return Math.max(
    item.relatedSources?.length ?? 0,
    Math.max(0, (item.duplicateCount ?? 1) - 1),
  );
}

export function homepageEventKey(item: LiveIntelligenceEvent) {
  return item.eventClusterId || item.id;
}

export function homepageFavoriteId(item: LiveIntelligenceEvent) {
  return `homepage-feed:event:${homepageEventKey(item)}`;
}

export function baseHomepageRecommendationScore(item: LiveIntelligenceEvent) {
  const quality =
    typeof item.qualityScore === "number"
      ? item.qualityScore
      : item.qualityStatus === "高可信"
        ? 92
        : item.qualityStatus === "可用"
          ? 74
          : item.qualityStatus === "低可信"
            ? 35
            : 65;
  const trackingMatches = Math.min(item.matchedTrackingTerms?.length ?? 0, 4);

  return (
    item.importance * 0.68 +
    quality * 0.18 +
    Math.min(relatedSourceCount(item), 5) * 2.2 +
    trackingMatches * 1.6 +
    (item.curated ? 3 : 0)
  );
}

function favoriteAffinity(item: LiveIntelligenceEvent, favorites: FavoriteItem[]) {
  if (!favorites.length) return { score: 0, sameSector: false, sameCompany: false, sameSource: false };
  const sector = normalized(item.sector);
  const company = normalized(item.company);
  const host = sourceHost(item.source.url);
  let sameSector = false;
  let sameCompany = false;
  let sameSource = false;

  for (const favorite of favorites) {
    if (
      sector &&
      favorite.sectors.some((candidate) => normalized(candidate) === sector)
    ) {
      sameSector = true;
    }
    if (company && normalized(favorite.company) === company) sameCompany = true;
    if (
      host &&
      favorite.sources.some((source) => sourceHost(source.url) === host)
    ) {
      sameSource = true;
    }
    if (sameSector && sameCompany && sameSource) break;
  }

  const exactSaved = favorites.some((favorite) => favorite.id === homepageFavoriteId(item));
  const score = Math.min(
    18,
    (exactSaved ? 4 : 0) +
      (sameSector ? 7 : 0) +
      (sameCompany ? 4 : 0) +
      (sameSource ? 2 : 0),
  );
  return { score, sameSector, sameCompany, sameSource };
}

export function personalizedHomepageRecommendationScore(
  item: LiveIntelligenceEvent,
  preferences: HomepagePreferenceState,
  favorites: FavoriteItem[],
) {
  const followed = preferences.followedSectors.some(
    (sector) => normalized(sector) === normalized(item.sector),
  );
  const dislikeCount = preferences.sectorDislikes[item.sector] ?? 0;
  const affinity = favoriteAffinity(item, favorites);
  return (
    baseHomepageRecommendationScore(item) +
    (followed ? 14 : 0) +
    affinity.score -
    Math.min(12, dislikeCount * 3)
  );
}

export function isHomepageEventDismissed(
  item: LiveIntelligenceEvent,
  preferences: HomepagePreferenceState,
) {
  const key = homepageEventKey(item);
  return preferences.dismissedEventIds.includes(key);
}

export function isHomepageSectorFollowed(
  item: LiveIntelligenceEvent,
  preferences: HomepagePreferenceState,
) {
  const sector = normalized(item.sector);
  return preferences.followedSectors.some((candidate) => normalized(candidate) === sector);
}

export function matchesHomepageFollowChannel(
  item: LiveIntelligenceEvent,
  preferences: HomepagePreferenceState,
) {
  return Boolean(
    item.curated ||
      item.matchedTrackingTerms?.length ||
      isHomepageSectorFollowed(item, preferences),
  );
}

function favoriteChannelMeta(item: LiveIntelligenceEvent): Pick<FavoriteInput, "channel" | "channelLabel"> {
  if (item.type === "人物观点") {
    return { channel: "people", channelLabel: "核心人物" };
  }
  if (
    ["融资", "产业投资", "商业进展", "公司动态", "并购", "财报", "IPO"].includes(item.type)
  ) {
    return { channel: "companies", channelLabel: "核心公司" };
  }
  return { channel: "technology", channelLabel: "核心赛道" };
}

export function homepageFeedFavoriteInput(item: LiveIntelligenceEvent): FavoriteInput {
  const channel = favoriteChannelMeta(item);
  const relatedSources = item.relatedSources ?? [];
  const sources = [
    { name: item.source.name, url: item.source.url, level: item.source.level },
    ...relatedSources.map((source) => ({
      name: source.name,
      url: source.url,
      level: source.level,
    })),
  ];

  return {
    id: homepageFavoriteId(item),
    href: item.source.url,
    title: item.title,
    summary: item.summary,
    ...channel,
    keywords: [
      item.type,
      item.region,
      item.sector,
      item.company,
      ...(item.matchedTrackingTerms ?? []),
    ].filter(Boolean) as string[],
    sectors: item.sector ? [item.sector] : [],
    sources,
    region: item.region,
    company: item.company,
    publishedAt: item.publishedAt.slice(0, 10),
    importance: item.importance,
    eventType: item.type,
  };
}

export function homepageRecommendationReasons(
  item: LiveIntelligenceEvent,
  preferences: HomepagePreferenceState,
  favorites: FavoriteItem[],
) {
  const reasons: string[] = [];
  const affinity = favoriteAffinity(item, favorites);

  if (isHomepageSectorFollowed(item, preferences)) {
    reasons.push(`你关注「${item.sector}」`);
  }
  if (affinity.sameSector || affinity.sameCompany) {
    reasons.push(
      affinity.sameCompany
        ? `你稍后读过与「${item.company || item.sector}」相关的内容`
        : `你稍后读过「${item.sector}」相关内容`,
    );
  }
  if (item.matchedTrackingTerms?.length) {
    reasons.push(`命中关注词：${item.matchedTrackingTerms.slice(0, 2).join("、")}`);
  }
  if (item.importance >= 90) reasons.push(`重要度 ${item.importance}`);
  if (item.qualityStatus === "高可信" || (item.qualityScore ?? 0) >= 85) {
    reasons.push("来源可信度较高");
  }
  const relatedCount = relatedSourceCount(item);
  if (relatedCount > 0) reasons.push(`${relatedCount + 1} 个来源相互印证`);
  if (item.curated) reasons.push("人工精选事件");
  if (!reasons.length) reasons.push("综合重要度、可信度与来源信号排序");

  return reasons.slice(0, 4);
}
