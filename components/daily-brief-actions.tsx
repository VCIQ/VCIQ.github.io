"use client";

import { ArrowUpRight, Bookmark, BookmarkPlus, Share2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import styles from "@/components/daily-brief-actions.module.css";
import { useFavorite } from "@/components/use-favorites";
import { selectDailyBriefEvents } from "@/lib/daily-brief";
import {
  toggleFavorite,
  type FavoriteChannel,
  type FavoriteInput,
} from "@/lib/favorites";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";
import {
  useArticles,
  type ArticlePayload,
  type LiveIntelligenceEvent,
} from "@/lib/use-articles";

const SHARE_REQUEST_EVENT = "vciq:favorite-share-request";
const DAILY_BRIEF_LIMIT = 10;

type FavoriteChannelMeta = {
  channel: FavoriteChannel;
  channelLabel: string;
};

type ActionTarget = {
  button: HTMLButtonElement;
  host: HTMLElement;
  item: LiveIntelligenceEvent;
  top: number;
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

export function DailyBriefActions({ item }: { item: LiveIntelligenceEvent }) {
  const favorite = dailyBriefFavoriteInput(item);
  const saved = useFavorite(favorite.id);

  return (
    <div className={styles.actions} aria-label={`快速操作：${item.title}`}>
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

export function DailyBriefQuickActions({
  initialPayload,
  trackedSectorAliases,
}: {
  initialPayload: ArticlePayload;
  trackedSectorAliases: string[];
}) {
  const { articles } = useArticles(initialPayload);
  const [targets, setTargets] = useState<ActionTarget[]>([]);
  const sharedSelectionApplied = useRef(false);

  const dailyBriefEvents = useMemo(() => {
    const enabled = new Set(trackedSectorAliases);
    const trusted = articles.filter(
      (item) => enabled.has(item.sector) && item.qualityStatus !== "低可信",
    );
    const briefDate = trusted.reduce(
      (latest, item) => (item.publishedAt > latest ? item.publishedAt : latest),
      "",
    );
    const sameDay = briefDate
      ? trusted.filter((item) => item.publishedAt === briefDate)
      : [];
    const source = sameDay.length >= DAILY_BRIEF_LIMIT ? sameDay : trusted;
    return selectDailyBriefEvents(source, DAILY_BRIEF_LIMIT, briefDate);
  }, [articles, trackedSectorAliases]);

  useEffect(() => {
    const section = document.querySelector<HTMLElement>(
      'section[aria-label="每日情报简报"]',
    );
    if (!section) return;
    section.id = "daily-brief";

    const analysis = document.querySelector<HTMLElement>('aside[aria-label="分析桌"]');
    if (analysis) analysis.id = "analysis-desk";

    const rowListeners = new Map<HTMLButtonElement, () => void>();

    const scan = () => {
      const buttons = [
        ...section.querySelectorAll<HTMLButtonElement>('button[class*="briefItem"]'),
      ].slice(0, DAILY_BRIEF_LIMIT);
      const compact = window.matchMedia("(max-width: 720px)").matches;
      const next: ActionTarget[] = [];

      buttons.forEach((button, index) => {
        const item = dailyBriefEvents[index];
        const host = button.parentElement;
        if (!item || !host) return;

        host.style.position = "relative";
        button.style.paddingRight = compact ? "126px" : "160px";
        button.dataset.dailyBriefEvent = dailyBriefEventKey(item);
        button.title = "点击查看分析；右侧可收藏、追踪、分享或打开原文";

        const top = button.offsetTop + Math.max(0, (button.offsetHeight - 27) / 2);
        next.push({ button, host, item, top });

        if (!rowListeners.has(button)) {
          const onClick = () => {
            window.requestAnimationFrame(() => {
              document.getElementById("analysis-desk")?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            });
          };
          rowListeners.set(button, onClick);
          button.addEventListener("click", onClick);
        }
      });

      setTargets(next);

      if (!sharedSelectionApplied.current) {
        const requested = new URLSearchParams(window.location.search).get("event");
        if (requested) {
          const index = dailyBriefEvents.findIndex(
            (item) => item.id === requested || dailyBriefEventKey(item) === requested,
          );
          const button = index >= 0 ? buttons[index] : undefined;
          if (button) {
            sharedSelectionApplied.current = true;
            button.click();
            window.requestAnimationFrame(() => {
              section.scrollIntoView({ behavior: "auto", block: "start" });
            });
          }
        }
      }
    };

    scan();
    window.addEventListener("resize", scan);

    return () => {
      window.removeEventListener("resize", scan);
      for (const [button, listener] of rowListeners) {
        button.removeEventListener("click", listener);
        button.style.paddingRight = "";
        delete button.dataset.dailyBriefEvent;
      }
    };
  }, [dailyBriefEvents]);

  return (
    <>
      {targets.map(({ host, item, top }) =>
        createPortal(
          <div
            className={styles.mount}
            style={{ top }}
            data-daily-brief-action-mount
          >
            <DailyBriefActions item={item} />
          </div>,
          host,
          `daily-brief-actions:${dailyBriefEventKey(item)}`,
        ),
      )}
    </>
  );
}
