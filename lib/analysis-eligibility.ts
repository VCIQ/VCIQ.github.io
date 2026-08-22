import type { ChannelUpdateItem } from "@/lib/channel-updates";
import {
  canonicalTracksForItem,
  type CanonicalSectorAssignmentRecord,
} from "@/lib/canonical-sector-assignment";
import {
  contentRelevanceForItem,
  type ContentRelevanceStatus,
} from "@/lib/content-relevance";
import {
  buildSectorQualityReviewQueue,
  type SectorQualityCategory,
  type SectorQualityFinding,
} from "@/lib/sector-quality-audit";
import {
  buildSourceTrackRelevanceProfiles,
  sourceTrackRelevanceForItem,
  type SourceTrackProfile,
  type SourceTrackProfileStatus,
  type SourceTrackRelevanceStatus,
} from "@/lib/source-track-relevance";
import {
  trackSemanticRescueForItem,
  type TrackSemanticRescueStatus,
} from "@/lib/track-semantic-rescue";

export type AnalysisEligibilityStatus =
  | "included"
  | "canonical-corrected"
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
  observedTrack?: string;
  canonicalAssignment?: CanonicalSectorAssignmentRecord;
  sectorQualityCategory?: SectorQualityCategory;
  contentRelevanceStatus?: ContentRelevanceStatus;
  contentWeight?: number;
  trackSemanticRescueStatus?: TrackSemanticRescueStatus;
  trackSemanticRescueMultiplier?: number;
  trackSemanticTitleAnchors?: string[];
  trackSemanticSummaryAnchors?: string[];
  sourceTrackProfileStatus?: SourceTrackProfileStatus;
  sourceTrackRelevanceStatus?: SourceTrackRelevanceStatus;
  sourceTrackWeight?: number;
  reason: string;
};

export type CanonicalSectorResolution = ReturnType<typeof canonicalTracksForItem>;

function unique(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

export function analysisEligibilityForFinding(
  item: ChannelUpdateItem,
  finding?: SectorQualityFinding,
  canonicalResolution: CanonicalSectorResolution = canonicalTracksForItem(item),
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

  if (canonicalResolution.applied && canonicalResolution.assignment) {
    return {
      item,
      status: "canonical-corrected",
      sectorWeight: 1,
      topicWeight: topicSlugs.length ? 1 : 0,
      analysisTracks: canonicalResolution.canonicalTracks,
      analysisTopicSlugs: topicSlugs,
      observedTrack: currentTrack,
      canonicalAssignment: canonicalResolution.assignment,
      sectorQualityCategory: finding?.category,
      reason:
        canonicalResolution.assignment.mode === "replace"
          ? `已确认规范赛道覆盖：分析层使用 ${canonicalResolution.canonicalTracks.join("、")}，原始赛道“${currentTrack}”继续保留作为 provenance。`
          : `已确认跨赛道补充：分析层使用 ${canonicalResolution.canonicalTracks.join("、")}，原始赛道“${currentTrack}”继续保留作为 provenance。`,
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
      observedTrack: currentTrack,
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
      observedTrack: currentTrack,
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
      observedTrack: currentTrack,
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
    observedTrack: currentTrack,
    sectorQualityCategory: finding.category,
    reason: "赛道归类证据不足：暂保留当前赛道但按 0.5 权重计入，技术主题按 0.75 权重计入。",
  };
}

function applyContentRelevance(
  entry: TechnologyAnalysisEntry,
): TechnologyAnalysisEntry {
  const assessment = contentRelevanceForItem(entry.item);
  return {
    ...entry,
    sectorWeight: entry.sectorWeight * assessment.weight,
    topicWeight: entry.topicWeight * assessment.weight,
    contentRelevanceStatus: assessment.status,
    contentWeight: assessment.weight,
    reason:
      assessment.weight < 1
        ? `${entry.reason} ${assessment.reason}`
        : entry.reason,
  };
}

function applyTrackSemanticRescue(
  entry: TechnologyAnalysisEntry,
): TechnologyAnalysisEntry {
  const assessment = trackSemanticRescueForItem(entry.item);
  return {
    ...entry,
    sectorWeight: entry.sectorWeight * assessment.multiplier,
    trackSemanticRescueStatus: assessment.status,
    trackSemanticRescueMultiplier: assessment.multiplier,
    trackSemanticTitleAnchors: assessment.titleAnchors,
    trackSemanticSummaryAnchors: assessment.summaryAnchors,
    reason:
      assessment.multiplier > 1
        ? `${entry.reason} ${assessment.reason}`
        : entry.reason,
  };
}

function applySourceTrackRelevance(
  entry: TechnologyAnalysisEntry,
  profiles: Map<string, SourceTrackProfile>,
): TechnologyAnalysisEntry {
  const assessment = sourceTrackRelevanceForItem(entry.item, profiles, {
    canonicalReviewed: entry.status === "canonical-corrected",
  });
  return {
    ...entry,
    sectorWeight: entry.sectorWeight * assessment.weight,
    sourceTrackProfileStatus: assessment.profileStatus,
    sourceTrackRelevanceStatus: assessment.status,
    sourceTrackWeight: assessment.weight,
    reason:
      assessment.weight < 1
        ? `${entry.reason} ${assessment.reason}`
        : entry.reason,
  };
}

export function buildTechnologyAnalysisPopulation(items: ChannelUpdateItem[]) {
  const reviewById = new Map(
    buildSectorQualityReviewQueue(items).map((finding) => [finding.id, finding]),
  );
  const sourceTrackProfiles = buildSourceTrackRelevanceProfiles(items);

  return items.map((item) =>
    applySourceTrackRelevance(
      applyTrackSemanticRescue(
        applyContentRelevance(
          analysisEligibilityForFinding(item, reviewById.get(item.id)),
        ),
      ),
      sourceTrackProfiles,
    ),
  );
}
