"use client";

import { RotateCcw, Search } from "lucide-react";
import { useEffect, useState } from "react";
import {
  matchesPersonDirectoryRecord,
  type PersonDirectoryFilters,
} from "@/lib/person-directory-filter";
import styles from "./page.module.css";

type ChangeFilter = PersonDirectoryFilters["change"];

export function PeopleDirectoryControls({
  sectors,
  total,
  gridId,
}: {
  sectors: string[];
  total: number;
  gridId: string;
}) {
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("all");
  const [status, setStatus] = useState("all");
  const [change, setChange] = useState<ChangeFilter>("all");
  const [resultCount, setResultCount] = useState(total);

  useEffect(() => {
    const grid = document.getElementById(gridId);
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll<HTMLElement>("[data-person-card]"));
    let visible = 0;
    for (const card of cards) {
      const matches = matchesPersonDirectoryRecord(
        {
          text: card.textContent ?? "",
          sectors: (card.dataset.sectors ?? "").split("|").filter(Boolean),
          status: card.dataset.status ?? "",
          recentChange: card.dataset.recentChange === "true",
        },
        { query, sector, status, change },
      );
      card.hidden = !matches;
      if (matches) visible += 1;
    }
    setResultCount(visible);
  }, [change, gridId, query, sector, status]);

  const hasFilters = Boolean(query || sector !== "all" || status !== "all" || change !== "all");

  function reset() {
    setQuery("");
    setSector("all");
    setStatus("all");
    setChange("all");
  }

  return (
    <div className={styles.filters} aria-label="人物研究目录筛选">
      <label className={styles.search}>
        <Search size={15} aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索人物、角色或研究摘要"
          aria-label="搜索人物研究档案"
          aria-controls={gridId}
        />
      </label>

      <select
        value={sector}
        onChange={(event) => setSector(event.target.value)}
        aria-label="按赛道筛选人物"
        aria-controls={gridId}
      >
        <option value="all">全部赛道</option>
        {sectors.map((item) => <option value={item} key={item}>{item}</option>)}
      </select>

      <select
        value={status}
        onChange={(event) => setStatus(event.target.value)}
        aria-label="按档案状态筛选人物"
        aria-controls={gridId}
      >
        <option value="all">全部档案状态</option>
        <option value="complete">档案较完整</option>
        <option value="partial">补充中</option>
        <option value="pending">待抓取</option>
      </select>

      <select
        value={change}
        onChange={(event) => setChange(event.target.value as ChangeFilter)}
        aria-label="按近期变化筛选人物"
        aria-controls={gridId}
      >
        <option value="all">全部变化状态</option>
        <option value="recent">90 天内有变化</option>
        <option value="quiet">暂无近期变化</option>
      </select>

      <div className={styles.filterMeta}>
        <span aria-live="polite">显示 {resultCount} / {total} 位人物</span>
        <button type="button" onClick={reset} disabled={!hasFilters}>
          <RotateCcw size={13} aria-hidden="true" />
          重置
        </button>
      </div>

      {resultCount === 0 ? (
        <p className={styles.emptyFilter} role="status">
          没有匹配的人物档案，请调整关键词或筛选条件。
        </p>
      ) : null}
    </div>
  );
}
