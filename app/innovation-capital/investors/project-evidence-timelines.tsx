import {
  globalInnovationInvestors,
  investorEvidenceKindLabels,
  investorProjectEvidenceTimelines,
} from "@/lib/innovation-investor-research";
import styles from "./project-timelines.module.css";

/** Server-rendered evidence chronology. No source scraping or speculative performance model in the browser. */
export function ProjectEvidenceTimelines() {
  const groups = investorProjectEvidenceTimelines();
  const names = new Map(globalInnovationInvestors.map((firm) => [firm.id, firm.name]));
  const sourceCount = new Set(groups.flatMap((group) => group.entries.map((item) => item.source.url))).size;
  const reportedInvestments = groups.reduce((count, group) => count + group.investmentDisclosures, 0);
  const outcomeCount = groups.reduce((count, group) => count + group.outcomeMilestones, 0);

  return <section className={styles.section} id="project-timelines">
    <div className={styles.heading}>
      <h2>项目证据时间线与跨机构观察口径</h2>
      <p>按原始披露证据排序，不从日期推定交易交割；同一篇文章的投资披露和投资论点单独列示，但不会被计成两次投资。只覆盖本页样例，并非机构的完整组合。</p>
    </div>
    <div className={styles.metrics} aria-label="样本范围">
      <p><strong>{groups.length}</strong><span>出现证据的项目样例</span></p>
      <p><strong>{sourceCount}</strong><span>不重复的原始来源</span></p>
      <p><strong>{reportedInvestments}</strong><span>明确披露的投资事件样例</span></p>
      <p><strong>{outcomeCount}</strong><span>已记录项目结果节点</span></p>
    </div>
    <div className={styles.groups}>
      {groups.map((group) => <details key={group.institutionId + ":" + group.project} className={styles.project}>
        <summary>
          <span className={styles.projectName}>{group.project}</span>
          <span className={styles.institutionName}>{names.get(group.institutionId) ?? group.institutionId}</span>
          <span className={styles.projectMeta}>
            截至所收录的 {group.latestEvidenceDate} 原始证据 · {group.sourceCount} 个来源 · 投资披露 {group.investmentDisclosures} · 观点 {group.viewpointDisclosures} · 结果 {group.outcomeMilestones}
          </span>
        </summary>
        <ol className={styles.timeline}>
          {group.entries.map((item) => <li key={item.id}>
            <div className={styles.eventHeading}>
              <time dateTime={item.datePrecision === "day" ? item.date : undefined}>{item.date}</time>
              <span className={styles.kind}>{investorEvidenceKindLabels[item.kind] ?? item.kind}</span>
            </div>
            <h3>{item.title}</h3>
            <p>{item.summary}</p>
            {item.speakers.length > 0 ? <p className={styles.people}>
              已署名：{item.speakers.map((speaker) => speaker.name).join("、")}（不据署名认定独立交易责任）
            </p> : null}
            <p><a href={item.source.url} target="_blank" rel="noreferrer">查看原始披露 ↗</a> · {item.source.publishedAt ?? "发布日期未核实"} · {item.source.locator}</p>
          </li>)}
        </ol>
        <p className={styles.unknown}>后续结果未出现不代表项目失败或停滞；基金现金收益仍未知，不展示IRR/MOIC或投资绩效排序。</p>
      </details>)}
    </div>
  </section>;
}
