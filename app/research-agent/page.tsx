import type { Metadata } from "next";
import {
  Activity,
  Bot,
  ExternalLink,
  FileSearch,
  Radar,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import {
  researchAgentDatasetLabels,
  researchAgentEvidenceById,
  researchAgentReport,
  type ResearchAgentChange,
  type ResearchDevelopment,
  type ResearchAgentEvidence,
} from "@/lib/research-agent-data";
import { personResearchQueue } from "@/lib/person-research-queue";
import PersonResearchQueuePanel from "./person-research-queue-panel";
import styles from "./research-agent.module.css";

export const metadata: Metadata = {
  title: "Research Agent",
  description: "面向核心人物与核心公司的每日变化检测和证据摘要，并公开四类研究对象的接入状态。",
};

const researchWorkspaceUrl = process.env.NEXT_PUBLIC_QM_WORKSPACE_URL?.trim();

const statusLabels: Record<string, string> = {
  model: "模型研判完成",
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

const degradedStatuses = new Set(["offline-fallback", "missing-key-fallback", "api-fallback"]);

type GroupedChange = ResearchAgentChange & {
  mergedCount: number;
  summaries: string[];
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

function groupDevelopments(items: ResearchDevelopment[]) {
  const grouped = new Map<string, ResearchDevelopment & { mergedCount: number }>();
  for (const item of items) {
    const key = `${item.title.trim()}::${[...item.entities].sort().join("|")}`;
    const current = grouped.get(key);
    if (!current) {
      grouped.set(key, { ...item, evidenceIds: [...item.evidenceIds], mergedCount: 1 });
      continue;
    }
    current.mergedCount += 1;
    current.importance = Math.max(current.importance, item.importance);
    current.evidenceIds = [...new Set([...current.evidenceIds, ...item.evidenceIds])];
  }
  return [...grouped.values()];
}

function groupChanges(items: ResearchAgentChange[]) {
  const grouped = new Map<string, GroupedChange>();
  for (const item of items) {
    const key = `${item.dataset}::${item.entityName.trim()}::${item.action}`;
    const current = grouped.get(key);
    if (!current) {
      grouped.set(key, {
        ...item,
        changedFields: [...item.changedFields],
        evidenceIds: [...item.evidenceIds],
        mergedCount: 1,
        summaries: item.summary ? [item.summary] : [],
      });
      continue;
    }
    current.mergedCount += 1;
    current.importance = Math.max(current.importance, item.importance);
    current.changedFields = [...new Set([...current.changedFields, ...item.changedFields])];
    current.evidenceIds = [...new Set([...current.evidenceIds, ...item.evidenceIds])];
    if (item.summary && !current.summaries.includes(item.summary)) current.summaries.push(item.summary);
  }
  return [...grouped.values()];
}

function evidenceGradeSummary(ids: string[]) {
  const counts = new Map<string, number>();
  for (const id of new Set(ids)) {
    const grade = researchAgentEvidenceById.get(id)?.evidenceGrade || "未分级";
    counts.set(grade, (counts.get(grade) ?? 0) + 1);
  }
  return [...counts.entries()].map(([grade, count]) => `${grade} ${count}`).join(" · ");
}

function EvidenceLinks({ ids }: { ids: string[] }) {
  const items = ids
    .map((id) => researchAgentEvidenceById.get(id))
    .filter((item): item is ResearchAgentEvidence => Boolean(item));
  if (!items.length) return null;
  return (
    <div className={styles.evidenceLinks}>
      {items.map((item) =>
        item.url ? (
          <a href={item.url} key={item.id} target="_blank" rel="noreferrer">
            <span className={styles.evidenceId}>{item.id}</span>
            <span className={styles.evidenceText}>
              <strong>{item.title || item.sourceName || "证据标题待补"}</strong>
              <small>
                {item.sourceName || "原始信源"} · {item.evidenceGrade || "未分级"} · {item.publishedAt || "日期待补"}
              </small>
            </span>
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        ) : (
          <span className={styles.internalEvidence} key={item.id}>
            {item.id} · {item.evidenceGrade}
          </span>
        ),
      )}
    </div>
  );
}

export default function ResearchAgentPage() {
  const { analysis, changeSummary, changes, evidence, history, methodology, model, pipelineHealth } =
    researchAgentReport;
  const status = statusLabels[researchAgentReport.runStatus] ?? researchAgentReport.runStatus;
  const isDegraded = degradedStatuses.has(researchAgentReport.runStatus);
  const latestModelRun = [...history].reverse().find((item) => item.runStatus === "model");
  const hasEvidenceQualityContract =
    Boolean(changeSummary.byChangeType) &&
    changes.every(
      (change) =>
        change.changeType === "external_event" && change.eligibleForKeyDevelopment === true,
    );
  const suppressLegacyDegradedOutput = isDegraded && !hasEvidenceQualityContract;
  const visibleDevelopments = suppressLegacyDegradedOutput ? [] : analysis.keyDevelopments;
  const visibleChanges = suppressLegacyDegradedOutput ? [] : changes;
  const visibleEvidence = suppressLegacyDegradedOutput ? [] : evidence;
  const groupedDevelopments = groupDevelopments(visibleDevelopments);
  const groupedChanges = groupChanges(visibleChanges);
  const changesByDataset = [...new Set(groupedChanges.map((item) => item.dataset))].map((dataset) => ({
    dataset,
    items: groupedChanges.filter((item) => item.dataset === dataset),
  }));
  const hasQueuedResearch =
    personResearchQueue.candidateTaskCount > 0 || personResearchQueue.selectedTaskCount > 0;
  const coreObjectCoverage = [
    { label: "核心技术", count: changeSummary.byDataset.technology ?? "待接入" },
    { label: "核心赛道", count: changeSummary.byDataset.track ?? changeSummary.byDataset.sector ?? "待接入" },
    { label: "核心人物", count: changeSummary.byDataset.person ?? 0 },
    { label: "核心公司", count: changeSummary.byDataset.ventureCompany ?? 0 },
  ];
  const hasQualityBreakdown =
    typeof changeSummary.maintenanceExcluded === "number" ||
    typeof changeSummary.qualityRejected === "number";
  const pipelineSummary = pipelineHealth
    ? `管线 ${pipelineHealth.healthyJobs}/${pipelineHealth.jobCount} 正常`
    : "管线状态待同步";

  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.hero}`}>
        <p className="eyebrow">TOOL / RESEARCH AGENT</p>
        <h1>每日研究变化</h1>
        <p>
          当前自动日报已接入核心人物与核心公司；核心技术和核心赛道公开显示接入状态，
          待稳定数据工件完成后再启用变化检测。投资机构、公开市场、资本事件和监管披露仅作为辅助证据；
          模型不能添加证据包之外的事实。
        </p>
      </header>

      <section className={styles.statusGrid} aria-label="Research Agent 运行状态">
        <article className={styles.statusCard}>
          <Bot size={19} aria-hidden="true" />
          <span>运行状态</span>
          <strong>{status}</strong>
          <small>{model.used ? `${model.provider} · ${model.name}` : "本轮模型未参与研判"}</small>
        </article>
        <article className={styles.statusCard}>
          <Activity size={19} aria-hidden="true" />
          <span>本期变化</span>
          <strong>{visibleChanges.length}</strong>
          <small>
            {suppressLegacyDegradedOutput
              ? `旧版降级产物 ${changeSummary.total} 条已隔离`
              : hasQualityBreakdown
              ? `原始 ${changeSummary.totalDetected} · 维护排除 ${changeSummary.maintenanceExcluded ?? 0} · 证据未通过 ${changeSummary.qualityRejected ?? 0}`
              : `原始检测 ${changeSummary.totalDetected} 条 · ${Math.max(0, changeSummary.totalDetected - changeSummary.total)} 条未进入展示`}
          </small>
        </article>
        <article className={styles.statusCard}>
          <FileSearch size={19} aria-hidden="true" />
          <span>证据节点</span>
          <strong>{visibleEvidence.length}</strong>
          <small>
            {suppressLegacyDegradedOutput
              ? `${evidence.length} 个旧证据节点等待质量门重建`
              : "每条模型判断必须绑定字段级证据"}
          </small>
        </article>
        <article className={styles.statusCard}>
          <Radar size={19} aria-hidden="true" />
          <span>数据截至</span>
          <strong>{researchAgentReport.asOfDate || "—"}</strong>
          <small>{formatDate(researchAgentReport.generatedAt)} · {pipelineSummary}</small>
        </article>
      </section>

      {isDegraded && (
        <section className={styles.degradedBanner} role="status" aria-label="本轮降级说明">
          <TriangleAlert size={20} aria-hidden="true" />
          <div>
            <strong>本轮仅生成结构化变化快照，未完成模型研判</strong>
            <p>
              当前内容表示字段或记录发生变化，不等同于事实已经确认。
              {methodology.fallbackReason
                ? ` 降级原因：${fallbackReasonLabels[methodology.fallbackReason] ?? methodology.fallbackReason}。`
                : ""}
              {suppressLegacyDegradedOutput
                ? " 该产物生成于证据质量门升级前，旧变化卡片已暂时隔离。"
                : ""}
            </p>
          </div>
          <small>
            {latestModelRun
              ? `最近一次模型研判完成：${formatDate(latestModelRun.generatedAt)}`
              : "暂无可用的历史模型研判记录"}
          </small>
        </section>
      )}

      <section className={styles.summaryPanel}>
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">EXECUTIVE SUMMARY</p>
            <h2>今日研究摘要</h2>
          </div>
          <span>{researchAgentReport.baselineSource}</span>
        </div>
        <p className={styles.executiveSummary}>
          {suppressLegacyDegradedOutput
            ? `旧版降级产物中的 ${changeSummary.total} 条变化暂不作为研究结果公开，等待下一轮按实体与证据质量门重新生成。`
            : localizeFieldNames(analysis.executiveSummary)}
        </p>
        <div className={styles.coverageBlock}>
          <strong>当前研究对象覆盖</strong>
          <div className={styles.datasetStrip}>
            {coreObjectCoverage.map((item) => (
              <span key={item.label} data-empty={item.count === 0}>
                {item.label} <strong>{item.count}</strong>
              </span>
            ))}
          </div>
          <p className={styles.filterHint}>
            存量覆盖来自当前研究范围或稳定快照；“本期变化”和“证据节点”只表示本轮增量。
            即使本轮无新增重大变化或进入降级模式，也不会把历史研究对象清零。
          </p>
          {pipelineHealth && pipelineHealth.issueJobs.length > 0 && (
            <p className={styles.filterHint}>
              数据管线：{pipelineHealth.healthyJobs}/{pipelineHealth.jobCount} 正常；待关注
              {" "}{pipelineHealth.issueJobs.map((item) => `${item.name}（${item.status}）`).join("、")}。
            </p>
          )}
        </div>
        <div className={styles.datasetStrip} aria-label="本轮辅助证据与数据集变化">
          {Object.entries(changeSummary.byDataset)
            .filter(([dataset]) => !["technology", "sector", "person", "ventureCompany"].includes(dataset))
            .map(([dataset, count]) => (
              <span key={dataset}>
                {researchAgentDatasetLabels[dataset] ?? dataset} <strong>{count}</strong>
              </span>
            ))}
        </div>
      </section>

      <div className={styles.twoColumn}>
        <section className={styles.panel}>
          <div className={styles.sectionHeading}>
            <div>
              <p className="section-index">KEY DEVELOPMENTS</p>
              <h2>今日重点</h2>
            </div>
            <ShieldCheck size={19} aria-hidden="true" />
          </div>
          <p className={styles.scaleLegend}>重要度统一采用 5 级：1–2 低，3 中，4 高，5 关键。</p>
          <div className={styles.developmentList}>
            {groupedDevelopments.map((item, index) => (
              <article key={`${item.title}-${index}`}>
                <div className={styles.itemMeta}>
                  <span>重要度 {importanceOnFivePointScale(item.importance)}/5</span>
                  <span>{confidenceLabels[item.confidence]}</span>
                </div>
                <h3>{localizeFieldNames(item.title)}</h3>
                {item.mergedCount > 1 && (
                  <p className={styles.mergeNote}>已合并同一事件的 {item.mergedCount} 条记录</p>
                )}
                <p>{localizeFieldNames(item.assessment)}</p>
                {item.entities.length > 0 && (
                  <div className={styles.tags}>
                    {item.entities.map((entity) => <span key={entity}>{entity}</span>)}
                  </div>
                )}
                <EvidenceLinks ids={item.evidenceIds} />
              </article>
            ))}
            {!groupedDevelopments.length && (
              <p className={styles.empty}>
                {suppressLegacyDegradedOutput
                  ? "旧版降级结果已隔离，等待下一轮质量门重建。"
                  : "本轮无新增关键变化；存量研究对象仍保留。"}
              </p>
            )}
          </div>
        </section>

        <aside className={styles.sideStack}>
          <section className={styles.panel}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">THESIS UPDATES</p>
                <h2>研究假设变化</h2>
              </div>
            </div>
            <div className={styles.compactList}>
              {analysis.thesisUpdates.map((item, index) => (
                <article key={`${item.entity}-${index}`}>
                  <div className={styles.itemMeta}>
                    <strong>{item.entity}</strong>
                    <span data-direction={item.direction}>{directionLabels[item.direction]}</span>
                  </div>
                  <p>{item.statement}</p>
                  <EvidenceLinks ids={item.evidenceIds} />
                </article>
              ))}
              {!analysis.thesisUpdates.length && <p className={styles.empty}>本期未形成证据充分的假设调整。</p>}
            </div>
          </section>

          <section className={styles.panel}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">WATCHLIST & RISKS</p>
                <h2>待验证事项</h2>
              </div>
              <TriangleAlert size={19} aria-hidden="true" />
            </div>
            <div className={styles.compactList}>
              {analysis.watchlist.map((item, index) => (
                <article key={`${item.item}-${index}`}>
                  <h3>{item.item}</h3>
                  <p>{item.reason}</p>
                  {item.nextEvidence && <small>下一证据：{item.nextEvidence}</small>}
                  <EvidenceLinks ids={item.evidenceIds} />
                </article>
              ))}
              {analysis.risks.map((item, index) => (
                <article key={`${item.risk}-${index}`}>
                  <h3>{item.risk}</h3>
                  <p>{item.reason}</p>
                  <EvidenceLinks ids={item.evidenceIds} />
                </article>
              ))}
              {!analysis.watchlist.length && !analysis.risks.length && (
                <p className={styles.empty}>本期无新增待验证事项。</p>
              )}
            </div>
          </section>
        </aside>
      </div>

      <section className={styles.panel}>
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">STRUCTURED CHANGE LOG</p>
            <h2>结构化变化明细</h2>
          </div>
          <span>{visibleChanges.length} 条记录 · {groupedChanges.length} 个实体动作</span>
        </div>
        <p className={styles.filterHint}>
          按研究对象折叠浏览；每项同时标明动作、证据等级与统一的 5 级重要度。
        </p>
        <div className={styles.changeGroups}>
          {changesByDataset.map((group, groupIndex) => {
            const recordCount = group.items.reduce((total, item) => total + item.mergedCount, 0);
            const evidenceIds = [...new Set(group.items.flatMap((item) => item.evidenceIds))];
            const actionSummary = (["added", "updated", "removed"] as const)
              .map((action) => ({
                action,
                count: group.items
                  .filter((item) => item.action === action)
                  .reduce((total, item) => total + item.mergedCount, 0),
              }))
              .filter((item) => item.count > 0);
            return (
              <details className={styles.changeGroup} key={group.dataset} open={groupIndex === 0}>
                <summary>
                  <strong>{researchAgentDatasetLabels[group.dataset] ?? group.items[0]?.entityType}</strong>
                  <span>{group.items.length} 个实体动作 · {recordCount} 条记录</span>
                  <span className={styles.groupFacets}>
                    {actionSummary.map((item) => (
                      <em key={item.action}>{actionLabels[item.action]} {item.count}</em>
                    ))}
                    {evidenceGradeSummary(evidenceIds) && <em>{evidenceGradeSummary(evidenceIds)}</em>}
                  </span>
                </summary>
                <div className={styles.changeTable}>
                  {group.items.map((change) => (
                    <article key={`${change.dataset}-${change.entityName}-${change.action}`}>
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
                        {change.mergedCount > 1 && (
                          <p className={styles.mergeNote}>已合并 {change.mergedCount} 条同对象记录</p>
                        )}
                        {change.summaries.slice(0, 2).map((summary) => (
                          <p key={summary}>{localizeFieldNames(summary)}</p>
                        ))}
                        <small>
                          变化字段：{change.changedFields.map((field) => fieldLabels[field] ?? field).join("、") || "—"}
                        </small>
                        <small>证据等级：{evidenceGradeSummary(change.evidenceIds) || "暂无证据"}</small>
                        {change.evidenceIds.length > 0 && (
                          <details className={styles.evidenceDisclosure}>
                            <summary>查看 {change.evidenceIds.length} 条证据</summary>
                            <EvidenceLinks ids={change.evidenceIds} />
                          </details>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              </details>
            );
          })}
          {!visibleChanges.length && (
            <p className={styles.empty}>
              {suppressLegacyDegradedOutput
                ? "旧版变化明细已隔离，等待下一轮按新质量门重建。"
                : "本轮没有新的实体级材料变化；当前存量研究对象仍保留。"}
            </p>
          )}
        </div>
      </section>

      <section className={styles.utilityStack} aria-label="研究工具入口">
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
            >
              进入研究工作台
              <ExternalLink size={14} aria-hidden="true" />
            </a>
          </section>
        ) : (
          <details className={styles.utilityDisclosure}>
            <summary>
              <strong>交互式研究工作台</strong>
              <span>尚未发布，已从主阅读路径折叠</span>
            </summary>
            <div className={styles.utilityBody}>
              公开站继续只读发布已审核数据；工作台将在配置服务地址后启用，不直接改写生产数据。
            </div>
          </details>
        )}

        {hasQueuedResearch ? (
          <PersonResearchQueuePanel />
        ) : (
          <details className={styles.utilityDisclosure}>
            <summary>
              <strong>今日人物研究队列</strong>
              <span>暂无候选任务，已从主阅读路径折叠</span>
            </summary>
            <PersonResearchQueuePanel />
          </details>
        )}
      </section>

      {history.length > 0 && (
        <section className={styles.panel}>
          <div className={styles.sectionHeading}>
            <div>
              <p className="section-index">30-DAY HISTORY</p>
              <h2>最近运行记录</h2>
            </div>
          </div>
          <div className={styles.historyGrid}>
            {[...history].reverse().slice(0, 30).map((item) => (
              <article key={`${item.date}-${item.generatedAt}`}>
                <div className={styles.historyMeta}>
                  <span>{item.date}</span>
                  <em data-status={item.runStatus}>{statusLabels[item.runStatus] ?? item.runStatus}</em>
                </div>
                <strong>{item.changeCount} 条变化</strong>
                <p>
                  {item.runStatus.endsWith("-fallback")
                    ? `${item.changeCount} 条结构化候选；降级运行未形成研究结论。`
                    : item.executiveSummary}
                </p>
                <small>生成于 {formatDate(item.generatedAt)}</small>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className={styles.methodology}>
        <ShieldCheck size={18} aria-hidden="true" />
        <div>
          <strong>方法约束</strong>
          <p>{analysis.methodologyNote || methodology.disclaimer}</p>
          <small>{methodology.disclaimer}</small>
        </div>
      </section>
    </main>
  );
}
