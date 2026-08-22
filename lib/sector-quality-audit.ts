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
  currentTrackTitleTerms: string[];
  currentTrackSummaryTerms: string[];
  currentTrackSourceTerms: string[];
  reason: string;
  sourceGrade?: ChannelUpdateItem["sourceGrade"];
};

type SectorQualityInput = Pick<
  ChannelUpdateItem,
  | "id"
  | "title"
  | "summary"
  | "source"
  | "href"
  | "track"
  | "topicSlugs"
  | "sourceGrade"
>;

const sectorAnchorTerms: Record<string, string[]> = {
  "AI / AGI": [
    "AI Agent",
    "agentic AI",
    "大模型",
    "LLM",
    "GPT",
    "Claude",
    "Gemini",
    "DeepSeek",
    "Qwen",
    "智能体",
  ],
  机器人: [
    "机器人",
    "robot",
    "robotics",
    "humanoid",
    "具身智能",
    "physical AI",
    "robotaxi",
    "autonomous driving",
    "Waymo",
    "Unitree",
    "宇树",
  ],
  半导体: [
    "半导体",
    "semiconductor",
    "chip",
    "芯片",
    "GPU",
    "CPU",
    "NPU",
    "TPU",
    "wafer",
    "晶圆",
    "foundry",
    "封装",
    "packaging",
    "RAM",
    "mini PC",
    "Cerebras",
    "SambaNova",
    "Moore Threads",
    "摩尔线程",
    "Mobileye",
    "HorizonRobotics",
    "地平线",
  ],
  新能源: [
    "新能源",
    "battery",
    "电池",
    "储能",
    "solar",
    "wind",
    "光伏",
    "风电",
    "grid",
    "电网",
    "renewable energy",
  ],
  可控核聚变: [
    "可控核聚变",
    "fusion",
    "tokamak",
    "托卡马克",
    "stellarator",
    "仿星器",
  ],
  生物科技: [
    "生物科技",
    "biotech",
    "biology",
    "drug",
    "pharma",
    "protein",
    "gene",
    "genome",
    "clinical",
    "molecule",
    "药物",
    "蛋白",
    "基因",
    "临床",
    "分子",
  ],
  量子计算: ["量子计算", "quantum", "qubit", "量子比特"],
  商业航天: [
    "商业航天",
    "space",
    "satellite",
    "卫星",
    "rocket",
    "火箭",
    "orbit",
    "轨道",
    "spacecraft",
    "eVTOL",
    "vertiport",
    "Joby",
    "aviation",
  ],
  Web3: [
    "Web3",
    "blockchain",
    "区块链",
    "crypto",
    "DeFi",
    "wallet",
    "stablecoin",
    "稳定币",
    "RWA",
    "tokenization",
  ],
  新材料: [
    "新材料",
    "material",
    "材料",
    "ceramic",
    "陶瓷",
    "alloy",
    "合金",
    "composite",
    "复合材料",
    "GaN",
    "SiC",
    "Ga2O3",
    "氧化镓",
  ],
  医疗科技: [
    "医疗科技",
    "medical",
    "healthcare",
    "diagnostic",
    "诊断",
    "medical device",
    "医疗器械",
  ],
  智能交通: [
    "智能交通",
    "transport",
    "mobility",
    "autonomous driving",
    "robotaxi",
    "vehicle",
    "车路协同",
  ],
  智能制造: [
    "智能制造",
    "manufacturing",
    "factory",
    "industrial automation",
    "工厂",
    "工业自动化",
  ],
  AI网络通信: [
    "AI网络通信",
    "telecom",
    "通信",
    "RAN",
    "wireless",
    "无线",
    "5G",
    "6G",
  ],
};

function normalize(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function normalizedSearchText(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase("zh-CN");
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function sectorAnchorMatchesText(text: string, term: string) {
  const normalizedTerm = normalizedSearchText(term).trim();
  if (!text.trim() || !normalizedTerm) return false;

  if (/^[a-z0-9.+-]+$/u.test(normalizedTerm)) {
    const tokenPattern = new RegExp(
      `(^|[^a-z0-9])${escapeRegExp(normalizedTerm)}([^a-z0-9]|$)`,
      "iu",
    );
    return tokenPattern.test(normalizedSearchText(text));
  }

  return technologyTermMatchesText(text, term);
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

function matchedSectorAnchors(text: string, track: string) {
  const anchors = sectorAnchorTerms[track] ?? [track];
  return anchors.filter((term) => sectorAnchorMatchesText(text, term));
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
  const currentTrackTitleTerms = matchedSectorAnchors(item.title, currentTrack);
  const currentTrackSummaryTerms = matchedSectorAnchors(item.summary, currentTrack);
  const currentTrackSourceTerms = matchedSectorAnchors(
    `${item.source} ${item.href}`,
    currentTrack,
  );

  let category: SectorQualityCategory;
  let reason: string;

  if (compatible.length) {
    category = "reasonable-cross-sector";
    reason = `当前赛道已有 ${compatible.map((topic) => topic.name).join("、")} 支撑，同时出现 ${incompatible.map((topic) => topic.name).join("、")} 的跨赛道证据。`;
  } else if (currentTrackTitleTerms.length || currentTrackSourceTerms.length) {
    category = "reasonable-cross-sector";
    const anchors = [
      ...new Set([...currentTrackTitleTerms, ...currentTrackSourceTerms]),
    ];
    reason = `标题或原始信源仍有“${anchors.join("、")}”等当前赛道锚点，同时出现 ${incompatible.map((topic) => topic.name).join("、")} 的跨赛道技术主题。`;
  } else if (currentTrackSummaryTerms.length) {
    category = "needs-review";
    reason = `摘要仍有“${currentTrackSummaryTerms.join("、")}”等当前赛道锚点；虽然标题支持 ${incompatible.map((topic) => topic.name).join("、")}，但不足以判定应直接改写赛道。`;
  } else if (incompatibleTitleEvidence && recommendations.length) {
    category = "high-confidence-misclassification";
    reason = `标题直接命中 ${incompatible.map((topic) => topic.name).join("、")}，而标题、摘要和原始信源都没有“${currentTrack}”锚点，且该赛道不在这些主题的父赛道中。`;
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
    currentTrackTitleTerms,
    currentTrackSummaryTerms,
    currentTrackSourceTerms,
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
