"use client";

import { ArrowUpRight, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { EventQualityIndicator } from "@/components/event-quality-indicator";
import { SourceArticleLink } from "@/components/source-article-link";
import {
  HomepageSortToggle,
  type HomepageSortMode,
} from "@/components/homepage-sort-toggle";
import styles from "@/components/homepage-research-panels.module.css";
import { getSnapshotFreshness } from "@/lib/snapshot-freshness";
import {
  useArticles,
  type ArticlePayload,
  type EventType,
  type IntelligenceEvent,
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

export function DashboardClient({
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

  const enabledSectorNames = useMemo(
    () => new Set(bootstrap.trackedSectorAliases),
    [bootstrap.trackedSectorAliases],
  );
  const activeArticles = useMemo(
    () => articles.filter((item) => enabledSectorNames.has(item.sector)),
    [articles, enabledSectorNames],
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
  const processedAt = freshness.processedAt;
  const freshnessLabel = freshness.label;
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
  const newArticleCountLabel = refreshAudit?.newArticleCount ?? "待刷新";
  const activeArticleCount = isLive ? activeArticles.length : bootstrap.activeArticleCount;
  const chinaCount = isLive
    ? activeArticles.filter((item) => item.region === "中国").length
    : bootstrap.chinaCount;
  const usCount = isLive
    ? activeArticles.filter((item) => item.region === "美国").length
    : bootstrap.usCount;

  const liveMarketSourceCount = (market: "中国" | "美国") =>
    new Set(
      activeArticles
        .filter((item) => item.region === market)
        .map((item) => item.source.url),
    ).size;
  const marketSourceCount = (market: "中国" | "美国") =>
    isLive ? liveMarketSourceCount(market) : bootstrap.marketSourceCounts[market];
  const liveTopSector = (market: "中国" | "美国") => {
    const counts = new Map<string, number>();
    activeArticles
      .filter((item) => item.region === market)
      .forEach((item) => counts.set(item.sector, (counts.get(item.sector) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "持续更新";
  };
  const topSector = (market: "中国" | "美国") =>
    isLive ? liveTopSector(market) : bootstrap.topSectors[market];

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
    <>
      <section className="dashboard-intro">
        <div>
          <p className="eyebrow">PRIMARY MARKET RESEARCH DESK · 中美双轨</p>
          <h1>围绕四类核心对象持续研究</h1>
          <p className="intro-copy">
            以核心技术、核心赛道、核心人物和核心公司为主线，持续连接官方披露、专业创投媒体、
            微信公开索引、开放论文与监管材料。上市和退出信息仅作为公司生命周期证据。
          </p>
        </div>
      </section>

      <section className="market-strip" aria-label="中美一级市场科技研究概览">
        <MarketSummary
          market="中国"
          sources={marketSourceCount("中国")}
          events={String(chinaCount).padStart(2, "0")}
          sector={topSector("中国")}
        />
        <div className="market-divider"><span>CN</span><i /><span>US</span></div>
        <MarketSummary
          market="美国"
          sources={marketSourceCount("美国")}
          events={String(usCount).padStart(2, "0")}
          sector={topSector("美国")}
        />
      </section>

      <section className="content-grid">
        <div className="primary-column">
          <div className="section-heading">
            <div>
              <p className="section-index">01 / KEY EVENTS</p>
              <h2>关键事件</h2>
            </div>
            <span>
              当前展示 {displayedEvents.length} 条；滚动总库 {activeArticleCount} 条；今日事件 {todayArticleCount} 条
            </span>
          </div>

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
              <article className="event-row" key={item.id}>
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

        {middle}

        <div className="side-column-stack">{children}</div>
      </section>

      <section className={styles.researchGrid} aria-label="首页研究概览">
        <article className={`${styles.panel} ${styles.snapshotPanel}`}>
          <header className={styles.panelHeader}>
            <div>
              <p>04 / INTEL SNAPSHOT</p>
              <h2>情报快照</h2>
            </div>
            <span className={styles.panelMeta}>{freshnessLabel}</span>
          </header>

          <div className={styles.panelBody}>
            <div className={styles.snapshotLead}>
              <div className={styles.snapshotStatus}>
                <span>最新情报 · {latestPublishedAt || "暂无"}</span>
                <strong>{freshnessLabel}</strong>
              </div>
              <strong className={styles.snapshotValue}>
                {String(activeArticleCount).padStart(2, "0")}
              </strong>
              <p className={styles.snapshotDescription}>{freshness.description}</p>
            </div>

            <dl className={styles.metricGrid}>
              <div><dt>有效来源</dt><dd>{healthySourceCount || sourceCount}</dd></div>
              <div><dt>平台类型</dt><dd>{platformCount}</dd></div>
              <div><dt>核心赛道</dt><dd>{bootstrap.sectorCount}</dd></div>
              <div><dt>今日情报</dt><dd>{todayArticleCount}</dd></div>
              <div><dt>本轮新收录</dt><dd>{newArticleCountLabel}</dd></div>
              <div><dt>最后成功发布</dt><dd>{processedAt}</dd></div>
            </dl>

            <div className={styles.qualityLedger}>
              <div className={styles.qualityHeader}>
                <span>RESEARCH OBJECT QUALITY</span>
                <strong>{qualityGate?.passed === false ? "REVIEW" : "PASSED"}</strong>
              </div>
              {trackingQuality ? (
                <div className={styles.qualityStats}>
                  <div><span>通过</span><strong>{trackingQuality.acceptedUserArticles}</strong></div>
                  <div><span>过滤</span><strong>{trackingQuality.rejectedUserArticles}</strong></div>
                  <div><span>重复聚合</span><strong>{trackingQuality.clusteredDuplicates}</strong></div>
                </div>
              ) : (
                <p className={styles.qualityEmpty}>等待研究对象质量统计。</p>
              )}
            </div>
          </div>
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p>05 / FOCUS COMPANIES</p>
              <h2>本周重点公司</h2>
            </div>
            <Link className={styles.panelLink} href="/companies">核心公司</Link>
          </header>

          <div className={styles.companyList}>
            {focusCompanies.map((company, index) => (
              <Link
                className={styles.companyCard}
                href={`/companies/${company.slug}`}
                key={company.slug}
              >
                <div className={styles.cardTop}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <i>{company.name.slice(0, 2).toUpperCase()}</i>
                </div>
                <h3>{company.name}</h3>
                <p>{company.focus}</p>
                <small>{company.region} · {company.stage}</small>
              </Link>
            ))}
          </div>
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p>06 / RESEARCH OBJECTS</p>
              <h2>四类研究对象</h2>
            </div>
            <Link className={styles.panelLink} href="/tracking">发布规则</Link>
          </header>

          <div className={styles.companyList}>
            {researchObjects.map((object, index) => (
              <Link className={styles.companyCard} href={object.href} key={object.href}>
                <div className={styles.cardTop}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <i>{object.code}</i>
                </div>
                <h3>{object.name}</h3>
                <p>{object.description}</p>
                <small>{object.count} 个公开对象</small>
              </Link>
            ))}
          </div>
        </article>
      </section>
    </>
  );
}

function EventTitle({ item }: { item: IntelligenceEvent }) {
  return (
    <SourceArticleLink href={item.source.url}>
      {item.title}
    </SourceArticleLink>
  );
}

function MarketSummary({
  market,
  sources,
  events,
  sector,
}: {
  market: string;
  sources: number;
  events: string;
  sector: string;
}) {
  return (
    <div className="market-summary">
      <div className="market-name">
        <span>{market === "中国" ? "CN" : "US"}</span>
        <strong>{market}</strong>
      </div>
      <dl>
        <div><dt>样本事件</dt><dd>{events}</dd></div>
        <div><dt>原始来源</dt><dd>{sources}</dd></div>
        <div><dt>高活跃赛道</dt><dd>{sector}</dd></div>
      </dl>
    </div>
  );
}
