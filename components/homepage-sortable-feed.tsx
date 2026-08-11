"use client";

import { ArrowUpRight, BookmarkPlus } from "lucide-react";
import { useMemo, useState } from "react";
import {
  HomepageSortToggle,
  type HomepageSortMode,
} from "@/components/homepage-sort-toggle";
import columnStyles from "@/components/homepage-columns.module.css";
import styles from "@/components/homepage-sortable-feed.module.css";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";

export type HomepageFeedItem = {
  id: string;
  title: string;
  href: string;
  tag: string;
  context: string;
  date: string;
  time?: string;
  asideLabel: string;
  sortAt: string;
  importance: number;
};

const INITIAL_FEED_RENDER_LIMIT = 60;

function sortItems(items: HomepageFeedItem[], mode: HomepageSortMode) {
  return [...items].sort((left, right) => {
    if (mode === "importance") {
      return (
        right.importance - left.importance ||
        right.sortAt.localeCompare(left.sortAt) ||
        left.title.localeCompare(right.title, "zh-CN")
      );
    }
    return (
      right.sortAt.localeCompare(left.sortAt) ||
      right.importance - left.importance ||
      left.title.localeCompare(right.title, "zh-CN")
    );
  });
}

export function HomepageSortableFeed({
  items,
  description,
  ariaLabel,
  limit = 80,
  initialSort = "latest",
  emptyMessage = "当前暂无可展示的情报记录。",
}: {
  items: HomepageFeedItem[];
  description: string;
  ariaLabel: string;
  limit?: number;
  initialSort?: HomepageSortMode;
  emptyMessage?: string;
}) {
  const [sortMode, setSortMode] = useState<HomepageSortMode>(initialSort);
  const [renderLimit, setRenderLimit] = useState(
    Math.min(limit, INITIAL_FEED_RENDER_LIMIT),
  );
  const sortedItems = useMemo(
    () => sortItems(items, sortMode).slice(0, limit),
    [items, limit, sortMode],
  );
  const visibleItems = sortedItems.slice(0, renderLimit);
  const hasMore = visibleItems.length < sortedItems.length;

  function openTrackingCapture(item: HomepageFeedItem) {
    const href = buildTrackingCaptureLink({
      url: item.href,
      title: item.title,
      summary: item.context,
      keywords: [item.tag, item.asideLabel].filter(Boolean),
      source: item.context,
      channel: "homepage",
    });
    window.open(href, "_blank", "noopener,noreferrer");
  }

  return (
    <>
      <div className={`method-note homepage-sort-panel ${styles.methodPanel}`}>
        <p>{description}</p>
        <HomepageSortToggle
          value={sortMode}
          onChange={(value) => {
            setSortMode(value);
            setRenderLimit(Math.min(limit, INITIAL_FEED_RENDER_LIMIT));
          }}
          ariaLabel={`${ariaLabel}排序方式`}
        />
      </div>

      <div className={columnStyles.feedList} aria-label={ariaLabel}>
        {visibleItems.map((item, index) => (
          <div className={styles.feedItem} key={`${item.id}-${item.href}`}>
            <a
              className={`${columnStyles.feedRow} ${styles.feedRowWithAction}`}
              href={item.href}
              rel="noreferrer"
              target="_blank"
            >
              <span className={columnStyles.feedIndex}>
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className={columnStyles.feedBody}>
                <strong className={columnStyles.feedTitle} title={item.title}>
                  {item.title}
                </strong>
                <small className={columnStyles.feedContext} title={item.context}>
                  <b className={columnStyles.feedTag}>{item.tag}</b>
                  {item.context}
                </small>
              </span>
              <span className={columnStyles.feedAside}>
                <span>{item.date}</span>
                {item.time ? <span>{item.time}</span> : null}
                <span>{item.asideLabel}</span>
              </span>
              <b className={columnStyles.feedArrow} aria-hidden="true">
                <ArrowUpRight size={14} />
              </b>
            </a>
            <button
              type="button"
              className={styles.trackingButton}
              onClick={() => openTrackingCapture(item)}
              title="从这张卡片提取并加入追踪"
              aria-label={`加入追踪：${item.title}`}
            >
              <BookmarkPlus size={12} aria-hidden="true" />
              加入追踪
            </button>
          </div>
        ))}
        {!visibleItems.length ? <p className={styles.empty}>{emptyMessage}</p> : null}
      </div>

      {hasMore ? (
        <div className={styles.loadMore}>
          <button
            type="button"
            onClick={() =>
              setRenderLimit((current) =>
                Math.min(limit, current + INITIAL_FEED_RENDER_LIMIT),
              )
            }
          >
            显示更多 · 已显示 {visibleItems.length}/{sortedItems.length}
          </button>
        </div>
      ) : null}
    </>
  );
}
