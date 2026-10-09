import type { Metadata } from "next";
import Link from "next/link";
import { Building2, Landmark, Radar, Route, ShieldCheck } from "lucide-react";
import watchlist from "@/config/innovation_listing_watchlist.json";
import lifecycle from "@/config/innovation_listing_lifecycle.json";
import { buildInnovationOpportunityPool } from "@/lib/innovation-capital-opportunity";
import { buildInnovationCapitalResearchModel } from "@/lib/innovation-capital-research";
import { InnovationDirectory } from "./innovation-directory";
import { InnovationListingLifecycle } from "./innovation-listing-lifecycle";
import { InnovationOpportunityPool } from "./innovation-opportunity-pool";
import { ListedInnovationDirectory } from "@/components/listed-innovation-directory";
import { InnovationGlobalInvestors } from "@/components/innovation-global-investors";
import { listedInnovationCompanies, listedInnovationApprovedAt } from "@/lib/listed-innovation-companies";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "科创频道",
  description: "以项目变化与可核验证据为核心，连接六家券商拟上市储备、全球重点科创投资机构、投资人观点与项目结果研究。",
};

export default function InnovationCapitalPage() {
  const projects = watchlist.projects;
  const opportunities = buildInnovationOpportunityPool();
  const research = buildInnovationCapitalResearchModel();
  const coreCount = projects.filter((item) => item.pool === "core").length;
  const observationCount = projects.filter((item) => item.pool === "observation").length;
  const refileCount = projects.filter((item) => item.pool === "refile").length;
  const aPlusHCount = projects.filter((item) => item.capitalMarketPath === "A+H").length;
  // These are recorded milestones, not a fabricated "today" feed. Preserve
  // source dates and never infer a previous status from a current-state record.
  const recordedNodes = [
    ...projects.map((item) => ({
      key: item.id, company: item.company, date: item.latestEventDate,
      event: item.latestEvent, stage: item.stage, broker: item.broker,
      sourceUrl: item.source.url, sourceTitle: item.source.title,
    })),
    ...lifecycle.projects.map((item) => ({
      key: item.id, company: item.company, date: item.latestEventDate,
      event: item.latestEvent, stage: item.stage, broker: item.broker,
      sourceUrl: item.sources[0]?.url ?? "", sourceTitle: item.sources[0]?.title ?? "",
    })),
  ].filter((item) => item.sourceUrl && item.date)
    .sort((a, b) => b.date.localeCompare(a.date));
  const latestNodes = [...new Map(recordedNodes.map((item) => [
    `${item.company}:${item.date}:${item.sourceUrl}`, item,
  ])).values()].slice(0, 6);

  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">03 / INNOVATION CAPITAL</p>
        <h1>科创频道</h1>
        <p className={styles.headerIntro}>
          从项目变化出发，连接技术、公司、投资人公开判断与资本行为。持续跟踪中信证券、中信建投、中金公司、
          国泰海通、华泰联合、广发证券的科创板、创业板及A+H硬科技项目储备，
          并以全球重点科创投资机构发现项目、验证论点和研究结果。
        </p>
        <div className={styles.statsGrid}>
          <div><Radar size={18} /><strong>{projects.length}</strong><span>拟上市储备记录</span></div>
          <div><ShieldCheck size={18} /><strong>{coreCount}</strong><span>明确双创板核心池</span></div>
          <div><Route size={18} /><strong>{observationCount}</strong><span>十五五硬科技观察池</span></div>
          <div><Landmark size={18} /><strong>{aPlusHCount}</strong><span>A+H / H先行</span></div>
          <div><Building2 size={18} /><strong>{refileCount}</strong><span>二次申报项目</span></div>
        </div>
        <div className={styles.asOf}>
          储备目录资料时点 {watchlist.asOf} · 生命周期资料时点 {lifecycle.asOf}。
          这是资料版本，不是今天的采集成功时间；页面重新部署不会自动刷新底层项目事实。
        </div>
      </header>

      <nav className="hero-chips" aria-label="科创研究视图">
        <a href="#recorded-changes">最近记录的项目节点</a>
        <a href="#project-reserves">拟上市项目储备</a>
        <a href="#listing-lifecycle-view">上市生命周期</a>
        <a href="#global-investors">全球重点投资机构</a>
        <a href="#research-patterns">资本与研究关系</a>
        <a href="#listed-innovation">上市科创标杆与产业生态（{listedInnovationCompanies.length}）</a>
      </nav>

      <section className={styles.researchSection} id="recorded-changes">
        <div className={styles.sectionHeader}>
          <div><span>RECORDED PROJECT MILESTONES</span><h2>先看项目节点，再进入完整档案</h2></div>
          <p>按已记录事件日期排序，不把历史材料冒充实时快讯。没有前一状态证据时，不绘制虚假的“原阶段 → 新阶段”。</p>
        </div>
        <div className={styles.methodGrid}>
          {latestNodes.map((item) => <article key={item.key}>
            <small>{item.date} · {item.broker}</small>
            <h3>{item.company}</h3><strong>{item.stage}</strong><p>{item.event}</p>
            <a href={item.sourceUrl} target="_blank" rel="noreferrer">{item.sourceTitle} ↗</a>
          </article>)}
        </div>
        <p className={styles.scopeNote}>节点来源沿用现有审核目录；本次界面调整未重新核验全部项目，也没有改写其上市状态。状态变化需要监管、交易所或明确机构原文支持。</p>
      </section>

      <div id="project-reserves"><InnovationDirectory /></div>
      <div id="listing-lifecycle-view"><InnovationListingLifecycle /></div>
      <InnovationGlobalInvestors />
      <InnovationOpportunityPool opportunities={opportunities} />

      <section className={styles.researchSection} id="research-patterns">
        <div className={styles.sectionHeader}>
          <div><span>RESEARCH PATTERNS</span><h2>从项目监控升级为规律研究</h2></div>
          <p>Research Agent 持续验证券商×赛道集中度、状态跳变、A+H / H→A、路线迁移、机构资本重复命中与成熟项目转化；
            当前样本只用于提出和更新研究假设，不输出上市概率、券商排名或投资评级。</p>
        </div>
        <div className={styles.researchSummary}>
          <article><strong>{research.tasks.length}</strong><span>当前结构化研究任务</span></article>
          <article><strong>{research.hypotheses.length}</strong><span>持续验证研究假设</span></article>
          <article><strong>{research.institutionCount}</strong><span>机构资本网络节点</span></article>
          <article><strong>{research.unknownRouteCount}</strong><span>保持板块未定的项目</span></article>
        </div>
        <div className={styles.researchHypotheses}>
          {research.hypotheses.slice(0, 4).map((item) => <article key={item.id}>
            <span>{item.status === "observed" ? "已观察到样本信号" : "持续验证"}</span>
            <h3>{item.title}</h3><p>{item.evidence}</p><small>下一验证：{item.nextCheck}</small>
          </article>)}
        </div>
        <Link className={styles.researchLink} href="/research-agent/#queuecf">进入 Research Agent 科创规律研究队列 →</Link>
      </section>

      <ListedInnovationDirectory rows={listedInnovationCompanies} approvedAt={listedInnovationApprovedAt} />

      <section className={styles.policySection} id="policy">
        <div className={styles.sectionHeader}>
          <div><span>POLICY RADAR</span><h2>科创上市政策雷达</h2></div>
          <p>只记录官方政策与交易所规则变化。十五五产业方向用于确定观察范围，不等同于企业已确定上市板块。</p>
        </div>
        <div className={styles.policyGrid}>
          {watchlist.policySignals.map((item) => <a href={item.url} target="_blank" rel="noreferrer" className={styles.policyCard} key={item.url}>
            <div className={styles.policyMeta}><span>{item.date}</span><span>{item.authority}</span></div>
            <h3>{item.title}</h3><p>{item.note}</p><span className={styles.sourceLink}>查看官方/原始来源 ↗</span>
          </a>)}
        </div>
      </section>

      <section className={styles.methodSection}>
        <div className={styles.sectionHeader}><div><span>METHODOLOGY</span><h2>入池与迁移规则</h2></div></div>
        <div className={styles.methodGrid}>
          <article><strong>核心池</strong><p>公开辅导或可靠监管引用明确指向科创板 / 创业板，且当前尚未进入交易所受理。</p></article>
          <article><strong>二次申报池</strong><p>历史曾递表后撤回、终止，当前重新辅导。历史申请不能抹掉，必须保留完整上市路径。</p></article>
          <article><strong>观察池</strong><p>已经启动A股辅导，属于重点硬科技方向，但公开材料尚未锁定科创板或创业板。</p></article>
          <article><strong>A+H</strong><p>港股与A股状态分开存储，不用单一“上市状态”覆盖。未公开确定的板块保持未知。</p></article>
          <article><strong>受理后迁移</strong><p>交易所受理后，从“辅导储备”转为“审核进展”，继续追踪问询、上会、注册、发行与上市。</p></article>
          <article><strong>证据等级</strong><p>优先监管/交易所与券商原文；机构观点、媒体转述与出资事实分开。板块未明示时禁止凭行业属性强行归类。</p></article>
        </div>
        <p className={styles.scopeNote}>{watchlist.scopeNote}</p>
      </section>
    </main>
  );
}
