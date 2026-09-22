"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Search } from "lucide-react";
import type { InnovationOpportunity } from "@/lib/innovation-capital-opportunity";
import styles from "./page.module.css";

type Props = {
  opportunities: InnovationOpportunity[];
};

export function InnovationOpportunityPool({ opportunities }: Props) {
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState("all");
  const [focus, setFocus] = useState("all");

  const themes = useMemo(
    () => Array.from(new Set(opportunities.flatMap((item) => item.policyThemes))).sort(),
    [opportunities],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("zh-CN");
    return opportunities
      .filter((item) => theme === "all" || item.policyThemes.includes(theme))
      .filter((item) => {
        if (focus === "late") return item.lateStageRounds.length > 0;
        if (focus === "institution") return item.institutionBackers.length > 0;
        if (focus === "priority") return item.readinessBand === "重点复核";
        return true;
      })
      .filter((item) => !needle || [
        item.name,
        item.sector,
        item.stage,
        item.headquarters,
        item.latestRound,
        ...item.policyThemes,
        ...item.institutionBackers,
      ].join(" ").toLocaleLowerCase("zh-CN").includes(needle));
  }, [focus, opportunities, query, theme]);

  return (
    <section className={styles.opportunitySection} id="opportunity-pool">
      <div className={styles.sectionHeader}>
        <div>
          <span>HARD-TECH OPPORTUNITY SOURCE</span>
          <h2>硬科技潜在项目源</h2>
        </div>
        <p>
          从已纳管硬科技投资机构的公开组合与公司档案反向筛选十五五重点方向，优先展示
          D / E / Pre-IPO / Growth 等成熟期融资信号。这里的“准备度”只表示公开证据和资本阶段完整度，
          不代表上市成功概率或投资评级。
        </p>
      </div>

      <div className={styles.opportunitySummary}>
        <article>
          <strong>{opportunities.length}</strong>
          <span>潜在项目源</span>
        </article>
        <article>
          <strong>{opportunities.filter((item) => item.lateStageRounds.length > 0).length}</strong>
          <span>D/E/Pre-IPO 等成熟期</span>
        </article>
        <article>
          <strong>{opportunities.filter((item) => item.institutionBackers.length > 0).length}</strong>
          <span>已命中机构公开组合</span>
        </article>
        <article>
          <strong>{opportunities.filter((item) => item.readinessBand === "重点复核").length}</strong>
          <span>重点复核</span>
        </article>
      </div>

      <div className={styles.opportunityFilters}>
        <label className={styles.searchBox}>
          <Search size={15} aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索公司、行业、机构、融资阶段"
            aria-label="搜索硬科技潜在项目源"
          />
        </label>
        <select value={theme} onChange={(event) => setTheme(event.target.value)} aria-label="筛选十五五方向">
          <option value="all">全部十五五方向</option>
          {themes.map((item) => <option value={item} key={item}>{item}</option>)}
        </select>
        <select value={focus} onChange={(event) => setFocus(event.target.value)} aria-label="筛选项目成熟度">
          <option value="all">全部候选</option>
          <option value="late">D/E/Pre-IPO 等成熟期</option>
          <option value="institution">机构组合已命中</option>
          <option value="priority">重点复核</option>
        </select>
      </div>

      <div className={styles.opportunityGrid}>
        {filtered.map((item) => (
          <article className={styles.opportunityCard} key={item.slug}>
            <header>
              <div>
                <span className={styles.opportunityBand}>{item.readinessBand}</span>
                <h3>{item.name}</h3>
              </div>
              <div className={styles.readinessScore}>
                <strong>{item.readinessScore}</strong>
                <span>资料准备度</span>
              </div>
            </header>

            <div className={styles.badges}>
              <span>{item.sector}</span>
              {item.lateStageRounds.map((round) => <span key={round}>{round}</span>)}
              {!item.lateStageRounds.length && item.latestRound ? <span>{item.latestRound}</span> : null}
            </div>

            <div className={styles.themeRow}>
              {item.policyThemes.map((tag) => <span key={tag}>{tag}</span>)}
            </div>

            <dl className={styles.metaGrid}>
              <div><dt>公司阶段</dt><dd>{item.stage || "待核验"}</dd></div>
              <div><dt>所在地</dt><dd>{item.headquarters || "—"}</dd></div>
              <div><dt>最新融资</dt><dd>{item.latestRound || "待补证"}</dd></div>
              <div><dt>融资日期</dt><dd>{item.latestDate || "—"}</dd></div>
            </dl>

            <div className={styles.opportunityEvidence}>
              <strong>机构组合线索</strong>
              <p>
                {item.institutionBackers.length
                  ? item.institutionBackers.join(" · ")
                  : "当前公开机构目录尚未形成可核对连接。"}
              </p>
            </div>

            <div className={styles.opportunityEvidence}>
              <strong>当前信号</strong>
              <p>{item.signals.length ? item.signals.join(" · ") : "等待更多一级公开证据。"}</p>
            </div>

            {item.gaps.length ? (
              <div className={styles.opportunityGaps}>
                <strong>待补证</strong>
                <p>{item.gaps.join(" · ")}</p>
              </div>
            ) : null}

            {item.sourceUrl ? (
              <a className={styles.evidence} href={item.sourceUrl} target="_blank" rel="noreferrer">
                查看公司一级来源
                <ExternalLink size={13} aria-hidden="true" />
              </a>
            ) : null}
          </article>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className={styles.empty}>当前筛选条件下没有潜在项目源。</div>
      ) : null}
    </section>
  );
}
