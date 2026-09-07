"use client";

import { ArrowUpRight, BookmarkPlus, Bot, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { EventQualityIndicator } from "@/components/event-quality-indicator";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";
import {
  useArticles,
  type ArticlePayload,
  type LiveIntelligenceEvent,
  type Region,
} from "@/lib/use-articles";
import styles from "./homepage-news-feed.module.css";
import polishStyles from "./homepage-news-feed-polish.module.css";

type ChannelId =
  | "follow"
  | "recommend"
  | "latest"
  | "ai"
  | "embodied"
  | "semiconductor"
  | "space"
  | "solid-state"
  | "hbm";

type RegionFilter = "全部" | Region;
type QualityScope = "trusted" | "all";

const CHANNELS: ReadonlyArray<{
  id: ChannelId;
  label: string;
  keywords?: readonly string[];
}> = [
  { id: "follow", label: "关注" },
  { id: "recommend", label: "推荐" },
  { id: "latest", label: "快讯" },
  { id: "ai", label: "AI / AGI", keywords: ["AI", "AGI", "人工智能", "大模型", "基础模型", "算力"] },
  { id: "embodied", label: "具身智能", keywords: ["具身", "人形机器人", "机器人", "灵巧手", "Physical AI", "物理AI"] },
  { id: "semiconductor", label: "半导体", keywords: ["半导体", "芯片", "GPU", "DRAM", "晶圆", "封装", "光刻"] },
  { id: "space", label: "商业航天", keywords: ["商业航天", "航天", "火箭", "卫星", "运载", "太空"] },
  { id: "solid-state", label: "固态电池", keywords: ["固态电池", "全固态", "固态电解质", "电解质"] },
  { id: "hbm", label: "HBM", keywords: ["HBM", "高带宽内存", "高带宽存储"] },
];

const REGIONS: readonly RegionFilter[] = ["全部", "中国", "美国", "全球"];
const INITIAL_FEED_LIMIT = 24;
const FEED_BATCH = 24;
const TOP_SIGNAL_LIMIT = 10;
const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

const CHINA_DATE_TIME_FORMATTER = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const CHINA_CLOCK_FORMATTER = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export type HomepageFeedBootstrap = {
  trackedSectorAliases: string[];
  todayArticleCount: number;
  sectorCount: number;
  activeArticleCount: number;
  sourceCount: number;
  platformCount: number;
  latestPublishedAt: string;
  chinaCount: number;
  usCount: number;
  marketSourceCounts: { 中国: number; 美国: number };
  topSectors: { 中国: string; 美国: string };
  researchObjectStats: {
    technologyCount: number;
    trackCount: number;
    personCount: number;
    companyCount: number;
  };
};

function itemSearchText(item: LiveIntelligenceEvent) {
  return [
    item.title,
    item.summary,
    item.company,
    item.sector,
    item.type,
    item.region,
    item.source.name,
    item.source.platform,
    item.wechatAccount,
    ...(item.authors ?? []),
    ...(item.mentionedCompanies ?? []),
    ...(item.mentionedPeople ?? []),
    ...(item.matchedTrackingTerms ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function recommendationScore(item: LiveIntelligenceEvent) {
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
  const relatedCount = Math.max(
    item.relatedSources?.length ?? 0,
    Math.max(0, (item.duplicateCount ?? 1) - 1),
  );
  const trackingMatches = Math.min(item.matchedTrackingTerms?.length ?? 0, 4);

  return (
    item.importance * 0.68 +
    quality * 0.18 +
    Math.min(relatedCount, 5) * 2.2 +
    trackingMatches * 1.6 +
    (item.curated ? 3 : 0)
  );
}

function matchesChannel(item: LiveIntelligenceEvent, channelId: ChannelId) {
  if (channelId === "recommend" || channelId === "latest") return true;
  if (channelId === "follow") {
    return Boolean(item.curated || item.matchedTrackingTerms?.length);
  }

  const channel = CHANNELS.find((candidate) => candidate.id === channelId);
  if (!channel?.keywords?.length) return true;
  const haystack = itemSearchText(item);
  return channel.keywords.some((keyword) => haystack.includes(keyword.toLowerCase()));
}

function compactSummary(summary: string, maxLength: number) {
  const normalized = summary.trim();
  return normalized.length > maxLength
    ? `${normalized.slice(0, maxLength)}…`
    : normalized;
}

function formatAbsolutePublishedAt(timestampMs: number) {
  return CHINA_DATE_TIME_FORMATTER.format(new Date(timestampMs)).replaceAll("/", "-");
}

function formatPublishedAt(publishedAt: string, nowMs: number | null) {
  const timestampMs = Date.parse(publishedAt);
  if (!Number.isFinite(timestampMs)) return publishedAt;

  const absolute = formatAbsolutePublishedAt(timestampMs);
  if (nowMs === null) return absolute;

  const delta = nowMs - timestampMs;
  if (delta < 0 || delta >= 7 * DAY_MS) return absolute;
  if (delta < MINUTE_MS) return "刚刚";
  if (delta < HOUR_MS) return `${Math.max(1, Math.floor(delta / MINUTE_MS))}分钟前`;
  if (delta < DAY_MS) return `${Math.max(1, Math.floor(delta / HOUR_MS))}小时前`;
  if (delta < 2 * DAY_MS) {
    return `昨天 ${CHINA_CLOCK_FORMATTER.format(new Date(timestampMs))}`;
  }
  return `${Math.max(2, Math.floor(delta / DAY_MS))}天前`;
}

function trackingHref(item: LiveIntelligenceEvent) {
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
    ]
      .filter(Boolean)
      .slice(0, 8) as string[],
    source: `${item.source.level} · ${item.source.name}`,
    channel: "homepage-recommendation-feed",
  });
}

export function HomepageNewsFeed({
  initialPayload,
  bootstrap,
}: {
  initialPayload: ArticlePayload;
  bootstrap: HomepageFeedBootstrap;
}) {
  const { articles, refreshAudit, isLive } = useArticles(initialPayload);
  const [channel, setChannel] = useState<ChannelId>("recommend");
  const [region, setRegion] = useState<RegionFilter>("全部");
  const [qualityScope, setQualityScope] = useState<QualityScope>("trusted");
  const [query, setQuery] = useState("");
  const [feedLimit, setFeedLimit] = useState(INITIAL_FEED_LIMIT);
  const [clockMs, setClockMs] = useState<number | null>(null);

  useEffect(() => {
    const updateClock = () => setClockMs(Date.now());
    updateClock();
    const timer = window.setInterval(updateClock, MINUTE_MS);
    return () => window.clearInterval(timer);
  }, []);

  const enabledSectorNames = useMemo(
    () => new Set(bootstrap.trackedSectorAliases),
    [bootstrap.trackedSectorAliases],
  );
  const activeArticles = useMemo(
    () => articles.filter((item) => enabledSectorNames.has(item.sector)),
    [articles, enabledSectorNames],
  );
  const trustedArticles = useMemo(
    () => activeArticles.filter((item) => item.qualityStatus !== "低可信"),
    [activeArticles],
  );
  const liveLatestPublishedAt = useMemo(
    () =>
      activeArticles.reduce(
        (latest, item) => (item.publishedAt > latest ? item.publishedAt : latest),
        "",
      ),
    [activeArticles],
  );
  const latestPublishedAt = isLive
    ? liveLatestPublishedAt
    : bootstrap.latestPublishedAt || liveLatestPublishedAt;
  const normalizedQuery = query.trim().toLowerCase();

  const visibleArticles = useMemo(() => {
    const base = qualityScope === "trusted" ? trustedArticles : activeArticles;
    return base
      .filter((item) => region === "全部" || item.region === region)
      .filter((item) => matchesChannel(item, channel))
      .filter((item) => !normalizedQuery || itemSearchText(item).includes(normalizedQuery))
      .sort((left, right) => {
        if (channel === "latest") {
          return (
            right.publishedAt.localeCompare(left.publishedAt) ||
            right.importance - left.importance
          );
        }
        return (
          recommendationScore(right) - recommendationScore(left) ||
          right.publishedAt.localeCompare(left.publishedAt)
        );
      });
  }, [activeArticles, channel, normalizedQuery, qualityScope, region, trustedArticles]);

  const displayedArticles = visibleArticles.slice(0, feedLimit);
  const latestDate = latestPublishedAt.slice(0, 10);
  const latestDayArticles = trustedArticles.filter(
    (item) => !latestDate || item.publishedAt.slice(0, 10) === latestDate,
  );
  const topSignalSource = latestDayArticles.length >= 5 ? latestDayArticles : trustedArticles;
  const topSignals = [...topSignalSource]
    .sort(
      (left, right) =>
        recommendationScore(right) - recommendationScore(left) ||
        right.publishedAt.localeCompare(left.publishedAt),
    )
    .slice(0, TOP_SIGNAL_LIMIT);

  const sectorTrends = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of topSignalSource) {
      counts.set(item.sector, (counts.get(item.sector) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((left, right) => right[1] - left[1])
      .slice(0, 6);
  }, [topSignalSource]);

  const todayArticleCount = refreshAudit?.todayArticleCount ?? bootstrap.todayArticleCount;
  const newArticleCount = refreshAudit?.newArticleCount ?? "待刷新";
  const activeArticleCount = isLive ? activeArticles.length : bootstrap.activeArticleCount;
  const highPriorityCount = trustedArticles.filter((item) => item.importance >= 90).length;
  const currentChannelLabel =
    CHANNELS.find((candidate) => candidate.id === channel)?.label ?? "推荐";

  function changeChannel(nextChannel: ChannelId) {
    setChannel(nextChannel);
    setFeedLimit(INITIAL_FEED_LIMIT);
  }

  function changeRegion(nextRegion: RegionFilter) {
    setRegion(nextRegion);
    setFeedLimit(INITIAL_FEED_LIMIT);
  }

  function toggleQualityScope() {
    setQualityScope((current) => (current === "trusted" ? "all" : "trusted"));
    setFeedLimit(INITIAL_FEED_LIMIT);
  }

  function scrollHome() {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <section
      className={`${styles.shell} ${polishStyles.mobileSafeArea}`}
      aria-label="VCIQ 今日推荐情报流"
    >
      <header className={styles.feedHeader}>
        <div className={styles.feedIdentity}>
          <span>VCIQ INTELLIGENCE FEED</span>
          <strong>今日推荐</strong>
          <p>重要度、可信度、关联来源与关注词共同排序。</p>
        </div>

        <label className={styles.searchBox}>
          <Search size={18} aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setFeedLimit(INITIAL_FEED_LIMIT);
            }}
            placeholder="搜公司、人物、技术、事件"
            aria-label="搜索首页情报"
          />
        </label>
      </header>

      <div className={styles.statusStrip} aria-label="今日情报状态">
        <span>今日 {todayArticleCount} 条</span>
        <span>新收录 {newArticleCount}</span>
        <span>高优先级 {highPriorityCount}</span>
        <span>滚动情报库 {activeArticleCount}</span>
        <span className={styles.statusFreshness}>
          {isLive ? "实时快照" : "页面快照"} · 最新{" "}
          {latestPublishedAt ? (
            <time dateTime={latestPublishedAt}>{formatPublishedAt(latestPublishedAt, clockMs)}</time>
          ) : (
            "暂无"
          )}
        </span>
      </div>

      <div className={styles.channelBar}>
        <nav className={styles.channelRail} aria-label="情报频道">
          {CHANNELS.map((item) => (
            <button
              type="button"
              key={item.id}
              className={channel === item.id ? styles.channelActive : ""}
              onClick={() => changeChannel(item.id)}
              aria-pressed={channel === item.id}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className={styles.filters}>
          <label>
            <span>地区</span>
            <select
              value={region}
              onChange={(event) => changeRegion(event.target.value as RegionFilter)}
            >
              {REGIONS.map((item) => (
                <option value={item} key={item}>{item}</option>
              ))}
            </select>
          </label>
          <button type="button" onClick={toggleQualityScope}>
            {qualityScope === "trusted" ? "仅可信" : "全部质量"}
          </button>
        </div>
      </div>

      <div className={styles.contentGrid}>
        <main className={styles.feedColumn}>
          <div className={styles.feedHeading}>
            <div>
              <span>{currentChannelLabel}</span>
              <strong>{visibleArticles.length} 条候选情报</strong>
            </div>
            <p>先看最值得知道的变化，再决定是否进入追踪或深度研究。</p>
          </div>

          <div className={styles.feedList}>
            {displayedArticles.length ? (
              displayedArticles.map((item, index) => {
                const score = recommendationScore(item);
                const hero = index === 0 && !normalizedQuery && channel !== "latest";
                const major = !hero && (item.importance >= 90 || score >= 88);
                const prominenceClass = hero
                  ? styles.heroCard
                  : major
                    ? styles.majorCard
                    : styles.standardCard;

                return (
                  <article
                    className={`${styles.feedCard} ${prominenceClass}`}
                    key={item.id}
                    data-id={item.id}
                  >
                    <div className={styles.cardBody}>
                      <div className={styles.cardTags}>
                        <span>{item.type}</span>
                        <span>{item.region}</span>
                        <span>{item.sector}</span>
                      </div>

                      <h2>
                        <a href={item.source.url} target="_blank" rel="noreferrer">
                          {item.title}
                        </a>
                      </h2>

                      <p className={styles.cardSummary}>
                        {compactSummary(item.summary, hero ? 230 : major ? 170 : 125)}
                      </p>

                      <EventQualityIndicator item={item} />

                      <div className={`${styles.cardMeta} ${polishStyles.cardMeta}`}>
                        <span>{item.source.name}</span>
                        <time dateTime={item.publishedAt}>{formatPublishedAt(item.publishedAt, clockMs)}</time>
                        <strong>重要度 {item.importance}</strong>
                      </div>

                      <div className={`${styles.cardActions} ${polishStyles.mobileActions}`}>
                        <a href={item.source.url} target="_blank" rel="noreferrer">
                          查看来源 <ArrowUpRight size={13} aria-hidden="true" />
                        </a>
                        <a href={trackingHref(item)} target="_blank" rel="noreferrer">
                          <BookmarkPlus size={13} aria-hidden="true" />
                          追踪
                        </a>
                        <Link href="/research-agent">
                          <Bot size={13} aria-hidden="true" />
                          深度研究
                        </Link>
                      </div>
                    </div>

                    {hero ? (
                      <div className={styles.signalVisual} aria-hidden="true">
                        <span>{item.sector}</span>
                        <strong>{item.importance}</strong>
                        <small>INTELLIGENCE</small>
                      </div>
                    ) : null}
                  </article>
                );
              })
            ) : (
              <div className={styles.emptyState}>
                <strong>当前频道没有匹配情报</strong>
                <p>可以切换频道、地区，或清空搜索条件。</p>
              </div>
            )}
          </div>

          {displayedArticles.length < visibleArticles.length ? (
            <button
              type="button"
              className={styles.loadMore}
              onClick={() => setFeedLimit((current) => current + FEED_BATCH)}
            >
              继续加载下一批情报
            </button>
          ) : null}
        </main>

        <aside className={styles.rightRail} aria-label="今日重大信号">
          <section className={styles.railPanel}>
            <header>
              <span>TOP SIGNALS</span>
              <strong>今日重大信号 TOP 10</strong>
            </header>
            <ol className={styles.signalList}>
              {topSignals.map((item, index) => (
                <li key={item.id}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <a href={item.source.url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                    <small>{item.sector} · {item.importance}</small>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className={styles.railPanel}>
            <header>
              <span>SECTOR PULSE</span>
              <strong>热门赛道</strong>
            </header>
            <div className={styles.sectorPulse}>
              {sectorTrends.map(([sector, count]) => (
                <button
                  type="button"
                  key={sector}
                  onClick={() => {
                    setQuery(sector);
                    changeChannel("recommend");
                    scrollHome();
                  }}
                >
                  <span>{sector}</span>
                  <strong>{count}</strong>
                </button>
              ))}
            </div>
          </section>

          <section className={`${styles.railPanel} ${styles.railMetrics}`}>
            <header>
              <span>TODAY</span>
              <strong>今日数据</strong>
            </header>
            <dl>
              <div><dt>事件</dt><dd>{todayArticleCount}</dd></div>
              <div><dt>新收录</dt><dd>{newArticleCount}</dd></div>
              <div><dt>来源</dt><dd>{bootstrap.sourceCount}</dd></div>
              <div><dt>平台</dt><dd>{bootstrap.platformCount}</dd></div>
            </dl>
          </section>
        </aside>
      </div>

      <nav
        className={`${styles.mobileBottomNav} ${polishStyles.mobileBottomNav}`}
        aria-label="移动端快捷导航"
      >
        <button
          type="button"
          className={channel === "recommend" ? styles.mobileNavActive : ""}
          onClick={() => {
            changeChannel("recommend");
            scrollHome();
          }}
        >
          首页
        </button>
        <button
          type="button"
          className={channel === "follow" ? styles.mobileNavActive : ""}
          onClick={() => {
            changeChannel("follow");
            scrollHome();
          }}
        >
          关注
        </button>
        <button
          type="button"
          className={channel === "latest" ? styles.mobileNavActive : ""}
          onClick={() => {
            changeChannel("latest");
            scrollHome();
          }}
        >
          快讯
        </button>
        <Link href="/research-agent">研究</Link>
        <Link href="/favorites">我的</Link>
      </nav>
    </section>
  );
}
