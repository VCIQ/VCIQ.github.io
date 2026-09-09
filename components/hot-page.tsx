"use client";

import {
  Bookmark,
  Building2,
  ExternalLink,
  Flame,
  Search,
  Share2,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import institutionStyles from "@/components/hot-institution-ranking.module.css";
import styles from "@/components/hot-page.module.css";
import { useFavorites } from "@/components/use-favorites";
import { useHotness } from "@/components/use-hotness";
import { toggleFavorite, type FavoriteInput } from "@/lib/favorites";
import {
  INSTITUTION_HOT_WEIGHTS,
  rankInstitutionsByActivity,
} from "@/lib/institution-hot-ranking";
import { institutionDirectoryHref } from "@/lib/institution-activity";
import {
  HOTNESS_WEIGHTS,
  calculateHotnessScore,
  canonicalHotnessKey,
  metricsByHref,
  recordArticleOpen,
  recordArticleShare,
  setArticleFavorite,
  type HotnessInput,
} from "@/lib/hotness";
import { syncSharePreference } from "@/lib/share-preference-sync";
import type { ArticlePayload, LiveIntelligenceEvent } from "@/lib/use-articles";
import { useArticles } from "@/lib/use-articles";

const SHARE_REQUEST_EVENT = "vciq:favorite-share-request";
const DISPLAY_LIMIT = 100;
const INSTITUTION_LIMIT = 16;

type RankedArticle = {
  article: LiveIntelligenceEvent;
  score: number;
  opens: number;
  favorite: boolean;
  shares: number;
};

function favoriteInput(article: LiveIntelligenceEvent): FavoriteInput {
  return {
    id: article.id,
    href: article.source.url,
    title: article.title,
    summary: article.summary,
    channel: "technology",
    channelLabel: "09 热点",
    keywords: [article.type, article.region, article.sector],
    sectors: [article.sector],
    sources: [
      {
        name: article.source.name,
        url: article.source.url,
        level: article.source.level,
      },
    ],
    region: article.region,
    company: article.company,
    publishedAt: article.publishedAt,
    importance: article.importance,
    eventType: article.type,
  };
}

function hotnessInput(article: LiveIntelligenceEvent): HotnessInput {
  return {
    id: article.id,
    href: article.source.url,
    title: article.title,
    summary: article.summary,
    publishedAt: article.publishedAt,
    importance: article.importance,
    sourceName: article.source.name,
    channelLabel: "09 热点",
  };
}

function shareArticle(article: LiveIntelligenceEvent) {
  recordArticleShare(hotnessInput(article));
  const preferenceItem = favoriteInput(article);
  void syncSharePreference({
    ...preferenceItem,
    id: article.eventClusterId || article.id,
    sharedAt: new Date().toISOString(),
  });
  window.dispatchEvent(
    new CustomEvent(SHARE_REQUEST_EVENT, {
      detail: {
        title: article.title,
        summary: article.summary,
        url: article.source.url,
      },
    }),
  );
}

export function HotPage({ initialPayload }: { initialPayload: ArticlePayload }) {
  const { articles, generatedAt, refetch, isFetching } = useArticles(initialPayload, {
    enabled: false,
  });
  const hotness = useHotness();
  const favorites = useFavorites();
  const [query, setQuery] = useState("");
  const [onlyInteracted, setOnlyInteracted] = useState(false);
  const [fullArchiveLoaded, setFullArchiveLoaded] = useState(false);
  const [archiveError, setArchiveError] = useState(false);

  const favoriteKeys = useMemo(
    () => new Set(favorites.map((item) => canonicalHotnessKey(item.href)).filter(Boolean)),
    [favorites],
  );

  const allRanked = useMemo(() => {
    const metrics = metricsByHref(hotness);
    return articles
      .map<RankedArticle>((article) => {
        const key = canonicalHotnessKey(article.source.url);
        const item = metrics.get(key);
        const favorite = favoriteKeys.has(key) || item?.favorite === true;
        const opens = item?.opens ?? 0;
        const shares = item?.shares ?? 0;
        return {
          article,
          opens,
          favorite,
          shares,
          score: calculateHotnessScore({ opens, favorite, shares }),
        };
      })
      .sort(
        (left, right) =>
          right.score - left.score ||
          right.shares - left.shares ||
          Number(right.favorite) - Number(left.favorite) ||
          right.opens - left.opens ||
          right.article.importance - left.article.importance ||
          right.article.publishedAt.localeCompare(left.article.publishedAt) ||
          left.article.title.localeCompare(right.article.title, "zh-CN"),
      );
  }, [articles, favoriteKeys, hotness]);

  const articleEngagement = useMemo(
    () =>
      new Map(
        allRanked.map((item) => [
          canonicalHotnessKey(item.article.source.url),
          {
            opens: item.opens,
            favorite: item.favorite,
            shares: item.shares,
          },
        ] as const),
      ),
    [allRanked],
  );

  const rankedInstitutions = useMemo(
    () =>
      rankInstitutionsByActivity(articles, articleEngagement).slice(
        0,
        INSTITUTION_LIMIT,
      ),
    [articleEngagement, articles],
  );

  const interactedCount = useMemo(
    () => allRanked.filter((item) => item.score > 0).length,
    [allRanked],
  );

  const ranked = useMemo(() => {
    const needle = query.normalize("NFKC").trim().toLocaleLowerCase("zh-CN");
    return allRanked
      .filter((item) => !onlyInteracted || item.score > 0)
      .filter((item) => {
        if (!needle) return true;
        const article = item.article;
        return [
          article.title,
          article.summary,
          article.company,
          article.sector,
          article.type,
          article.region,
          article.source.name,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLocaleLowerCase("zh-CN").includes(needle));
      })
      .slice(0, DISPLAY_LIMIT);
  }, [allRanked, onlyInteracted, query]);

  const loadFullArchive = () => {
    if (fullArchiveLoaded || isFetching) return;
    setArchiveError(false);
    void refetch()
      .then(() => setFullArchiveLoaded(true))
      .catch(() => setArchiveError(true));
  };

  return (
    <>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">09 / HOT RANKING</p>
          <h1>热点</h1>
          <p className="intro-copy">
            文章榜根据当前浏览器的打开、收藏与分享行为实时排名；活跃机构榜则以爬虫识别到的机构文章、事件质量、来源等级和时间衰减为主，本地关注行为仅作小幅修正。
          </p>
        </div>
        <div className={styles.summary}>
          <span>{fullArchiveLoaded ? "完整文章池" : "部署候选池"}</span>
          <strong>{articles.length}</strong>
          <p>
            当前候选 · 总档案 {initialPayload.articleCount} 条 · 数据快照 {generatedAt.slice(0, 10)}
          </p>
          {!fullArchiveLoaded ? (
            <button
              type="button"
              className={styles.archiveButton}
              onClick={loadFullArchive}
              disabled={isFetching}
            >
              {isFetching ? "正在加载完整档案…" : "需要时加载完整档案"}
            </button>
          ) : null}
          {archiveError ? (
            <small className={styles.archiveStatus}>完整档案暂时不可用，当前候选池仍可正常使用。</small>
          ) : null}
        </div>
      </header>

      <section className={styles.weightBar} aria-label="热点排名权重">
        <div><ExternalLink size={15} /><span>打开</span><strong>× {HOTNESS_WEIGHTS.open}</strong></div>
        <div><Bookmark size={15} /><span>收藏</span><strong>× {HOTNESS_WEIGHTS.favorite}</strong></div>
        <div><Share2 size={15} /><span>分享</span><strong>× {HOTNESS_WEIGHTS.share}</strong></div>
        <p>
          机构活跃度：公开活动 {Math.round(INSTITUTION_HOT_WEIGHTS.crawlerActivity * 100)}% + 本地关注 {Math.round(INSTITUTION_HOT_WEIGHTS.localAttention * 100)}%；同一事件簇去重，时间半衰期 {INSTITUTION_HOT_WEIGHTS.halfLifeDays} 天。
        </p>
      </section>

      <section className={institutionStyles.board} aria-label="09 热点活跃机构排名">
        <header className={institutionStyles.header}>
          <div>
            <p>ACTIVE INSTITUTIONS</p>
            <h2>活跃机构</h2>
          </div>
          <span>{rankedInstitutions.length} 家 · 关联投资机构目录</span>
        </header>
        {rankedInstitutions.length ? (
          <div className={institutionStyles.ranking}>
            {rankedInstitutions.map((item, index) => {
              const institution = item.relation.institution;
              return (
                <Link
                  className={institutionStyles.row}
                  href={institutionDirectoryHref(institution)}
                  key={institution.name}
                >
                  <span className={institutionStyles.rank} data-top={index < 3 ? "true" : "false"}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <Building2 size={17} aria-hidden="true" />
                  <div className={institutionStyles.main}>
                    <strong>{institution.name}</strong>
                    <small>
                      {institution.region} · {institution.type} · 直接文章 {item.directArticleCount} 条 · 组合关联 {item.portfolioArticleCount} 条 · 本地关注分 {item.attentionScore}
                    </small>
                  </div>
                  <dl className={institutionStyles.signals}>
                    <div><dt>活跃度</dt><dd>{item.score}</dd></div>
                    <div><dt>公开分</dt><dd>{item.crawlerScore}</dd></div>
                    <div><dt>文章</dt><dd>{item.articleCount}</dd></div>
                    <div><dt>来源</dt><dd>{item.sourceCount}</dd></div>
                  </dl>
                </Link>
              );
            })}
          </div>
        ) : (
          <div className={institutionStyles.empty}>
            <Building2 size={24} />
            <strong>暂无可核对的机构—文章关联</strong>
            <p>系统不会仅凭宽泛标签生成机构排名；需要直接机构提及或公开被投组合关系。</p>
          </div>
        )}
      </section>

      <div className={styles.toolbar}>
        <div className={styles.tabs} aria-label="热点榜范围">
          <button
            type="button"
            className={!onlyInteracted ? styles.active : ""}
            onClick={() => setOnlyInteracted(false)}
          >
            全部文章
          </button>
          <button
            type="button"
            className={onlyInteracted ? styles.active : ""}
            onClick={() => setOnlyInteracted(true)}
          >
            已互动 {interactedCount}
          </button>
        </div>
        <label className={styles.search}>
          <Search size={15} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索热点文章、公司或赛道"
            aria-label="搜索热点文章"
          />
        </label>
      </div>

      <section className={styles.ranking} aria-label="09 热点文章排名">
        {ranked.length ? (
          ranked.map(({ article, score, opens, favorite, shares }, index) => {
            const input = favoriteInput(article);
            return (
              <article className={styles.row} key={article.id}>
                <div className={styles.rank} data-top={index < 3 ? "true" : "false"}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <Flame size={15} aria-hidden="true" />
                </div>

                <a
                  className={styles.main}
                  href={article.source.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => recordArticleOpen(hotnessInput(article))}
                >
                  <div className={styles.meta}>
                    <span>{article.type}</span>
                    <span>{article.region}</span>
                    <span>{article.sector}</span>
                    <time>{article.publishedAt}</time>
                  </div>
                  <h2>{article.title}</h2>
                  <p>{article.summary}</p>
                  <small>{article.source.level} · {article.source.name} ↗</small>
                </a>

                <div className={styles.signals} aria-label={`热点分 ${score}`}>
                  <strong>{score}</strong>
                  <span>热点分</span>
                  <dl>
                    <div><dt>打开</dt><dd>{opens}</dd></div>
                    <div><dt>收藏</dt><dd>{favorite ? 1 : 0}</dd></div>
                    <div><dt>分享</dt><dd>{shares}</dd></div>
                  </dl>
                  <div className={styles.actions}>
                    <button
                      type="button"
                      data-active={favorite ? "true" : "false"}
                      onClick={() => {
                        const next = toggleFavorite(input);
                        setArticleFavorite(hotnessInput(article), next);
                      }}
                      aria-label={favorite ? `取消收藏：${article.title}` : `收藏：${article.title}`}
                    >
                      <Bookmark size={14} fill={favorite ? "currentColor" : "none"} />
                    </button>
                    <button
                      type="button"
                      onClick={() => shareArticle(article)}
                      aria-label={`分享：${article.title}`}
                    >
                      <Share2 size={14} />
                    </button>
                  </div>
                </div>
              </article>
            );
          })
        ) : (
          <div className={styles.empty}>
            <Flame size={28} />
            <strong>当前条件下没有热点文章</strong>
            <p>关闭“已互动”筛选或更换搜索词后再试。</p>
          </div>
        )}
      </section>

      <p className={styles.disclosure}>
        文章热点统计仍只保存在当前浏览器；“分享”会在已登录的情况下额外以私有偏好信号同步到 Tracking Admin，用于后续个性化学习，不公开个人行为记录。
      </p>
    </>
  );
}
