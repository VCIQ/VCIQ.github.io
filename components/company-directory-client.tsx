"use client";

import { ArrowUpRight, RotateCcw, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { companyDirectoryRelationTags } from "../lib/company-directory-tags";
import styles from "./company-directory.module.css";

export type CompanyDirectoryRecord = {
  slug: string;
  name: string;
  englishName: string;
  region: string;
  sector: string;
  stage: string;
  status: string;
  summary: string;
  lifecycleStage: string;
  fundingRound: string;
  nextWatch: string;
  latestChange?: { date: string; title: string };
  priorityScore: number;
  priorityLevel: "P1" | "P2" | "P3";
  priorityLabel: string;
  evidenceScore: number;
  coverageLabel: string;
  hasProfile: boolean;
  identityConfidence: number;
  updatedAt: string;
  recentChange: boolean;
  relatedTracks: string[];
  relatedTopics: string[];
  relatedPeople: string[];
  searchIndex: string;
};

type SortOrder = "priority" | "latest" | "coverage" | "name";
type ResearchSignal = "全部" | "重点跟踪" | "近期变化" | "高证据覆盖" | "待补证据";

function newestDate(record: CompanyDirectoryRecord) {
  return record.latestChange?.date ?? record.updatedAt ?? "";
}

function optionCounts(values: string[]) {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return [...counts].sort(([left], [right]) => left.localeCompare(right, "zh-CN"));
}

export function CompanyDirectoryClient({ records, pageSize = 12 }: { records: CompanyDirectoryRecord[]; pageSize?: number }) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("全部");
  const [sector, setSector] = useState("全部");
  const [status, setStatus] = useState("全部");
  const [lifecycle, setLifecycle] = useState("全部");
  const [fundingRound, setFundingRound] = useState("全部");
  const [signal, setSignal] = useState<ResearchSignal>("全部");
  const [sortOrder, setSortOrder] = useState<SortOrder>("priority");
  const [page, setPage] = useState(1);

  const regions = useMemo(() => optionCounts(records.map((item) => item.region)), [records]);
  const sectors = useMemo(() => optionCounts(records.map((item) => item.sector)), [records]);
  const statuses = useMemo(() => optionCounts(records.map((item) => item.status)), [records]);
  const lifecycles = useMemo(() => optionCounts(records.map((item) => item.lifecycleStage)), [records]);
  const fundingRounds = useMemo(() => optionCounts(records.map((item) => item.fundingRound)), [records]);

  useEffect(() => {
    const url = new URL(window.location.href);
    const values: Record<string, string> = {
      q: query.trim(),
      region: region === "全部" ? "" : region,
      sector: sector === "全部" ? "" : sector,
      status: status === "全部" ? "" : status,
      stage: lifecycle === "全部" ? "" : lifecycle,
      round: fundingRound === "全部" ? "" : fundingRound,
      signal: signal === "全部" ? "" : signal,
      sort: sortOrder === "priority" ? "" : sortOrder,
      page: page > 1 ? String(page) : "",
    };
    for (const [key, value] of Object.entries(values)) {
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    }
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }, [fundingRound, lifecycle, page, query, region, sector, signal, sortOrder, status]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("zh-CN");
    return records
      .filter((item) =>
        (region === "全部" || item.region === region) &&
        (sector === "全部" || item.sector === sector) &&
        (status === "全部" || item.status === status) &&
        (lifecycle === "全部" || item.lifecycleStage === lifecycle) &&
        (fundingRound === "全部" || item.fundingRound === fundingRound) &&
        (!needle || item.searchIndex.includes(needle)) &&
        (signal === "全部" ||
          (signal === "重点跟踪" && item.priorityLevel === "P1") ||
          (signal === "近期变化" && item.recentChange) ||
          (signal === "高证据覆盖" && item.hasProfile && item.evidenceScore >= 85) ||
          (signal === "待补证据" && (!item.hasProfile || item.evidenceScore < 65))),
      )
      .sort((left, right) => {
        if (sortOrder === "latest") return newestDate(right).localeCompare(newestDate(left)) || right.priorityScore - left.priorityScore;
        if (sortOrder === "coverage") return right.evidenceScore - left.evidenceScore || right.priorityScore - left.priorityScore;
        if (sortOrder === "name") return left.name.localeCompare(right.name, "zh-CN");
        return right.priorityScore - left.priorityScore || newestDate(right).localeCompare(newestDate(left)) || left.name.localeCompare(right.name, "zh-CN");
      });
  }, [fundingRound, lifecycle, query, records, region, sector, signal, sortOrder, status]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pages);
  const visible = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);
  const activeFilterLabels = [
    query.trim() ? `关键词：${query.trim()}` : "",
    signal !== "全部" ? signal : "",
    region !== "全部" ? region : "",
    sector !== "全部" ? sector : "",
    status !== "全部" ? status : "",
    lifecycle !== "全部" ? lifecycle : "",
    fundingRound !== "全部" ? fundingRound : "",
  ].filter(Boolean);

  function updateFilter(action: () => void) {
    action();
    setPage(1);
  }

  function clearFilters() {
    setQuery("");
    setRegion("全部");
    setSector("全部");
    setStatus("全部");
    setLifecycle("全部");
    setFundingRound("全部");
    setSignal("全部");
    setPage(1);
  }

  return (
    <>
      <div className={styles.filters}>
        <div className={styles.filterGrid}>
          <label className={styles.search}>
            <Search size={16} aria-hidden="true" />
            <input value={query} onChange={(event) => updateFilter(() => setQuery(event.target.value))} placeholder="公司、产品、技术主题或关键人物" aria-label="搜索公司研究档案" />
          </label>
          <select value={signal} onChange={(event) => updateFilter(() => setSignal(event.target.value as ResearchSignal))} aria-label="研究信号">
            {(["全部", "重点跟踪", "近期变化", "高证据覆盖", "待补证据"] as ResearchSignal[]).map((item) => <option key={item} value={item}>研究信号 · {item}</option>)}
          </select>
          <select value={sortOrder} onChange={(event) => updateFilter(() => setSortOrder(event.target.value as SortOrder))} aria-label="排序">
            <option value="priority">排序 · 研究优先级</option><option value="latest">排序 · 最新变化</option><option value="coverage">排序 · 证据覆盖</option><option value="name">排序 · 公司名称</option>
          </select>
          <select value={region} onChange={(event) => updateFilter(() => setRegion(event.target.value))} aria-label="地区">
            <option value="全部">地区 · 全部</option>{regions.map(([item, count]) => <option key={item} value={item}>{item}（{count}）</option>)}
          </select>
          <select value={sector} onChange={(event) => updateFilter(() => setSector(event.target.value))} aria-label="赛道">
            <option value="全部">赛道 · 全部</option>{sectors.map(([item, count]) => <option key={item} value={item}>{item}（{count}）</option>)}
          </select>
          <select value={status} onChange={(event) => updateFilter(() => setStatus(event.target.value))} aria-label="公司状态">
            <option value="全部">公司状态 · 全部</option>{statuses.map(([item, count]) => <option key={item} value={item}>{item}（{count}）</option>)}
          </select>
          <select value={lifecycle} onChange={(event) => updateFilter(() => setLifecycle(event.target.value))} aria-label="资本阶段">
            <option value="全部">资本阶段 · 全部</option>{lifecycles.map(([item, count]) => <option key={item} value={item}>{item}（{count}）</option>)}
          </select>
          <select value={fundingRound} onChange={(event) => updateFilter(() => setFundingRound(event.target.value))} aria-label="最新融资轮次">
            <option value="全部">最新融资轮次 · 全部</option>{fundingRounds.map(([item, count]) => <option key={item} value={item}>{item}（{count}）</option>)}
          </select>
        </div>

        <div className={styles.filterMeta}>
          <div className={styles.activeFilters} aria-live="polite">{activeFilterLabels.length ? activeFilterLabels.map((item) => <span key={item}>{item}</span>) : <span>当前未设置筛选条件</span>}</div>
          <strong>共 {filtered.length} 家</strong>
          {activeFilterLabels.length ? <button type="button" onClick={clearFilters}><RotateCcw size={13} aria-hidden="true" />清除筛选</button> : null}
        </div>

        <details className={styles.metricGuide}>
          <summary>指标说明</summary>
          <div>
            <p><strong>研究优先级</strong>综合近期变化、证据覆盖、研究关系和资本事件计算，仅用于安排研究顺序。</p>
            <p><strong>证据覆盖</strong>表示公司档案中已有可追溯来源的结构化字段比例，不代表事实正确概率。</p>
            <p><strong>主体核验</strong>表示公司名称、官网和登记实体之间的身份匹配置信度。</p>
          </div>
        </details>
      </div>

      <div className={styles.grid}>
        {visible.map((company) => (
          <Link href={`/companies/${company.slug}`} className={styles.card} key={company.slug}>
            <div className={styles.cardTop}><span>{company.region} · {company.sector} · {company.status}</span><b data-priority={company.priorityLevel}>{company.priorityLevel} · {company.priorityLabel}</b></div>
            <div className={styles.titleRow}><i>{company.name.slice(0, 2).toUpperCase()}</i><div><h3>{company.name}</h3>{company.englishName ? <p>{company.englishName}</p> : null}</div><ArrowUpRight size={17} aria-hidden="true" /></div>
            <p className={styles.positioning}>{company.summary}</p>
            <div className={styles.latestChange}><span>最新变化</span><p>{company.latestChange ? `${company.latestChange.date} · ${company.latestChange.title}` : "暂无达到公开门槛的近期公司事件。"}</p></div>
            <div className={styles.nextWatch}><span>下一步</span><p>{company.nextWatch}</p></div>
            <div className={styles.relationRow}>{companyDirectoryRelationTags(company).slice(0, 4).map((item) => <span key={item}>{item}</span>)}{!company.relatedTracks.length && !company.relatedTopics.length && !company.relatedPeople.length ? <span>关系待建立</span> : null}</div>
            <footer className={styles.cardFooter}>
              <span title={`原始阶段：${company.stage}`}>{company.lifecycleStage}</span>
              <span title="已有可追溯来源的档案字段覆盖比例">证据 {company.hasProfile ? `${company.evidenceScore}%` : "待刷新"}</span>
              <span title="用于安排研究顺序的综合分，不是投资评级">研究分 {company.priorityScore}</span>
              <time title={`主体核验 ${company.identityConfidence}%`}>{company.updatedAt ? `更新 ${company.updatedAt}` : company.coverageLabel}</time>
            </footer>
          </Link>
        ))}
      </div>

      {!visible.length ? <div className={styles.empty}><Search size={22} aria-hidden="true" /><strong>没有匹配的公司研究档案</strong><p>请调整关键词、赛道、阶段或研究信号筛选。</p></div> : null}
      <div className={styles.pagination}><button disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>上一页</button><span>{safePage} / {pages}</span><button disabled={safePage === pages} onClick={() => setPage(safePage + 1)}>下一页</button></div>
    </>
  );
}
