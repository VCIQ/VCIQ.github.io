import type { Metadata } from "next";
import Link from "next/link";
import { buildInvestorIntelligence, investorIntelligenceCoverage, investorEvidenceDateLabel } from "@/lib/innovation-investor-intelligence";
import { formatDisclosedMoney, investorEvidenceKindLabels, investorResearchReviewedAt } from "@/lib/innovation-investor-research";
import styles from "./intelligence.module.css";

export const metadata: Metadata = {
  title: "机构投资情报 | 科创投资研究",
  description: "区分管理人资格、基金募集、项目投资与退出回款，追踪研究机构的已审查披露、观点和项目进展。",
};
const dimensions = [["registration", "管理人资格"], ["fundraising", "基金募集"], ["investment", "项目投资"], ["exit", "退出回款"]] as const;
const outcomeLabels: Record<string, string> = {acquired:"项目被收购", listed:"项目上市", "company-reported-commercial-update":"公司自述商业进展"};

export default function InvestorIntelligencePage() {
  const rows = buildInvestorIntelligence();
  const coverage = investorIntelligenceCoverage(rows);
  const globalCount = rows.filter(row => row.cohorts.includes("global-core")).length;
  const chinaCount = rows.filter(row => row.cohorts.includes("china-focus")).length;
  const overlap = rows.filter(row => row.cohorts.includes("global-core") && row.cohorts.includes("china-focus")).length;
  return <main className="page-shell subpage">
    <header className="page-header">
      <p className="eyebrow">INNOVATION CAPITAL / INVESTOR INTELLIGENCE</p>
      <h1>机构投资情报</h1>
      <p className={styles.intro}>从公开判断走到实际出手，再跟踪项目后续变化。每条结论保留原始来源与尚待核验的问题。</p>
      <nav className={styles.links} aria-label="机构研究导航">
        <Link href="/innovation-capital/">科创频道</Link>
        <Link href="/innovation-capital/investors/">机构与项目档案</Link>
        <Link href="/innovation-capital/coverage/">采集覆盖与缺口</Link>
        <a href="#activity-evidence">四项证据口径</a>
      </nav>
    </header>
    <section className={styles.metrics} aria-label="已审查样本覆盖">
      <article><strong>{coverage.registeredInstitutions}</strong><span>统一研究目录机构</span></article>
      <article><strong>{coverage.evidenceCoveredInstitutions}</strong><span>有已审查证据的机构</span></article>
      <article><strong>{coverage.reviewedEvidenceRecords}</strong><span>已审查证据条目</span></article>
      <article><strong>{coverage.reviewedCanonicalProjects}</strong><span>已关联项目身份</span></article>
    </section>
    <aside className={styles.boundary}>
      <strong>两个“35家”不是同一份名单</strong>
      <p>本研究目录合并全球核心 {globalCount} 家与中国重点 {chinaCount} 家，重合 {overlap} 家，去重为 {coverage.registeredInstitutions} 家。这是本站研究样本，与投中网报道的“35家新登记管理人”不是同一集合，不能互用登记数量、月份或登记日期结论。</p>
      <p>证据集核验记录：{investorResearchReviewedAt}（UTC）。该时间不表示全部机构的最新登记、股东、高管或基金状态已实时复核。当前自动发现仍按既有全球核心目录运行，完整覆盖请查看采集覆盖页。</p>
    </aside>
    <section id="activity-evidence" className={styles.section}>
      <h2>四项证据分别核验</h2>
      <p>取得管理人资格、完成基金募集、披露项目投资、形成退出回款是不同事实。它们不是可由前一项自动推导的进度条，也不是机构实力排名。</p>
      <div className={styles.stageGrid}>
        <article><h3>管理人资格</h3><p>核对适用司法辖区、法律主体、登记编号、当前状态与核验日期；国际机构不能统一套用中基协登记。</p></article>
        <article><h3>基金募集</h3><p>分别记录基金设立、目标规模、认缴承诺、募集关闭、产品备案与实缴。基金公告不能自动升级为募集完成。</p></article>
        <article><h3>项目投资</h3><p>区分组合关系、具体投资披露、轮次总额与机构出资额。投资人观点和组合页面不能补成未披露的交易。</p></article>
        <article><h3>退出回款</h3><p>分别核验上市或并购、持股出售、现金回款与基金分配；没有可审计现金流时，实际回报保持未知。</p></article>
      </div>
    </section>
    <section className={styles.section} aria-label="机构分析">
      <h2>逐机构证据与下一步核验</h2>
      <p className={styles.note}>目录研究主题是本站维护的跟踪方向，不代表已核实的投资分布。暂无证据表示资料缺口，不等于没有业务。</p>
      <nav className={styles.directory} aria-label="跳转到研究机构">{rows.map(row => <a href={`#institution-${row.institutionId}`} key={row.institutionId}>{row.name}<span>{row.reviewedEvidenceCount} 条</span></a>)}</nav>
      {rows.map(row => <details id={`institution-${row.institutionId}`} key={row.institutionId} className={styles.institution}>
        <summary><strong>{row.name}</strong><span>{row.reviewedEvidenceCount} 条证据 · {row.monitoredProjectCount} 个项目</span></summary>
        <div className={styles.body}>
          <p>目录研究主题：{row.focusAreas.join("、") || "待补充"}</p>
          <dl className={styles.stageGrid}>{dimensions.map(([key,label]) => <div key={key}><dt>{label} · {row.activityEvidence[key].status === "observed" ? "有已审查披露" : "未核验 / 未知"}</dt><dd>{row.activityEvidence[key].explanation}</dd></div>)}</dl>
          <p className={styles.note}>投资披露 {row.reviewedInvestmentCount} · 观点 {row.reviewedViewpointCount} · 基金/主题公告 {row.fundAnnouncementCount} · 项目进展 {row.reviewedOutcomeCount}。数字均为证据条目数。</p>
          {row.events.length === 0 ? <p>暂无已审查样例。先补齐官方来源与具体事件，再判断投资活动。</p> : <ol className={styles.events}>{row.events.map(event => <li key={event.evidenceId}>
            <p className={styles.note}>{investorEvidenceDateLabel(event.date,event.datePrecision)} · {investorEvidenceKindLabels[event.kind] ?? event.kind}</p>
            <h3>{event.headline}</h3><p>{event.summary}</p>
            {event.projectName && <p>关联项目：{event.projectName}</p>}
            {event.kind === "investment" && <p>披露参与角色：{event.participation ?? "未披露"}；轮次：{event.round ?? "未披露"}。轮次总额：{formatDisclosedMoney(event.roundAmount)}；机构出资额：{formatDisclosedMoney(event.investorAmount)}。</p>}
            {event.viewpoints.map((speaker, i) => <p key={i}>署名 / 发言人：{speaker.name}（{speaker.roleAtPublication}）。责任范围：{speaker.projectResponsibility}。观点采用转述，不作为逐字引语。</p>)}
            {event.outcomeStatus && <p>项目节点：{outcomeLabels[event.outcomeStatus] ?? event.outcomeStatus}；机构退出回款与基金实际回报仍未核验。</p>}
            <p><a href={event.sourceUrl} target="_blank" rel="noopener noreferrer">{event.sourceTitle} ↗</a></p>
            <p className={styles.note}>来源：{event.sourcePublisher} · 原文日期：{event.sourcePublishedAt || "未披露"} · 定位：{event.sourceLocator}</p>
            <p className={styles.next}>下一步核验：{event.followUp}</p>
          </li>)}</ol>}
        </div>
      </details>)}
    </section>
    <section className={styles.section}>
      <h2>如何阅读这份证据索引</h2>
      <p>按已知日期分组展示；只有年或月的记录无法确定同期间内的先后顺序。事件日期与原文发布日期分开保留，后续采访不能充当历史投资的交割日。</p>
      <p>同一项目出现在多家机构记录中，不证明共同领投或参与同一轮。项目上市、被收购及公司自述进展也不构成机构投资回报证明。</p>
      <p>本页仅展示已审查样本，不代表完整组合；不计算机构成功率、IRR、DPI、TVPI或收益排名。</p>
    </section>
  </main>;
}

