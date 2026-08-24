import type { FavoriteChannel, FavoriteInput } from "@/lib/favorites";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

type FavoriteChannelMeta = {
  channel: FavoriteChannel;
  channelLabel: string;
};

function channelForEvent(item: LiveIntelligenceEvent): FavoriteChannelMeta {
  if (item.type === "人物观点") {
    return { channel: "people", channelLabel: "核心人物" };
  }
  if (["政策", "监管文件"].includes(item.type)) {
    return { channel: "reports", channelLabel: "研究材料" };
  }
  if (["论文", "技术突破", "产品发布"].includes(item.type)) {
    return { channel: "technology", channelLabel: "核心技术" };
  }
  return { channel: "companies", channelLabel: "核心公司" };
}

export function dailyBriefEventKey(item: LiveIntelligenceEvent) {
  return item.eventClusterId || item.id;
}

export function dailyBriefPermalink(item: LiveIntelligenceEvent) {
  return `/?event=${encodeURIComponent(dailyBriefEventKey(item))}#daily-brief`;
}

export function dailyBriefFavoriteInput(item: LiveIntelligenceEvent): FavoriteInput {
  const channel = channelForEvent(item);
  const sources = [
    {
      name: item.source.name,
      url: item.source.url,
      level: item.source.level,
    },
    ...(item.relatedSources ?? []).map((source) => ({
      name: source.name,
      url: source.url,
      level: source.level,
    })),
  ];

  return {
    id: `daily-brief:event:${dailyBriefEventKey(item)}`,
    href: dailyBriefPermalink(item),
    title: item.title,
    summary: item.summary,
    ...channel,
    keywords: [
      item.type,
      item.region,
      item.sector,
      item.company,
      ...(item.mentionedCompanies ?? []),
      ...(item.mentionedPeople ?? []),
      ...(item.matchedTrackingTerms ?? []),
    ].filter(Boolean),
    sectors: [item.sector],
    sources,
    region: item.region,
    company: item.company || undefined,
    publishedAt: item.publishedAt.slice(0, 10),
    importance: item.importance,
    eventType: item.type,
  };
}

export function dailyBriefTrackingHref(item: LiveIntelligenceEvent) {
  return buildTrackingCaptureLink({
    url: item.source.url,
    title: item.title,
    summary: item.summary,
    keywords: [
      item.type,
      item.region,
      item.sector,
      item.company,
      ...(item.matchedTrackingTerms ?? []),
    ].filter(Boolean).slice(0, 8),
    source: `${item.source.level} · ${item.source.name}`,
    channel: "homepage-daily-brief",
  });
}
