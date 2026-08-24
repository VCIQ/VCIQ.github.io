"use client";

import { ArrowUpRight, Bookmark, BookmarkPlus, Share2 } from "lucide-react";
import { useFavorite } from "@/components/use-favorites";
import {
  toggleFavorite,
  type FavoriteChannel,
  type FavoriteInput,
} from "@/lib/favorites";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

const SHARE_REQUEST_EVENT = "vciq:favorite-share-request";

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

function shareDailyBriefEvent(item: LiveIntelligenceEvent) {
  const relative = dailyBriefPermalink(item);
  const url = new URL(relative, window.location.origin).href;
  window.dispatchEvent(
    new CustomEvent(SHARE_REQUEST_EVENT, {
      detail: {
        title: item.title,
        summary: item.summary,
        url,
      },
    }),
  );
}

export function DailyBriefActions({
  item,
  className,
}: {
  item: LiveIntelligenceEvent;
  className?: string;
}) {
  const favorite = dailyBriefFavoriteInput(item);
  const saved = useFavorite(favorite.id);

  return (
    <div className={className} aria-label={`快速操作：${item.title}`}>
      <button
        type="button"
        data-saved={saved ? "true" : "false"}
        aria-pressed={saved}
        aria-label={saved ? `取消收藏：${item.title}` : `收藏事件：${item.title}`}
        title={saved ? "取消收藏" : "收藏这条独立事件"}
        onClick={() => toggleFavorite(favorite)}
      >
        <Bookmark size={14} fill={saved ? "currentColor" : "none"} />
      </button>
      <a
        href={dailyBriefTrackingHref(item)}
        target="_blank"
        rel="noreferrer"
        aria-label={`加入追踪：${item.title}`}
        title="把事件及关联对象加入追踪"
      >
        <BookmarkPlus size={14} />
      </a>
      <button
        type="button"
        aria-label={`分享事件：${item.title}`}
        title="分享这条 VCIQ 事件链接"
        onClick={() => shareDailyBriefEvent(item)}
      >
        <Share2 size={14} />
      </button>
      <a
        href={item.source.url}
        target="_blank"
        rel="noreferrer"
        aria-label={`打开原始信源：${item.title}`}
        title={`打开原始信源 · ${item.source.name}`}
      >
        <ArrowUpRight size={14} />
      </a>
    </div>
  );
}
