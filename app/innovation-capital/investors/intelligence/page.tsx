import type { Metadata } from "next";
import Link from "next/link";
import {
  buildInvestorIntelligence,
  investorIntelligenceCoverage,
} from "@/lib/innovation-investor-intelligence";

export const metadata: Metadata = {
  title: "Investor Intelligence | 科创投资研究",
  description: "35家统一机构的已审查投资披露、投资人观点和项目进展证据索引。",
};

const kindLabels: Record<string, string> = {
  investment: "投资披露",
  viewpoint: "投资观点",
  outcome: "项目进展",
  "portfolio-relationship": "组合关系",
  "fund-announcement": "基金公告",
};

export default function InvestorIntelligencePage() {
  const rows = buildInvestorIntelligence();
  const coverage = investorIntelligenceCoverage(rows);
  return <main className="page-shell subpage">
    <header className="page-header">
      <p className="eyebrow">INNOVATION CAPITAL / INVESTOR INTELLIGENCE</p>
      <h1>机构投资情报</h1>
      <p>基于统一机构身份与逐条审查证据的投资方向、时间线、观点和项目进展索引。</p>
      <p>本页展示的是已审查样本，不代表完整投资组合，也不提供基金回报排名。</p>
      <Link href="/innovation-capital/investors/">← 返回机构研究</Link>
    </header>
    <section aria-label="样本覆盖">
      <h2>证据覆盖</h2>
      <p>{coverage.registeredInstitutions} 家机构 · {coverage.evidenceCoveredInstitutions} 家有样例 · {coverage.reviewedEvidenceRecords} 条已审查证据 · {coverage.reviewedCanonicalProjects} 个已关联项目</p>
    </section>
    <section aria-label="机构分析">
      <h2>逐机构分析</h2>
      {rows.map(row => <details key={row.institutionId} style={{marginBlock: "1rem"}}>
        <summary><strong>{row.name}</strong> — {row.reviewedEvidenceCount} 条证据 / {row.monitoredProjectCount} 个已关联项目</summary>
        <p>登记研究方向：{row.focusAreas.join("、") || "未登记"}</p>
        <p>已披露投资记录 {row.reviewedInvestmentCount} · 观点记录 {row.reviewedViewpointCount} · 项目结果记录 {row.reviewedOutcomeCount}。最近证据日期：{row.latestEvidenceDate ?? "无"}</p>
        {row.events.length === 0
          ? <p>暂无已审查样例；不代表该机构没有投资行为。</p>
          : <ol>{row.events.map(event => <li key={event.evidenceId} style={{marginBlock:"0.75rem"}}>
              <span>{event.date}（{event.datePrecision}） · {kindLabels[event.kind] ?? event.kind}</span>
              <p><strong>{event.projectName ?? "非项目事件"}：{event.headline}</strong></p>
              {event.participation && <p>披露参与角色：{event.participation}；轮次：{event.round ?? "未披露"}</p>}
              {event.viewpoints.map((speaker, i) => <p key={i}>署名：{speaker.name}（{speaker.roleAtPublication}）；项目责任：{speaker.projectResponsibility}</p>)}
              {event.outcomeStatus && <p>项目披露状态：{event.outcomeStatus}（不能据此推算投资人收益）</p>}
              <p><a href={event.sourceUrl} target="_blank" rel="noopener noreferrer">查看原始证据</a> · 后续核验：{event.followUp}</p>
            </li>)}</ol>}
      </details>)}
    </section>
    <section>
      <h2>解释口径</h2>
      <p>研究方向取自机构登记字段，并不表示已核实该机构在各方向的全部投资。证据按原有日期精度排序，年/月精度不能误读为具体交易日期。</p>
      <p>同一项目出现在多家机构记录中，不证明共同领投或参与同一融资轮次；组合项目关联人不自动等于交易负责人。</p>
      <p>没有可审计的基金投入和退出现金流，因此实际投资回报均保持未知。</p>
    </section>
  </main>;
}
