"use client";

import {
  ArrowDownUp,
  ArrowUpRight,
  BookmarkPlus,
  RadioTower,
  Tags,
} from "lucide-react";
import { useId, useMemo, useState } from "react";
import {
  ALL_CHANNEL_UPDATE_CLASSIFICATIONS,
  ALL_CHANNEL_UPDATE_KEYWORDS,
  collectChannelUpdateClassifications,
  collectChannelUpdateKeywords,
  countChannelUpdatesFirstSeenForSnapshotDay,
  countChannelUpdatesForSnapshotDay,
  filterAndSortChannelUpdates,
  type ChannelUpdateSortOrder,
} from "@/lib/channel-update-filter";
import type {
  ChannelUpdateDirectory,
  ChannelUpdateKey,
} from "@/lib/channel-updates";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";
import styles from "./channel-update-directory.module.css";

const channelLabels: Record<ChannelUpdateKey, string> = {
  technology: "新兴科技",
  companies: "创业案例",
  institutions: "投资机构",
  reports: "研究报告",
  people: "人物研究",
};

type ChannelArchivePayload = {
  schemaVersion: number;
  channels?: Partial<Record<ChannelUpdateKey, ChannelUpdateDirectory>>;
};

export function ChannelUpdateDirectoryClient({
  channel,
  directory,
  totalItemCount,
  layout = "default",
}: {
  channel: ChannelUpdateKey;
  directory: ChannelUpdateDirectory;
  totalItemCount: number;
  layout?: "default" | "split";
}) {
  const eventTypeSelectId = useId();
  const classificationSelectId = useId();
  const sortSelectId = useId();
  const [keyword, setKeyword] = useState(ALL_CHANNEL_UPDATE_KEYWORDS);
  const [classification, setClassification] = useState(
    ALL_CHANNEL_UPDATE_CLASSIFICATIONS,
  );
  const [sortOrder, setSortOrder] = useState<ChannelUpdateSortOrder>("newest");
  const [archiveItems, setArchiveItems] = useState<ChannelUpdateDirectory["items"] | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveError, setArchiveError] = useState(false);

  const allItems = archiveItems ?? directory.items;
  const fullArchiveLoaded = archiveItems !== null || directory.items.length >= totalItemCount;

  const eventTypeOptions = useMemo(
    () => collectChannelUpdateKeywords(allItems),
    [allItems],
  );
  const classificationOptions = useMemo(
    () => collectChannelUpdateClassifications(allItems),
    [allItems],
  );
  const visibleItems = useMemo(
    () =>
      filterAndSortChannelUpdates({
        items: allItems,
        keyword,
        classification,
        sortOrder,
      }),
    [allItems, classification, keyword, sortOrder],
  );
  const firstSeenItemCount = useMemo(
    () => countChannelUpdatesFirstSeenForSnapshotDay(allItems, directory.generatedAt),
    [allItems, directory.generatedAt],
  );
  const snapshotDayItemCount = useMemo(
    () => countChannelUpdatesForSnapshotDay(allItems, directory.generatedAt),
    [allItems, directory.generatedAt],
  );
  const latestDatedItemId = useMemo(() => {
    let latest: (typeof visibleItems)[number] | undefined;
    for (const item of visibleItems) {
      if (item.datePrecision === "undated") continue;
      if (!latest || item.sortAt > latest.sortAt) latest = item;
    }
    return latest?.id ?? "";
  }, [visibleItems]);
  const isFiltered =
    keyword !== ALL_CHANNEL_UPDATE_KEYWORDS ||
    classification !== ALL_CHANNEL_UPDATE_CLASSIFICATIONS;

  async function loadFullArchive() {
    if (fullArchiveLoaded || archiveLoading) return;
    setArchiveLoading(true);
    setArchiveError(false);
    try {
      const response = await fetch("/data/channel_update_directories.json", {
        cache: "default",
      });
      if (!response.ok) throw new Error(`channel archive returned ${response.status}`);
      const payload = (await response.json()) as ChannelArchivePayload;
      const nextDirectory = payload.channels?.[channel];
      if (!nextDirectory || !Array.isArray(nextDirectory.items)) {
        throw new Error("channel archive is missing the requested directory");
      }
      setArchiveItems(nextDirectory.items);
    } catch {
      setArchiveError(true);
    } finally {
      setArchiveLoading(false);
    }
  }

  function openTrackingCapture(item: ChannelUpdateDirectory["items"][number]) {
    const trackingHref = buildTrackingCaptureLink({
      url: item.href,
      title: item.title,
      summary: item.summary,
      keywords: item.keywords,
      source: item.source,
      channel,
    });
    window.open(trackingHref, "_blank", "noopener,noreferrer");
  }

  return (
    <section
      className={styles.directory}
      aria-labelledby={`${channel}-updates-title`}
      data-layout={layout === "split" ? "split" : undefined}
    >
      <div className={styles.header}>
        <div className={styles.heading}>
          <p className="section-index">LATEST CRAWLED UPDATES</p>
          <div className={styles.titleLine}>
            <RadioTower size={19} aria-hidden="true" />
            <h2 id={`${channel}-updates-title`}>{directory.title}</h2>
          </div>
          <p>{directory.description}</p>
          {!fullArchiveLoaded ? (
            <button
              type="button"
              className={styles.importToggle}
              onClick={loadFullArchive}
              disabled={archiveLoading}
            >
              {archiveLoading
                ? "正在加载完整更新目录…"
                : `加载完整更新目录（${totalItemCount} 条）`}
            </button>
          ) : null}
          {archiveError ? <small>完整目录暂时不可用；最新更新仍可正常浏览。</small> : null}
        </div>
        <div className={styles.snapshot}>
          <span>滚动总库</span>
          <strong>{totalItemCount}</strong>
          <small title="首次收录按精确 firstSeenAt 计算；快照日事件按来源事件日期计算">
            当前载入 {allItems.length} · 今日首次收录 {firstSeenItemCount} · 快照日事件 {snapshotDayItemCount}
          </small>
        </div>
      </div>

      {allItems.length ? (
        <>
          <div className={styles.controls}>
            <div className={styles.controlIntro}>
              <Tags size={17} aria-hidden="true" />
              <div>
                <strong>按事件和证据分类筛选</strong>
                <span>
                  {fullArchiveLoaded
                    ? "当前筛选完整滚动目录。"
                    : `首屏仅载入最新 ${directory.items.length} 条；需要全库筛选时再加载完整目录。`}
                </span>
              </div>
            </div>

            <label className={styles.control} htmlFor={eventTypeSelectId}>
              <span>事件类型</span>
              <select
                id={eventTypeSelectId}
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              >
                <option value={ALL_CHANNEL_UPDATE_KEYWORDS}>
                  全部事件（{allItems.length}）
                </option>
                {eventTypeOptions.map((option) => (
                  <option key={option.keyword} value={option.keyword}>
                    {option.keyword}（{option.count}）
                  </option>
                ))}
              </select>
            </label>

            <label className={styles.control} htmlFor={classificationSelectId}>
              <span>来源 / 频道分类</span>
              <select
                id={classificationSelectId}
                value={classification}
                onChange={(event) => setClassification(event.target.value)}
              >
                <option value={ALL_CHANNEL_UPDATE_CLASSIFICATIONS}>
                  全部分类
                </option>
                {classificationOptions.map((option) => (
                  <option key={option.keyword} value={option.keyword}>
                    {option.keyword}（{option.count}）
                  </option>
                ))}
              </select>
            </label>

            <label className={styles.control} htmlFor={sortSelectId}>
              <span>时间排序</span>
              <select
                id={sortSelectId}
                value={sortOrder}
                onChange={(event) =>
                  setSortOrder(event.target.value as ChannelUpdateSortOrder)
                }
              >
                <option value="newest">最新优先</option>
                <option value="oldest">最早优先</option>
              </select>
            </label>

            <div className={styles.resultSummary} aria-live="polite">
              <ArrowDownUp size={14} aria-hidden="true" />
              <span>
                {isFiltered
                  ? `${keyword !== ALL_CHANNEL_UPDATE_KEYWORDS ? `“${keyword}”` : ""}${
                      keyword !== ALL_CHANNEL_UPDATE_KEYWORDS &&
                      classification !== ALL_CHANNEL_UPDATE_CLASSIFICATIONS
                        ? " + "
                        : ""
                    }${
                      classification !== ALL_CHANNEL_UPDATE_CLASSIFICATIONS
                        ? `“${classification}”`
                        : ""
                    } · `
                  : ""}
                {visibleItems.length} 条
              </span>
            </div>
          </div>

          {visibleItems.length ? (
            <div className={styles.list}>
              {visibleItems.map((item, index) => {
                const sourceDateTitle =
                  item.dateOriginal && item.dateOriginal !== item.date
                    ? `来源时间标注：${item.dateOriginal}`
                    : undefined;
                return (
                  <div className={styles.itemWrap} key={item.id}>
                    <a
                      className={styles.item}
                      href={item.href}
                      rel="noreferrer"
                      target="_blank"
                      data-intelligence-item="true"
                      data-intelligence-title={item.title}
                      data-intelligence-summary={item.summary}
                      data-intelligence-type={item.label}
                      data-intelligence-date={
                        item.datePrecision === "undated" ? undefined : item.sortAt
                      }
                      data-intelligence-source={item.source}
                      data-intelligence-source-level={item.sourceGrade}
                      data-intelligence-source-grade={item.sourceGrade}
                      data-intelligence-context={item.context}
                      data-intelligence-keywords={item.keywords.join("|")}
                      data-intelligence-channel={channel}
                      data-intelligence-channel-label={channelLabels[channel]}
                    >
                      <span className={styles.index}>
                        {String(index + 1).padStart(3, "0")}
                      </span>
                      <div className={styles.content}>
                        <div className={styles.meta}>
                          <span>{item.label}</span>
                          {item.sourceGrade && (
                            <em
                              className={styles.sourceGrade}
                              data-source-grade={item.sourceGrade}
                              title={item.sourceVerificationPolicy}
                            >
                              {item.sourceGrade}级 · {item.sourceGradeLabel}
                            </em>
                          )}
                          <time
                            dateTime={item.datePrecision === "undated" ? undefined : item.sortAt}
                            title={sourceDateTitle}
                          >
                            {item.date}
                          </time>
                          {item.id === latestDatedItemId && <b>时间最新</b>}
                        </div>
                        <h3 data-intelligence-title>{item.title}</h3>
                        <p data-intelligence-summary>{item.summary}</p>
                        <small data-intelligence-source>
                          {item.context} · {item.source}
                        </small>
                      </div>
                      <ArrowUpRight className={styles.arrow} size={18} aria-hidden="true" />
                    </a>
                    <button
                      type="button"
                      className={styles.trackingLink}
                      onClick={() => openTrackingCapture(item)}
                      title="在受保护的 Tracking Admin 中提取并加入研究对象"
                    >
                      <BookmarkPlus size={13} aria-hidden="true" />
                      加入追踪
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={styles.empty}>
              <strong>当前筛选条件下暂无更新</strong>
              <p>请选择其他事件类型或来源分类，或切换回全部。</p>
            </div>
          )}
        </>
      ) : (
        <div className={styles.empty}>
          <strong>尚未发现可展示的更新</strong>
          <p>下一次数据抓取完成后，新记录会自动出现在这里。</p>
        </div>
      )}
    </section>
  );
}
