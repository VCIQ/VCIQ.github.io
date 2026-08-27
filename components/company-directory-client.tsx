"use client";

import { ArrowUpRight, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
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
  whyImportant: string;
  nextWatch: string;
  latestChange?: {
    date: string;
    title: string;
    type: string;
  };
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

export function CompanyDirectoryClient({
  records,
  pageSize = 12,
}: {
  records: CompanyDirectoryRecord[];
  pageSize?: number;
}) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("全部");
  const [sector, setSector] = useState("全部");
  const [stage, setStage] = useState("全部");
  const [signal, setSignal] = useState<ResearchSignal>("全部");
  const [sortOrder, setSortOrder] = useState<SortOrder>("priority");
  const [page, setPage] = useState(1);
  const regions = ["全部", ...Array.from(new Set(records.map((item) => item.region))).sort()];
  const sectors = ["全部", ...Array.from(new Set(records.map((item) => item.sector))).sort()];
  const stages = ["全部", ...Array.from(new Set(records.map((item) => item.stage))).sort()];
  const advancedFilterCount = [region, sector, stage].filter((item) => item !== "全部").length;

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("zh-CN");
    return records
      .filter((item) =>
        (region === "全部" || item.region === region) &&
        (sector === "全部" || item.sector === sector) &&
        (stage === "全部" || item.stage === stage) &&
        (!needle || item.searchIndex.includes(needle)) &&
        (signal === "全部" ||
          (signal === "重点跟踪" && item.priorityLevel === "P1") ||
          (signal === "近期变化" && item.recentChange) ||
          (signal === "高证据覆盖" && item.hasProfile && item.evidenceScore >= 85) ||
          (signal === "待补证据" && (!item.hasProfile || item.evidenceScore < 65))),
      )
      .sort((left, right) => {
        if (sortOrder === "latest") {
          return newestDate(right).localeCompare(newestDate(left)) ||
            right.priorityScore - left.priorityScore;
        }
        if (sortOrder === "coverage") {
          return right.evidenceScore - left.evidenceScore ||
            right.priorityScore - left.priorityScore;
        }
        if (sortOrder === "name") {
          return left.name.localeCompare(right.name, "zh-CN");
        }
        return right.priorityScore - left.priorityScore ||
          newestDate(right).localeCompare(newestDate(left)) ||
          left.name.localeCompare(right.name, "zh-CN");
      });
  }, [query, records, region, sector, signal, sortOrder, stage]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pages);
  const visible = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  function updateFilter(action: () => void) {
    action();
    setPage(1);
  }

  return (
    <>
      <div className={styles.filters}>
        <div className={styles.primaryFilters}>
          <label className={styles.search}>
            <Search size={16} aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => updateFilter(() => setQuery(event.target.value))}
              placeholder="公司、产品、技术主题或关键人物"
              aria-label="搜索公司研究档案"
            />
          </label>
          <select value={signal} onChange={(event) => updateFilter(() => setSignal(event.target.value as ResearchSignal))} aria-label="研究信号">
            {(["全部", "重点跟踪", "近期变化", "高证据覆盖", "待补证据"] as ResearchSignal[]).map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={sortOrder} onChange={(event) => updateFilter(() => setSortOrder(event.target.value as SortOrder))} aria-label="排序">
            <option value="priority">研究优先级</option>
            <option value="latest">最新变化</option>
            <option value="coverage">证据覆盖</option>
            <option value="name">公司名称</option>
          </select>
        </div>
        <div className={styles.filterMeta}>
          <details className={styles.advancedFilters}>
            <summary>更多筛选{advancedFilterCount ? ` · ${advancedFilterCount}` : ""}</summary>
            <div className={styles.advancedGrid}>
              <select value={region} onChange={(event) => updateFilter(() => setRegion(event.target.value))} aria-label="地区">
                {regions.map((item) => <option key={item}>{item}</option>)}
              </select>
              <select value={sector} onChange={(event) => updateFilter(() => setSector(event.target.value))} aria-label="赛道">
                {sectors.map((item) => <option key={item}>{item}</option>)}
              </select>
              <select value={stage} onChange={(event) => updateFilter(() => setStage(event.target.value))} aria-label="阶段">
                {stages.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
          </details>
          <span>共 {filtered.length} 家公司研究档案</span>
        </div>
      </div>

      <div className={styles.grid}>
        {visible.map((company) => (
          <Link href={`/companies/${company.slug}`} className={styles.card} key={company.slug}>
            <div className={styles.cardTop}>
              <span>{company.region} · {company.status}</span>
              <b data-priority={company.priorityLevel}>{company.priorityLevel} · {company.priorityLabel}</b>
            </div>
            <div className={styles.titleRow}>
              <i>{company.name.slice(0, 2).toUpperCase()}</i>
              <div>
                <h3>{company.name}</h3>
                <p>{company.englishName}</p>
              </div>
              <ArrowUpRight size={16} aria-hidden="true" />
            </div>

            <div className={styles.researchRows}>
              <div>
                <strong>最新变化</strong>
                <p>
                  {company.latestChange
                    ? `${company.latestChange.date} · ${company.latestChange.title}`
                    : "暂无达到公开门槛的近期公司事件。"}
                </p>
              </div>
              <div>
                <strong>为什么重要</strong>
                <p>{company.whyImportant}</p>
              </div>
              <div>
                <strong>下一步观察</strong>
                <p>{company.nextWatch}</p>
              </div>
            </div>

            <div className={styles.relationRow}>
              {companyDirectoryRelationTags(company)
                .map((item) => <span key={item}>{item}</span>)}
              {!company.relatedTracks.length && !company.relatedTopics.length && !company.relatedPeople.length
                ? <span>关系待建立</span>
                : null}
            </div>

            <dl className={styles.cardMetrics} aria-label="公司研究指标">
              <div><dt>阶段</dt><dd>{company.stage}</dd></div>
              <div>
                <dt>证据</dt>
                <dd>{company.hasProfile ? `${company.evidenceScore}%` : "待刷新"}</dd>
              </div>
              <div><dt>研究分</dt><dd>{company.priorityScore}</dd></div>
            </dl>
            <small className={styles.cardFooter}>
              {company.coverageLabel} · 主体核验 {company.identityConfidence}%
              {company.updatedAt ? ` · 更新 ${company.updatedAt}` : ""}
            </small>
          </Link>
        ))}
      </div>

      {!visible.length ? (
        <div className={styles.empty}>
          <Search size={22} aria-hidden="true" />
          <strong>没有匹配的公司研究档案</strong>
          <p>请调整关键词、赛道、阶段或研究信号筛选。</p>
        </div>
      ) : null}

      <div className={styles.pagination}>
        <button disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>上一页</button>
        <span>{safePage} / {pages}</span>
        <button disabled={safePage === pages} onClick={() => setPage(safePage + 1)}>下一页</button>
      </div>
    </>
  );
}
