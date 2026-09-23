import Link from "next/link";
import { Activity, GitBranch, Landmark, Network, Search, ShieldCheck } from "lucide-react";

import {
  buildInnovationCapitalResearchModel,
  type InnovationResearchTask,
} from "@/lib/innovation-capital-research";
import {
  currentInnovationCapitalThesisObservations,
  type InnovationCapitalThesisMemory,
  type InnovationCapitalThesisTransition,
} from "@/lib/innovation-capital-thesis-memory";
import rawInnovationCapitalThesisMemory from "@/public/data/innovation_capital_thesis_memory.json";
import styles from "./innovation-capital-research-panel.module.css";

const transitionLabels: Record<InnovationCapitalThesisTransition, string> = {
  initiated: "首次建立",
  reaffirmed: "持续强化",
  revised: "证据修订",
  direction_changed: "状态转向",
  returned: "回到历史版本",
};

const typeLabels: Record<InnovationResearchTask["taskType"], string> = {
  lifecycle_validation: "生命周期",
  cross_market_path: "A+H / H→A",
  route_migration: "路线迁移",
  broker_pattern: "券商结构",
  capital_network: "机构网络",
  mature_discovery: "成熟候选",
  evidence_maintenance: "证据维护",
};

function deltaLabel(value: number, suffix = "") {
  if (!Number.isFinite(value) || value === 0) return `0${suffix}`;
  return `${value > 0 ? "+" : ""}${value}${suffix}`;
}

function iconFor(type: InnovationResearchTask["taskType"]) {
  if (type === "cross_market_path") return <Landmark size={14} aria-hidden="true" />;
  if (type === "route_migration") return <GitBranch size={14} aria-hidden="true" />;
  if (type === "capital_network") return <Network size={14} aria-hidden="true" />;
  if (type === "evidence_maintenance") return <ShieldCheck size={14} aria-hidden="true" />;
  return <Search size={14} aria-hidden="true" />;
}

