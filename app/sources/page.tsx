import type { Metadata } from "next";
import { ArrowUpRight, Radio, ShieldCheck } from "lucide-react";
import {
  coreSourceStats,
  coreSourcesByKind,
  type CoreSourceKind,
} from "@/lib/core-sources";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "核心信源",
  description: "将微信公众号、专业媒体、研究机构与官方原始来源作为第五类研究对象，按赛道、人物、公司与技术覆盖持续评估。",
};

const groups: Array<{
  kind: CoreSourceKind;
  eyebrow: string;
  title: string;
  description: string;
}> = [
  {
    kind: "微信公众号",
    eyebrow: "WECHAT PRECISION SOURCES",
    title: "微信公众号",
    description: "人工配置的中文科技与产业精确信源；按赛道关键词、公司和人物增强微信公开索引发现。",
  },
  {
    kind: "官方 / 原始",
    eyebrow: "PRIMARY SOURCES",
    title: "官方与原始来源",
    description: "公司、研究机构、监管或原始材料入口，优先承担事实核验和关键结论回溯。",
  },
  {
    kind: "媒体 / 研究",
    eyebrow: "MEDIA & RESEARCH SOURCES",
    title: "专业媒体与研究来源",
    description: "用于发现产业变化、融资、产品和研究进展；结论仍需结合独立来源与原始材料交叉验证。",
  },
];

export default function SourcesPage() {
  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / CORE SOURCES</p>
        <h1>核心信源</h1>
        <p>
          信源不是文章的附属字段，而是 VCIQ 的第五类研究对象。这里记录哪些公众号、专业媒体、研究机构和官方入口值得持续观察，
          并把它们与赛道、技术、人物、公司及研究线索连接起来。
        </p>
        <div className="hero-chips">
          <span>{coreSourceStats.total} 个已配置重点信源</span>
          <span>{coreSourceStats.wechat} 个微信公众号</span>
          <span>{coreSourceStats.official} 个官方 / 原始来源</span>
          <span>{coreSourceStats.sectors} 个显式赛道覆盖</span>
        </div>
      </header>

      <details className={styles.lifecycle}>
        <summary>
          <span>SOURCE LIFECYCLE</span>
          <strong>Candidate → Tracked → Core</strong>
          <small>展开查看信源升级规则</small>
        </summary>
        <div className={styles.lifecycleDetails}>
          <p>
            单篇高价值文章只产生候选信号；持续命中率、直接证据比例、跨日稳定性与人工判断共同决定是否升级。
          </p>
          <div className={styles.lifecycleFlow}>
            <div>
              <strong>Candidate</strong>
              <p>由收藏、研究线索或自动发现提出。</p>
            </div>
            <div>
              <strong>Tracked</strong>
              <p>人工确认后进入持续抓取与质量观测。</p>
            </div>
            <div>
              <strong>Core</strong>
              <p>多期证据稳定后成为长期研究入口。</p>
            </div>
          </div>
        </div>
      </details>

      {groups.map((group) => {
        const sources = coreSourcesByKind(group.kind);
        if (!sources.length) return null;
        return (
          <section className={styles.group} key={group.kind}>
            <div className={styles.groupHeader}>
              <div>
                <span>{group.eyebrow}</span>
                <h2>{group.title}</h2>
              </div>
              <strong>{sources.length} 个已追踪</strong>
            </div>
            <p className="intro-copy">{group.description}</p>

            <div className={styles.grid}>
              {sources.map((source) => (
                <article className={styles.card} id={source.id.replace(/[:]/g, "-")} key={source.id}>
                  <div className={styles.cardHead}>
                    <div>
                      <div className={styles.cardMeta}>
                        {source.region} · {source.platform} · {source.sourceLevel}
                      </div>
                      <h3>{source.name}</h3>
                    </div>
                    <span className={styles.status}>TRACKED</span>
                  </div>

                  <div className={styles.coverageRow} aria-label="覆盖摘要">
                    {source.sectors.length ? <span>{source.sectors.length} 赛道</span> : null}
                    {source.companies.length ? <span>{source.companies.length} 公司</span> : null}
                    {source.people.length ? <span>{source.people.length} 人物</span> : null}
                    {source.keywords.length ? <span>{source.keywords.length} 发现词</span> : null}
                  </div>

                  {source.sectors.length ? (
                    <div className={styles.tags} aria-label="覆盖赛道">
                      {source.sectors.slice(0, 5).map((sector) => (
                        <span key={sector}>{sector}</span>
                      ))}
                    </div>
                  ) : null}

                  {source.keywords.length ? (
                    <div className={styles.signalBlock}>
                      <span className={styles.signalLabel}>重点发现词</span>
                      <p>{source.keywords.slice(0, 8).join(" · ")}</p>
                    </div>
                  ) : null}

                  {source.companies.length ? (
                    <div className={styles.signalBlock}>
                      <span className={styles.signalLabel}>重点公司</span>
                      <p>{source.companies.slice(0, 6).join(" · ")}</p>
                    </div>
                  ) : null}

                  {source.people.length ? (
                    <div className={styles.signalBlock}>
                      <span className={styles.signalLabel}>重点人物</span>
                      <p>{source.people.slice(0, 6).join(" · ")}</p>
                    </div>
                  ) : null}

                  <div className={styles.cardFooter}>
                    <span><Radio size={11} aria-hidden="true" /> 持续追踪</span>
                    {source.url ? (
                      <a href={source.url} target="_blank" rel="noreferrer">
                        原始入口 <ArrowUpRight size={12} />
                      </a>
                    ) : (
                      <span>微信公众号精确信源</span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        );
      })}

      <section className={styles.group} aria-label="信源治理原则">
        <div className={styles.groupHeader}>
          <div>
            <span>SOURCE GOVERNANCE</span>
            <h2>信源进入核心层的约束</h2>
          </div>
          <ShieldCheck size={20} aria-hidden="true" />
        </div>
        <div className={styles.governance}>
          <article>
            <strong>文章价值 ≠ 媒体价值</strong>
            <p>单篇优秀文章只产生候选信号；不因一次收藏就把整个公众号或媒体升级为核心信源。</p>
          </article>
          <article>
            <strong>来源 × 赛道分别评估</strong>
            <p>同一媒体可能在 AI 很强、在半导体很弱；质量权重按具体来源—赛道组合积累，而不是给媒体一个全局万能分数。</p>
          </article>
          <article>
            <strong>强证据可以绕过来源惩罚</strong>
            <p>官方披露、原始材料、高置信公司匹配或人工规范纠错等强证据优先，不因历史来源噪声误伤关键事实。</p>
          </article>
        </div>
      </section>
    </main>
  );
}
