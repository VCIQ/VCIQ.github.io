import type { Metadata } from "next";
import { ArrowUpRight, Radio, ShieldCheck } from "lucide-react";
import {
  coreSourceStats,
  coreSourcesByKind,
  type CoreSourceKind,
  type SourceHealthStatus,
  type SourceRole,
} from "@/lib/core-sources";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "重点信源",
  description: "将微信公众号、专业媒体、公司官方来源、监管机构与原始材料作为第五类研究对象，并公开呈现角色、生命周期与采集健康。",
};

const groups: Array<{
  kind: CoreSourceKind;
  eyebrow: string;
  title: string;
  description: string;
}> = [
  {
    kind: "微信公众号",
    eyebrow: "DISCOVERY SOURCES",
    title: "微信公众号",
    description: "中文科技与产业精确信源主要承担发现职责；采集健康与媒体本身分开评估，微信索引失效不等于 Publisher 失效。",
  },
  {
    kind: "官方 / 原始",
    eyebrow: "PRIMARY SOURCES",
    title: "官方与原始来源",
    description: "直接读取已配置的公司官方来源与监管披露入口，优先承担事实核验和关键结论回溯；未配置稳定新闻入口的公司保留为 Candidate。",
  },
  {
    kind: "媒体 / 研究",
    eyebrow: "CORROBORATION SOURCES",
    title: "专业媒体与研究来源",
    description: "用于发现与交叉验证产业变化、融资、产品和研究进展；关键结论仍回到 Primary Source 核验。",
  },
];

const healthLabels: Record<SourceHealthStatus, string> = {
  ok: "OK",
  partial: "PARTIAL",
  error: "ERROR",
  unknown: "UNKNOWN",
};

const roleLabels: Record<SourceRole, string> = {
  primary: "PRIMARY",
  corroboration: "CORROBORATION",
  discovery: "DISCOVERY",
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
          <span>{coreSourceStats.primary} 个 Primary Source</span>
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
                      <span className={styles.roleStatus}>{roleLabels[source.sourceRole]}</span>
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
                      <span>暂无稳定公开入口</span>
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
          <small>生命周期、证据角色与采集健康相互独立</small>
        </summary>
        <div className={styles.lifecycleDetails}>
          <p>
            Candidate 表示已进入信源图但尚未建立稳定采集入口；Tracked 表示已配置持续采集；Core 只会在多期质量稳定并完成人工复核后产生。
            PRIMARY / CORROBORATION / DISCOVERY 描述证据角色，OK / PARTIAL / ERROR 描述采集通道健康，三者不再混为一个状态。
          </p>
          <div className={styles.lifecycleFlow}>
            <div>
              <strong>Candidate</strong>
              <p>已有明确 Publisher，但稳定采集入口或质量证据仍不足。</p>
            </div>
            <div>
              <strong>Tracked</strong>
              <p>已配置持续抓取与质量观测，尚不自动等价于核心信源。</p>
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
          <strong>证据角色与信源频道说明</strong>
          <small>展开查看</small>
        </summary>
        <p>
          Primary Source 包括公司官网、监管/交易所披露与原始材料；Corroboration Source 用于独立交叉验证；Discovery Source 负责高召回发现。
          Publisher 表示媒体、机构或公司本身，Collection Endpoint 表示微信索引、官网、RSS、监管接口或公开网页等采集通道。
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
            <p>同一 Publisher 的微信、官网、RSS 与公开镜像分别记录健康；可靠备用通道可用时，不把 Publisher 整体误判为失效。</p>
          </article>
          <article>
            <strong>发现 ≠ 事实确认</strong>
            <p>微信公众号与媒体负责发现和交叉验证；重大公司、融资、监管和产品事实优先回溯公司官网、交易所、监管文件或原始材料。</p>
          </article>
          <article>
            <strong>Core 必须经过质量门槛</strong>
            <p>Tracked 不自动升级为 Core；持续可用性、有效产出、跨日稳定性和人工复核共同决定是否晋级。</p>
          </article>
        </div>
      </section>
    </main>
  );
}
