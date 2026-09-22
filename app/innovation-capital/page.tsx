import type { Metadata } from "next";
import { Building2, Landmark, Radar, Route, ShieldCheck } from "lucide-react";
import watchlist from "@/config/innovation_listing_watchlist.json";
import { InnovationDirectory } from "./innovation-directory";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "科创频道",
  description: "跟踪五大头部券商科创板、创业板、A+H及十五五硬科技拟上市项目储备与上市政策。",
};

export default function InnovationCapitalPage() {
  const projects = watchlist.projects;
  const coreCount = projects.filter((item) => item.pool === "core").length;
  const observationCount = projects.filter((item) => item.pool === "observation").length;
  const refileCount = projects.filter((item) => item.pool === "refile").length;
  const aPlusHCount = projects.filter((item) => item.capitalMarketPath === "A+H").length;

  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">03 / INNOVATION CAPITAL</p>
        <h1>科创频道</h1>
        <p className={styles.headerIntro}>
          面向一级市场与PE/VC项目挖掘，持续跟踪中信证券、中信建投、中金公司、国泰海通、华泰联合的
          科创板、创业板及A+H硬科技项目储备。项目进入交易所审核后不删除，而是继续转入上市审核生命周期跟踪。
        </p>

        <div className={styles.statsGrid}>
          <div><Radar size={18} /><strong>{projects.length}</strong><span>首批跟踪项目</span></div>
          <div><ShieldCheck size={18} /><strong>{coreCount}</strong><span>明确双创板核心池</span></div>
          <div><Route size={18} /><strong>{observationCount}</strong><span>十五五硬科技观察池</span></div>
          <div><Landmark size={18} /><strong>{aPlusHCount}</strong><span>A+H / H先行</span></div>
          <div><Building2 size={18} /><strong>{refileCount}</strong><span>二次申报项目</span></div>
        </div>

        <div className={styles.asOf}>
          数据时点 {watchlist.asOf} · 首批数据为人工核验种子集，后续应由证监会辅导公示、交易所审核状态与券商公告持续更新。
        </div>
      </header>

      <InnovationDirectory />

      <section className={styles.policySection} id="policy">
        <div className={styles.sectionHeader}>
          <div>
            <span>POLICY RADAR</span>
            <h2>科创上市政策雷达</h2>
          </div>
          <p>
            只记录官方政策与交易所规则变化。十五五产业方向用于确定观察范围，不等同于企业已确定上市板块。
          </p>
        </div>
        <div className={styles.policyGrid}>
          {watchlist.policySignals.map((item) => (
            <a href={item.url} target="_blank" rel="noreferrer" className={styles.policyCard} key={item.url}>
              <div className={styles.policyMeta}>
                <span>{item.date}</span>
                <span>{item.authority}</span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.note}</p>
              <span className={styles.sourceLink}>查看官方/原始来源 ↗</span>
            </a>
          ))}
        </div>
      </section>

      <section className={styles.methodSection}>
        <div className={styles.sectionHeader}>
          <div>
            <span>METHODOLOGY</span>
            <h2>入池与迁移规则</h2>
          </div>
        </div>
        <div className={styles.methodGrid}>
          <article>
            <strong>核心池</strong>
            <p>公开辅导或可靠监管引用明确指向科创板 / 创业板，且当前尚未进入交易所受理。</p>
          </article>
          <article>
            <strong>二次申报池</strong>
            <p>历史曾递表后撤回、终止，当前重新辅导。历史申请不能抹掉，必须保留完整上市路径。</p>
          </article>
          <article>
            <strong>观察池</strong>
            <p>已经启动A股辅导，属于重点硬科技方向，但公开材料尚未锁定科创板或创业板。</p>
          </article>
          <article>
            <strong>A+H</strong>
            <p>港股已上市或已递交港股申请，同时推进A股辅导。A股与港股状态分开存储，不用单一“上市状态”覆盖。</p>
          </article>
          <article>
            <strong>受理后迁移</strong>
            <p>交易所一旦受理，从“辅导储备”转为“审核进展”，继续追踪问询、上会、注册、发行与上市。</p>
          </article>
          <article>
            <strong>证据等级</strong>
            <p>优先监管/交易所与券商原文；媒体仅在明确援引监管材料时作为补充。板块未明示时禁止凭行业属性强行归类。</p>
          </article>
        </div>
        <p className={styles.scopeNote}>{watchlist.scopeNote}</p>
      </section>
    </main>
  );
}
