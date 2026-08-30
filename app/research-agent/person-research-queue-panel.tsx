import Link from "next/link";
import { ListChecks, Search, ShieldCheck } from "lucide-react";

import {
  personResearchQueue,
  type PersonResearchQueueItem,
  type PersonResearchQueueScoreBreakdown,
} from "@/lib/person-research-queue";
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
      <div className={styles.queueRank} aria-label={`队列第 ${item.rank} 位`}>
        {String(item.rank).padStart(2, "0")}
      </div>
      <div className={styles.queueBody}>
        <div className={styles.itemMeta}>
          <span>
            {item.priority} · {taskTypeLabels[item.taskType]} · {statusLabels[item.status]}
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

export default function PersonResearchQueuePanel() {
  const queue = personResearchQueue;
  const primaryQueue = queue.queue.slice(0, 3);
  const remainingQueue = queue.queue.slice(3);

  return (
    <section className={styles.queuePanel} id="queue" aria-labelledby="queue-title">
      <div className={styles.sectionHeading}>
        <div>
          <p className="section-index">TODAY&apos;S RESEARCH QUEUE</p>
          <h2 id="queue-title">研究队列</h2>
        </div>
        <div className={styles.headingActions}>
          <span>{queue.researchDate || "等待生成"}</span>
          <Link href="/research-agent/strategy/">查看研究策略 →</Link>
        </div>
      </div>

      <p className={styles.queueIntro}>
        默认展示优先级最高的 3 项；检索成本、评分拆解和成功判据按需展开。
      </p>

      <div className={styles.queueStats}>
        <article>
          <span>候选任务池</span>
          <strong>{queue.candidateTaskCount}</strong>
          <small>未关闭、未阻塞</small>
        </article>
        <article>
          <span>今日任务</span>
          <strong>{queue.selectedTaskCount}/{queue.limits.tasks}</strong>
          <small>{queue.selectedPeopleCount} 位人物</small>
        </article>
        <article>
          <span>主动检索槽位</span>
          <strong>{queue.allocatedQuerySlots}/{queue.limits.activeQuerySlots}</strong>
          <small>按成本效用分配</small>
        </article>
        <article>
          <span>历史主动尝试</span>
          <strong>{queue.outcomeMemoryAttemptCount}</strong>
          <small>只影响排序与预算</small>
        </article>
      </div>

      <div className={styles.queueList}>
        {primaryQueue.map((item) => <QueueItem item={item} key={item.taskId} />)}
        {!primaryQueue.length && <p className={styles.empty}>等待人物主动研究任务生成后形成今日队列。</p>}
      </div>

      {remainingQueue.length > 0 && (
        <details className={styles.remainingQueue}>
          <summary>查看其余 {remainingQueue.length} 项任务</summary>
          <div>
            {remainingQueue.map((item) => (
              <article key={item.taskId}>
                <span>{String(item.rank).padStart(2, "0")} · {item.priority} · {statusLabels[item.status]}</span>
                <h3>
                  <Link href={item.personRoute}>{item.personName}</Link>
                  {item.target ? ` · ${item.target}` : ""}
                </h3>
                <p>{item.question}</p>
              </article>
            ))}
          </div>
        </details>
      )}

      <details className={styles.queueMethodology}>
        <summary>查看队列排序说明</summary>
        <p>{queue.methodology}</p>
      </details>
    </section>
  );
}
