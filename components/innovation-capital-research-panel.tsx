import Link from "next/link";
import { ArrowRight, BrainCircuit, ListChecks, Network, Route, ShieldCheck } from "lucide-react";

import {
  buildInnovationCapitalResearchModel,
  type InnovationResearchTask,
} from "@/lib/innovation-capital-research";
import styles from "./innovation-capital-research-panel.module.css";

type Props = {
  anchorId?: string;
  context?: "innovation-capital" | "research-agent";
};

function QueueItem({ item }: { item: InnovationResearchTask }) {
  return (
    <article className={styles.queueItem}>
      <div className={styles.rank}>{String(item.rank).padStart(2, "0")}</div>
      <div className={styles.queueBody}>
        <div className={styles.meta}>
          <span>{item.priority} · {item.taskType}</span>
          <span>Research Score {item.score}</span>
        </div>
        <h3>{item.subject}</h3>
        <p>{item.question}</p>
        <div className={styles.whyNow}>
          {item.whyNow.slice(0, 3).map((reason) => <span key={reason}>{reason}</span>)}
        </div>
        <details className={styles.details}>
          <summary>查看证据要求与成功判据</summary>
          <div>
            <p><strong>下一证据：</strong>{item.nextEvidence}</p>
            <p><strong>成功判据：</strong>{item.successCriteria}</p>
            <Link href={item.href}>打开对应科创数据层 <ArrowRight size={13} aria-hidden="true" /></Link>
          </div>
        </details>
      </div>
    </article>
  );
}

export function InnovationCapitalResearchPanel({
  anchorId = "innovation-research",
  context = "innovation-capital",
}: Props) {
  const model = buildInnovationCapitalResearchModel();
  const primaryQueue = model.queue.slice(0, 5);
  const remainingQueue = model.queue.slice(5);
  const crossLink = context === "innovation-capital"
    ? "/research-agent/#innovation-capital-queue"
    : "/innovation-capital/#innovation-research";
  const crossLabel = context === "innovation-capital"
    ? "进入 Research Agent 科创研究队列"
    : "返回科创频道查看项目与证据";

  return (
    <section className={styles.panel} id={anchorId} aria-labelledby={`${anchorId}-title`}>
      <div className={styles.heading}>
        <div>
          <p className={styles.eyebrow}>INNOVATION CAPITAL RESEARCH</p>
          <h2 id={`${anchorId}-title`}>科创规律研究与 Research Queue</h2>
        </div>
        <Link className={styles.crossLink} href={crossLink}>
          {crossLabel}
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </div>

      <p className={styles.intro}>
        这一层不新增“第五类核心研究对象”，而是从已核验的项目、上市生命周期、机构资本和成熟候选中
        生成可持续验证的研究假设与任务。所有结论都保留样本边界：监管/交易所/券商原文优先，
        板块未公开确认时不推断为科创板或创业板。
      </p>

      <div className={styles.stats}>
        <article>
          <Route size={17} aria-hidden="true" />
          <strong>{model.stats.routeUnconfirmedCount}</strong>
          <span>板块待一级证据确认</span>
        </article>
        <article>
          <BrainCircuit size={17} aria-hidden="true" />
          <strong>{model.stats.lifecycleCount}</strong>
          <span>后续上市生命周期项目</span>
        </article>
        <article>
          <Network size={17} aria-hidden="true" />
          <strong>{model.stats.institutionCount}</strong>
          <span>相关资本机构</span>
        </article>
        <article>
          <ListChecks size={17} aria-hidden="true" />
          <strong>{model.queue.length}</strong>
          <span>当前结构化研究任务</span>
        </article>
      </div>

      <div className={styles.patternHeader}>
        <div>
          <span>PATTERN SNAPSHOT</span>
          <h3>当前样本里已经能看到什么</h3>
        </div>
        <small>数据时点 {model.asOf || "待同步"}</small>
      </div>
      <div className={styles.patternGrid}>
        {model.patterns.map((pattern) => (
          <article key={pattern.id}>
            <strong>{pattern.value}</strong>
            <h4>{pattern.title}</h4>
            <p>{pattern.summary}</p>
          </article>
        ))}
      </div>

      <div className={styles.researchColumns}>
        <section aria-labelledby={`${anchorId}-thesis-title`}>
          <div className={styles.subheading}>
            <BrainCircuit size={17} aria-hidden="true" />
            <div>
              <span>THESIS MEMORY</span>
              <h3 id={`${anchorId}-thesis-title`}>待持续验证的科创假设</h3>
            </div>
          </div>
          <div className={styles.thesisList}>
            {model.theses.map((thesis) => (
              <article key={thesis.id}>
                <div className={styles.meta}>
                  <span>{thesis.status}</span>
                  <span>样本研究，不作结果预测</span>
                </div>
                <h4>{thesis.title}</h4>
                <p>{thesis.observation}</p>
                <small><strong>下一证据：</strong>{thesis.nextEvidence}</small>
                <small><strong>边界：</strong>{thesis.caveat}</small>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby={`${anchorId}-queue-title`}>
          <div className={styles.subheading}>
            <ListChecks size={17} aria-hidden="true" />
            <div>
              <span>RESEARCH QUEUE</span>
              <h3 id={`${anchorId}-queue-title`}>今日优先研究任务</h3>
            </div>
          </div>
          <div className={styles.queueList}>
            {primaryQueue.map((item) => <QueueItem item={item} key={item.id} />)}
          </div>
          {remainingQueue.length > 0 && (
            <details className={styles.remaining}>
              <summary>查看其余研究任务（{remainingQueue.length}）</summary>
              <div className={styles.queueList}>
                {remainingQueue.map((item) => <QueueItem item={item} key={item.id} />)}
              </div>
            </details>
          )}
        </section>
      </div>

      <div className={styles.method}>
        <ShieldCheck size={16} aria-hidden="true" />
        <p>
          Research Queue 只负责提出下一步需要验证的问题和证据需求，不会把媒体报道自动升级成监管事实；
          融资轮次、辅导时长、机构重复出现和产业标签只作为研究信号，不代表上市概率、投资评级或券商优劣。
        </p>
      </div>
    </section>
  );
}
