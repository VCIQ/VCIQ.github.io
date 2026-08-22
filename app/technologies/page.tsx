import type { Metadata } from "next";
import { Cpu, Layers3, Network, RadioTower } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { coreTechnologyEntities } from "@/lib/core-research-objects";
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

export default function TechnologyResearchPage() {
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
  }));

  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">02 / TECHNOLOGY RESEARCH</p>
        <h1>科技研究</h1>
        <p className={styles.headerIntro}>
          用“核心赛道 → 重点技术主题 → 核心技术对象”组织研究入口。赛道保留产业结构与
          HeatScore，技术主题承接稳定监测 taxonomy，具体技术对象只在形成公开证据后进入目录。
        </p>
        <div className={styles.headerChips}>
          <span><Network size={14} />{trackedSectors.length} 个核心赛道</span>
          <span><RadioTower size={14} />{technologyTopicDefinitions.length} 个重点技术主题</span>
          <span><Cpu size={14} />{coreTechnologyEntities.length} 个核心技术对象</span>
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
              <p>保留产业结构、样本公司、机构、HeatScore 与长期研究变量；这里不与具体技术对象混排。</p>
            </div>
            <span className={styles.layerCount}>{trackedSectors.length} 个赛道</span>
          </div>
          <div className={styles.trackGrid}>
            {trackedSectors.map((sector, index) => {
              const topics = technologyTopicsForTrack(sector);
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
              <p>固定主题层用于承接 Google Alerts 等稳定监测入口；英文别名、缩写和具体产品继续由后端 taxonomy 扩展。</p>
            </div>
            <span className={styles.layerCount}>{technologyTopicDefinitions.length} 个主题</span>
          </div>
          <div className={styles.topicGrid}>
            {topicCards.map(({ topic, tracks, entities }, index) => (
              <article className={styles.topicCard} id={`topic-${topic.slug}`} key={topic.slug}>
                <header>
                  <span>{String(index + 1).padStart(2, "0")} · ALERT {topic.alertQuery}</span>
                  <strong>{entities.length} 个技术对象</strong>
                </header>
                <h4>{topic.name}</h4>
                <p>{topic.description}</p>
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
