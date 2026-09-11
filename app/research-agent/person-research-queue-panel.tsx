import Link from "next/link";
import { ListChecks, Search, ShieldCheck } from "lucide-react";

import {
  personResearchQueue,
  type PersonResearchQueueItem,
  type PersonResearchQueueScoreBreakdown,
} from "@/lib/person-research-queue";
import { researchAgentReport } from "@/lib/research-agent-data";
import ResearchThesisMemoryPanel from "./research-thesis-memory";
import styles from "./person-research-queue-panel.module.css";

const taskTypeLabels = {
  identity_verification: "身份核验",
  first_party_evidence: "补一手证据",
  viewpoint_verification: "观点变化核验",
  execution_verification: "组织执行核验",
  freshness_update: "近期证据补齐",
};

const executorLabels = {
  person_video: "人物视频 / 一手材料",
  cross_channel: "公司 / 技术跨频道",
  official_source: "官方来源核验",
};

const statusLabels = {
  open: "待检索",
  candidate_found: "已有候选",
};

const workstreamLabels = {
  research: "Research",
  maintenance: "Maintenance",
};

function scoreSummary(breakdown: PersonResearchQueueScoreBreakdown) {
  return [
    ["优先级", breakdown.priority],
    ["类型", breakdown.taskType],
    ["状态", breakdown.status],
    ["缺口", breakdown.evidenceGap],
    ["近期", breakdown.recency],
    ["交叉验证", breakdown.crossValidation],
    ["可执行", breakdown.queryReadiness],
    ["研究记忆", breakdown.researchOutcomeMemory],
    ["策略 ROI", breakdown.researchStrategyROI],
    ["成本效率", breakdown.researchCostEfficiency],
  ] as const;
}

function QueueItem({ item }: { item: PersonResearchQueueItem }) {
  return (
    <article className={styles.queueItem}>
      <div className={styles.queueRank} aria-label={`${workstreamLabels[item.workstream]} 队列第 ${item.workstreamRank} 位`}>
        {String(item.workstreamRank).padStart(2, "0")}
      </div>
      <div className={styles.queueBody}>
        <div className={styles.itemMeta}>
          <span>
            {workstreamLabels[item.workstream]} · {item.priority} · {taskTypeLabels[item.taskType]} · {statusLabels[item.status]}
          </span>
          <span>Research Score {item.score}</span>
        </div>
        <h3>
          <Link href={item.personRoute}>{item.personName}</Link>
          {item.target ? <span> · {item.target}</span> : null}
        </h3>
        <p>{item.question}</p>

        {item.whyNow.length > 0 && (
          <div className={styles.queueWhy}>
            {item.whyNow.slice(0, 2).map((reason) => <span key={reason}>{reason}</span>)}
          </div>
        )}

        <div className={styles.queueExecutionSummary}>
          <ListChecks size={14} aria-hidden="true" />
          <span>执行器：{executorLabels[item.executor]}</span>
          <span>检索槽位：{item.queryBudget}</span>
          <span>证据：{item.evidenceBasisCount} 基础 / {item.candidateEvidenceCount} 候选</span>
        </div>

        <details className={styles.taskDetails}>
          <summary>查看执行与评分明细</summary>
          <div className={styles.taskDetailBody}>
            <div className={styles.queueExecution}>
              {item.queryStrategyLabel ? <span>策略：{item.queryStrategyLabel}</span> : null}
              {item.strategySampleSize > 0 ? (
                <span>
                  历史样本 {item.strategySampleSize} · 候选命中 {(item.expectedSuccessRate * 100).toFixed(0)}% · 单槽位候选 {item.expectedEvidenceYield.toFixed(2)}
                </span>
              ) : null}
              {item.costSampleSize > 0 ? (
                <span>
                  成本样本 {item.costSampleSize} · 预期成本 {item.queryUnitCost.toFixed(2)} · 单位成本候选 {item.expectedYieldPerCost.toFixed(2)}
                </span>
              ) : null}
              {item.averageQueryDurationMs > 0 ? (
                <span>历史平均检索 {(item.averageQueryDurationMs / 1000).toFixed(1)} 秒</span>
              ) : null}
              <span>预算效用 {item.allocationUtility.toFixed(1)}</span>
              {item.topHistoricalSourceTypeLabel ? <span>历史高产来源：{item.topHistoricalSourceTypeLabel}</span> : null}
              {item.cooldownUntil ? <span>冷却至：{item.cooldownUntil}</span> : null}
            </div>

            {item.searchQueries.length > 0 && (
              <div className={styles.queueQuery}>
                <Search size={13} aria-hidden="true" />
                <code>{item.searchQueries[0]}</code>
              </div>
            )}

            <div className={styles.scoreBreakdown} aria-label="Research Score 评分拆解">
              {scoreSummary(item.scoreBreakdown).map(([label, value]) => (
                <span key={label}>{label} {value >= 0 ? `+${value}` : value}</span>
              ))}
            </div>

            <small className={styles.queueCriteria}>
              <ShieldCheck size={12} aria-hidden="true" />
              成功判据：{item.successCriteria}
            </small>
          </div>
        </details>
      </div>
    </article>
  );
}

