import type { Metadata } from "next";
import { Cpu, Layers3, Network, RadioTower } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { coreTechnologyEntities } from "@/lib/core-research-objects";
import { buildTechnologyAnalysisSnapshot, type MomentumWindowComparison } from "@/lib/technology-momentum";
import {
  technologyTopicDefinitions,
  technologyTopicsForEntity,
  technologyTopicsForTrack,
} from "@/lib/technology-topics";
import { trackedSectors } from "@/lib/tracked-sectors";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "科技研究",
  description: "以核心赛道、重点技术主题和具体技术对象三层结构组织可追溯科技研究。",
};

function directionMark(direction: MomentumWindowComparison["direction"]) {
  if (direction === "up") return "↑";
  if (direction === "down") return "↓";
  if (direction === "new") return "NEW";
  return "→";
}

function growthLabel(momentum: MomentumWindowComparison) {
  if (!momentum.comparisonReady) return "积累中";
  if (momentum.growthPct === null) return "NEW";
  return `${momentum.growthPct > 0 ? "+" : ""}${momentum.growthPct}%`;
}

function weightedEventLabel(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function shortWindowLabel(prefix: string, momentum: MomentumWindowComparison) {
  const current = weightedEventLabel(momentum.currentWeightedEvents);
  if (!momentum.comparisonReady) return `${prefix} ${current} · 积累中`;
  return `${prefix} ${directionMark(momentum.direction)} ${current}`;
}

function momentumTitle(momentum: MomentumWindowComparison) {
  if (!momentum.comparisonReady) {
    return `当前窗口加权事件 ${weightedEventLabel(momentum.currentWeightedEvents)}；可靠 first-seen 观测历史尚不足 ${momentum.windowDays * 2} 天，暂不计算涨跌。`;
  }
  return `当前 ${momentum.windowDays} 日 ${weightedEventLabel(momentum.currentWeightedEvents)} / 前 ${momentum.windowDays} 日 ${weightedEventLabel(momentum.previousWeightedEvents)}`;
}

export default function TechnologyResearchPage() {
  const analysis = buildTechnologyAnalysisSnapshot();
  const trackMomentum = new Map(analysis.tracks.map((item) => [item.name, item]));
  const topicMomentum = new Map(analysis.topics.map((item) => [item.slug, item]));
  const entityTopicMap = new Map(
    coreTechnologyEntities.map((entity) => [
      entity.id,
      technologyTopicsForEntity(entity),
    ]),
  );
  const topicCards = technologyTopicDefinitions.map((topic) => ({
    topic,
    tracks: trackedSectors.filter((sector) =>
      technologyTopicsForTrack(sector).some((item) => item.slug === topic.slug),
    ),
    entities: coreTechnologyEntities.filter((entity) =>
      (entityTopicMap.get(entity.id) ?? []).some((item) => item.slug === topic.slug),
    ),
    momentum: topicMomentum.get(topic.slug),
  }));

  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">02 / TECHNOLOGY RESEARCH</p>
        <h1>科技研究</h1>
        <p className={styles.headerIntro}>
          用“核心赛道 → 重点技术主题 → 核心技术对象”组织研究入口。赛道保留产业结构与
          HeatScore；7 日趋势和 30 日 Momentum 只读取经过 taxonomy、赛道质量、规范赛道纠错、内容相关性与时间覆盖审计后的分析样本。原始赛道和原始事件始终保留为 provenance。
        </p>
        <div className={styles.headerChips}>
          <span><Network size={14} />{trackedSectors.length} 个核心赛道</span>
          <span><RadioTower size={14} />{technologyTopicDefinitions.length} 个重点技术主题</span>
          <span><Cpu size={14} />{coreTechnologyEntities.length} 个核心技术对象</span>
        </div>
        <div className={styles.analysisPolicy}>
          <span>分析时点 {analysis.asOf.slice(0, 10)}</span>
          <span>{analysis.population.canonicalCorrected} 条已确认规范赛道纠错</span>
          <span>{analysis.population.sectorExcluded} 条未复核高置信错分暂不计入赛道 Momentum</span>
          <span>{analysis.population.downweighted} 条待复核赛道事件降权</span>
          <span>{analysis.population.crossSector} 条合理跨赛道事件保留多赛道贡献</span>
          <span>{analysis.population.contentPartialEvidence} 条部分内容证据按 0.5 权重</span>
          <span>{analysis.population.contentWeakEvidence} 条弱内容证据按 0.25 权重</span>
          <span>
            可靠观测 {analysis.coverage.observedDays === null ? "待建立" : `${analysis.coverage.observedDays} 天`}
            {` · 7D ${analysis.coverage.sevenDayComparisonReady ? "可比" : "积累中"} · 30D ${analysis.coverage.thirtyDayComparisonReady ? "可比" : "积累中"}`}
          </span>
        </div>
      </header>

      <ChannelSplitLayout
        channel="technology"
        eyebrow="RESEARCH TAXONOMY"
        title="科技研究目录"
        description="先从产业赛道定位，再进入稳定技术主题，最后下钻到有证据的具体技术对象。"
        count={trackedSectors.length}
        countLabel="核心赛道"
        statusText={`${technologyTopicDefinitions.length} 主题 · ${coreTechnologyEntities.length} 技术对象`}
        icon={<Layers3 size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <section className={styles.layer} id="core-tracks">
          <div className={styles.layerHeader}>
            <div>
              <span className={styles.layerIndex}>L1 / CORE TRACKS</span>
              <h3>核心赛道</h3>
              <p>HeatScore 继续保留原算法；7D / 30D 只反映清洗后事件活跃度变化。已确认的规范赛道纠错只覆盖分析层，不回写原始事件；弱内容证据仅降权、不删除，历史观测不足完整对照窗口时只显示样本量，不输出涨跌。</p>
            </div>
            <span className={styles.layerCount}>{trackedSectors.length} 个赛道</span>
          </div>
          <div className={styles.trackGrid}>
            {trackedSectors.map((sector, index) => {
              const topics = technologyTopicsForTrack(sector);
              const momentum = trackMomentum.get(sector.name);
              return (
                <Link
                  href={`/technologies/tracks/${sector.slug}`}
                  className={styles.trackCard}
                  key={sector.slug}
                >
                  <div className={styles.cardTop}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{sector.heat}</strong>
                  </div>
                  <h4>{sector.name}</h4>
                  <p>{sector.events} 项公开事件 · {sector.institutions} 家活跃机构</p>
                  {momentum ? (
                    <div className={styles.momentumRow}>
                      <span title={momentumTitle(momentum.sevenDayTrend)}>
                        {shortWindowLabel("7D", momentum.sevenDayTrend)}
                      </span>
                      <span title={momentumTitle(momentum.thirtyDayMomentum)}>
                        30D {growthLabel(momentum.thirtyDayMomentum)}
                      </span>
                    </div>
                  ) : null}
                  <div className={styles.tagRow}>
                    {(topics.length ? topics.map((topic) => topic.name) : sector.subsectors)
                      .slice(0, 4)
                      .map((name) => <span key={name}>{name}</span>)}
                  </div>
                  <div className={styles.trackMeta}>
                    <span>{topics.length} 个重点主题</span>
                    <span>覆盖 {sector.completeness}%</span>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>

        <section className={styles.layer} id="technology-topics">
          <div className={styles.layerHeader}>
            <div>
              <span className={styles.layerIndex}>L2 / TECHNOLOGY TOPICS</span>
              <h3>重点技术主题</h3>
              <p>主题趋势保留赛道错分但主题证据仍成立的事件；待复核主题按 0.75 权重计入。明确命中重点技术主题的事件不因 crawler 低置信标签而额外降权；时间覆盖不足时同样不输出虚假的增长率。</p>
            </div>
            <span className={styles.layerCount}>{technologyTopicDefinitions.length} 个主题</span>
          </div>
          <div className={styles.topicGrid}>
            {topicCards.map(({ topic, tracks, entities, momentum }, index) => (
              <article className={styles.topicCard} id={`topic-${topic.slug}`} key={topic.slug}>
                <header>
                  <span>{String(index + 1).padStart(2, "0")} · ALERT {topic.alertQuery}</span>
                  <strong>{entities.length} 个技术对象</strong>
                </header>
                <h4>{topic.name}</h4>
                <p>{topic.description}</p>
                {momentum ? (
                  <div className={styles.momentumRow}>
                    <span title={momentumTitle(momentum.sevenDayTrend)}>
                      {shortWindowLabel("7D", momentum.sevenDayTrend)}
                    </span>
                    <span title={momentumTitle(momentum.thirtyDayMomentum)}>
                      30D {growthLabel(momentum.thirtyDayMomentum)}
                    </span>
                  </div>
                ) : null}
                <div className={styles.tagRow}>
                  {tracks.map((track) => (
                    <Link href={`/technologies/tracks/${track.slug}`} key={track.slug}>
                      {track.name}
                    </Link>
                  ))}
                </div>
                <div className={styles.topicMeta}>
                  <span>监测主词：{topic.alertQuery}</span>
                  <span>{tracks.length} 个关联赛道</span>
                </div>
                <div className={styles.topicEntities}>
                  {entities.length
                    ? `已归类：${entities.slice(0, 4).map((entity) => entity.name).join(" · ")}${entities.length > 4 ? " …" : ""}`
                    : "等待具体技术对象形成公开证据后自动挂接。"}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.layer} id="core-technologies">
          <div className={styles.layerHeader}>
            <div>
              <span className={styles.layerIndex}>L3 / TECHNOLOGY ENTITIES</span>
              <h3>核心技术对象</h3>
              <p>只收录已有公开证据、人工发现或研究记录的具体技术、模型、技术系统与关键能力；目录保持紧凑，详情保留摘要与可追溯时间线。</p>
            </div>
            <span className={styles.layerCount}>{coreTechnologyEntities.length} 个对象</span>
          </div>

          {coreTechnologyEntities.length ? (
            <div className={styles.entityGrid}>
              {coreTechnologyEntities.map((entity) => {
                const evidenceCount = entity.captureCount + entity.articleCount;
                const topics = entityTopicMap.get(entity.id) ?? [];
                return (
                  <Link
                    href={`/tracking/entities/topic/${entity.slug}`}
                    className={styles.entityCard}
                    key={entity.id}
                  >
                    <div className={styles.cardTop}>
                      <span>{evidenceCount} 条证据</span>
                      <strong>{entity.priority ? `P${entity.priority}` : evidenceCount}</strong>
                    </div>
                    <h4>{entity.name}</h4>
                    <p>
                      {entity.trackNames.length
                        ? entity.trackNames.slice(0, 2).join(" · ")
                        : "待建立赛道关联"}
                    </p>
                    <div className={styles.tagRow}>
                      {(topics.length ? topics.map((topic) => topic.name) : ["待归类"])
                        .slice(0, 3)
                        .map((name) => <span key={name}>{name}</span>)}
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <div className={styles.emptyNote}>
              暂无达到公开门槛的具体技术对象；对象会在出现可追溯证据、人工发现或研究记录后自动进入目录。
            </div>
          )}
        </section>
      </ChannelSplitLayout>
    </main>
  );
}
