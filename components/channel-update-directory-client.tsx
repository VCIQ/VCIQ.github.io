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
  ALL_CHANNEL_UPDATE_EVIDENCE,
  ALL_CHANNEL_UPDATE_KEYWORDS,
  ALL_CHANNEL_UPDATE_REGIONS,
  ALL_CHANNEL_UPDATE_TOPICS,
  ALL_CHANNEL_UPDATE_TRACKS,
  collectChannelUpdateClassifications,
  collectChannelUpdateEvidenceGrades,
  collectChannelUpdateKeywords,
  collectChannelUpdateRegions,
  collectChannelUpdateTopics,
  collectChannelUpdateTracks,
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
  technology: "科技研究",
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
  layout?: "default" | "split" | "workspace";
}) {
  const eventTypeSelectId = useId();
  const classificationSelectId = useId();
  const trackSelectId = useId();
  const topicSelectId = useId();
  const regionSelectId = useId();
  const evidenceSelectId = useId();
  const sortSelectId = useId();
  const [keyword, setKeyword] = useState(ALL_CHANNEL_UPDATE_KEYWORDS);
  const [classification, setClassification] = useState(
    ALL_CHANNEL_UPDATE_CLASSIFICATIONS,
  );
  const [track, setTrack] = useState(ALL_CHANNEL_UPDATE_TRACKS);
  const [topic, setTopic] = useState(ALL_CHANNEL_UPDATE_TOPICS);
  const [region, setRegion] = useState(ALL_CHANNEL_UPDATE_REGIONS);
  const [evidence, setEvidence] = useState(ALL_CHANNEL_UPDATE_EVIDENCE);
  const [sortOrder, setSortOrder] = useState<ChannelUpdateSortOrder>("newest");
  const [archiveItems, setArchiveItems] = useState<ChannelUpdateDirectory["items"] | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveError, setArchiveError] = useState(false);

  const isTechnologyChannel = channel === "technology";
  const allItems = archiveItems ?? directory.items;
  const fullArchiveLoaded = archiveItems !== null || directory.items.length >= totalItemCount;

  const trackOptions = useMemo(
    () => collectChannelUpdateTracks(allItems),
    [allItems],
  );
  const trackScopedItems = useMemo(
    () =>
      isTechnologyChannel
        ? filterAndSortChannelUpdates({
            items: allItems,
            keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
            track,
            sortOrder: "newest",
          })
        : allItems,
    [allItems, isTechnologyChannel, track],
  );
  const topicOptions = useMemo(
    () => collectChannelUpdateTopics(trackScopedItems),
    [trackScopedItems],
  );
  const topicScopedItems = useMemo(
    () =>
      isTechnologyChannel
        ? filterAndSortChannelUpdates({
            items: trackScopedItems,
            keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
            topic,
            sortOrder: "newest",
          })
        : allItems,
    [allItems, isTechnologyChannel, topic, trackScopedItems],
  );
  const eventTypeOptions = useMemo(
    () => collectChannelUpdateKeywords(topicScopedItems),
    [topicScopedItems],
  );
  const eventScopedItems = useMemo(
    () =>
      isTechnologyChannel
        ? filterAndSortChannelUpdates({
            items: topicScopedItems,
            keyword,
            sortOrder: "newest",
          })
        : allItems,
    [allItems, isTechnologyChannel, keyword, topicScopedItems],
  );
  const regionOptions = useMemo(
    () => collectChannelUpdateRegions(eventScopedItems),
    [eventScopedItems],
  );
  const regionScopedItems = useMemo(
    () =>
      isTechnologyChannel
        ? filterAndSortChannelUpdates({
            items: eventScopedItems,
            keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
            region,
            sortOrder: "newest",
          })
        : allItems,
    [allItems, eventScopedItems, isTechnologyChannel, region],
  );
  const evidenceOptions = useMemo(
    () => collectChannelUpdateEvidenceGrades(regionScopedItems),
    [regionScopedItems],
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
        classification: isTechnologyChannel
          ? ALL_CHANNEL_UPDATE_CLASSIFICATIONS
          : classification,
        track: isTechnologyChannel ? track : ALL_CHANNEL_UPDATE_TRACKS,
        topic: isTechnologyChannel ? topic : ALL_CHANNEL_UPDATE_TOPICS,
        region: isTechnologyChannel ? region : ALL_CHANNEL_UPDATE_REGIONS,
        evidence: isTechnologyChannel ? evidence : ALL_CHANNEL_UPDATE_EVIDENCE,
        sortOrder,
      }),
    [
      allItems,
      classification,
      evidence,
      isTechnologyChannel,
      keyword,
      region,
      sortOrder,
      topic,
      track,
    ],
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
  const activeFilterLabels = isTechnologyChannel
    ? [
        track !== ALL_CHANNEL_UPDATE_TRACKS ? track : "",
        topic !== ALL_CHANNEL_UPDATE_TOPICS ? topic : "",
        keyword !== ALL_CHANNEL_UPDATE_KEYWORDS ? keyword : "",
        region !== ALL_CHANNEL_UPDATE_REGIONS ? region : "",
        evidence !== ALL_CHANNEL_UPDATE_EVIDENCE ? `${evidence}级` : "",
      ].filter(Boolean)
    : [
        keyword !== ALL_CHANNEL_UPDATE_KEYWORDS ? keyword : "",
        classification !== ALL_CHANNEL_UPDATE_CLASSIFICATIONS ? classification : "",
      ].filter(Boolean);

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
      keywords: [...item.keywords, ...(item.topicNames ?? [])].slice(0, 8),
      source: item.source,
      channel,
    });
    window.open(trackingHref, "_blank", "noopener,noreferrer");
  }

  return (
    <section
      className={styles.directory}
      aria-labelledby={`${channel}-updates-title`}
      data-layout={layout === "default" ? undefined : layout}
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
          <span>{isTechnologyChannel ? "聚合事件库" : channel === "companies" ? "重要事件簇" : "滚动总库"}</span>
          <strong>{totalItemCount}</strong>
          <small title="首次收录按精确 firstSeenAt 计算；快照日事件按来源事件日期计算">
            {fullArchiveLoaded ? `已加载全部 ${allItems.length}` : `当前展示 ${allItems.length} / 总库 ${totalItemCount}`}
            {` · 今日新增 ${firstSeenItemCount} · 当日事件 ${snapshotDayItemCount}`}
          </small>
        </div>
      </div>

      {allItems.length ? (
        <>
          <div
            className={`${styles.controls} ${
              isTechnologyChannel ? styles.technologyControls : ""
            }`}
          >
            <div className={styles.controlIntro}>
              <Tags size={17} aria-hidden="true" />
              <div>
                <strong>
                  {isTechnologyChannel
                    ? "按研究 taxonomy 逐层筛选"
                    : "按事件和证据分类筛选"}
                </strong>
                <span>
                  {fullArchiveLoaded
                    ? "当前筛选完整滚动目录。"
                    : `首屏仅载入最新 ${directory.items.length} 条；需要全库筛选时再加载完整目录。`}
                </span>
              </div>
            </div>

            {isTechnologyChannel ? (
              <>
                <label className={styles.control} htmlFor={trackSelectId}>
                  <span>核心赛道</span>
                  <select
                    id={trackSelectId}
                    value={track}
                    onChange={(event) => {
                      setTrack(event.target.value);
                      setTopic(ALL_CHANNEL_UPDATE_TOPICS);
                    }}
                  >
                    <option value={ALL_CHANNEL_UPDATE_TRACKS}>全部赛道</option>
                    {trackOptions.map((option) => (
                      <option key={option.keyword} value={option.keyword}>
                        {option.keyword}（{option.count}）
                      </option>
                    ))}
                  </select>
                </label>

                <label className={styles.control} htmlFor={topicSelectId}>
                  <span>技术主题</span>
                  <select
                    id={topicSelectId}
                    value={topic}
                    onChange={(event) => setTopic(event.target.value)}
                  >
                    <option value={ALL_CHANNEL_UPDATE_TOPICS}>全部主题</option>
                    {topicOptions.map((option) => (
                      <option key={option.keyword} value={option.keyword}>
                        {option.keyword}（{option.count}）
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}

            <label className={styles.control} htmlFor={eventTypeSelectId}>
              <span>事件类型</span>
              <select
                id={eventTypeSelectId}
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              >
                <option value={ALL_CHANNEL_UPDATE_KEYWORDS}>
                  全部事件（{topicScopedItems.length}）
                </option>
                {eventTypeOptions.map((option) => (
                  <option key={option.keyword} value={option.keyword}>
                    {option.keyword}（{option.count}）
                  </option>
                ))}
              </select>
            </label>

            {isTechnologyChannel ? (
              <>
                <label className={styles.control} htmlFor={regionSelectId}>
                  <span>地区</span>
                  <select
                    id={regionSelectId}
                    value={region}
                    onChange={(event) => setRegion(event.target.value)}
                  >
                    <option value={ALL_CHANNEL_UPDATE_REGIONS}>全部地区</option>
                    {regionOptions.map((option) => (
                      <option key={option.keyword} value={option.keyword}>
                        {option.keyword}（{option.count}）
                      </option>
                    ))}
                  </select>
                </label>

                <label className={styles.control} htmlFor={evidenceSelectId}>
                  <span>证据等级</span>
                  <select
                    id={evidenceSelectId}
                    value={evidence}
                    onChange={(event) => setEvidence(event.target.value)}
                  >
                    <option value={ALL_CHANNEL_UPDATE_EVIDENCE}>全部等级</option>
                    {evidenceOptions.map((option) => (
                      <option key={option.keyword} value={option.keyword}>
                        {option.keyword}级（{option.count}）
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : (
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
            )}

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
                {activeFilterLabels.length
                  ? `${activeFilterLabels.map((value) => `“${value}”`).join(" + ")} · `
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
                const visibleSources = (item.sources ?? []).slice(0, 3);
                const hiddenSourceCount = Math.max(
                  0,
                  (item.sourceCount ?? visibleSources.length) - visibleSources.length,
                );
                return (
                  <div className={styles.itemWrap} key={item.id}>
                    <a
                      className={`${styles.item} ${
                        visibleSources.length > 1 ? styles.itemWithSources : ""
                      }`}
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
                      data-intelligence-keywords={[
                        ...item.keywords,
                        ...(item.topicNames ?? []),
                      ].join("|")}
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
                          {(item.sourceCount ?? 1) > 1 && (
                            <i>{item.sourceCount} 个信源</i>
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
                    {visibleSources.length > 1 ? (
                      <div className={styles.sourceRow} aria-label="关联公开信源">
                        <span>信源</span>
                        {visibleSources.map((source) => (
                          <a
                            href={source.href}
                            key={source.href}
                            rel="noreferrer"
                            target="_blank"
                            title={source.title}
                          >
                            {source.name}
                          </a>
                        ))}
                        {hiddenSourceCount > 0 ? <small>+{hiddenSourceCount}</small> : null}
                      </div>
                    ) : null}
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
              <p>
                {isTechnologyChannel
                  ? "请放宽赛道、技术主题、事件类型、地区或证据等级筛选。"
                  : "请选择其他事件类型或来源分类，或切换回全部。"}
              </p>
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
