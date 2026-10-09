import type { Metadata } from "next";
import Link from "next/link";
import {
  globalInnovationInvestors, investorEvidenceRecords, investorEvidenceScope,
  investorEvidenceSummary, investorMonitoringPolicy, investorResearchReviewedAt,
  investorResearchScope, validateInvestorResearch,
} from "@/lib/innovation-investor-research";
import { InvestorResearchDirectory } from "./research-directory";
import styles from "./research.module.css";

export const metadata: Metadata = {
  title: "全球重点科创投资机构研究",
  description: "30家重点研究样本，分开核验项目、投资人公开观点、投资行为和结果；不将退出新闻等同于基金收益。",
};

export default function InnovationInvestorsPage() {
  const errors = validateInvestorResearch();
  if (errors.length) throw new Error(`Investor evidence contract: ${errors.join("; ")}`);
  const summary = investorEvidenceSummary();
  return <main className="page-shell subpage">
    <header className="page-header">
      <p className="eyebrow">INNOVATION CAPITAL / GLOBAL INVESTOR RESEARCH</p>
      <h1>全球重点科创投资机构研究</h1>
      <p className={styles.intro}>{investorResearchScope}</p>
      <p className={styles.note}>目录及样例核验记录：{investorResearchReviewedAt}（UTC）。不代表全部项目的最新状态。</p>
      <Link href="/innovation-capital/">← 返回科创频道</Link>
    </header>
    <section className={styles.metrics} aria-label="证据覆盖范围">
      <article><strong>{summary.registeredInstitutions}</strong><span>登记研究样本</span></article>
      <article><strong>{summary.evidenceCoveredInstitutions}</strong><span>具备核验事件样例</span></article>
      <article><strong>{summary.reviewedRecords}</strong><span>来源可追溯的证据条目</span></article>
      <article><strong>未知</strong><span>基金实际回报，不推算</span></article>
    </section>
    <aside className={styles.boundary}><strong>覆盖范围 ≠ 投资业绩</strong><p>{investorMonitoringPolicy}</p><p>{investorEvidenceScope}</p></aside>
    <InvestorResearchDirectory institutions={globalInnovationInvestors} records={investorEvidenceRecords} />
    <section className={styles.method} id="methodology">
      <h2>投资行为与结果：先统一分母，再讨论差异</h2>
      <div className={styles.methodGrid}>
        <article><h3>出手行为</h3><p>区分新投、跟投、共同领投、并购、基金募集。融资总额与本机构出资额分列；未知值不填零。</p></article>
        <article><h3>投资人发言</h3><p>记录原始链接、署名、发言时间、当时职务、项目语境、论点与验证条件。转述不加引号；没有项目责任证据，不写“主导投资”。</p></article>
        <article><h3>项目结果</h3><p>技术验证、临床进展、客户订单、后续融资、上市、并购、清算分别记录。只发现成功项目的样本不能用于比较成功率。</p></article>
        <article><h3>财务回报</h3><p>实际回报需要同一基金、币种、费用口径和带日期现金流。没有这些资料，不展示IRR、DPI、TVPI或倍数排名。</p></article>
      </div>
      <p className={styles.note}>登记和自动发现不会直接创建正式投资关系。只有逐项核验后的证据进入本页；原有券商项目、公司主档、上市生命周期继续保留。</p>
    </section>
  </main>;
}
