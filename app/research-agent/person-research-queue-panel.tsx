import Link from "next/link";
import { ListChecks, Search, ShieldCheck } from "lucide-react";

import { personResearchQueue } from "@/lib/person-research-queue";
import styles from "./research-agent.module.css";

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

function scoreSummary(breakdown: typeof personResearchQueue.queue[number]["scoreBreakdown"]) {
  return [
    ["优先级", breakdown.priority],
    ["类型", breakdown.taskType],
    ["状态", breakdown.status],
    ["缺口", breakdown.evidenceGap],
    ["近期", breakdown.recency],
    ["交叉验证", breakdown.crossValidation],
    ["可执行", breakdown.queryReadiness],
  ] as const;
}

export default function PersonResearchQueuePanel() {
  const queue = personResearchQueue;

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
        不改变任何任务的事实状态或证据门槛。
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
          <span>主动检索槽位</span>
          <strong>{queue.allocatedQuerySlots}/{queue.limits.activeQuerySlots}</strong>
          <small>每位人物最多占用 1 个槽位</small>
        </article>
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
