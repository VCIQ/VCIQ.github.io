import type { ChannelUpdateItem } from "@/lib/channel-updates";
import {
  buildSectorQualityReviewQueue,
  type SectorQualityCategory,
  type SectorQualityFinding,
} from "@/lib/sector-quality-audit";

export type AnalysisEligibilityStatus =
  | "included"
  | "cross-sector"
  | "downweighted"
  | "sector-excluded"
  | "unscoped";

export type TechnologyAnalysisEntry = {
  item: ChannelUpdateItem;
  status: AnalysisEligibilityStatus;
  sectorWeight: number;
  topicWeight: number;
  analysisTracks: string[];
  analysisTopicSlugs: string[];
  sectorQualityCategory?: SectorQualityCategory;
  reason: string;
};

function unique(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

export function analysisEligibilityForFinding(
  item: ChannelUpdateItem,
  finding?: SectorQualityFinding,
): TechnologyAnalysisEntry {
  const currentTrack = item.track?.trim() || "";
  const topicSlugs = unique(item.topicSlugs ?? []);

  if (!currentTrack) {
    return {
      item,
      status: "unscoped",
      sectorWeight: 0,
      topicWeight: topicSlugs.length ? 1 : 0,
      analysisTracks: [],
      analysisTopicSlugs: topicSlugs,
      reason: "事件没有规范赛道，不能进入赛道趋势；已验证的技术主题仍可独立统计。",
    };
  }

  if (!finding) {
    return {
      item,
      status: "included",
      sectorWeight: 1,
      topicWeight: topicSlugs.length ? 1 : 0,
      analysisTracks: [currentTrack],
      analysisTopicSlugs: topicSlugs,
      reason: "未发现赛道质量冲突，按完整权重进入分析样本。",
    };
  }

  if (finding.category === "high-confidence-misclassification") {
    return {
      item,
      status: "sector-excluded",
      sectorWeight: 0,
      topicWeight: topicSlugs.length ? 1 : 0,
      analysisTracks: [],
      analysisTopicSlugs: topicSlugs,
      sectorQualityCategory: finding.category,
      reason: "高置信度赛道错分候选：纠正前不进入赛道 Momentum，但技术主题证据仍可用于主题趋势。",
    };
  }

  if (finding.category === "reasonable-cross-sector") {
    return {
      item,
      status: "cross-sector",
      sectorWeight: 1,
      topicWeight: topicSlugs.length ? 1 : 0,
      analysisTracks: unique([currentTrack, ...finding.recommendedTracks]),
      analysisTopicSlugs: topicSlugs,
      sectorQualityCategory: finding.category,
      reason: "存在可解释的跨赛道证据：事件以完整权重进入每个相关赛道，赛道总和因此不要求可加。",
    };
  }

  return {
    item,
    status: "downweighted",
    sectorWeight: 0.5,
    topicWeight: topicSlugs.length ? 0.75 : 0,
    analysisTracks: [currentTrack],
    analysisTopicSlugs: topicSlugs,
    sectorQualityCategory: finding.category,
    reason: "赛道归类证据不足：暂保留当前赛道但按 0.5 权重计入，技术主题按 0.75 权重计入。",
  };
}

export function buildTechnologyAnalysisPopulation(items: ChannelUpdateItem[]) {
  const reviewById = new Map(
    buildSectorQualityReviewQueue(items).map((finding) => [finding.id, finding]),
  );

  return items.map((item) =>
    analysisEligibilityForFinding(item, reviewById.get(item.id)),
  );
}
