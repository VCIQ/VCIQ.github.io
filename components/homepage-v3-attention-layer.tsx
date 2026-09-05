import Link from "next/link";
import styles from "@/components/homepage-v3-attention-layer.module.css";
import type { RankedIntelligenceProjectionItem } from "@/lib/ranked-intelligence";
import { trackedSectors } from "@/lib/tracked-sectors";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

const FOR_YOU_LIMIT = 6;
const MAX_PER_TRACK = 2;
const MAX_PER_SOURCE = 2;
const CHANNEL_LIMIT = 6;

const eventTypeLabels: Record<string, string> = {
  Funding: "融资",
  "M&A": "并购",
  IPO: "IPO",
  Product: "产品",
  Technology: "技术",
  Research: "研究",
  Patent: "专利",
  Partnership: "合作",
  Personnel: "人事",
  Policy: "政策",
  Market: "市场",
  Production: "产能",
  Order: "订单",
};

function normalizeKey(value: string) {
  return value.normalize("NFKC").trim().toLocaleLowerCase("en-US");
}

function uniqueStrings(values: string[], limit: number) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw.trim();
    const key = normalizeKey(value);
    if (!value || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
    if (result.length >= limit) break;
  }
  return result;
}

function primaryTrack(item: RankedIntelligenceProjectionItem) {
  return item.tracks[0]?.trim() || "跨赛道精选";
}

function selectDiverseRecommendations(items: RankedIntelligenceProjectionItem[]) {
  const selected: RankedIntelligenceProjectionItem[] = [];
  const selectedIds = new Set<string>();
  const trackCounts = new Map<string, number>();
  const sourceCounts = new Map<string, number>();

  const tryAdd = (item: RankedIntelligenceProjectionItem, enforceCaps: boolean) => {
    if (selectedIds.has(item.id)) return;
    const track = normalizeKey(primaryTrack(item));
    const source = normalizeKey(item.source);
    if (enforceCaps && (trackCounts.get(track) ?? 0) >= MAX_PER_TRACK) return;
    if (enforceCaps && source && (sourceCounts.get(source) ?? 0) >= MAX_PER_SOURCE) return;

    selected.push(item);
    selectedIds.add(item.id);
    trackCounts.set(track, (trackCounts.get(track) ?? 0) + 1);
    if (source) sourceCounts.set(source, (sourceCounts.get(source) ?? 0) + 1);
  };

  for (const item of items) {
    if (selected.length >= FOR_YOU_LIMIT) break;
    tryAdd(item, true);
  }
  for (const item of items) {
    if (selected.length >= FOR_YOU_LIMIT) break;
    tryAdd(item, false);
  }

  return selected;
}

function publicRecommendationReasons(item: RankedIntelligenceProjectionItem) {
  const reasons: string[] = [];
  if (item.priority === "P0") reasons.push("P0 高优先级");
  else if (item.priority === "P1") reasons.push("P1 重点观察");

  if (item.tracks[0]) reasons.push(`关联 ${item.tracks[0]}`);
  if (item.entities[0]?.name) reasons.push(`命中 ${item.entities[0].name}`);
  if (item.duplicateCount > 1) reasons.push(`${item.duplicateCount} 个同事件来源`);
  if (item.eventTypes[0]) reasons.push(eventTypeLabels[item.eventTypes[0]] ?? item.eventTypes[0]);

  return uniqueStrings(reasons, 3);
}

function formatTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

function trackHref(track: string) {
  const key = normalizeKey(track);
  const matched = trackedSectors.find(
    (sector) =>
      normalizeKey(sector.name) === key ||
      sector.aliases.some((alias) => normalizeKey(alias) === key),
  );
  return matched ? `/technology/${matched.slug}` : "/technology";
}

function channelTracks(items: RankedIntelligenceProjectionItem[]) {
  return uniqueStrings(items.flatMap((item) => item.tracks), CHANNEL_LIMIT);
}

