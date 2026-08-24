"use client";

import { ArrowUpRight, Bookmark, BookmarkPlus, Share2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import styles from "@/components/daily-brief-actions.module.css";
import { useFavorite } from "@/components/use-favorites";
import {
  dailyBriefEventKey,
  dailyBriefFavoriteInput,
  dailyBriefPermalink,
  dailyBriefTrackingHref,
} from "@/lib/daily-brief-actions";
import { selectDailyBriefEvents } from "@/lib/daily-brief";
import { toggleFavorite } from "@/lib/favorites";
import {
  useArticles,
  type ArticlePayload,
  type LiveIntelligenceEvent,
} from "@/lib/use-articles";

const SHARE_REQUEST_EVENT = "vciq:favorite-share-request";
const DAILY_BRIEF_LIMIT = 10;

type ActionTarget = {
  button: HTMLButtonElement;
  host: HTMLElement;
  item: LiveIntelligenceEvent;
  top: number;
};

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
