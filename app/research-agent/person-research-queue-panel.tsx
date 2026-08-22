import Link from "next/link";
import { History, ListChecks, Search, ShieldCheck } from "lucide-react";

import {
  personResearchQueue,
  type PersonResearchOutcome,
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

const outcomeLabels: Record<PersonResearchOutcome, string> = {
  new_evidence: "发现新增证据",
  rediscovered: "仅重复命中",
  no_yield: "未发现合格材料",
  error: "执行失败",
  "": "暂无历史",
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
    ["历史效率", breakdown.researchHistory],
  ] as const;
}

function percent(value: number | null) {
  if (value === null) return "—";
  return `${Math.round(value * 100)}%`;
}

export default function PersonResearchQueuePanel() {
  const queue = personResearchQueue;
  const memory = queue.outcomeMemory;
  const dailyQueryUsage = queue.usedQuerySlotsToday + queue.allocatedQuerySlots;

  return (
    <section className={styles.queuePanel} aria-label="今日人物研究队列">
      <div className={styles.sectionHeading}>
        <div>
          <p className="section-index">TODAY&apos;S RESEARCH QUEUE</p>
          <h2>今日人物研究队列</h2>
        </div>
        <span>{queue.researchDate || "等待生成"}</span>
      </div>

      <p className={styles.queueIntro}>
        从全部开放人物研究任务中按可解释规则分配今日预算。队列只决定“先查什么”和主动检索槽位，
        不改变任何任务的事实状态或证据门槛；历史研究结果只用于减少重复、低产出的检索浪费。
      </p>

      <div className={styles.queueStats}>
        <article>
          <span>候选任务池</span>
          <strong>{queue.candidateTaskCount}</strong>
          <small>全部未关闭、未阻塞任务</small>
        </article>
        <article>
          <span>今日人物</span>
          <strong>{queue.selectedPeopleCount}/{queue.limits.people}</strong>
          <small>同一人物最多 {queue.limits.tasksPerPerson} 个任务</small>
        </article>
        <article>
          <span>今日任务</span>
          <strong>{queue.selectedTaskCount}/{queue.limits.tasks}</strong>
          <small>按研究价值和证据缺口排序</small>
        </article>
        <article>
          <span>主动检索日预算</span>
          <strong>{dailyQueryUsage}/{queue.limits.activeQuerySlots}</strong>
          <small>已执行 {queue.usedQuerySlotsToday} / 待执行 {queue.allocatedQuerySlots}</small>
        </article>
      </div>

      <div className={styles.memoryPanel} aria-label="Research Outcome Memory">
        <div className={styles.memoryHeading}>
          <div>
            <History size={16} aria-hidden="true" />
            <strong>Research Outcome Memory</strong>
          </div>
          <small>这里只衡量研究动作产出率，不代表材料可信度。</small>
        </div>
        <div className={styles.memoryStats}>
          <span>历史主动尝试 <strong>{memory.attemptCount}</strong></span>
          <span>产生新增证据 <strong>{memory.yieldingAttemptCount}</strong></span>
          <span>新增证据 URL <strong>{memory.newEvidenceCount}</strong></span>
          <span>未新增尝试 <strong>{memory.zeroYieldAttemptCount}</strong></span>
          <span>当前冷却任务 <strong>{memory.cooldownTaskCount}</strong></span>
        </div>
        {memory.sources.length > 0 && (
          <div className={styles.sourceYield} aria-label="研究入口历史产出率">
            {memory.sources.map((source) => (
              <span key={source.source}>
                {source.source} · {source.yieldingAttempts}/{source.attempts} 次有新增 · {percent(source.yieldRate)}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className={styles.queueList}>
        {queue.queue.map((item) => (
          <article key={item.taskId} className={styles.queueItem}>
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
                  {item.whyNow.map((reason) => <span key={reason}>{reason}</span>)}
                </div>
              )}

              <div className={styles.queueExecution}>
                <ListChecks size={14} aria-hidden="true" />
                <span>执行器：{executorLabels[item.executor]}</span>
                <span>检索槽位：{item.queryBudget}</span>
                <span>
                  现有证据：{item.evidenceBasisCount} 基础 / {item.candidateEvidenceCount} 候选
                </span>
              </div>

              {item.researchMemory.attempts > 0 && (
                <div className={styles.taskMemory} data-cooldown={item.cooldownActive ? "true" : "false"}>
                  <span>
                    历史：{item.researchMemory.attempts} 次主动尝试 / {item.researchMemory.yieldingAttempts} 次发现新增
                  </span>
                  <span>上次结果：{outcomeLabels[item.researchMemory.lastOutcome]}</span>
                  {item.researchMemory.zeroYieldStreak > 0 && (
                    <span>连续未新增：{item.researchMemory.zeroYieldStreak} 次</span>
                  )}
                  {item.cooldownActive && item.researchMemory.nextEligibleDate && (
                    <strong>主动检索冷却至 {item.researchMemory.nextEligibleDate}</strong>
                  )}
                </div>
              )}

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
          </article>
        ))}
        {!queue.queue.length && (
          <p className={styles.empty}>等待人物主动研究任务生成后形成今日队列。</p>
        )}
      </div>

      <p className={styles.queueMethodology}>{queue.methodology}</p>
    </section>
  );
}
