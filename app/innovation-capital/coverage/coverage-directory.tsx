"use client";

import { useMemo, useState } from "react";
import type { InvestorCoverageRow } from "@/lib/innovation-investor-coverage";
import styles from "./coverage.module.css";

type Cohort = "all" | "global-core" | "china-focus";
type SourceFilter = "all" | "pending" | "with-evidence";

export function InvestorCoverageDirectory({rows}: {rows: readonly InvestorCoverageRow[]}) {
  const [query, setQuery] = useState("");
  const [cohort, setCohort] = useState<Cohort>("all");
  const [status, setStatus] = useState<SourceFilter>("all");

  const filtered = useMemo(() => {
    const needle = query.normalize("NFKC").toLocaleLowerCase("zh-CN").trim();
    return rows.filter((row) => {
      if (cohort !== "all" && !row.cohorts.includes(cohort)) return false;
      if (status === "pending" && row.sourceStatus !== "pending-official-source") return false;
      if (status === "with-evidence" && row.reviewedEvidenceCount === 0) return false;
      if (!needle) return true;
      return [row.name, row.id, ...row.aliases, ...row.focusAreas, row.region]
        .some((text) => text.normalize("NFKC").toLocaleLowerCase("zh-CN").includes(needle));
    });
  }, [cohort, query, rows, status]);

  return (
    <section className={styles.directory} id="institutions" aria-label="全球及中国科创投资机构覆盖目录">
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.kicker}>CANONICAL INVESTOR DIRECTORY</span>
          <h2>机构来源与证据覆盖矩阵</h2>
        </div>
        <p>按唯一机构统计，不叠加全球与中国双重成员数。没有已核实案例不代表没有投资。</p>
      </div>
      <div className={styles.filters}>
        <label>机构 / 研究方向
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)}
            placeholder="机构中文名、英文名、主题或 ID" />
        </label>
        <label>研究范围
          <select value={cohort} onChange={(event) => setCohort(event.target.value as Cohort)}>
            <option value="all">全部唯一机构</option>
            <option value="global-core">原全球30家</option>
            <option value="china-focus">中国重点机构</option>
          </select>
        </label>
        <label>证据 / 来源状态
          <select value={status} onChange={(event) => setStatus(event.target.value as SourceFilter)}>
            <option value="all">全部状态</option>
            <option value="with-evidence">有核验证据</option>
            <option value="pending">官网来源待补</option>
          </select>
        </label>
      </div>
      <p className={styles.resultCount} role="status">
        显示 {filtered.length} / {rows.length} 个唯一机构；筛选不修改采集任务或正式研究台账。
      </p>
      <div className={styles.list}>
        {filtered.map((row) => (
          <article key={row.id} className={styles.institution} id={`investor-${row.id}`}>
            <div className={styles.institutionHeader}>
              <div>
                <p className={styles.tags}>
                  {row.cohorts.includes("global-core") && <span>全球既有</span>}
                  {row.cohorts.includes("china-focus") && <span>中国重点</span>}
                </p>
                <h3>{row.name}</h3>
                <p className={styles.aliases}>{row.region} · {row.focusAreas.join(" / ") || "研究主题待补"}</p>
              </div>
              <div className={styles.coverageState} aria-label="覆盖评分状态">
                <span>Coverage Score</span>
                <strong>待评估</strong>
                <small>尚无可比较的采集健康度基线</small>
              </div>
            </div>
            <div className={styles.statRow}>
              <div><strong>{row.reviewedEvidenceCount}</strong><span>已核实证据条目</span></div>
              <div><strong>{row.investmentDisclosureCount}</strong><span>投资披露样例</span></div>
              <div><strong>{row.reviewedCompanyCount}</strong><span>已核验项目名</span></div>
              <div><strong>{row.distinctOriginalCount}</strong><span>独立原文来源</span></div>
            </div>
            <div className={styles.details}>
              <p><b>官网来源：</b>
                {row.officialHomepage
                  ? <a href={row.officialHomepage} target="_blank" rel="noreferrer">已登记官网 ↗</a>
                  : <span>待官方核验与接入</span>}
                {row.discoveryUrl && <> · <a href={row.discoveryUrl} target="_blank" rel="noreferrer">官方发现入口 ↗</a></>}
              </p>
              <p><b>最近核实的投资披露：</b>
                {row.lastReviewedInvestment
                  ? <a href={row.lastReviewedInvestment.sourceUrl} target="_blank" rel="noreferrer">
                      {row.lastReviewedInvestment.company}（{row.lastReviewedInvestment.date}）↗
                    </a>
                  : <span>尚无核实样例；不代表没有投资</span>}
              </p>
              <p><b>最近成功采集：</b>尚未建立跨机构可比的运行基线</p>
            </div>
            <p className={styles.anchor}><a href={`/innovation-capital/investors/#institution-${row.id}`}>
              {row.cohorts.includes("global-core") ? "查看原全球机构研究档案 →" : "中国机构研究档案待接入 →"}
            </a></p>
          </article>
        ))}
        {!filtered.length && <p className={styles.empty}>没有符合筛选条件的机构，请调整范围或关键词。</p>}
      </div>
    </section>
  );
}
