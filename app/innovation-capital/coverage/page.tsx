import type { Metadata } from "next";
import Link from "next/link";
import { investorResearchReviewedAt } from "@/lib/innovation-investor-research";
import { investorRegistryV2Errors } from "@/lib/innovation-investor-registry-v2";
import { buildInvestorCoverageDirectory } from "@/lib/innovation-investor-coverage";
import { InvestorCoverageDirectory } from "./coverage-directory";
import styles from "./coverage.module.css";

export const metadata: Metadata = {
  title: "全球与中国科创投资机构覆盖质量",
  description: "基于唯一机构ID与已审核原始证据，审计35家全球及中国重点科创投资机构的来源接入和研究样本，不虚构覆盖健康度或投资回报。",
};

export default function InvestorCoveragePage() {
  const errors = investorRegistryV2Errors();
  if (errors.length) throw new Error(`Investor registry v2 invalid: ${errors.join("; ")}`);
  const {rows, summary} = buildInvestorCoverageDirectory();

  return <main className="page-shell subpage">
    <header className="page-header">
      <p className="eyebrow">INNOVATION CAPITAL / INVESTOR COVERAGE</p>
      <h1>全球与中国科创投资机构覆盖质量</h1>
      <p className={styles.intro}>统一全球既有机构与中国重点科创机构的研究入口。按照 canonical ID 去重，
        分开记录官网已登记、投资披露已核实、持续监测尚待完善三个不同层次。</p>
      <div className={styles.quickLinks}>
        <Link href="/innovation-capital/">← 返回科创研究</Link>
        <Link href="/innovation-capital/investors/">全球30家机构深度研究 →</Link>
      </div>
    </header>

    <section aria-label="统一机构覆盖总览" className={styles.overview}>
      <div><strong>{summary.uniqueInstitutions}</strong><span>唯一科创投资机构</span></div>
      <div><strong>{summary.globalCore}</strong><span>原全球重点机构</span></div>
      <div><strong>{summary.chinaFocus}</strong><span>中国重点机构</span></div>
      <div><strong>{summary.withVerifiedEvidence}</strong><span>已有核实样例的机构</span></div>
      <div><strong>{summary.reviewedEvidenceRecords}</strong><span>经审核的证据条目</span></div>
      <div><strong>{summary.registeredHomepages}/{summary.uniqueInstitutions}</strong><span>已登记官网入口</span></div>
    </section>

    <aside className={styles.methodNote}>
      <strong>研究分组不能直接相加</strong>
      <p>全球{summary.globalCore}家、中国重点{summary.chinaFocus}家，共有{summary.overlap}家重合，按机构ID去重后共{summary.uniqueInstitutions}家。
        当前并行 Registry v2 不改变旧30家官网 Scout 的运行范围，也不会自动发布新机构的投资新闻。</p>
      <p>数据台账最后人工审核：{investorResearchReviewedAt}（UTC）；这不是“最后成功抓取时间”。已登记官网不等于已完整采集官网新闻、投资组合和投资人发言。</p>
    </aside>

    <InvestorCoverageDirectory rows={rows} />

    <section className={styles.methodology} id="coverage-methodology">
      <h2>Coverage Score 为什么暂不显示分数？</h2>
      <p>目前只有可核验的原文与机构身份计数，没有跨机构可比较的长期成功扫描率、栏目召回率和审核滞后数据。
        因此所有机构暂标为“待评估”，不会人为填写80分、90分，也不会把“0条核实证据”理解成“没有投资”。</p>
      <div className={styles.methodSteps}>
        <article><h3>1. 官方来源覆盖</h3><p>校验官网、新闻、组合与团队入口，记录不可访问和结构变化。缺失来源保持未知。</p></article>
        <article><h3>2. 证据质量</h3><p>按原文、项目身份、参与角色与日期粒度计算审核样本；不将融资总额归为机构出资额。</p></article>
        <article><h3>3. 连续采集</h3><p>积累多次成功 Scout 与不同来源的变化量，区分网站故障、采集漏报和真实无新增。</p></article>
        <article><h3>4. 历史关系</h3><p>Sequoia Capital 与 HongShan 独立建档，历史品牌关联不构成当前同一主体。</p></article>
      </div>
      <p className={styles.footerNote}>该页面为覆盖治理面板，而不是基金收益排名。已审核投资事件仍以原研究台账及官方原文为准；首次上线不新增未经审核的投资关系。</p>
    </section>
  </main>;
}