function CompactQueueItems({ items }: { items: PersonResearchQueueItem[] }) {
  return (
    <div>
      {items.map((item) => (
        <article key={item.taskId}>
          <span>
            {String(item.workstreamRank).padStart(2, "0")} · {item.priority} · {taskTypeLabels[item.taskType]} · {statusLabels[item.status]}
          </span>
          <h3>
            <Link href={item.personRoute}>{item.personName}</Link>
            {item.target ? ` · ${item.target}` : ""}
          </h3>
          <p>{item.question}</p>
        </article>
      ))}
    </div>
  );
}

export default function PersonResearchQueuePanel() {
  const queue = personResearchQueue;
  const researchQueue = queue.queue.filter((item) => item.workstream === "research");
  const maintenanceQueue = queue.queue.filter((item) => item.workstream === "maintenance");
  const primaryResearch = researchQueue.slice(0, 3);
  const remainingResearch = researchQueue.slice(3);
  const primaryMaintenance = maintenanceQueue.slice(0, 2);
  const remainingMaintenance = maintenanceQueue.slice(2);
  const hasLaneCandidateTotals = queue.schemaVersion >= 5;

  return (
    <>
      <ResearchThesisMemoryPanel memory={researchAgentReport.thesisMemory} />

      <section className={styles.queuePanel} id="queue" aria-labelledby="queue-title">
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">TODAY&apos;S RESEARCH WORKSTREAMS</p>
            <h2 id="queue-title">研究任务</h2>
          </div>
          <div className={styles.headingActions}>
            <span>{queue.researchDate || "等待生成"}</span>
            <Link href="/research-agent/strategy/">查看研究策略 →</Link>
          </div>
        </div>

        <p className={styles.queueIntro}>
          Research 处理观点、执行和一手研究证据；Maintenance 处理身份/任职与时效补齐。调度层先保证 Research，不再让资料维护挤占核心研究任务。
        </p>

        <div className={styles.queueStats}>
          <article>
            <span>{hasLaneCandidateTotals ? "Research 候选 / 今日" : "Research 今日任务"}</span>
            <strong>
              {hasLaneCandidateTotals
                ? `${queue.candidateResearchTaskCount}/${queue.selectedResearchTaskCount}`
                : queue.selectedResearchTaskCount}
            </strong>
            <small>{hasLaneCandidateTotals ? "核心研究 lane" : "旧工件仅能可靠拆分已入队任务"}</small>
          </article>
          <article>
            <span>{hasLaneCandidateTotals ? "Maintenance 候选 / 今日" : "Maintenance 今日任务"}</span>
            <strong>
              {hasLaneCandidateTotals
                ? `${queue.candidateMaintenanceTaskCount}/${queue.selectedMaintenanceTaskCount}`
                : queue.selectedMaintenanceTaskCount}
            </strong>
            <small>最多 {queue.limits.maintenanceTasks} 项</small>
          </article>
          <article>
            <span>主动检索槽位</span>
            <strong>{queue.allocatedResearchQuerySlots}+{queue.allocatedMaintenanceQuerySlots}/{queue.limits.activeQuerySlots}</strong>
            <small>Research + Maintenance</small>
          </article>
          <article>
            <span>历史主动尝试</span>
            <strong>{queue.outcomeMemoryAttemptCount}</strong>
            <small>只影响排序与预算</small>
          </article>
        </div>

        <p className={styles.queueIntro}>
          <strong>Research Queue</strong> · 默认展开最高价值的实质研究任务。
        </p>
        <div className={styles.queueList}>
          {primaryResearch.map((item) => <QueueItem item={item} key={item.taskId} />)}
          {!primaryResearch.length && <p className={styles.empty}>当前没有开放的实质研究任务。</p>}
        </div>

        {remainingResearch.length > 0 && (
          <details className={styles.remainingQueue}>
            <summary>查看其余 Research 任务（{remainingResearch.length}）</summary>
            <CompactQueueItems items={remainingResearch} />
          </details>
        )}

        <p className={styles.queueIntro}>
          <strong>Maintenance Queue</strong> · 身份、任职和证据时效维护使用独立 lane。
        </p>
        <div className={styles.queueList}>
          {primaryMaintenance.map((item) => <QueueItem item={item} key={item.taskId} />)}
          {!primaryMaintenance.length && <p className={styles.empty}>当前没有开放的资料维护任务。</p>}
        </div>

        {remainingMaintenance.length > 0 && (
          <details className={styles.remainingQueue}>
            <summary>查看其余 Maintenance 任务（{remainingMaintenance.length}）</summary>
            <CompactQueueItems items={remainingMaintenance} />
          </details>
        )}

        <details className={styles.queueMethodology}>
          <summary>查看队列排序说明</summary>
          <p>{queue.methodology}</p>
        </details>
      </section>
    </>
  );
}
