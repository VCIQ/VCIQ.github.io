"use client";

import { ArrowUpRight } from "lucide-react";
import { useMemo, useState } from "react";
import {
  HomepageSortToggle,
  type HomepageSortMode,
} from "@/components/homepage-sort-toggle";
import columnStyles from "@/components/homepage-columns.module.css";
import styles from "@/components/homepage-sortable-feed.module.css";

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

const INITIAL_FEED_RENDER_LIMIT = 10;

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
  archiveHref,
  archiveLabel = "查看全部",
}: {
  items: HomepageFeedItem[];
  description: string;
  ariaLabel: string;
  limit?: number;
  initialSort?: HomepageSortMode;
  emptyMessage?: string;
  archiveHref?: string;
  archiveLabel?: string;
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

      <section className={columnStyles.feedList} aria-label={ariaLabel}>
        {visibleItems.map((item, index) => (
          <article
            className={`${styles.feedItem} ${columnStyles.feedRow}`}
            data-intelligence-item="true"
            data-intelligence-id={item.id}
            data-intelligence-href={item.href}
            data-intelligence-title={item.title}
            data-intelligence-summary={item.context}
            data-intelligence-date={item.date}
            data-intelligence-importance={item.importance}
            key={`${item.id}-${item.href}`}
          >
            <span className={columnStyles.feedIndex}>
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className={columnStyles.feedBody}>
              <a
                className={columnStyles.feedTitle}
                data-intelligence-link="true"
                href={item.href}
                rel="noreferrer"
                target="_blank"
                title={item.title}
              >
                {item.title}
              </a>
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
          </article>
        ))}
        {!visibleItems.length ? <p className={styles.empty}>{emptyMessage}</p> : null}
      </section>

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

      {archiveHref ? (
        <a className={columnStyles.archiveLink} href={archiveHref}>
          {archiveLabel}
          <ArrowUpRight size={14} aria-hidden="true" />
        </a>
      ) : null}
    </>
  );
}
