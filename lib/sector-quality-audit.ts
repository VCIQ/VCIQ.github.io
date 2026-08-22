import type { ChannelUpdateItem } from "@/lib/channel-updates";
import { technologyTermMatchesText } from "@/lib/technology-term-matching";
import {
  technologyTopicDefinitions,
  type TechnologyTopicDefinition,
} from "@/lib/technology-topics";
import { userTrackingConfig } from "@/lib/user-tracking";

export type SectorQualityCategory =
  | "high-confidence-misclassification"
  | "reasonable-cross-sector"
  | "needs-review";

export type SectorQualityTopicEvidence = {
  slug: string;
  name: string;
  parentTracks: string[];
  compatibleWithCurrentTrack: boolean;
  titleTerms: string[];
  summaryTerms: string[];
};

export type SectorQualityFinding = {
  id: string;
  title: string;
  currentTrack: string;
  category: SectorQualityCategory;
  recommendedTracks: string[];
  evidenceTopics: SectorQualityTopicEvidence[];
  compatibleTopics: string[];
  incompatibleTopics: string[];
  reason: string;
  sourceGrade?: ChannelUpdateItem["sourceGrade"];
};

type SectorQualityInput = Pick<
  ChannelUpdateItem,
  "id" | "title" | "summary" | "track" | "topicSlugs" | "sourceGrade"
>;

function normalize(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

const canonicalTrackByKey = new Map(
  userTrackingConfig.tracks
    .filter((track) => track.enabled)
    .map((track) => [normalize(track.name), track.name] as const),
);

function canonicalTrackName(value: string) {
  return canonicalTrackByKey.get(normalize(value));
}

function canonicalTopicParentTracks(topic: TechnologyTopicDefinition) {
  return [
    ...new Set(
      topic.trackNames
        .map((name) => canonicalTrackName(name))
        .filter((name): name is string => Boolean(name)),
    ),
  ];
}

function matchedTerms(text: string, topic: TechnologyTopicDefinition) {
  if (!text.trim()) return [];
  return topic.matchTerms.filter((term) => technologyTermMatchesText(text, term));
}

function topicEvidence(
  topic: TechnologyTopicDefinition,
  currentTrack: string,
  title: string,
  summary: string,
): SectorQualityTopicEvidence {
  const parentTracks = canonicalTopicParentTracks(topic);
  return {
    slug: topic.slug,
    name: topic.name,
    parentTracks,
    compatibleWithCurrentTrack: parentTracks.includes(currentTrack),
    titleTerms: matchedTerms(title, topic),
    summaryTerms: matchedTerms(summary, topic),
  };
}

function recommendationScores(evidence: SectorQualityTopicEvidence[]) {
  const scores = new Map<string, number>();
  for (const item of evidence) {
    const weight = item.titleTerms.length ? 4 : item.summaryTerms.length ? 2 : 1;
    for (const track of item.parentTracks) {
      scores.set(track, (scores.get(track) ?? 0) + weight);
    }
  }
  return scores;
}

function recommendedTracks(evidence: SectorQualityTopicEvidence[]) {
  if (!evidence.length) return [];

  const parentSets = evidence
    .map((item) => new Set(item.parentTracks))
    .filter((set) => set.size > 0);
  if (!parentSets.length) return [];

  const sharedParents = [...parentSets[0]].filter((track) =>
    parentSets.every((set) => set.has(track)),
  );
  const scores = recommendationScores(evidence);

  if (sharedParents.length) {
    return sharedParents.sort(
      (left, right) =>
        (scores.get(right) ?? 0) - (scores.get(left) ?? 0) ||
        left.localeCompare(right, "zh-CN"),
    );
  }

  const ranked = [...scores.entries()].sort(
    (left, right) =>
      right[1] - left[1] || left[0].localeCompare(right[0], "zh-CN"),
  );
  const topScore = ranked[0]?.[1] ?? 0;
  return ranked
    .filter(([, score]) => score === topScore)
    .map(([track]) => track);
}

export function assessSectorQuality(
  item: SectorQualityInput,
): SectorQualityFinding | null {
  const currentTrack = item.track ? canonicalTrackName(item.track) : undefined;
  if (!currentTrack) return null;

  const topicSlugs = new Set(item.topicSlugs ?? []);
  if (!topicSlugs.size) return null;

  const evidenceTopics = technologyTopicDefinitions
    .filter((topic) => topicSlugs.has(topic.slug))
    .map((topic) => topicEvidence(topic, currentTrack, item.title, item.summary));
  if (!evidenceTopics.length) return null;

  const compatible = evidenceTopics.filter(
    (topic) => topic.compatibleWithCurrentTrack,
  );
  const incompatible = evidenceTopics.filter(
    (topic) => !topic.compatibleWithCurrentTrack,
  );
  if (!incompatible.length) return null;

  const recommendations = recommendedTracks(incompatible).filter(
    (track) => track !== currentTrack,
  );
  const incompatibleTitleEvidence = incompatible.some(
    (topic) => topic.titleTerms.length > 0,
  );

  let category: SectorQualityCategory;
  let reason: string;

  if (compatible.length) {
    category = "reasonable-cross-sector";
    reason = `当前赛道已有 ${compatible.map((topic) => topic.name).join("、")} 支撑，同时出现 ${incompatible.map((topic) => topic.name).join("、")} 的跨赛道证据。`;
  } else if (incompatibleTitleEvidence && recommendations.length) {
    category = "high-confidence-misclassification";
    reason = `标题直接命中 ${incompatible.map((topic) => topic.name).join("、")}，但当前赛道“${currentTrack}”不在这些主题的父赛道中。`;
  } else {
    category = "needs-review";
    reason = `跨赛道主题主要来自摘要或弱证据，暂不足以自动建议改写“${currentTrack}”。`;
  }

  return {
    id: item.id,
    title: item.title,
    currentTrack,
    category,
    recommendedTracks: recommendations,
    evidenceTopics,
    compatibleTopics: compatible.map((topic) => topic.name),
    incompatibleTopics: incompatible.map((topic) => topic.name),
    reason,
    sourceGrade: item.sourceGrade,
  };
}

const categoryRank: Record<SectorQualityCategory, number> = {
  "high-confidence-misclassification": 0,
  "reasonable-cross-sector": 1,
  "needs-review": 2,
};

export function buildSectorQualityReviewQueue(items: SectorQualityInput[]) {
  return items
    .map(assessSectorQuality)
    .filter((item): item is SectorQualityFinding => Boolean(item))
    .sort(
      (left, right) =>
        categoryRank[left.category] - categoryRank[right.category] ||
        left.currentTrack.localeCompare(right.currentTrack, "zh-CN") ||
        left.title.localeCompare(right.title, "zh-CN"),
    );
}
