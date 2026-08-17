"use client";

import { ArrowUpRight, Bot, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { EventQualityIndicator } from "@/components/event-quality-indicator";
import {
  HomepageSortToggle,
  type HomepageSortMode,
} from "@/components/homepage-sort-toggle";
import styles from "@/components/dashboard-v2.module.css";
import { getSnapshotFreshness } from "@/lib/snapshot-freshness";
import {
  useArticles,
  type ArticlePayload,
  type EventType,
  type LiveIntelligenceEvent,
} from "@/lib/use-articles";

const regions = ["全部", "中国", "美国", "全球"] as const;
const eventTypes = [
  "全部",
  "融资",
  "产业投资",
  "并购",
  "IPO",
  "财报",
  "政策",
  "监管文件",
  "商业进展",
  "产品发布",
  "技术突破",
  "公司动态",
  "论文",
  "人物观点",
] as const;
const KEY_EVENTS_LIMIT = 200;
const DAILY_BRIEF_LIMIT = 5;
const TRACKING_ADMIN_URL = "https://vciq-tracking-console.pages.dev/";

const focusCompanies = [
  {
    slug: "openai",
    name: "OpenAI",
    region: "美国",
    stage: "成长期",
    focus: "基础模型、开发者平台与 AI 基础设施",
  },
  {
    slug: "deepseek",
    name: "DeepSeek",
    region: "中国",
    stage: "成长期",
    focus: "开源推理模型与训练效率",
  },
  {
    slug: "figure-ai",
    name: "Figure AI",
    region: "美国",
    stage: "Series C",
    focus: "通用人形机器人、具身模型与制造",
  },
  {
    slug: "unitree",
    name: "宇树科技",
    region: "中国",
    stage: "成长期",
    focus: "四足与人形机器人产品化",
  },
  {
    slug: "pony-ai",
    name: "小马智行",
    region: "中国",
    stage: "已上市",
    focus: "Robotaxi 规模运营与车队扩张",
  },
  {
    slug: "rocket-lab",
    name: "Rocket Lab",
    region: "美国",
    stage: "已上市",
    focus: "发射服务、航天系统与新火箭进度",
  },
] as const;

export type DashboardBootstrap = {
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

function signalLabel(importance: number) {
  if (importance >= 85) return "高优先级";
  if (importance >= 70) return "值得跟进";
  return "常规观察";
}

function uniqueNonEmpty(values: Array<string | undefined>) {
  return [...new Set(values.map((value) => value?.trim()).filter(Boolean) as string[])];
}

export function DashboardV2Client({
  middle,
  children,
  initialPayload,
  bootstrap,
}: {
  middle?: ReactNode;
  children: ReactNode;
  initialPayload: ArticlePayload;
  bootstrap: DashboardBootstrap;
}) {
  const {
    articles,
    generatedAt,
    isLive,
    sourceStatus,
    qualityGate,
    refreshAudit,
  } = useArticles(initialPayload);
  const [region, setRegion] = useState<(typeof regions)[number]>("全部");
  const [eventType, setEventType] = useState<(typeof eventTypes)[number]>("全部");
  const [eventSort, setEventSort] = useState<HomepageSortMode>("importance");
  const [qualityScope, setQualityScope] = useState<"trusted" | "all">("trusted");
  const [query, setQuery] = useState("");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

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
  const freshness = getSnapshotFreshness({
    isLive,
    generatedAt,
    latestPublishedAt,
    qualityPassed: qualityGate?.passed,
    refreshAudit,
  });
  const normalizedQuery = query.trim().toLowerCase();

  const visibleEvents = useMemo(
    () =>
      activeArticles
        .filter((item) => qualityScope === "all" || item.qualityStatus !== "低可信")
        .filter((item) => region === "全部" || item.region === region)
        .filter((item) => eventType === "全部" || item.type === (eventType as EventType))
        .filter((item) => {
          if (!normalizedQuery) return true;
          const searchableText = [
            item.title,
            item.summary,
            item.company,
            item.sector,
            item.type,
            item.region,
            item.source.name,
            item.source.platform,
            item.source.level,
            item.wechatAccount,
            ...(item.authors ?? []),
            ...(item.mentionedCompanies ?? []),
            ...(item.mentionedPeople ?? []),
            ...(item.matchedTrackingTerms ?? []),
            ...(item.relatedSources ?? []).flatMap((source) => [
              source.name,
              source.platform,
              source.title,
            ]),
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          return searchableText.includes(normalizedQuery);
        })
        .sort((a, b) =>
          eventSort === "importance"
            ? b.importance - a.importance || b.publishedAt.localeCompare(a.publishedAt)
            : b.publishedAt.localeCompare(a.publishedAt) || b.importance - a.importance,
        ),
    [activeArticles, eventSort, eventType, normalizedQuery, qualityScope, region],
  );
  const displayedEvents = visibleEvents.slice(0, KEY_EVENTS_LIMIT);

  const briefDate = latestPublishedAt;
  const dailyBriefEvents = useMemo(() => {
    const sameDay = briefDate
      ? trustedArticles.filter((item) => item.publishedAt === briefDate)
      : [];
    const source = sameDay.length >= 3 ? sameDay : trustedArticles;
    return [...source]
      .sort(
        (left, right) =>
          right.importance - left.importance ||
          right.publishedAt.localeCompare(left.publishedAt),
      )
      .slice(0, DAILY_BRIEF_LIMIT);
  }, [briefDate, trustedArticles]);

  const selectedEvent =
    activeArticles.find((item) => item.id === selectedEventId) ??
    displayedEvents[0] ??
    dailyBriefEvents[0] ??
    activeArticles[0];

  const selectedEntities = selectedEvent
    ? uniqueNonEmpty([
        selectedEvent.company,
        ...(selectedEvent.mentionedCompanies ?? []),
        ...(selectedEvent.mentionedPeople ?? []),
        ...(selectedEvent.matchedTrackingTerms ?? []),
      ]).slice(0, 8)
    : [];
  const selectedSignals = selectedEvent
    ? uniqueNonEmpty([
        ...(selectedEvent.qualitySignals ?? []),
        selectedEvent.relatedSources?.length
          ? `${selectedEvent.relatedSources.length + 1} 个关联信源`
          : undefined,
        selectedEvent.duplicateCount && selectedEvent.duplicateCount > 1
          ? `${selectedEvent.duplicateCount} 条同事件聚合`
          : undefined,
      ]).slice(0, 5)
    : [];

  const computedSourceCount = new Set(activeArticles.map((item) => item.source.url)).size;
  const computedPlatformCount = new Set(
    activeArticles.map((item) => item.source.platform).filter(Boolean),
  ).size;
  const sourceCount = isLive ? computedSourceCount : bootstrap.sourceCount;
  const platformCount = isLive ? computedPlatformCount : bootstrap.platformCount;
  const activeSourceIds = new Set(activeArticles.map((item) => item.sourceId).filter(Boolean));
  const healthySourceCount = sourceStatus.filter(
    (item) =>
      activeSourceIds.has(item.id) &&
      ["ok", "partial"].includes(item.status) &&
      item.accepted > 0,
  ).length;
  const trackingQuality = qualityGate?.trackingQuality;
  const todayArticleCount = refreshAudit?.todayArticleCount ?? bootstrap.todayArticleCount;
  const newArticleCount = refreshAudit?.newArticleCount ?? "待刷新";
  const activeArticleCount = isLive ? activeArticles.length : bootstrap.activeArticleCount;
  const chinaCount = isLive
    ? activeArticles.filter((item) => item.region === "中国").length
    : bootstrap.chinaCount;
  const usCount = isLive
    ? activeArticles.filter((item) => item.region === "美国").length
    : bootstrap.usCount;

  const researchObjects = [
    {
      href: "/technologies",
      code: "TECH",
      name: "核心技术",
      description: "具体技术、技术系统与关键能力",
      count: bootstrap.researchObjectStats.technologyCount,
    },
    {
      href: "/technology",
      code: "TRACK",
      name: "核心赛道",
      description: "产业结构、关键变量与长期验证框架",
      count: bootstrap.researchObjectStats.trackCount,
    },
    {
      href: "/people",
      code: "PEOPLE",
      name: "核心人物",
      description: "创始人、科学家与关键决策者",
      count: bootstrap.researchObjectStats.personCount,
    },
    {
      href: "/companies",
      code: "CO",
      name: "核心公司",
      description: "一级市场科技公司与生命周期证据",
      count: bootstrap.researchObjectStats.companyCount,
    },
  ] as const;

  return (
    <div className={styles.dashboard}>
      <section className={styles.brief} aria-label="每日情报简报">
        <header className={styles.briefHeader}>
          <div>
            <p className={styles.kicker}>VCIQ DASHBOARD V2 · PERSONAL RESEARCH DESK</p>
            <h1>今天先处理最重要的情报</h1>
            <p className={styles.briefIntro}>
              先看今日高优先级变化，再进入情报收件箱做筛选、证据核对与追踪；深度模型结论继续由 Research Agent 承担。
            </p>
          </div>
          <div className={styles.freshness}>
            <span>最新情报 {latestPublishedAt || "暂无"}</span>
            <strong>{freshness.label}</strong>
            <span>最后成功发布 {freshness.processedAt}</span>
          </div>
        </header>

        <div className={styles.metricStrip} aria-label="今日研究快照">
          <div><span>今日事件</span><strong>{todayArticleCount}</strong></div>
          <div><span>本轮新收录</span><strong>{newArticleCount}</strong></div>
          <div><span>可信/有效来源</span><strong>{healthySourceCount || sourceCount}</strong></div>
          <div><span>滚动情报库</span><strong>{activeArticleCount}</strong></div>
          <div><span>中国 / 美国</span><strong>{chinaCount} / {usCount}</strong></div>
          <div><span>平台类型</span><strong>{platformCount}</strong></div>
        </div>

        <div className={styles.briefBody}>
          <div className={styles.briefLabel}>
            <strong>Daily Brief</strong>
            <p>{freshness.description}</p>
          </div>
          <div className={styles.briefList}>
            {dailyBriefEvents.length ? dailyBriefEvents.map((item, index) => (
              <button
                className={`${styles.briefItem} ${selectedEvent?.id === item.id ? styles.briefItemActive : ""}`}
                key={item.id}
                type="button"
                onClick={() => setSelectedEventId(item.id)}
              >
                <span className={styles.briefRank}>{String(index + 1).padStart(2, "0")}</span>
                <span className={styles.briefCopy}>
                  <strong>{item.title}</strong>
                  <small>{item.type} · {item.region} · {item.sector}</small>
                </span>
                <span className={styles.briefScore}>{item.importance}</span>
              </button>
            )) : (
              <div className={styles.analysisEmpty}>等待下一次可信情报刷新。</div>
            )}
          </div>
        </div>
      </section>

      <section className={styles.workbench} aria-label="情报处理工作台">
        <div className={styles.inbox}>
          <header className={styles.sectionHeader}>
            <div>
              <p>01 / INTELLIGENCE INBOX</p>
              <h2>情报收件箱</h2>
            </div>
            <span className={styles.sectionMeta}>
              展示 {displayedEvents.length} / {activeArticleCount} · 今日 {todayArticleCount}
            </span>
          </header>

          <div className="filter-bar">
            <div className="segmented" aria-label="地区筛选">
              {regions.map((item) => (
                <button
                  className={region === item ? "active" : ""}
                  key={item}
                  onClick={() => setRegion(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <select
              value={eventType}
              onChange={(event) =>
                setEventType(event.target.value as (typeof eventTypes)[number])
              }
              aria-label="事件类型"
            >
              {eventTypes.map((item) => <option key={item}>{item}</option>)}
            </select>
            <select
              value={qualityScope}
              onChange={(event) => setQualityScope(event.target.value as "trusted" | "all")}
              aria-label="线索质量"
            >
              <option value="trusted">可信优先</option>
              <option value="all">全部线索</option>
            </select>
            <HomepageSortToggle
              value={eventSort}
              onChange={setEventSort}
              ariaLabel="关键事件排序方式"
            />
            <label className="inline-search">
              <Search size={15} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索技术、赛道、人物、公司或事件"
                aria-label="搜索技术、赛道、人物、公司或事件"
              />
            </label>
          </div>

          <div className="event-list">
            {displayedEvents.length ? displayedEvents.map((item) => (
              <article
                className={`event-row ${selectedEvent?.id === item.id ? styles.selectedEvent : ""}`}
                key={item.id}
              >
                <div className="event-date">
                  <strong>{item.publishedAt.slice(5)}</strong>
                  <span>{item.publishedAt.slice(0, 4)}</span>
                </div>
                <div className="event-main">
                  <div className="event-tags">
                    <span className={`tag tag-${item.type}`}>{item.type}</span>
                    <span>{item.region}</span>
                    <span>{item.sector}</span>
                  </div>
                  <h3><EventTitle item={item} /></h3>
                  <p>{item.summary}</p>
                  <a
                    className="source-link"
                    href={item.source.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {item.source.level} · {item.source.platform ? `${item.source.platform} · ` : ""}{item.source.name}
                    <ArrowUpRight size={14} />
                  </a>
                  <EventQualityIndicator item={item} />
                  <button
                    type="button"
                    className={`${styles.inspectButton} ${selectedEvent?.id === item.id ? styles.inspectButtonActive : ""}`}
                    onClick={() => setSelectedEventId(item.id)}
                    aria-pressed={selectedEvent?.id === item.id}
                  >
                    在分析桌查看
                  </button>
                </div>
                <div className="importance" title="按事件规模、信源等级与产业影响计算">
                  <span>重要度</span>
                  <strong>{item.importance}</strong>
                </div>
              </article>
            )) : (
              <div className="empty-state">
                <Search size={22} />
                <strong>当前筛选没有结果</strong>
                <p>搜索会同时受地区和事件类型限制；可切换为“全部”后再次搜索研究对象或事件。</p>
              </div>
            )}
          </div>
        </div>

        <aside className={styles.analysisPanel} aria-label="分析桌">
          <header className={styles.analysisHeader}>
            <div>
              <p>02 / ANALYSIS DESK</p>
              <h2>分析桌</h2>
            </div>
            <Link href="/research-agent">Research Agent</Link>
          </header>

          {selectedEvent ? (
            <div className={styles.analysisBody}>
              <div className={styles.analysisTags}>
                <span>{selectedEvent.type}</span>
                <span>{selectedEvent.region}</span>
                <span>{selectedEvent.sector}</span>
                <span>{selectedEvent.qualityStatus ?? "待评分"}</span>
              </div>
              <h3 className={styles.analysisTitle}>{selectedEvent.title}</h3>
              <p className={styles.analysisSummary}>{selectedEvent.summary}</p>

              <div className={styles.analysisMetrics}>
                <div><span>优先级</span><strong>{signalLabel(selectedEvent.importance)}</strong></div>
                <div><span>重要度</span><strong>{selectedEvent.importance}</strong></div>
                <div><span>信源</span><strong>{selectedEvent.source.level}</strong></div>
              </div>

              <div className={styles.analysisBlock}>
                <h3>EVIDENCE SIGNALS</h3>
                <div className={styles.signalList}>
                  {(selectedSignals.length ? selectedSignals : ["当前仅展示已发布结构化证据"]).map((signal) => (
                    <span key={signal}>{signal}</span>
                  ))}
                </div>
              </div>

              <div className={styles.analysisBlock}>
                <h3>RELATED OBJECTS</h3>
                <div className={styles.entityList}>
                  {(selectedEntities.length ? selectedEntities : [selectedEvent.sector]).map((entity) => (
                    <span key={entity}>{entity}</span>
                  ))}
                </div>
              </div>

              <div className={styles.analysisActions}>
                <a href={selectedEvent.source.url} target="_blank" rel="noreferrer">
                  原始信源 <ArrowUpRight size={13} />
                </a>
                <Link href="/research-agent">
                  深度研究 <Bot size={13} />
                </Link>
              </div>
            </div>
          ) : (
            <div className={styles.analysisEmpty}>从左侧选择一条情报进入分析桌。</div>
          )}
        </aside>
      </section>

      <section className={styles.tracking} aria-label="首页研究概览">
        <header className={styles.sectionHeader}>
          <div>
            <p>03 / WATCHLIST & TRACKING</p>
            <h2>追踪工作区</h2>
          </div>
          <a className={styles.sectionLink} href={TRACKING_ADMIN_URL}>管理追踪</a>
        </header>

        <div className={styles.trackingGrid}>
          {focusCompanies.map((company) => (
            <Link
              className={styles.trackingCard}
              href={`/companies/${company.slug}`}
              key={company.slug}
            >
              <small>{company.region} · {company.stage}</small>
              <h3>{company.name}</h3>
              <p>{company.focus}</p>
              <strong>查看研究档案</strong>
            </Link>
          ))}
        </div>

        <div className={styles.objectGrid}>
          {researchObjects.map((object) => (
            <Link className={styles.objectCard} href={object.href} key={object.href}>
              <span className={styles.objectCode}>{object.code}</span>
              <div>
                <strong>{object.name}</strong>
                <small>{object.description}</small>
              </div>
              <span className={styles.objectCount}>{object.count}</span>
            </Link>
          ))}
        </div>

        <div className={styles.trackingFooter}>
          <span>研究对象质量：{qualityGate?.passed === false ? "需复核" : "通过"}</span>
          {trackingQuality ? (
            <>
              <span>通过 {trackingQuality.acceptedUserArticles}</span>
              <span>过滤 {trackingQuality.rejectedUserArticles}</span>
              <span>重复聚合 {trackingQuality.clusteredDuplicates}</span>
            </>
          ) : null}
        </div>
      </section>

      <section className={styles.recentResearch} aria-label="最近研究">
        <header className={styles.sectionHeader}>
          <div>
            <p>04 / RECENT RESEARCH</p>
            <h2>最近研究与更新</h2>
          </div>
          <span className={styles.sectionMeta}>头条与四类研究对象更新</span>
        </header>
        <div className={styles.recentGrid}>
          <div className={styles.recentColumn}>{middle}</div>
          <div className={styles.recentColumn}>{children}</div>
        </div>
      </section>
    </div>
  );
}

function EventTitle({ item }: { item: LiveIntelligenceEvent }) {
  return (
    <a href={item.source.url} target="_blank" rel="noreferrer">
      {item.title}
    </a>
  );
}
