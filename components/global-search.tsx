"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ArticleSearchIndexPayload, SearchRecord } from "@/lib/search-index";
import { normalizeSearchText, searchTextIncludesQuery } from "@/lib/search-normalization";

const SEARCH_LIMIT = 30;
const EVENT_QUERY_MIN_LENGTH = 2;
const SEARCH_DEBOUNCE_MS = 120;

function normalizeQuery(value: string): string {
  return normalizeSearchText(value);
}

function parseArticleSearchIndex(value: unknown): ArticleSearchIndexPayload {
  if (!value || typeof value !== "object") throw new Error("事件搜索索引格式无效");
  const payload = value as Partial<ArticleSearchIndexPayload>;
  if (payload.schemaVersion !== 1 || !Array.isArray(payload.records)) {
    throw new Error("事件搜索索引缺少必要字段");
  }
  return payload as ArticleSearchIndexPayload;
}

function recordMatches(record: SearchRecord, query: string): boolean {
  return searchTextIncludesQuery(
    `${record.title} ${record.text} ${record.region}`,
    query,
  );
}

function uniqueRecords(records: SearchRecord[]): SearchRecord[] {
  const seen = new Set<string>();
  return records.filter((record) => {
    const key = `${record.type}\u0000${record.href}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function ResultLink({ record }: { record: SearchRecord }) {
  const content = (
    <>
      <span>{record.type}</span>
      <div>
        <h2>{record.title}</h2>
        <p>{record.text}</p>
      </div>
      <small>{record.region}</small>
    </>
  );

  if (/^https?:\/\//i.test(record.href)) {
    return (
      <a href={record.href} target="_blank" rel="noreferrer">
        {content}
      </a>
    );
  }

  return <Link href={record.href}>{content}</Link>;
}

export function GlobalSearch({ staticRecords }: { staticRecords: SearchRecord[] }) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [type, setType] = useState("全部");
  const [eventRecords, setEventRecords] = useState<SearchRecord[]>([]);
  const [eventStatus, setEventStatus] = useState<"idle" | "ready" | "error">("idle");
  const eventLoadStarted = useRef(false);

  useEffect(() => {
    const timer = window.setTimeout(
      () => setDebouncedQuery(normalizeQuery(query)),
      SEARCH_DEBOUNCE_MS,
    );
    return () => window.clearTimeout(timer);
  }, [query]);

  const shouldLoadEvents =
    debouncedQuery.length >= EVENT_QUERY_MIN_LENGTH &&
    (type === "全部" || type === "事件");

  useEffect(() => {
    if (
      !shouldLoadEvents ||
      eventStatus !== "idle" ||
      eventLoadStarted.current
    ) {
      return;
    }
    eventLoadStarted.current = true;
    void fetch("/data/article_search_index.json", { cache: "default" })
      .then((response) => {
        if (!response.ok) throw new Error(`事件搜索索引返回 ${response.status}`);
        return response.json();
      })
      .then((value) => {
        const payload = parseArticleSearchIndex(value);
        setEventRecords(payload.records);
        setEventStatus("ready");
      })
      .catch(() => {
        eventLoadStarted.current = false;
        setEventStatus("error");
      });
  }, [eventStatus, shouldLoadEvents]);

  const matches = useMemo(() => {
    if (!debouncedQuery) return [];
    const staticMatches = staticRecords.filter(
      (item) =>
        (type === "全部" || item.type === type) &&
        recordMatches(item, debouncedQuery),
    );
    const dynamicMatches =
      type === "全部" || type === "事件"
        ? eventRecords.filter((item) => recordMatches(item, debouncedQuery))
        : [];
    return uniqueRecords([...staticMatches, ...dynamicMatches]).slice(0, SEARCH_LIMIT);
  }, [debouncedQuery, eventRecords, staticRecords, type]);

  const waitingForEvents = shouldLoadEvents && eventStatus === "idle";

  return (
    <div className="search-workspace">
      <div className="global-search-box">
        <Search size={22} />
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索核心技术、赛道、人物、公司或证据资料"
          aria-label="全局搜索关键词"
        />
      </div>
      <div className="search-types">
        {["全部", "技术", "赛道", "人物", "公司", "资料", "事件"].map((item) => (
          <button
            className={type === item ? "active" : ""}
            onClick={() => setType(item)}
            key={item}
          >
            {item}
          </button>
        ))}
      </div>
      {!query && (
        <div className="search-guide">
          <strong>从四类研究对象开始</strong>
          <p>可尝试：推理芯片、具身智能、某位创始人或一家核心公司。</p>
        </div>
      )}
      {query && normalizeQuery(query).length < EVENT_QUERY_MIN_LENGTH && (type === "全部" || type === "事件") ? (
        <div className="search-guide">
          <strong>事件索引按需加载</strong>
          <p>输入至少 2 个字符后才会加载轻量事件索引；不会下载完整情报档案。</p>
        </div>
      ) : null}
      {waitingForEvents ? (
        <div className="search-guide" role="status">
          <strong>正在加载事件索引</strong>
          <p>核心对象结果可立即使用；事件结果加载完成后会自动补充。</p>
        </div>
      ) : null}
      {eventStatus === "error" && shouldLoadEvents ? (
        <div className="search-guide" role="status">
          <strong>事件索引暂时不可用</strong>
          <p>核心对象和辅助资料仍可正常搜索。</p>
        </div>
      ) : null}
      {debouncedQuery && !matches.length && !waitingForEvents && (
        <div className="empty-state">
          <Search size={22} />
          <strong>没有匹配记录</strong>
          <p>换一个关键词，或清除类型筛选。</p>
        </div>
      )}
      <div className="search-results">
        {matches.map((item, index) => (
          <ResultLink record={item} key={`${item.type}-${item.href}-${index}`} />
        ))}
      </div>
    </div>
  );
}
