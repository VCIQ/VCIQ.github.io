import type { Metadata } from "next";
import { ArrowUpRight, Radio, ShieldCheck } from "lucide-react";
import {
  sourceDirectoryStats,
  sourcesByDirectoryKind,
  type SourceDirectoryKind,
  type SourceHealthStatus,
  type SourceRole,
} from "@/lib/source-directory";
import type { SourcePromotionState } from "@/lib/source-lifecycle";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "重点信源",
  description: "将微信公众号、X 发现源、原始研究论文、专业媒体、公司官方来源与监管材料统一纳入 Source Entity 模型，并公开呈现角色、生命周期与采集健康。",
};

const groups: Array<{
  kind: SourceDirectoryKind;
  eyebrow: string;
  title: string;
  description: string;
}> = [
  {
    kind: "微信公众号",
    eyebrow: "DISCOVERY SOURCES",
    title: "微信公众号",
    description: "中文科技与产业精确信源主要承担发现职责；采集健康与媒体本身分开评估，微信索引失效不等于 Source Entity 失效。",
  },
  {
    kind: "X / 发现",
    eyebrow: "DISCOVERY SOURCES",
    title: "X Profiles",
    description: "组织与研究者的 X Profile 作为高时效发现入口单独管理，不与公司官网、论文和监管披露等 Primary Sources 混合；后续事实结论仍需要回到原始材料核验。",
  },
  {
    kind: "论文 / 原始研究",
    eyebrow: "PRIMARY RESEARCH SOURCES",
    title: "论文与原始研究",
    description: "直接读取已配置的论文仓库与原始研究检索入口。当前启用的 arXiv 采集不再只存在于 crawler 配置，而是进入 Source Governance、Collector Health 与生命周期模型。",
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

const promotionLabels: Record<SourcePromotionState, string> = {
  candidate: "NOT ELIGIBLE",
  evidence_pending: "EVIDENCE PENDING",
  review_pending: "CORE READY / REVIEW",
  blocked: "BLOCKED",
  core: "CORE",
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

function hasObservedEndpoint(
  endpoints: Array<{ status: SourceHealthStatus; sourceIds: string[] }>,
): boolean {
  return endpoints.some(
    (endpoint) => endpoint.sourceIds.length > 0 && endpoint.status !== "unknown",
  );
}

export default function SourcesPage() {
  const issueCount = sourceDirectoryStats.partial + sourceDirectoryStats.error;

  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / SOURCE GOVERNANCE</p>
        <h1>重点信源</h1>
        <div className="hero-chips">
          <span>{sourceDirectoryStats.total} 个 Source Entity</span>
          <span>{sourceDirectoryStats.primary} 个 Primary Source</span>
          <span>{sourceDirectoryStats.papers} 个原始研究源</span>
          <span>{sourceDirectoryStats.xProfiles} 个 X Discovery Source</span>
          <span>{sourceDirectoryStats.healthy} 个当前健康</span>
          <span>{issueCount} 个存在采集异常</span>
          <span>{sourceDirectoryStats.unknown} 个 Unobserved / 未建立观测</span>
          <span>{sourceDirectoryStats.evidencePending} 个等待晋级证据</span>
          <span>{sourceDirectoryStats.reviewPending} 个 Core Ready</span>
        </div>
      </header>

      {groups.map((group) => {
        const sources = sourcesByDirectoryKind(group.kind);
        if (!sources.length) return null;
        return (
          <section className={styles.group} key={group.kind}>
            <div className={styles.groupHeader}>
              <div>
                <span>{group.eyebrow}</span>
                <h2>{group.title}</h2>
              </div>
              <strong>{sources.length} 个信源实体</strong>
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
                    <span>Core readiness: {promotionLabels[source.promotion?.state ?? "candidate"]}</span>
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
                      <small>Source Entity 与采集通道分离</small>
                    </div>
                    <div className={styles.endpointList}>
                      {source.endpoints.slice(0, 4).map((endpoint) => (
                        <div className={styles.endpointRow} key={endpoint.id}>
                          <div>
                            <strong>{endpoint.label}</strong>
                            <small>
                              {endpoint.evidenceGrade ? `Grade ${endpoint.evidenceGrade} · ` : ""}
                              本次刷新 · 扫描 {endpoint.scanned} · 接受 {endpoint.accepted}
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

                  {source.promotion?.reasons.length ? (
                    <div className={styles.signalBlock}>
                      <span className={styles.signalLabel}>Core 晋级状态</span>
                      <p>{source.promotion.reasons.slice(0, 2).join(" · ")}</p>
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
                    <span>
                      <Radio size={11} aria-hidden="true" />
                      健康快照 {source.healthUpdatedAt?.slice(0, 10) || "不可用"}
                    </span>
                    {source.url ? (
                      <a href={source.url} target="_blank" rel="noreferrer">
                        原始入口 <ArrowUpRight size={12} />
                      </a>
                    ) : hasObservedEndpoint(source.endpoints) ? (
                      <span>采集端点已建立 · 未配置实体主页</span>
                    ) : (
                      <span>未建立观测 / 无稳定公开入口</span>
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
          <small>生命周期、晋级就绪度、证据角色与采集健康相互独立</small>
        </summary>
        <div className={styles.lifecycleDetails}>
          <p>
            Candidate 表示已进入信源图但尚未建立稳定采集入口；Tracked 表示已配置持续采集；Core 只会在滚动运行、跨日稳定性、可用率、有效产出、人工抽查全部达到版本化 Policy 后，再经过显式人工 Core 审批产生。
            人工批准不能绕过量化证据门，量化门达标也不能绕过人工批准。PRIMARY / CORROBORATION / DISCOVERY 描述证据角色，OK / PARTIAL / ERROR 描述采集通道健康，三者不再混为一个状态。
          </p>
          <div className={styles.lifecycleFlow}>
            <div>
              <strong>Candidate</strong>
              <p>已有明确 Source Entity，但稳定采集入口或质量证据仍不足。</p>
            </div>
            <div>
              <strong>Tracked</strong>
              <p>已配置持续抓取与滚动质量观测；EVIDENCE PENDING 与 CORE READY 会继续区分证据成熟度。</p>
            </div>
            <div>
              <strong>Core</strong>
              <p>跨运行证据、人工抽查与显式审批全部满足后才成为长期研究入口。</p>
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
          Primary Source 包括公司官网、监管/交易所披露、论文与原始研究材料；Corroboration Source 用于独立交叉验证；Discovery Source 包括微信公众号与 X Profiles，负责高召回和高时效发现。
          Source Entity 表示媒体、机构、公司、研究仓库或公开账号本身，Collection Endpoint 表示微信索引、官网、RSS、论文 API、X 公开时间线、监管接口或公开网页等采集通道。
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
            <strong>Source Entity ≠ Collection Endpoint</strong>
            <p>同一实体的微信、官网、RSS、论文 API 与公开时间线分别记录健康；可靠备用通道可用时，不把实体整体误判为失效。</p>
          </article>
          <article>
            <strong>发现 ≠ 事实确认</strong>
            <p>微信公众号、X Profiles 与媒体负责发现和交叉验证；重大公司、融资、监管、产品和研究结论优先回溯公司官网、论文、交易所、监管文件或其他原始材料。</p>
          </article>
          <article>
            <strong>Core 必须经过质量门槛</strong>
            <p>Tracked 不自动升级为 Core；持续可用性、有效产出、跨日稳定性、人工抽查和显式人工批准共同决定是否晋级。</p>
          </article>
        </div>
      </section>
    </main>
  );
}
