"use client";

import {
  ArrowUpRight,
  BookmarkPlus,
  Bot,
  CircleMinus,
  Clock3,
  Info,
  Radar,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { EventQualityIndicator } from "@/components/event-quality-indicator";
import { useFavorites } from "@/components/use-favorites";
import { useHomepagePreferences } from "@/components/use-homepage-preferences";
import { toggleFavorite } from "@/lib/favorites";
import {
  dismissHomepageEvent,
  toggleHomepageSectorFollow,
  undoDismissHomepageEvent,
  type HomepagePreferenceState,
} from "@/lib/homepage-preferences";
import {
  baseHomepageRecommendationScore,
  homepageEventKey,
  homepageFeedFavoriteInput,
  homepageFavoriteId,
  homepageRecommendationReasons,
  isHomepageEventDismissed,
  isHomepageSectorFollowed,
  matchesHomepageFollowChannel,
  personalizedHomepageRecommendationScore,
} from "@/lib/homepage-recommendation";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";
import {
  useArticles,
  type ArticlePayload,
  type LiveIntelligenceEvent,
  type Region,
} from "@/lib/use-articles";
import styles from "./homepage-news-feed.module.css";
import polishStyles from "./homepage-news-feed-polish.module.css";
import preferenceStyles from "./homepage-preference-controls.module.css";

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

type DismissedNotice = {
  eventId: string;
  sector: string;
  title: string;
};

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

function matchesChannel(
  item: LiveIntelligenceEvent,
  channelId: ChannelId,
  preferences: HomepagePreferenceState,
) {
  if (channelId === "recommend" || channelId === "latest") return true;
  if (channelId === "follow") {
    return matchesHomepageFollowChannel(item, preferences);
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
  const favorites = useFavorites();
  const preferences = useHomepagePreferences();
  const [channel, setChannel] = useState<ChannelId>("recommend");
  const [region, setRegion] = useState<RegionFilter>("全部");
  const [qualityScope, setQualityScope] = useState<QualityScope>("trusted");
  const [query, setQuery] = useState("");
  const [feedLimit, setFeedLimit] = useState(INITIAL_FEED_LIMIT);
  const [clockMs, setClockMs] = useState<number | null>(null);
  const [expandedReasonKey, setExpandedReasonKey] = useState<string | null>(null);
  const [dismissedNotice, setDismissedNotice] = useState<DismissedNotice | null>(null);

  useEffect(() => {
    const updateClock = () => setClockMs(Date.now());
    updateClock();
    const timer = window.setInterval(updateClock, MINUTE_MS);
    return () => window.clearInterval(timer);
  }, []);

  const favoriteIds = useMemo(
    () => new Set(favorites.map((favorite) => favorite.id)),
    [favorites],
  );
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
      .filter((item) => !isHomepageEventDismissed(item, preferences))
      .filter((item) => region === "全部" || item.region === region)
      .filter((item) => matchesChannel(item, channel, preferences))
      .filter((item) => !normalizedQuery || itemSearchText(item).includes(normalizedQuery))
      .sort((left, right) => {
        if (channel === "latest") {
          return (
            right.publishedAt.localeCompare(left.publishedAt) ||
            right.importance - left.importance
          );
        }
        return (
          personalizedHomepageRecommendationScore(right, preferences, favorites) -
            personalizedHomepageRecommendationScore(left, preferences, favorites) ||
          right.publishedAt.localeCompare(left.publishedAt)
        );
      });
  }, [
    activeArticles,
    channel,
    favorites,
    normalizedQuery,
    preferences,
    qualityScope,
    region,
    trustedArticles,
  ]);

  const displayedArticles = visibleArticles.slice(0, feedLimit);
  const latestDate = latestPublishedAt.slice(0, 10);
  const latestDayArticles = trustedArticles.filter(
    (item) =>
      (!latestDate || item.publishedAt.slice(0, 10) === latestDate) &&
      !isHomepageEventDismissed(item, preferences),
  );
  const trustedVisibleArticles = trustedArticles.filter(
    (item) => !isHomepageEventDismissed(item, preferences),
  );
  const topSignalSource = latestDayArticles.length >= 5
    ? latestDayArticles
    : trustedVisibleArticles;
  const topSignals = [...topSignalSource]
    .sort(
      (left, right) =>
        baseHomepageRecommendationScore(right) - baseHomepageRecommendationScore(left) ||
        right.publishedAt.localeCompare(left.publishedAt),
    )
    .slice(0, TOP_SIGNAL_LIMIT);

  const sectorTrendCounts = new Map<string, number>();
  for (const item of topSignalSource) {
    sectorTrendCounts.set(item.sector, (sectorTrendCounts.get(item.sector) ?? 0) + 1);
  }
  const sectorTrends = [...sectorTrendCounts.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 6);

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
          <p>重要度、可信度、关联来源、关注赛道与稍后读共同排序。</p>
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
            <p>
              先看最值得知道的变化，再决定是否进入追踪或深度研究。
              {(preferences.followedSectors.length || favorites.length) ? (
                <span className={preferenceStyles.preferenceSummary}>
                  个性化：关注 {preferences.followedSectors.length} · 稍后读 {favorites.length}
                </span>
              ) : null}
            </p>
          </div>

          <div className={styles.feedList}>
            {displayedArticles.length ? (
              displayedArticles.map((item, index) => {
                const score = personalizedHomepageRecommendationScore(item, preferences, favorites);
                const hero = index === 0 && !normalizedQuery && channel !== "latest";
                const major = !hero && (item.importance >= 90 || score >= 88);
                const prominenceClass = hero
                  ? styles.heroCard
                  : major
                    ? styles.majorCard
                    : styles.standardCard;
                const eventKey = homepageEventKey(item);
                const favorite = homepageFeedFavoriteInput(item);
                const saved = favoriteIds.has(homepageFavoriteId(item));
                const followed = isHomepageSectorFollowed(item, preferences);
                const reasonOpen = expandedReasonKey === eventKey;

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
                        <button
                          type="button"
                          className={`${preferenceStyles.sectorFollow} ${
                            followed ? preferenceStyles.sectorFollowActive : ""
                          }`}
                          onClick={() => toggleHomepageSectorFollow(item.sector)}
                          aria-pressed={followed}
                          title={followed ? `取消关注 ${item.sector}` : `关注 ${item.sector}`}
                        >
                          <Radar size={11} aria-hidden="true" />
                          {followed ? "已关注赛道" : "关注赛道"}
                        </button>
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

                      <div className={preferenceStyles.preferenceActions} aria-label="推荐反馈">
                        <button
                          type="button"
                          onClick={() => toggleFavorite(favorite)}
                          aria-pressed={saved}
                          title={saved ? "取消稍后读" : "保存到稍后读"}
                        >
                          <Clock3 size={12} aria-hidden="true" />
                          {saved ? "已稍后读" : "稍后读"}
                        </button>
                        <button
                          type="button"
                          className={preferenceStyles.dismissAction}
                          onClick={() => {
                            dismissHomepageEvent(eventKey, item.sector);
                            setDismissedNotice({ eventId: eventKey, sector: item.sector, title: item.title });
                            if (expandedReasonKey === eventKey) setExpandedReasonKey(null);
                          }}
                          title="隐藏这条，并减少类似赛道内容"
                        >
                          <CircleMinus size={12} aria-hidden="true" />
                          不感兴趣
                        </button>
                        <button
                          type="button"
                          onClick={() => setExpandedReasonKey(reasonOpen ? null : eventKey)}
                          aria-pressed={reasonOpen}
                          aria-expanded={reasonOpen}
                        >
                          <Info size={12} aria-hidden="true" />
                          为什么推荐
                        </button>
                      </div>

                      {reasonOpen ? (
                        <div className={preferenceStyles.reasonPanel}>
                          <strong>这条内容出现在推荐流，因为：</strong>
                          <ul>
                            {homepageRecommendationReasons(item, preferences, favorites).map((reason) => (
                              <li key={reason}>{reason}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

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

          {dismissedNotice ? (
            <div className={preferenceStyles.preferenceNotice} role="status">
              <span>
                已隐藏“{compactSummary(dismissedNotice.title, 44)}”，并降低「{dismissedNotice.sector}」类似内容权重。
              </span>
              <button
                type="button"
                onClick={() => {
                  undoDismissHomepageEvent(dismissedNotice.eventId, dismissedNotice.sector);
                  setDismissedNotice(null);
                }}
              >
                撤销
              </button>
            </div>
          ) : null}

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
