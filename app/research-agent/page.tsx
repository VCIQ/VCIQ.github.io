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
  type ResearchAgentEvidence,
} from "@/lib/research-agent-data";
import PersonResearchQueuePanel from "./person-research-queue-panel";
import styles from "./research-agent.module.css";

export const metadata: Metadata = {
  title: "Research Agent",
  description: "围绕核心技术、核心赛道、核心人物与核心公司的每日变化检测和证据摘要。",
};

const researchWorkspaceUrl = process.env.NEXT_PUBLIC_QM_WORKSPACE_URL?.trim();

const statusLabels: Record<string, string> = {
  model: "模型研判完成",
  "no-material-change": "无材料变化",
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
            <span>{item.id}</span>
            {item.sourceName || "原始信源"}
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
  const { analysis, changeSummary, changes, evidence, history, methodology, model } =
    researchAgentReport;
  const status = statusLabels[researchAgentReport.runStatus] ?? researchAgentReport.runStatus;

  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">TOOL / RESEARCH AGENT</p>
        <h1>四类研究对象的每日变化摘要</h1>
        <p>
          以核心技术、核心赛道、核心人物和核心公司为结论归属，识别结构化变化并形成证据包。
          投资机构、公开市场、资本事件和监管披露仅作为辅助证据；模型不能添加证据包之外的事实。
        </p>
      </header>

      <section className={styles.statusGrid} aria-label="Research Agent 运行状态">
        <article className={styles.statusCard}>
          <Bot size={19} aria-hidden="true" />
          <span>运行状态</span>
          <strong>{status}</strong>
          <small>{model.used ? `${model.provider} · ${model.name}` : "规则引擎可独立降级运行"}</small>
        </article>
        <article className={styles.statusCard}>
          <Activity size={19} aria-hidden="true" />
          <span>本期变化</span>
          <strong>{changeSummary.total}</strong>
          <small>原始检测 {changeSummary.totalDetected} 条</small>
        </article>
        <article className={styles.statusCard}>
          <FileSearch size={19} aria-hidden="true" />
          <span>证据节点</span>
          <strong>{evidence.length}</strong>
          <small>每条模型判断必须绑定证据编号</small>
        </article>
        <article className={styles.statusCard}>
          <Radar size={19} aria-hidden="true" />
          <span>数据截至</span>
          <strong>{researchAgentReport.asOfDate || "—"}</strong>
          <small>{formatDate(researchAgentReport.generatedAt)}</small>
        </article>
      </section>

      <section className={styles.workspacePanel} aria-label="VCIQ Research Workspace">
        <div>
          <p className="section-index">INTERACTIVE RESEARCH</p>
          <h2>VCIQ Research Workspace</h2>
          <p>
            交互式研究工作台由独立 QM 服务承载。公开站继续只读发布已审核数据；工作台只读消费
            VCIQ 数据，并用于持续研究、Memory、Skills、Watch 与候选 PR，不直接改写生产数据。
          </p>
          <div className={styles.workspaceBadges}>
            <span>只读 VCIQ 数据</span>
            <span>独立权限边界</span>
            <span>候选变更走 PR</span>
          </div>
        </div>
        {researchWorkspaceUrl ? (
          <a
            className={styles.workspaceAction}
            href={researchWorkspaceUrl}
            target="_blank"
            rel="noreferrer"
          >
            进入研究工作台
            <ExternalLink size={14} aria-hidden="true" />
          </a>
        ) : (
          <div className={styles.workspacePending}>
            <strong>工作台尚未发布</strong>
            <span>配置 QM_WORKSPACE_URL 后自动启用入口</span>
          </div>
        )}
      </section>

      <PersonResearchQueuePanel />

      <section className={styles.summaryPanel}>
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">EXECUTIVE SUMMARY</p>
            <h2>今日研究摘要</h2>
          </div>
          <span>{researchAgentReport.baselineSource}</span>
        </div>
        <p className={styles.executiveSummary}>{analysis.executiveSummary}</p>
        <div className={styles.datasetStrip}>
          {Object.entries(changeSummary.byDataset).map(([dataset, count]) => (
            <span key={dataset}>
              {researchAgentDatasetLabels[dataset] ?? dataset} <strong>{count}</strong>
            </span>
          ))}
          {!Object.keys(changeSummary.byDataset).length && <span>暂无进入阈值的变化</span>}
        </div>
      </section>

      <div className={styles.twoColumn}>
        <section className={styles.panel}>
          <div className={styles.sectionHeading}>
            <div>
              <p className="section-index">KEY DEVELOPMENTS</p>
              <h2>关键变化</h2>
            </div>
            <ShieldCheck size={19} aria-hidden="true" />
          </div>
          <div className={styles.developmentList}>
            {analysis.keyDevelopments.map((item, index) => (
              <article key={`${item.title}-${index}`}>
                <div className={styles.itemMeta}>
                  <span>重要度 {item.importance}/5</span>
                  <span>{confidenceLabels[item.confidence]}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.assessment}</p>
                {item.entities.length > 0 && (
                  <div className={styles.tags}>
                    {item.entities.map((entity) => <span key={entity}>{entity}</span>)}
                  </div>
                )}
                <EvidenceLinks ids={item.evidenceIds} />
              </article>
            ))}
            {!analysis.keyDevelopments.length && <p className={styles.empty}>本期无关键变化。</p>}
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
          <span>{changes.length} 条</span>
        </div>
        <div className={styles.changeTable}>
          {changes.map((change) => (
            <article key={change.id}>
              <span className={styles.importance}>{change.importance}</span>
              <div>
                <div className={styles.itemMeta}>
                  <span>{researchAgentDatasetLabels[change.dataset] ?? change.entityType}</span>
                  <span>{change.action}</span>
                </div>
                <h3>{change.entityName}</h3>
                <p>{change.summary}</p>
                <small>变化字段：{change.changedFields.join("、") || "—"}</small>
                <EvidenceLinks ids={change.evidenceIds} />
              </div>
            </article>
          ))}
          {!changes.length && <p className={styles.empty}>等待新一轮实体快照产生材料变化。</p>}
        </div>
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
                <span>{item.date}</span>
                <strong>{item.changeCount} 条变化</strong>
                <p>{item.executiveSummary}</p>
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
