import Link from "next/link";
import { globalInnovationInvestors, investorEvidenceSummary } from "@/lib/innovation-investor-research";
import styles from "@/app/innovation-capital/page.module.css";

export function InnovationGlobalInvestors() {
  const summary = investorEvidenceSummary();
  const groups = [...new Set(globalInnovationInvestors.map((item) => item.regionGroup))];
  return <section className={styles.researchSection} id="global-investors">
    <div className={styles.sectionHeader}><div><span>GLOBAL INNOVATION INVESTORS</span><h2>从机构发现项目，从证据研究结果</h2></div><p>全球30家重点研究样本。项目投资、投资人观点、基金募集和退出节点分开；不发布缺少现金流依据的收益排名。</p></div>
    <div className={styles.researchSummary}><article><strong>{summary.registeredInstitutions}</strong><span>登记机构，不是收益排名</span></article><article><strong>{summary.evidenceCoveredInstitutions}</strong><span>已有核验样例的机构</span></article><article><strong>{summary.reviewedRecords}</strong><span>可回溯原文的样例条目</span></article><article><strong>未知</strong><span>基金实际回报</span></article></div>
    <div className={styles.methodGrid}>{groups.map((group) => <article key={group}><strong>{group}</strong><p>{globalInnovationInvestors.filter((item) => item.regionGroup === group).map((item) => item.name).join("、")}</p></article>)}</div>
    <p className={styles.scopeNote}>{summary.coverageLabel}。没有样例不代表没有投资；官方入口核验不等于已完整接入组合、人物和动态采集。</p>
    <Link className={styles.researchLink} href="/innovation-capital/investors/">打开机构、项目、投资人发言与结果研究 →</Link>
  </section>;
}
