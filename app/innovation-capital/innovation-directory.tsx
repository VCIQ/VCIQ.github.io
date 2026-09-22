"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Search } from "lucide-react";
import watchlist from "@/config/innovation_listing_watchlist.json";
import styles from "./page.module.css";

type Project = (typeof watchlist.projects)[number];

const routeLabels: Record<string, string> = {
  STAR: "科创板",
  ChiNext: "创业板",
  "A-share-TBD": "A股待定",
};

const poolLabels: Record<string, string> = {
  core: "核心池",
  refile: "二次申报",
  observation: "观察池",
};

function confidenceLabel(value: string) {
  if (value === "official") return "官方明示";
  if (value === "high") return "高置信";
  if (value === "official-a-share-only") return "A股已确认";
  return "板块待确认";
}

function projectSearchText(project: Project) {
  return [
    project.company,
    project.broker,
    project.sector,
    project.subsector,
    project.route,
    project.stage,
    project.latestEvent,
    ...project.fifteenthTags,
  ]
    .join(" ")
    .toLowerCase();
}

export function InnovationDirectory() {
  const [query, setQuery] = useState("");
  const [broker, setBroker] = useState("all");
  const [route, setRoute] = useState("all");
  const [pool, setPool] = useState("all");
  const [theme, setTheme] = useState("all");

  const projects = watchlist.projects as Project[];
  const themes = useMemo(
    () => Array.from(new Set(projects.flatMap((item) => item.fifteenthTags))).sort(),
    [projects],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return projects
      .filter((item) => broker === "all" || item.broker === broker)
      .filter((item) => route === "all" || item.route === route)
      .filter((item) => pool === "all" || item.pool === pool)
      .filter((item) => theme === "all" || item.fifteenthTags.includes(theme))
      .filter((item) => !needle || projectSearchText(item).includes(needle))
      .sort((a, b) => b.latestEventDate.localeCompare(a.latestEventDate));
  }, [broker, pool, projects, query, route, theme]);

  return (
    <section className={styles.directorySection} id="projects">
      <div className={styles.sectionHeader}>
        <div>
          <span>PROJECT PIPELINE</span>
          <h2>五大券商科创项目储备</h2>
        </div>
        <p>
          当前显示 {filtered.length} / {projects.length} 个项目。路线、辅导阶段、历史递表与港股状态分别记录，避免把“科技属性”误当成“已确定科创板”。
        </p>
      </div>

      <div className={styles.filters}>
        <label className={styles.searchBox}>
          <Search size={15} aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索公司、赛道、券商、十五五主题"
            aria-label="搜索项目"
          />
        </label>
        <select value={broker} onChange={(event) => setBroker(event.target.value)} aria-label="筛选券商">
          <option value="all">全部券商</option>
          {watchlist.brokers.map((item) => <option value={item} key={item}>{item}</option>)}
        </select>
        <select value={route} onChange={(event) => setRoute(event.target.value)} aria-label="筛选上市路线">
          <option value="all">全部A股路线</option>
          <option value="STAR">科创板</option>
          <option value="ChiNext">创业板</option>
          <option value="A-share-TBD">A股待定</option>
        </select>
        <select value={pool} onChange={(event) => setPool(event.target.value)} aria-label="筛选项目池">
          <option value="all">全部项目池</option>
          <option value="core">核心池</option>
          <option value="refile">二次申报</option>
          <option value="observation">观察池</option>
        </select>
        <select value={theme} onChange={(event) => setTheme(event.target.value)} aria-label="筛选十五五主题">
          <option value="all">全部硬科技主题</option>
          {themes.map((item) => <option value={item} key={item}>{item}</option>)}
        </select>
      </div>

      <div className={styles.projectGrid}>
        {filtered.map((project) => (
          <article className={styles.projectCard} key={project.id}>
            <header className={styles.projectHeader}>
              <div>
                <span className={styles.broker}>{project.broker}</span>
                <h3>{project.company}</h3>
              </div>
              <span className={styles.stage}>{project.stage}</span>
            </header>

            <div className={styles.badges}>
              <span className={styles.routeBadge}>{routeLabels[project.route] ?? project.route}</span>
              <span>{poolLabels[project.pool] ?? project.pool}</span>
              <span>{confidenceLabel(project.routeConfidence)}</span>
              {project.capitalMarketPath === "A+H" ? <span>A+H</span> : null}
              {project.everFiledBefore ? <span>历史曾递表</span> : null}
            </div>

            <p className={styles.sector}>{project.sector} · {project.subsector}</p>
            <p className={styles.event}>{project.latestEvent}</p>

            <dl className={styles.metaGrid}>
              <div><dt>首次辅导</dt><dd>{project.firstGuidanceDate}</dd></div>
              <div><dt>最新核验</dt><dd>{project.latestEventDate}</dd></div>
              <div><dt>资本路径</dt><dd>{project.capitalMarketPath}</dd></div>
              <div><dt>港股状态</dt><dd>{project.hkStatus === "none" ? "—" : project.hkStatus}</dd></div>
            </dl>

            {project.priorFilingSummary ? (
              <p className={styles.history}><strong>历史：</strong>{project.priorFilingSummary}</p>
            ) : null}

            <div className={styles.themeRow}>
              {project.fifteenthTags.map((tag) => <span key={tag}>{tag}</span>)}
            </div>

            <a className={styles.evidence} href={project.source.url} target="_blank" rel="noreferrer">
              {project.source.title}
              <ExternalLink size={13} aria-hidden="true" />
            </a>
          </article>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className={styles.empty}>当前筛选条件下没有项目。</div>
      ) : null}
    </section>
  );
}
