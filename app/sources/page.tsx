import type { Metadata } from "next";
import { ArrowUpRight, Radio, ShieldCheck } from "lucide-react";
import {
  coreSourceStats,
  coreSourcesByKind,
  type CoreSourceKind,
  type SourceHealthStatus,
} from "@/lib/core-sources";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "重点信源",
  description: "将微信公众号、专业媒体、研究机构与官方原始来源作为第五类研究对象，并公开呈现实际采集健康与信源生命周期。",
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
    description: "人工配置的中文科技与产业精确信源；采集健康与媒体本身分开评估，微信索引失效不等于 Publisher 失效。",
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

const healthLabels: Record<SourceHealthStatus, string> = {
  ok: "OK",
  partial: "PARTIAL",
  error: "ERROR",
  unknown: "UNKNOWN",
};

function healthClass(status: SourceHealthStatus): string {
  if (status === "ok") return styles.healthOk;
  if (status === "partial") return styles.healthPartial;
  if (status === "error") return styles.healthError;
  return styles.healthUnknown;
}

function compactDate(value?: string): string {
  return value ? value.slice(0, 10) : "尚无成功记录";
}

export default function SourcesPage() {
  const issueCount = coreSourceStats.partial + coreSourceStats.error;

  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / SOURCE GOVERNANCE</p>
        <h1>重点信源</h1>
        <div className="hero-chips">
          <span>{coreSourceStats.total} 个已配置 Publisher</span>
          <span>{coreSourceStats.healthy} 个当前健康</span>
          <span>{issueCount} 个存在采集异常</span>
          <span>{coreSourceStats.sectors} 个显式赛道覆盖</span>
        </div>
      </header>

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
              <strong>{sources.length} 个 Publisher</strong>
            </div>

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
                    <div className={styles.statusStack} aria-label="信源状态">
                      <span className={styles.lifecycleStatus}>{source.lifecycle.toUpperCase()}</span>
                      <span className={`${styles.healthStatus} ${healthClass(source.healthStatus)}`}>
                        {healthLabels[source.healthStatus]}
                      </span>
                    </div>
                  </div>

                  <div className={styles.coverageRow} aria-label="覆盖摘要">
                    {source.sectors.length ? <span>{source.sectors.length} 赛道</span> : null}
                    {source.companies.length ? <span>{source.companies.length} 公司</span> : null}
                    {source.people.length ? <span>{source.people.length} 人物</span> : null}
                    <span>{source.endpoints.length} 采集通道</span>
                  </div>

                  {source.sectors.length ? (
                    <div className={styles.tags} aria-label="覆盖赛道">
                      {source.sectors.slice(0, 5).map((sector) => (
                        <span key={sector}>{sector}</span>
                      ))}
                    </div>
                  ) : null}

                  <div className={styles.endpointBlock} aria-label="采集通道健康">
                    <div className={styles.endpointHeader}>
                      <span>COLLECTION ENDPOINTS</span>
                      <small>Publisher 与采集通道分离</small>
                    </div>
                    <div className={styles.endpointList}>
                      {source.endpoints.slice(0, 4).map((endpoint) => (
                        <div className={styles.endpointRow} key={endpoint.id}>
                          <div>
                            <strong>{endpoint.label}</strong>
                            <small>
                              {endpoint.evidenceGrade ? `Grade ${endpoint.evidenceGrade} · ` : ""}
                              扫描 {endpoint.scanned} · 接受 {endpoint.accepted}
                            </small>
                          </div>
                          <div className={styles.endpointState}>
                            <span className={`${styles.healthDot} ${healthClass(endpoint.status)}`} aria-hidden="true" />
                            <strong>{healthLabels[endpoint.status]}</strong>
                            <small>{compactDate(endpoint.lastSuccessAt)}</small>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

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
                    <span>
                      <Radio size={11} aria-hidden="true" />
                      健康快照 {source.healthUpdatedAt?.slice(0, 10) || "不可用"}
                    </span>
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
            <p className="intro-copy">{group.description}</p>
          </section>
        );
      })}

      <details className={styles.lifecycle}>
        <summary>
          <span>SOURCE LIFECYCLE</span>
          <strong>Candidate → Tracked → Core</strong>
          <small>生命周期与采集健康是两个独立维度</small>
        </summary>
        <div className={styles.lifecycleDetails}>
          <p>
            当前 Publisher 的生命周期单独显示为 Candidate、Tracked 或 Core；OK / PARTIAL / ERROR 只描述采集通道健康，
            不再用 TRACKED 掩盖 Collector 故障。
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
              <p>多期证据稳定并完成人工复核后成为长期研究入口。</p>
            </div>
          </div>
        </div>
      </details>

      <details className={styles.methodology}>
        <summary>
          <span>SOURCE RESEARCH METHOD</span>
          <strong>信源频道说明</strong>
          <small>展开查看</small>
        </summary>
        <p>
          信源是 VCIQ 的第五类研究对象。Publisher 表示媒体、机构或公司本身；Collection Endpoint 表示微信索引、官网、
          RSS、公开网页等采集通道。同一个 Publisher 可以有多个 Endpoint，一个通道失败不再等价于整个信源失效。
        </p>
      </details>

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
            <strong>Publisher ≠ Collection Endpoint</strong>
            <p>同一 Publisher 的微信、官网、RSS 与公开镜像分别记录健康；只要可靠备用通道可用，就不把 Publisher 整体误判为失效。</p>
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
