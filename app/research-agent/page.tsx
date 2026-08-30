import type { Metadata } from "next";
import type { ReactNode } from "react";
import {
  Activity,
  Building2,
  ExternalLink,
  FileSearch,
  Radar,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import {
  researchAgentDatasetLabels,
  researchAgentReport,
  type ResearchAgentChange,
  type ResearchAgentEvidence,
} from "@/lib/research-agent-data";
import { buildResearchAgentViewModel } from "@/lib/research-agent-view-model";
import PersonResearchQueuePanel from "./person-research-queue-panel";
import { EvidenceLedger, EvidenceRefs } from "./research-agent-evidence";
import ResearchRunHistory from "./research-run-history";
import styles from "./research-agent.module.css";

export const metadata: Metadata = {
  title: "Research Agent",
  description: "面向核心人物与核心公司的每日变化检测和证据摘要，并公开四类研究对象的接入状态。",
};

const researchWorkspaceUrl = process.env.NEXT_PUBLIC_QM_WORKSPACE_URL?.trim();

const statusLabels: Record<string, string> = {
  model: "自动分析完成",
  "no-material-change": "本轮无新增重大变化",
  "offline-fallback": "离线规则摘要",
  "missing-key-fallback": "等待 API 密钥",
  "api-fallback": "API 降级摘要",
  "awaiting-first-run": "等待首次运行",
};

const directionLabels = {
  positive: "正向",
  negative: "负向",
  mixed: "分化",
  neutral: "中性",
};

const confidenceLabels = {
  high: "高置信",
  medium: "中置信",
  low: "低置信",
};

const actionLabels: Record<ResearchAgentChange["action"], string> = {
  added: "新增",
  updated: "更新",
  removed: "移除",
};

const fieldLabels: Record<string, string> = {
  aliases: "别名",
  background: "背景",
  books: "著作",
  capitalMarkets: "资本市场",
  companyName: "公司名称",
  companySlug: "公司标识",
  concepts: "研究概念",
  discoveredVia: "发现渠道",
  documentType: "文件类型",
  englishName: "英文名",
  exchange: "交易所",
  fallback: "降级标识",
  financing: "融资进展",
  handles: "公开账号",
  id: "记录编号",
  listingRole: "上市角色",
  market: "市场",
  materials: "研究材料",
  name: "名称",
  organizations: "相关组织",
  products: "产品",
  publishedAt: "发布时间",
  role: "职务",
  sectors: "所属赛道",
  slug: "对象标识",
  source: "原始来源",
  sources: "信源",
  status: "状态",
  summary: "摘要",
  team: "核心团队",
  technology: "技术进展",
  warnings: "风险提示",
};

const fallbackReasonLabels: Record<string, string> = {
  SiliconFlowResponseError: "模型响应未通过处理",
  SchemaValidationError: "模型输出未通过结构校验",
};

function formatDate(value: string) {
  if (!value) return "等待首次运行";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

function localizeFieldNames(value: string) {
  return Object.entries(fieldLabels)
    .sort(([left], [right]) => right.length - left.length)
    .reduce(
      (text, [field, label]) =>
        text.replace(new RegExp(`(^|[^A-Za-z])${field}(?=$|[^A-Za-z])`, "g"), `$1${label}`),
      value,
    );
}

function importanceOnFivePointScale(value: number) {
  if (!Number.isFinite(value)) return 1;
  return Math.max(1, Math.min(5, value <= 5 ? Math.round(value) : Math.ceil(value / 20)));
}

function evidenceGradeSummary(ids: string[], evidenceById: ReadonlyMap<string, ResearchAgentEvidence>) {
  const counts = new Map<string, number>();
  for (const id of new Set(ids)) {
    const grade = evidenceById.get(id)?.evidenceGrade || "未分级";
    counts.set(grade, (counts.get(grade) ?? 0) + 1);
  }
  return [...counts.entries()].map(([grade, count]) => `${grade} ${count}`).join(" · ");
}

function RemainingItems({ count, children }: { count: number; children: ReactNode }) {
  if (count <= 0) return null;
  return (
    <details className={styles.analysisMore}>
      <summary>查看其余 {count} 项</summary>
      <div className={styles.compactList}>{children}</div>
    </details>
  );
}

function reviewLabel(status?: string) {
  if (status === "reviewed" || status === "approved") return "已人工复核";
  if (status === "rejected") return "人工复核未通过";
  if (status === "pending" || status === "unreviewed" || status === "automated_unreviewed") {
    return "尚未人工复核";
  }
  return "未标记人工复核";
}

export default function ResearchAgentPage() {
  const { analysis, changeSummary, history, methodology, model, pipelineHealth } = researchAgentReport;
  const view = buildResearchAgentViewModel(researchAgentReport);
  const status = statusLabels[researchAgentReport.runStatus] ?? researchAgentReport.runStatus;
  const latestModelRun = [...history].reverse().find((item) => item.runStatus === "model");
  const evidenceById = new Map(view.visibleEvidence.map((item) => [item.id, item]));
  const changesByDataset = [...new Set(view.visibleChanges.map((item) => item.dataset))].map((dataset) => ({
    dataset,
    items: view.visibleChanges.filter((item) => item.dataset === dataset),
  }));
  const coreObjectCoverage = [
    { label: "核心技术", count: view.coverage.technology },
    { label: "核心赛道", count: view.coverage.track },
    { label: "核心人物", count: view.coverage.person },
    { label: "核心公司", count: view.coverage.ventureCompany },
  ];
  const pipelineValue = view.metrics.pipelineJobCount === null
    ? "—"
    : `${view.metrics.pipelineHealthyCount}/${view.metrics.pipelineJobCount}`;
  const hasQualityBreakdown =
    typeof changeSummary.maintenanceExcluded === "number" ||
    typeof changeSummary.qualityRejected === "number";
  const deterministicSummary = [
    view.metrics.formalChangeCount > 0
      ? `${view.metrics.formalChangeCount} 项核心变化通过正式发布门`
      : "核心对象暂无通过正式发布门的重大变化",
    `${view.metrics.candidateCount} 项候选更新`,
    `${view.metrics.externalClueCount} 项外部行业线索`,
  ].join("；") + "。候选与线索均不计入正式变化。";

  return (
    <main className={`page-shell subpage ${styles.page}`}>
      <header className={`page-header ${styles.hero}`}>
        <p className="eyebrow">TOOL / RESEARCH AGENT</p>
        <h1>每日研究变化</h1>
        <div className={styles.heroLead}>
          <p>
            先看核心人物与核心公司的证据充分变化；候选更新和行业线索单独计数，不混入正式变化。
          </p>
          <div className={styles.reportMeta} aria-label="报告状态">
            <span>{status}</span>
            <span>自动生成 · {reviewLabel(view.reviewStatus)}</span>
            <span>数据截至 {researchAgentReport.asOfDate || "待同步"}</span>
            <span>生成于 {formatDate(researchAgentReport.generatedAt)}</span>
            <span>{model.used ? `${model.provider} · ${model.name}` : "本轮模型未参与"}</span>
          </div>
        </div>
      </header>

      <nav className={styles.sectionNav} aria-label="研究助手页内导航">
        <a href="#brief">今日简报</a>
        <a href="#theses">研究假设</a>
        <a href="#changes">变化与证据</a>
        <a href="#queue">研究队列</a>
        <a href="#history">运行记录</a>
      </nav>

      {view.isDegraded && (
        <section className={styles.degradedBanner} role="status" aria-label="本轮降级说明">
          <TriangleAlert size={20} aria-hidden="true" />
          <div>
            <strong>本轮仅生成结构化变化快照，未完成自动分析</strong>
            <p>
              当前内容表示字段或记录发生变化，不等同于事实已经确认。
              {methodology.fallbackReason
                ? ` 降级原因：${fallbackReasonLabels[methodology.fallbackReason] ?? methodology.fallbackReason}。`
                : ""}
              {view.suppressLegacyDegradedOutput
                ? " 该产物生成于证据质量门升级前，旧变化卡片已暂时隔离。"
                : ""}
            </p>
          </div>
          <small>
            {latestModelRun
              ? `最近一次自动分析完成：${formatDate(latestModelRun.generatedAt)}`
              : "暂无可用的历史自动分析记录"}
          </small>
        </section>
      )}

      <section
        className={`${styles.summaryPanel} ${styles.anchorSection}`}
        id="brief"
        aria-labelledby="brief-title"
      >
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">TODAY&apos;S BRIEF</p>
            <h2 id="brief-title">今日简报</h2>
          </div>
          <span>{researchAgentReport.baselineSource}</span>
        </div>

        <dl className={styles.statusGrid} aria-label="本期分类统计">
          <div>
            <dt><ShieldCheck size={18} aria-hidden="true" />证据门通过的核心变化</dt>
            <dd>
              <strong>{view.metrics.formalChangeCount}</strong>
              <small>自动证据核验；人工状态见上方</small>
            </dd>
          </div>
          <div>
            <dt><Building2 size={18} aria-hidden="true" />候选更新</dt>
            <dd>
              <strong>{view.metrics.candidateCount}</strong>
              <small>其中公司 {view.metrics.companyCandidateCount} 项；不计入正式变化</small>
            </dd>
          </div>
          <div>
            <dt><Radar size={18} aria-hidden="true" />外部行业线索</dt>
            <dd>
              <strong>{view.metrics.externalClueCount}</strong>
              <small>行业与市场背景，不计入正式变化</small>
            </dd>
          </div>
          <div>
            <dt><Activity size={18} aria-hidden="true" />数据管线</dt>
            <dd>
              <strong>{pipelineValue}</strong>
              <small>{pipelineHealth?.overallStatus ? `总体状态：${pipelineHealth.overallStatus}` : "状态待同步"}</small>
            </dd>
          </div>
        </dl>

        <p className={styles.primaryFinding}>
          {view.metrics.formalChangeCount > 0
            ? `本期有 ${view.metrics.formalChangeCount} 项核心对象变化通过正式发布门。`
            : "本期核心对象暂无证据充分、可计入正式口径的重大变化。"}
        </p>
        <div className={styles.executiveBlock}>
          <strong>按发布层级生成的口径摘要</strong>
          <p className={styles.executiveSummary}>{deterministicSummary}</p>
        </div>
        {view.hasPublicationTierContract ? (
          <div className={styles.modelSummary}>
            <strong>自动摘要（{reviewLabel(view.reviewStatus)}）</strong>
            <p>
              {view.suppressLegacyDegradedOutput
                ? `本轮旧版降级产物中的 ${changeSummary.total} 条记录已隔离。`
                : localizeFieldNames(analysis.executiveSummary)}
            </p>
          </div>
        ) : (
          <details className={styles.legacySummary}>
            <summary>查看旧口径自动摘要（未人工复核）</summary>
            <p>{localizeFieldNames(analysis.executiveSummary)}</p>
          </details>
        )}

        <details className={styles.coverageDisclosure}>
          <summary>查看研究对象覆盖、质量过滤与管线异常</summary>
          <div className={styles.coverageBody}>
            <div className={styles.datasetStrip} aria-label="当前研究对象覆盖">
              {coreObjectCoverage.map((item) => (
                <span key={item.label}>
                  {item.label} <strong>{item.count}</strong>
                </span>
              ))}
            </div>
            <p>
              存量覆盖来自 researchScope；本期统计只从 changes 派生，只表示本轮增量，两者不混用。
              即使本轮无新增重大变化或进入降级模式，也不会把历史研究对象清零。
              {hasQualityBreakdown
                ? ` 原始检测 ${changeSummary.totalDetected} 条，维护排除 ${changeSummary.maintenanceExcluded ?? 0} 条，证据未通过 ${changeSummary.qualityRejected ?? 0} 条。`
                : ` 原始检测 ${changeSummary.totalDetected} 条。`}
            </p>
            {pipelineHealth && pipelineHealth.issueJobs.length > 0 && (
              <p>
                待关注：{pipelineHealth.issueJobs.map((item) => `${item.name}（${item.status}）`).join("、")}。
              </p>
            )}
          </div>
        </details>

        <div className={styles.keyDevelopmentHeader}>
          <h3>关键内容</h3>
          <span>最多展示 3 条</span>
        </div>
        <div className={styles.developmentList}>
          {view.topDevelopments.map((item, index) => (
            <article key={`${item.title}-${index}`}>
              <div className={styles.itemMeta}>
                <span>重要度 {importanceOnFivePointScale(item.importance)}/5</span>
                <span>{confidenceLabels[item.confidence]}</span>
              </div>
              <h4>{localizeFieldNames(item.title)}</h4>
              <p>{localizeFieldNames(item.assessment)}</p>
              {item.entities.length > 0 && (
                <div className={styles.tags}>
                  {item.entities.map((entity) => <span key={entity}>{entity}</span>)}
                </div>
              )}
              <EvidenceRefs ids={item.evidenceIds} evidenceById={evidenceById} />
            </article>
          ))}
          {!view.topDevelopments.length && (
            <p className={styles.empty}>
              {view.suppressLegacyDegradedOutput
                ? "旧版降级结果已隔离，等待下一轮质量门重建。"
                : "本轮无新增关键变化；存量研究对象仍保留。"}
            </p>
          )}
        </div>
        {view.hiddenDevelopmentCount > 0 && (
          <p className={styles.filterHint}>其余 {view.hiddenDevelopmentCount} 条不在首屏展开，可在“变化与证据”核查对应记录。</p>
        )}
      </section>

      <section
        className={`${styles.anchorSection} ${styles.thesisSection}`}
        id="theses"
        aria-labelledby="theses-title"
      >
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">THESIS & NEXT CHECK</p>
            <h2 id="theses-title">研究假设</h2>
          </div>
          <span>先看变化，再看验证与风险</span>
        </div>
        <div className={styles.analysisGrid}>
          <section className={styles.panel} aria-labelledby="thesis-updates-title">
            <h3 id="thesis-updates-title">假设变化</h3>
            <div className={styles.compactList}>
              {view.thesisUpdates.slice(0, 3).map((item, index) => (
                <article key={`${item.entity}-${index}`}>
                  <div className={styles.itemMeta}>
                    <strong>{item.entity}</strong>
                    <span data-direction={item.direction}>{directionLabels[item.direction]}</span>
                  </div>
                  <p>{item.statement}</p>
                  <EvidenceRefs ids={item.evidenceIds} evidenceById={evidenceById} />
                </article>
              ))}
              {!view.thesisUpdates.length && <p className={styles.empty}>本期未形成证据充分的假设调整。</p>}
            </div>
            <RemainingItems count={Math.max(0, view.thesisUpdates.length - 3)}>
              {view.thesisUpdates.slice(3).map((item, index) => (
                <article key={`${item.entity}-more-${index}`}>
                  <strong>{item.entity} · {directionLabels[item.direction]}</strong>
                  <p>{item.statement}</p>
                  <EvidenceRefs ids={item.evidenceIds} evidenceById={evidenceById} />
                </article>
              ))}
            </RemainingItems>
          </section>

          <section className={styles.panel} aria-labelledby="watchlist-title">
            <h3 id="watchlist-title">待验证事项</h3>
            <div className={styles.compactList}>
              {view.watchlist.slice(0, 3).map((item, index) => (
                <article key={`${item.item}-${index}`}>
                  <h4>{item.item}</h4>
                  <p>{item.reason}</p>
                  {item.nextEvidence && <small>下一证据：{item.nextEvidence}</small>}
                  <EvidenceRefs ids={item.evidenceIds} evidenceById={evidenceById} />
                </article>
              ))}
              {!view.watchlist.length && <p className={styles.empty}>本期无新增待验证事项。</p>}
            </div>
            <RemainingItems count={Math.max(0, view.watchlist.length - 3)}>
              {view.watchlist.slice(3).map((item, index) => (
                <article key={`${item.item}-more-${index}`}>
                  <strong>{item.item}</strong>
                  <p>{item.reason}</p>
                  <EvidenceRefs ids={item.evidenceIds} evidenceById={evidenceById} />
                </article>
              ))}
            </RemainingItems>
          </section>

          <section className={styles.panel} aria-labelledby="risks-title">
            <h3 id="risks-title">风险提示</h3>
            <div className={styles.compactList}>
              {view.risks.slice(0, 3).map((item, index) => (
                <article key={`${item.risk}-${index}`}>
                  <h4>{item.risk}</h4>
                  <p>{item.reason}</p>
                  <EvidenceRefs ids={item.evidenceIds} evidenceById={evidenceById} />
                </article>
              ))}
              {!view.risks.length && <p className={styles.empty}>本期无新增风险提示。</p>}
            </div>
            <RemainingItems count={Math.max(0, view.risks.length - 3)}>
              {view.risks.slice(3).map((item, index) => (
                <article key={`${item.risk}-more-${index}`}>
                  <strong>{item.risk}</strong>
                  <p>{item.reason}</p>
                  <EvidenceRefs ids={item.evidenceIds} evidenceById={evidenceById} />
                </article>
              ))}
            </RemainingItems>
          </section>
        </div>
      </section>

      <section
        className={`${styles.panel} ${styles.anchorSection} ${styles.changesSection}`}
        id="changes"
        aria-labelledby="changes-title"
      >
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">CHANGES & EVIDENCE</p>
            <h2 id="changes-title">变化与证据</h2>
          </div>
          <span>{view.visibleChanges.length} 条公开记录 · {view.visibleEvidence.length} 个唯一证据节点</span>
        </div>
        <p className={styles.filterHint}>
          每项变化只保留紧凑证据引用；完整来源信息统一收录在本节末尾的唯一证据台账。
        </p>
        <div className={styles.changeGroups}>
          {changesByDataset.map((group, groupIndex) => {
            const evidenceIds = [...new Set(group.items.flatMap((item) => item.evidenceIds))];
            const actionSummary = (["added", "updated", "removed"] as const)
              .map((action) => ({
                action,
                count: group.items.filter((item) => item.action === action).length,
              }))
              .filter((item) => item.count > 0);
            return (
              <details className={styles.changeGroup} key={group.dataset} open={groupIndex === 0}>
                <summary>
                  <strong>{researchAgentDatasetLabels[group.dataset] ?? group.items[0]?.entityType}</strong>
                  <span>{group.items.length} 条记录</span>
                  <span className={styles.groupFacets}>
                    {actionSummary.map((item) => (
                      <em key={item.action}>{actionLabels[item.action]} {item.count}</em>
                    ))}
                    {evidenceGradeSummary(evidenceIds, evidenceById) && (
                      <em>{evidenceGradeSummary(evidenceIds, evidenceById)}</em>
                    )}
                  </span>
                </summary>
                <div className={styles.changeTable}>
                  {group.items.map((change) => (
                    <article key={change.id}>
                      <span
                        className={styles.importance}
                        aria-label={`重要度 ${importanceOnFivePointScale(change.importance)}/5`}
                      >
                        {importanceOnFivePointScale(change.importance)}/5
                      </span>
                      <div>
                        <div className={styles.itemMeta}>
                          <span>{change.entityType}</span>
                          <span data-action={change.action}>{actionLabels[change.action]}</span>
                        </div>
                        <h3>{change.entityName}</h3>
                        {change.summary && <p>{localizeFieldNames(change.summary)}</p>}
                        <small>
                          变化字段：{change.changedFields.map((field) => fieldLabels[field] ?? field).join("、") || "—"}
                        </small>
                        <small>证据等级：{evidenceGradeSummary(change.evidenceIds, evidenceById) || "暂无证据"}</small>
                        <EvidenceRefs ids={change.evidenceIds} evidenceById={evidenceById} />
                      </div>
                    </article>
                  ))}
                </div>
              </details>
            );
          })}
          {!view.visibleChanges.length && (
            <p className={styles.empty}>
              {view.suppressLegacyDegradedOutput
                ? "旧版变化明细已隔离，等待下一轮按新质量门重建。"
                : "本轮没有通过公开质量门的实体级变化。"}
            </p>
          )}
        </div>

        <div className={styles.evidenceHeading}>
          <FileSearch size={18} aria-hidden="true" />
          <div>
            <h3>唯一证据台账</h3>
            <p>同一证据无论被摘要、假设或风险引用多少次，都只在此处完整展示一次。</p>
          </div>
        </div>
        <EvidenceLedger evidence={view.visibleEvidence} />
      </section>

      <PersonResearchQueuePanel />

      <ResearchRunHistory history={history} />

      <div className={styles.utilityStack} aria-label="研究工具与方法">
        {researchWorkspaceUrl ? (
          <section className={styles.workspacePanel} aria-label="VCIQ Research Workspace">
            <div>
              <p className="section-index">INTERACTIVE RESEARCH</p>
              <h2>VCIQ Research Workspace</h2>
              <p>独立研究工作台只读消费 VCIQ 数据，研究结果以候选变更形式进入审核流程。</p>
            </div>
            <a
              className={styles.workspaceAction}
              href={researchWorkspaceUrl}
              target="_blank"
              rel="noreferrer"
              aria-label="进入研究工作台（新窗口打开）"
            >
              进入研究工作台
              <ExternalLink size={14} aria-hidden="true" />
            </a>
          </section>
        ) : (
          <details className={styles.utilityDisclosure}>
            <summary>
              <strong>交互式研究工作台</strong>
              <span>尚未发布</span>
            </summary>
            <div className={styles.utilityBody}>
              公开站继续只读发布已审核数据；工作台将在配置服务地址后启用，不直接改写生产数据。
            </div>
          </details>
        )}

        <details className={styles.methodology}>
          <summary>
            <ShieldCheck size={18} aria-hidden="true" />
            <strong>方法约束</strong>
          </summary>
          <div>
            <p>{analysis.methodologyNote || methodology.disclaimer}</p>
            <small>{methodology.disclaimer}</small>
          </div>
        </details>
      </div>
    </main>
  );
}
