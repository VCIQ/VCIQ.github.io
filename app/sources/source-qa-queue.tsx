import sourceLifecyclePolicyConfig from "@/config/source_lifecycle_policy.json";
import type { SourceDirectoryEntry } from "@/lib/source-directory";
import type { SourceLifecyclePolicy } from "@/lib/source-lifecycle";
import {
  buildSourceQaQueue,
  summarizeSourceQaQueue,
  type SourceQaTier,
} from "@/lib/source-qa-queue";
import styles from "./source-qa-queue.module.css";

const roleLabels = {
  primary: "PRIMARY",
  corroboration: "CORROBORATION",
  discovery: "DISCOVERY",
} as const;

const tierLabels: Record<SourceQaTier, string> = {
  "qa-now": "NOW",
  "qa-next": "NEXT",
  defer: "DEFER",
};

function tierClass(tier: SourceQaTier): string {
  if (tier === "qa-now") return styles.now;
  if (tier === "qa-next") return styles.next;
  return styles.defer;
}

function rate(value: number | null): string {
  return value === null ? "待落账" : `${Math.round(value * 100)}%`;
}

export default function SourceQaQueue({ sources }: { sources: SourceDirectoryEntry[] }) {
  const policy = sourceLifecyclePolicyConfig as SourceLifecyclePolicy;
  const rows = buildSourceQaQueue(sources, policy);
  const summary = summarizeSourceQaQueue(rows);
  const visible = rows.slice(0, 12);

  return (
    <section className={styles.qaSection} aria-label="Source QA queue">
      <div className={styles.heading}>
        <div>
          <span>SOURCE QA QUEUE</span>
          <h2>优先审核最可能因人工抽查而接近 Core Ready 的 Source。</h2>
          <p>
            队列不创造新的分数：只读取现有 Core Gate、人工抽查数量与误归属审计证据。
            仅纳入默认可晋级 Core 的 Primary / Corroboration；Discovery-only 不消耗 Core QA 预算。
            非 QA Gate 较多或采集不健康的 Source 会自动下沉。
          </p>
        </div>
        <small>
          人工抽查目标 {policy.coreMinReviewedRecords} 条 / Source ·
          误归属率上限 {Math.round(policy.coreMaxMisattributionRate * 100)}%
        </small>
      </div>

      <div className={styles.summary}>
        <article><small>需要 QA</small><b>{summary.total}</b><span>Core 候选存在抽查 / 误归属证据缺口</span></article>
        <article><small>现在审核</small><b>{summary.now}</b><span>QA 是主要或唯一量化阻塞</span></article>
        <article><small>下一批</small><b>{summary.next}</b><span>只剩少量其他 Gate</span></article>
        <article><small>暂缓</small><b>{summary.deferred}</b><span>先处理采集 / 样本 / 质量问题</span></article>
      </div>

      <div className={styles.table} role="table" aria-label="Source QA priorities">
        <div className={styles.head} role="row">
          <span>SOURCE</span>
          <span>QA PROGRESS</span>
          <span>MISATTRIBUTION</span>
          <span>OTHER GATES</span>
          <span>ACTION</span>
        </div>
        {visible.map((row) => {
          const progress = Math.min(100, Math.round((row.reviewedRecords / row.requiredReviewedRecords) * 100));
          return (
            <article className={styles.row} role="row" key={row.sourceId}>
              <div className={styles.source}>
                <b>{row.name}</b>
                <span>{roleLabels[row.sourceRole]} · {row.kind}</span>
                <small>{row.healthStatus.toUpperCase()}</small>
              </div>
              <div className={styles.progress}>
                <b>{row.reviewedRecords} / {row.requiredReviewedRecords}</b>
                <div aria-label={`人工抽查完成 ${progress}%`}><i style={{ width: `${progress}%` }} /></div>
                <small>{row.reviewGap > 0 ? `还差 ${row.reviewGap} 条` : "抽查数量已满足"}</small>
              </div>
              <div className={styles.audit}>
                <b>{rate(row.misattributionRate)}</b>
                <span>{row.misattributionEvidenceMissing ? "需要形成可审计误归属率" : "已形成审计指标"}</span>
              </div>
              <div className={styles.blockers}>
                <b>{row.otherBlockers.length}</b>
                <span>{row.otherBlockers.length ? row.otherBlockers.slice(0, 2).join(" · ") : "无其他量化阻塞"}</span>
              </div>
              <div className={styles.action}>
                <strong className={`${styles.tier} ${tierClass(row.tier)}`}>{tierLabels[row.tier]}</strong>
                <p>{row.rationale}</p>
              </div>
            </article>
          );
        })}
        {!visible.length ? <p className={styles.empty}>当前没有需要人工 QA 的 Core 候选 Source。</p> : null}
      </div>

      {rows.length > visible.length ? (
        <p className={styles.note}>当前优先展示前 {visible.length} 个；剩余 {rows.length - visible.length} 个排在后续 QA 队列。</p>
      ) : null}
    </section>
  );
}
