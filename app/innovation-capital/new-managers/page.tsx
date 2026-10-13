import type { Metadata } from "next";
import Link from "next/link";
import { newManagerCohort, newManagerCohortSummary } from "@/lib/innovation-new-managers";
import styles from "../investors/intelligence/intelligence.module.css";
import table from "./page.module.css";
export const metadata: Metadata = {title:"投中新登记35家独立样本 | 科创研究", description:"逐项核对投中网35家固定名单与协会独立档案，区分登记、基金产品、投资与退出证据。"};
export default function NewManagersPage() {
  const cohort = newManagerCohort, summary = newManagerCohortSummary();
  return <main className="page-shell subpage">
    <header className="page-header"><p className="eyebrow">INNOVATION CAPITAL / REGISTRATION COHORT</p><h1>投中新登记 35 家独立样本</h1>
      <p className={styles.intro}>从媒体公布名单追溯到协会独立档案。固定样本截至 {cohort.sourceAsOf}，本次逐项查阅日期 {cohort.checkedAt}。本页与全球/中国重点投资机构研究目录分别统计。</p>
      <nav className={styles.links} aria-label="样本研究导航"><Link href="/innovation-capital/">科创频道</Link><Link href="/innovation-capital/investors/intelligence/">机构投资情报</Link><a href={cohort.sourceUrl} target="_blank" rel="noreferrer">投中网原报道</a><a href={cohort.listUrl} target="_blank" rel="noreferrer">协会查询入口</a></nav>
    </header>
    <section className={styles.metrics} aria-label="固定样本核查进展"><article><strong>{summary.total}</strong><span>媒体三表固定样本</span></article><article><strong>{summary.profilesChecked}</strong><span>已读取协会独立档案</span></article><article><strong>{summary.afterJune5}</strong><span>6月5日后登记</span></article><article><strong>{summary.withManagedFunds}</strong><span>列表显示有在管基金</span></article></section>
    <aside className={styles.boundary}><strong>核查结论与边界</strong><p>{cohort.scopeNote}</p><p>三张表合计：市场化 18 家、CVC 3 家、国资 14 家。原报道正文另有“40家”“6月5日后20家”的表述；对本页固定35家重算为15家，不能套用40家的推论。</p><p>{cohort.dateDisplayNote}</p><ul>{cohort.limitations.map(note=><li key={note}>{note}</li>)}</ul></aside>
    <section className={styles.section}><h2>按独立档案登记日期重算</h2><div className={table.scroll}><table className={table.table}><caption>2026年1—9月样本内登记数量（含零值月份）</caption><thead><tr>{summary.months.map(row=><th scope="col" key={row.month}>{row.month}</th>)}<th scope="col">合计</th></tr></thead><tbody><tr>{summary.months.map(row=><td key={row.month}>{row.count}</td>)}<td>{summary.total}</td></tr></tbody></table></div></section>
    <section className={styles.section}><h2>35 家档案与逐项证据</h2><p>分类沿用媒体原表；管理人资格、基金募集、项目投资、退出回款分别核查。有在管基金不等于本轮已核实募集实缴或投资交割。</p>
      {cohort.managers.map(row=><details className={styles.institution} id={row.id} key={row.id}><summary><strong>{row.legalName}</strong><span>{row.mediaCategory} · {row.registrationNumber} · 登记 {row.registrationDate}</span></summary><div className={styles.body}>
        <dl className={styles.stageGrid}><div><dt>登记公示</dt><dd>本轮在存续管理人目录中找到。成立 {row.establishedDate}；档案信息最后更新 {row.profileUpdatedAt || "未标明"}；本站查阅 {row.checkedAt}。</dd></div><div><dt>基金与项目</dt><dd>查询列表显示在管基金 {row.listedFundCount} 只。基金实缴、项目投资及退出回款均未逐项核验。</dd></div><div><dt>实际控制人公示</dt><dd>{row.controller || "未取得明确字段"}</dd></div><div><dt>高管姓名与职务</dt><dd>{row.executives.map(person=>`${person.name}（${person.role}）`).join("；") || "待核查"}。完整履历尚未逐项整理。</dd></div></dl>
        <div className={table.scroll}><table className={table.table}><caption>协会公示直接出资人（认缴比例）</caption><thead><tr><th scope="col">姓名 / 名称</th><th scope="col">认缴比例</th></tr></thead><tbody>{row.shareholders.map((holder,index)=><tr key={`${row.id}-${index}`}><td>{holder.name}</td><td>{holder.subscribedPercent}</td></tr>)}</tbody></table></div>
        <p className={styles.note}>媒体表登记日期 {row.reportedRegistrationDate}；协会独立档案 {row.registrationDate}；查询列表原显示 {row.listRegistrationDate}。统计采用独立档案日期。</p>
        <div className={styles.links}><a href={row.sourceUrl} target="_blank" rel="noreferrer">协会独立档案 ↗</a><a href={row.mediaTableImage} target="_blank" rel="noreferrer">原分类表 ↗</a></div>
      </div></details>)}
    </section>
  </main>;
}