export function HomepageV3AttentionLayer({
  rankedItems,
  todayItems,
}: {
  rankedItems: RankedIntelligenceProjectionItem[];
  todayItems: LiveIntelligenceEvent[];
}) {
  const forYouItems = selectDiverseRecommendations(rankedItems);
  const channels = channelTracks(rankedItems);

  if (!forYouItems.length && !todayItems.length) return null;

  return (
    <section className={styles.layer} aria-labelledby="homepage-v3-heading">
      <nav className={styles.channelBar} aria-label="首页情报频道">
        <a className={styles.channelActive} href="#for-you">推荐</a>
        <a href="#today-must-read">今日必看</a>
        <Link href="/favorites">关注</Link>
        {channels.map((track) => (
          <Link key={track} href={trackHref(track)}>{track}</Link>
        ))}
      </nav>

      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>VCIQ V3 · PERSONAL INTELLIGENCE FEED</p>
          <h1 id="homepage-v3-heading">先把最可能改变判断的事件推到面前</h1>
          <p>
            首屏直接消费后台 Ranked Intelligence 投影；推荐理由只展示公开可解释信号，不暴露私有 Feedback、身份或查询细节。
          </p>
        </div>
        <div className={styles.headerMeta}>
          <strong>{rankedItems.length}</strong>
          <span>本轮推荐候选</span>
          <small>展示层额外做赛道 / 来源多样性重排</small>
        </div>
      </header>

      <div className={styles.layout}>
        <div className={styles.feed} id="for-you">
          <div className={styles.sectionHeading}>
            <div>
              <p>01 / FOR YOU</p>
              <h2>为你推荐</h2>
            </div>
            <span>显式偏好排序 → 公开安全投影 → 多样性重排</span>
          </div>

          <div className={styles.feedList}>
            {forYouItems.map((item, index) => {
              const reasons = publicRecommendationReasons(item);
              return (
                <article
                  className={`${styles.feedCard} ${index === 0 ? styles.feedCardFeatured : ""}`}
                  key={item.id}
                >
                  <div className={styles.cardTopline}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <span>{item.priority}</span>
                    <span>{primaryTrack(item)}</span>
                    <time dateTime={item.publishedAt}>{formatTime(item.publishedAt)}</time>
                  </div>
                  <h3>
                    <a href={item.href} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                  </h3>
                  {item.summary ? <p className={styles.summary}>{item.summary}</p> : null}
                  <div className={styles.cardFooter}>
                    <div className={styles.reasonGroup} aria-label="推荐依据">
                      {reasons.map((reason) => <span key={reason}>{reason}</span>)}
                    </div>
                    <div className={styles.scoreBlock}>
                      <strong>{item.score}</strong>
                      <span>相关度</span>
                    </div>
                  </div>
                  <div className={styles.sourceLine}>
                    <span>{item.source}</span>
                    {item.duplicateCount > 1 ? <span>{item.duplicateCount} 条同事件聚合</span> : null}
                    <a href={item.href} target="_blank" rel="noreferrer">查看原文 ↗</a>
                  </div>
                </article>
              );
            })}
          </div>
        </div>

        <aside className={styles.mustRead} id="today-must-read" aria-labelledby="today-must-read-heading">
          <div className={styles.sectionHeading}>
            <div>
              <p>02 / DAILY MUST READ</p>
              <h2 id="today-must-read-heading">今日必看</h2>
            </div>
          </div>
          <p className={styles.mustReadIntro}>
            与个性化推荐分开：这里保留 Daily Brief 的事件级去重、来源与赛道多样性逻辑。
          </p>
          <ol className={styles.mustReadList}>
            {todayItems.map((item, index) => (
              <li key={item.id}>
                <span className={styles.mustReadRank}>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <a href={item.source.url} target="_blank" rel="noreferrer">{item.title}</a>
                  <small>{item.sector} · {item.source.name}</small>
                </div>
                <strong>{item.importance}</strong>
              </li>
            ))}
          </ol>
          <div className={styles.boundaryNote}>
            <strong>当前边界</strong>
            <p>本阶段只重构首屏注意力分配，不改变追踪目录、Resolver 权限或后台写入语义。</p>
          </div>
        </aside>
      </div>
    </section>
  );
}
