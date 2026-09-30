"use client";

import { useState } from "react";
import { findFocusCandidates, focusDisplayDecision, focusObservationLatency } from "@/lib/focus-diagnostics";
import type { HomepageFocusSelection } from "@/lib/homepage-focus";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";
import type { PriorityIntelligenceSnapshot } from "@/lib/priority-intelligence";
import { homepageMaterialUrl } from "@/lib/homepage-event-identity";

const COLLECTION_REASONS: Record<string, string> = {
  accepted: "采集已接受", "invalid-publication-date": "原文日期无效", "missing-title-or-url": "缺少标题或链接",
  "source-filter-or-invalid-record": "未通过来源解析或过滤（需复查原文）", "snapshot-capacity": "被快速快照容量上限暂缓", "outside-retention": "超出保留时间窗口",
};

export function FocusDiagnostics({ selection, filtered, rendered, snapshot, now }: {
  selection: HomepageFocusSelection; filtered: readonly LiveIntelligenceEvent[];
  rendered: readonly LiveIntelligenceEvent[]; snapshot: PriorityIntelligenceSnapshot | null; now: number;
}) {
  const [query, setQuery] = useState("");
  const matches = findFocusCandidates(query, selection);
  const traces = (snapshot?.collectionTrace ?? []).filter((row) => query.trim() &&
    ((homepageMaterialUrl(query.trim()) && homepageMaterialUrl(row.url) === homepageMaterialUrl(query.trim())) || row.id === query.trim() || row.title.toLowerCase().includes(query.trim().toLowerCase())));
  return <details aria-label="重点未入选原因诊断">
    <summary>重点诊断：为什么没看到这条信息？</summary>
    <p>候选报道 {selection.counts.candidateReports} · 通过入选 {selection.counts.admittedReports} ·
      去重后事件 {selection.counts.eventGroups} · 归组报道 {selection.counts.groupedReports} ·
      当前已渲染 {rendered.length} · 等待加载 {Math.max(0, filtered.length - rendered.length)}</p>
    <p>诊断仅在本浏览器计算，不上传收藏、分享或查询内容。缺少人工标注样本，暂不计算漏推率、无关率；渲染不等于阅读。</p>
    <label>按标题、原文链接或事件 ID 查询
      <input value={query} maxLength={1600} onChange={(event) => setQuery(event.target.value)} placeholder="输入未看到的新闻标题或原文链接" />
    </label>
    {matches.length > 0 ? <ul>{matches.slice(0, 40).map((item) => {
      const result = focusDisplayDecision(item.id, selection, filtered, rendered);
      const firstSeen = Date.parse(item.firstSeenAt ?? "");
      const delay = focusObservationLatency(item).collectionDelayMinutes;
      return <li key={item.id}><strong>{item.title}</strong>：{result.label}
        <small> · 对象关联 {result.entityState ?? "未知"}{result.groupedInto ? ` · 主事件 ${result.groupedInto}` : ""}</small>
        {result.reasons?.length ? <p>{result.reasons.join("；")}</p> : null}
        <p>原文发布时间 {item.publishedAt}；首次收录 {item.firstSeenAt ?? "未提供"}；
          采集延迟 {delay === null ? "时间证据不足" : `${Math.round(delay)} 分钟（本采集窗口观测）`}；
          当前渲染相对首次收录 {rendered.some((x) => x.id === item.id) && Number.isFinite(firstSeen) && now >= firstSeen
            ? `${Math.round((now - firstSeen) / 60000)} 分钟（非首次曝光延迟）` : "暂无可计算数据"}</p>
      </li>;
    })}</ul> : query.trim() ? <p>当前候选窗口未发现匹配记录。不能判断它是从未采到、超出保留窗口还是上游尚未发布。</p> : null}
    {matches.length > 40 ? <p>查询命中 {matches.length} 条，当前诊断仅展示前 40 条，请缩小查询范围。</p> : null}
    {traces.length ? <ul>{traces.slice(0, 40).map((row, index) => <li key={`${row.sourceId}:${row.id}:${row.reason}:${index}`}>采集证据：{row.title || row.id} · {COLLECTION_REASONS[row.reason] ?? row.reason} · {row.sourceId}</li>)}</ul> : null}
    {snapshot?.collectionSummary ? <p>快速采集：{snapshot.collectionSummary.scanned} 条观察记录 ·
      解析/过滤未接受 {snapshot.collectionSummary.filtered} · 过期 {snapshot.collectionSummary.expired} ·
      快照安全上限暂缓 {snapshot.collectionSummary.capacityHeld} ·
      待继续补采来源 {snapshot.collectionSummary.pendingSources}。
      诊断只覆盖有记录的本轮及保留窗口，不宣称全网完整覆盖。</p> : null}
    {snapshot?.collectionSummary?.traceTruncated ? <p>公开诊断超过安全条数，只保留最近 120 条；查询未命中不能解释为从未采到。</p> : null}
  </details>;
}
