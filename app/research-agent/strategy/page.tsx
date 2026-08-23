import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  Gauge,
  SearchCheck,
  ShieldCheck,
} from "lucide-react";

import { personResearchStrategyView } from "@/lib/person-research-strategy";
import styles from "./research-strategy.module.css";

export const metadata: Metadata = {
  title: "人物研究策略｜Research Agent",
  description: "展示人物主动研究中的查询策略、来源产出、任务-来源关系和单位检索成本，不改变事实证据门槛。",
};

const modeLabels = {
  observed: "历史观测",
  rule_prior: "规则先验",
  insufficient: "待积累",
};

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatDate(value: string) {
  if (!value) return "等待研究执行记录";
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

export default function PersonResearchStrategyPage() {
  const view = personResearchStrategyView;

  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <Link className={styles.backLink} href="/research-agent/">
          <ArrowLeft size={14} aria-hidden="true" />
          返回 Research Agent
        </Link>
        <p className="eyebrow">RESEARCH AGENT / STRATEGY MEMORY</p>
        <h1>人物研究策略</h1>
        <p>
          这里回答的不是“什么事实是真的”，而是“过去用什么方法更容易找到可核验证据”。
          Strategy Memory 只学习查询策略、来源产出和主动检索成本；事实是否成立仍由人物研究任务的 success criteria 与证据门决定。
        </p>
      </header>

      <section className={styles.statGrid} aria-label="研究策略记忆状态">
        <article>
          <SearchCheck size={18} aria-hidden="true" />
          <span>主动研究尝试</span>
          <strong>{view.attemptCount}</strong>
          <small>{formatDate(view.generatedAt)}</small>
        </article>
        <article>
          <BarChart3 size={18} aria-hidden="true" />
          <span>已观察查询策略</span>
          <strong>{view.observedStrategyCount}</strong>
          <small>仅统计真实执行历史</small>
        </article>
        <article>
          <Gauge size={18} aria-hidden="true" />
          <span>成本样本策略</span>
          <strong>{view.measuredCostStrategyCount}</strong>
          <small>真实主动检索耗时折算</small>
        </article>
        <article>
          <ShieldCheck size={18} aria-hidden="true" />
          <span>已观察来源类型</span>
          <strong>{view.observedSourceTypeCount}</strong>
          <small>候选产出 ≠ 事实 supported</small>
        </article>
      </section>

      <section className={styles.panel}>
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">TASK STRATEGY MAP</p>
            <h2>不同研究问题应该怎么查</h2>
          </div>
          <span>优先使用真实历史；无历史时明确标记规则先验</span>
        </div>
        <div className={styles.taskGrid}>
          {view.taskStrategies.map((task) => (
            <article key={task.taskType} className={styles.taskCard}>
              <div className={styles.cardMeta}>
                <span>{task.taskLabel}</span>
                <span>{modeLabels[task.mode]}</span>
              </div>
              <h3>{task.strategyLabel}</h3>
              {task.mode === "observed" ? (
                <p>
                  历史 {task.attempts} 次 · 候选命中 {percent(task.expectedSuccessRate)} ·
                  平均候选 {task.averageCandidates.toFixed(2)} · 单位成本产出 {task.candidateYieldPerCost.toFixed(2)}
                </p>
              ) : task.mode === "rule_prior" ? (
                <p>
                  当前调度以规则先验作为起点；预期值只用于有限预算排序，不应解释为历史成功率。
                </p>
              ) : (
                <p>尚无足够研究执行记录，不展示伪造的成功率或来源偏好。</p>
              )}
              <div className={styles.strategyFacts}>
                {task.sourceTypeLabel ? <span>优先来源：{task.sourceTypeLabel}</span> : <span>优先来源：待积累</span>}
                <span>预期成本：{task.averageCostUnits.toFixed(2)} 单位</span>
              </div>
              {task.queueExamples.length > 0 && (
                <div className={styles.examples}>
                  <small>当前队列示例</small>
                  {task.queueExamples.map((example) => (
                    <Link key={`${task.taskType}-${example.personRoute}-${example.question}`} href={example.personRoute}>
                      <strong>{example.personName}</strong>
                      <span>{example.question}</span>
                    </Link>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      </section>

      <div className={styles.twoColumn}>
        <section className={styles.panel}>
          <div className={styles.sectionHeading}>
            <div>
              <p className="section-index">QUERY EFFECTIVENESS</p>
              <h2>查询策略历史产出</h2>
            </div>
            <span>{view.strategies.length} 类有真实样本</span>
          </div>
          {view.strategies.length > 0 ? (
            <div className={styles.tableWrap}>
              <table>
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>尝试</th>
                    <th>候选命中</th>
                    <th>平均候选</th>
                    <th>平均成本</th>
                    <th>单位成本产出</th>
                  </tr>
                </thead>
                <tbody>
                  {view.strategies.map((strategy) => (
                    <tr key={strategy.strategy}>
                      <td><strong>{strategy.label}</strong></td>
                      <td>{strategy.attempts}</td>
                      <td>{percent(strategy.successRate)}</td>
                      <td>{strategy.averageCandidates.toFixed(2)}</td>
                      <td>{strategy.costSampleSize ? strategy.averageCostUnits.toFixed(2) : "待积累"}</td>
                      <td>{strategy.costSampleSize ? strategy.candidateYieldPerCost.toFixed(2) : "待积累"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className={styles.emptyState}>
              <strong>尚无真实 Query Strategy 样本</strong>
              <p>系统会继续按规则先验执行有界检索；只有真实主动研究 attempt 累积后，才会在这里显示历史命中率与成本效率。</p>
            </div>
          )}
        </section>

        <section className={styles.panel}>
          <div className={styles.sectionHeading}>
            <div>
              <p className="section-index">SOURCE YIELD</p>
              <h2>来源候选产出</h2>
            </div>
            <span>{view.sources.length} 类有真实样本</span>
          </div>
          {view.sources.length > 0 ? (
            <div className={styles.sourceList}>
              {view.sources.map((source) => (
                <article key={source.sourceType}>
                  <div>
                    <strong>{source.label}</strong>
                    <span>覆盖 {source.taskCoverage} 类研究任务</span>
                  </div>
                  <dl>
                    <div><dt>候选出现率</dt><dd>{percent(source.yieldRate)}</dd></div>
                    <div><dt>任务尝试</dt><dd>{source.taskAttempts}</dd></div>
                    <div><dt>候选材料</dt><dd>{source.candidates}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <strong>尚无来源产出样本</strong>
              <p>零历史时不会假设“视频一定优于论文”或“官方一定命中”；来源偏好必须由后续真实研究执行积累。</p>
            </div>
          )}
        </section>
      </div>

      <section className={styles.methodPanel}>
        <p className="section-index">EVIDENCE BOUNDARY</p>
        <h2>研究策略不是事实判断器</h2>
        <div className={styles.methodGrid}>
          <article>
            <strong>Strategy Memory 可以做</strong>
            <p>比较查询方式、来源候选产出、真实检索成本与有限预算效率。</p>
          </article>
          <article>
            <strong>Strategy Memory 不可以做</strong>
            <p>不能把 candidate_found 解释为事实成立，不能修改 supported，也不能绕过 success criteria。</p>
          </article>
          <article>
            <strong>低样本如何处理</strong>
            <p>无真实历史时只展示“规则先验”；不展示伪造的历史命中率，不因一次偶然成功形成强来源偏好。</p>
          </article>
        </div>
        <p className={styles.methodology}>{view.methodology}</p>
      </section>
    </main>
  );
}
