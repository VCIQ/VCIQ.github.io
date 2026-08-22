import rawArticles from "@/public/data/articles.json";
import type { ChannelUpdateItem } from "@/lib/channel-updates";

export type ContentRelevanceStatus =
  | "priority-topic"
  | "usable"
  | "partial-evidence"
  | "weak-evidence"
  | "unassessed";

export type ContentRelevanceAssessment = {
  status: ContentRelevanceStatus;
  weight: number;
  reason: string;
};

type RawArticleQuality = {
  id: string;
  qualityStatus?: string;
  qualitySignals?: string[];
};

type RawArticlePayload = {
  articles: RawArticleQuality[];
};

const rawQualityById = new Map(
  (rawArticles as RawArticlePayload).articles.map((article) => [article.id, article]),
);

export function contentRelevanceForEvidence(input: {
  topicCount: number;
  qualityStatus?: string;
  qualitySignals?: string[];
}): ContentRelevanceAssessment {
  if (input.topicCount > 0) {
    return {
      status: "priority-topic",
      weight: 1,
      reason: "事件命中重点技术主题，内容相关性按完整权重计入。",
    };
  }

  if (input.qualityStatus === "可用") {
    return {
      status: "usable",
      weight: 1,
      reason: "虽未命中20个重点技术主题，但 crawler 已有充分追踪证据，按完整权重保留长尾产业信号。",
    };
  }

  if (input.qualityStatus === "低可信") {
    const noValidTrackingTerm = (input.qualitySignals ?? []).some((signal) =>
      signal.includes("未命中有效追踪词"),
    );
    if (noValidTrackingTerm) {
      return {
        status: "weak-evidence",
        weight: 0.25,
        reason: "事件未命中重点技术主题，且 crawler 明确未命中有效追踪词；保留 provenance，但仅以 0.25 权重进入赛道趋势。",
      };
    }
    return {
      status: "partial-evidence",
      weight: 0.5,
      reason: "事件未命中重点技术主题且 crawler 置信度较低，但仍存在部分追踪证据；以 0.5 权重保留。",
    };
  }

  return {
    status: "unassessed",
    weight: 1,
    reason: "缺少可用于内容相关性降权的结构化质量证据，保持原分析权重。",
  };
}

export function contentRelevanceForItem(
  item: ChannelUpdateItem,
): ContentRelevanceAssessment {
  const raw = rawQualityById.get(item.id);
  return contentRelevanceForEvidence({
    topicCount: item.topicSlugs?.length ?? 0,
    qualityStatus: raw?.qualityStatus,
    qualitySignals: raw?.qualitySignals,
  });
}