export default function InnovationCapitalResearchPanel() {
  const model = buildInnovationCapitalResearchModel();
  const memory = rawInnovationCapitalThesisMemory as unknown as InnovationCapitalThesisMemory;
  const currentMemory = new Map(
    currentInnovationCapitalThesisObservations(memory).map((item) => [item.hypothesisId, item]),
  );
  const historyByHypothesis = new Map<string, InnovationCapitalThesisMemory["observations"]>();
  for (const observation of memory.observations) {
    const rows = historyByHypothesis.get(observation.hypothesisId) ?? [];
    rows.push(observation);
    historyByHypothesis.set(observation.hypothesisId, rows);
  }
  const researchTasks = model.tasks.filter((item) => item.taskType !== "evidence_maintenance");
  const maintenanceTasks = model.tasks.filter((item) => item.taskType === "evidence_maintenance");

  return (
    <section className={styles.panel} id="queuecf" aria-labelledby="queuecf-title">
      <div className={styles.heading}>
        <div>
          <p className="section-index">INNOVATION CAPITAL RESEARCH</p>
          <h2 id="queuecf-title">科创规律研究队列</h2>
        </div>
        <div className={styles.headingActions}>
          <span>数据截至 {model.asOf || "待同步"}</span>
          <Link href="/innovation-capital/">查看科创项目 →</Link>
        </div>
      </div>

      <p className={styles.intro}>
        不把科创频道当成新闻列表，而是持续验证“券商—赛道—项目阶段—资本市场路线—机构资本”的结构性规律。
        Research 处理实质假设，Maintenance 只补证据与路线字段。
      </p>

      <div className={styles.stats}>
        <article><strong>{model.projectCount}</strong><span>辅导储备项目</span></article>
        <article><strong>{model.lifecycleCount}</strong><span>后续生命周期项目</span></article>
        <article><strong>{model.institutionCount}</strong><span>相关资本机构</span></article>
        <article><strong>{model.unknownRouteCount}</strong><span>A股板块未公开确认</span></article>
      </div>

      <div className={styles.layout}>
        <div>
          <div className={styles.subheading}>
            <h3>Research Queue</h3>
            <span>{researchTasks.length} 项</span>
          </div>
          <div className={styles.taskList}>
            {researchTasks.slice(0, 8).map((task) => (
              <article className={styles.task} key={task.id}>
                <div className={styles.rank}>{String(task.rank).padStart(2, "0")}</div>
                <div>
                  <div className={styles.meta}>
                    <span>{task.priority} · {typeLabels[task.taskType]}</span>
                    <span>Research Score {task.score}</span>
                  </div>
                  <h4>{task.title} · {task.target}</h4>
                  <p>{task.question}</p>
                  <div className={styles.why}>
                    {task.whyNow.slice(0, 2).map((reason) => <span key={reason}>{reason}</span>)}
                  </div>
                  <details>
                    <summary>{iconFor(task.taskType)} 查看成功判据</summary>
                    <p>{task.successCriteria}</p>
                    <Link href={task.sourceRoute}>进入对应科创数据层 →</Link>
                  </details>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className={styles.hypotheses}>
          <div className={styles.subheading}>
            <h3>Thesis Watch</h3>
            <span>{model.hypotheses.length} 条 · 历史观察 {memory.observationCount}</span>
          </div>
          {model.hypotheses.map((item) => {
            const observation = currentMemory.get(item.id);
            const history = historyByHypothesis.get(item.id) ?? [];
            return (
              <article key={item.id}>
                <div className={styles.thesisMeta}>
                  <Activity size={13} aria-hidden="true" />
                  <span>{item.status === "observed" ? "已观察到样本信号" : "持续验证"}</span>
                  {observation ? (
                    <span className={styles.transition}>
                      {transitionLabels[observation.lastTransition]} · {observation.observationCount} 次观测
                    </span>
                  ) : null}
                </div>
                <h4>{item.title}</h4>
                <p>{item.evidence}</p>
                <div className={styles.metricGrid} aria-label="量化证据">
                  <span><strong>{item.metrics.supportCount}</strong> 支持样本</span>
                  <span><strong>{item.metrics.contrastCount}</strong> 对照/未支持</span>
                  <span><strong>{item.metrics.universeCount}</strong> 样本宇宙</span>
                  <span><strong>{item.metrics.evidenceCoveragePct.toFixed(1)}%</strong> 证据覆盖</span>
                  <span><strong>{item.metrics.supportSharePct.toFixed(1)}%</strong> 支持样本占比</span>
                </div>
                {observation?.metricDelta ? (
                  <div className={styles.metricDelta}>
                    <span>较上版：</span>
                    <span>支持 {deltaLabel(observation.metricDelta.supportDelta)}</span>
                    <span>对照 {deltaLabel(observation.metricDelta.contrastDelta)}</span>
                    <span>样本 {deltaLabel(observation.metricDelta.universeDelta)}</span>
                    <span>覆盖 {deltaLabel(observation.metricDelta.evidenceCoverageDeltaPct, "pct")}</span>
                  </div>
                ) : null}
                <details className={styles.metricMethod}>
                  <summary>查看量化口径</summary>
                  <p><strong>支持：</strong>{item.metrics.supportDefinition}</p>
                  <p><strong>对照/未支持：</strong>{item.metrics.contrastDefinition}</p>
                  {item.metrics.neutralCount > 0 ? <p><strong>中性/未分类：</strong>{item.metrics.neutralCount} 个</p> : null}
                  <p>这些数字只描述当前已纳入样本，不代表概率、评级或因果结论。</p>
                </details>
                <small>下一验证：{item.nextCheck}</small>
                {observation ? (
                  <div className={styles.memoryMeta}>
                    首次 {observation.firstSeenAt || "—"} · 最近 {observation.lastSeenAt || "—"}
                  </div>
                ) : null}
                {history.length > 1 ? (
                  <details className={styles.thesisHistory}>
                    <summary>查看历史演化（{history.length} 个版本）</summary>
                    <div>
                      {[...history].reverse().map((row) => (
                        <section key={row.id}>
                          <strong>{transitionLabels[row.lastTransition]} · {row.firstSeenAt}</strong>
                          <p>{row.evidence}</p>
                          {row.metrics ? (
                            <small>
                              支持 {row.metrics.supportCount} · 对照 {row.metrics.contrastCount} ·
                              样本 {row.metrics.universeCount} · 覆盖 {row.metrics.evidenceCoveragePct.toFixed(1)}%
                            </small>
                          ) : null}
                        </section>
                      ))}
                    </div>
                  </details>
                ) : null}
              </article>
            );
          })}
        </aside>
      </div>

      {maintenanceTasks.length > 0 && (
        <details className={styles.maintenance}>
          <summary>Maintenance Queue · {maintenanceTasks.length} 项</summary>
          {maintenanceTasks.map((task) => (
            <article key={task.id}>
              <strong>{task.title} · {task.target}</strong>
              <p>{task.question}</p>
              <small>{task.successCriteria}</small>
            </article>
          ))}
        </details>
      )}

      <p className={styles.methodology}>{model.methodology}</p>
    </section>
  );
}
