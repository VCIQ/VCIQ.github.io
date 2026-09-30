import { homepageMaterialUrl } from "@/lib/homepage-event-identity";
import type { HomepageFocusSelection } from "@/lib/homepage-focus";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export const FOCUS_REASON_LABELS: Readonly<Record<string, string>> = Object.freeze({
  dismissed: "已按明确的不感兴趣／事件排除规则隐藏",
  "low-quality": "未通过质量门槛",
  "invalid-date": "原文发布时间无效，未用采集时间补造",
  stale: "不在允许的发布时间窗口内",
  "low-impact": "未达到重要度或实质变化门槛",
  "entity-unresolved": "缺少可用对象关联且无直接兴趣信号；不是已确认的唯一漏推根因",
  "no-personal-signal": "当前浏览器未匹配到追踪、分享或收藏信号",
  grouped: "已归入同事件卡片，不再重复占位",
  "view-filter": "已入选，但被当前地区或搜索条件过滤",
  "next-page": "已入选，位于后续页面；点击加载更多即可查看",
  displayed: "已在当前页面的渲染列表中（不代表已经阅读）",
  "not-observed": "当前候选窗口没有这条记录；无法据此断言从未采到，需查上游采集记录",
});

export function focusDisplayDecision(id: string, selection: HomepageFocusSelection,
  filtered: readonly LiveIntelligenceEvent[], rendered: readonly LiveIntelligenceEvent[]) {
  const decision = selection.decisions.get(id);
  if (!decision) return { code: "not-observed", label: FOCUS_REASON_LABELS["not-observed"] };
  const code = decision.exclusion ?? (decision.groupedInto ? "grouped" :
    !filtered.some((x) => x.id === id) ? "view-filter" :
      rendered.some((x) => x.id === id) ? "displayed" : "next-page");
  return { code, label: FOCUS_REASON_LABELS[code], groupedInto: decision.groupedInto,
    entityState: decision.entityState, reasons: decision.reasons };
}

export function findFocusCandidates(query: string, selection: HomepageFocusSelection) {
  const value = query.trim(); if (!value) return [];
  const url = homepageMaterialUrl(value);
  return selection.candidates.filter((item) => url ? homepageMaterialUrl(item.source.url) === url :
    item.id === value || `${item.title} ${item.company} ${(item.mentionedPeople ?? []).join(" ")}`.toLowerCase().includes(value.toLowerCase()));
}

/** No judged set => no recall/irrelevance rate; no inferred labels from clicks. */
export function focusQualityMetrics(expected: readonly string[] | null, judged: Readonly<Record<string, boolean>>,
  renderedIds: readonly string[]) {
  const rendered = new Set(renderedIds);
  const relevant = expected === null ? null : [...new Set(expected)];
  const judgedVisible = Object.entries(judged).filter(([id]) => rendered.has(id));
  const missed = relevant?.filter((id) => !rendered.has(id)) ?? null;
  return { expectedCount: relevant?.length ?? null, missedCount: missed?.length ?? null,
    recall: relevant?.length ? (relevant.length - missed!.length) / relevant.length : null,
    judgedVisibleCount: judgedVisible.length,
    irrelevantRate: judgedVisible.length ? judgedVisible.filter(([, value]) => value === false).length / judgedVisible.length : null };
}

/** Exact source timestamps only; first render/read times are not reconstructed. */
export function focusObservationLatency(item: LiveIntelligenceEvent) {
  const observed = Date.parse(item.firstSeenAt ?? ""); const published = Date.parse(item.publishedAt);
  const precise = item.publicationTimePrecision === "second" || /T\d{2}:\d{2}/u.test(item.publishedAt);
  return { collectionDelayMinutes: precise && Number.isFinite(observed) && Number.isFinite(published) && observed >= published
    ? (observed - published) / 60_000 : null, firstExposureDelayMinutes: null };
}
