import type { ChannelUpdateItem } from "@/lib/channel-updates";
import { contentRelevanceForItem } from "@/lib/content-relevance";

export type TrackSemanticRescueStatus =
  | "title-rescue"
  | "summary-rescue"
  | "none";

export type TrackSemanticRescueAssessment = {
  status: TrackSemanticRescueStatus;
  multiplier: number;
  titleAnchors: string[];
  summaryAnchors: string[];
  reason: string;
};

const trackRescueTerms: Record<string, string[]> = {
  机器人: ["机器人", "robot", "robotics", "humanoid", "具身智能", "灵巧手"],
  半导体: [
    "半导体",
    "芯片",
    "晶圆",
    "wafer",
    "foundry",
    "封装",
    "packaging",
    "光刻",
    "DRAM",
    "HBM",
  ],
  新能源: [
    "新能源",
    "电池",
    "储能",
    "光伏",
    "风电",
    "电网",
    "battery",
    "energy storage",
    "solar",
    "wind",
  ],
  可控核聚变: ["可控核聚变", "fusion", "tokamak", "托卡马克", "stellarator", "仿星器"],
  生物科技: [
    "生物科技",
    "biotech",
    "药物",
    "蛋白",
    "基因",
    "临床",
    "分子",
    "drug",
    "protein",
    "gene",
    "clinical",
  ],
  量子计算: ["量子计算", "quantum computing", "qubit", "量子比特"],
  商业航天: [
    "商业航天",
    "火箭",
    "卫星",
    "轨道",
    "航天器",
    "rocket",
    "satellite",
    "orbit",
    "spacecraft",
  ],
  新材料: [
    "新材料",
    "材料",
    "先进材料",
    "半导体材料",
    "光刻胶",
    "陶瓷",
    "合金",
    "复合材料",
    "material",
    "ceramic",
    "alloy",
    "composite",
  ],
  医疗科技: ["医疗科技", "医疗器械", "诊断", "medical device", "diagnostic"],
  智能交通: ["智能交通", "车路协同", "mobility", "vehicle", "交通基础设施"],
  智能制造: ["智能制造", "工业自动化", "工厂", "manufacturing", "factory", "industrial automation"],
  AI网络通信: ["AI网络通信", "通信", "无线", "基站", "telecom", "wireless", "RAN", "base station"],
};

function normalizedText(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase("zh-CN");
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function termMatches(text: string, term: string) {
  const normalizedTerm = normalizedText(term).trim();
  if (!text.trim() || !normalizedTerm) return false;

  if (/^[a-z0-9 .+\-]+$/u.test(normalizedTerm)) {
    const pieces = normalizedTerm
      .split(/\s+/u)
      .filter(Boolean)
      .map(escapeRegExp);
    const body = pieces.join("[\\s\\-–—_/]*");
    return new RegExp(`(^|[^a-z0-9])${body}([^a-z0-9]|$)`, "iu").test(
      normalizedText(text),
    );
  }

  return normalizedText(text).includes(normalizedTerm);
}

function matchingAnchors(text: string, track: string) {
  const terms = trackRescueTerms[track] ?? [];
  return terms.filter((term) => termMatches(text, term));
}

export function trackSemanticRescueForItem(
  item: ChannelUpdateItem,
): TrackSemanticRescueAssessment {
  const track = item.track?.trim() ?? "";
  const content = contentRelevanceForItem(item);
  const topicBacked = (item.topicSlugs?.length ?? 0) > 0;

  if (!track || topicBacked || content.status !== "weak-evidence") {
    return {
      status: "none",
      multiplier: 1,
      titleAnchors: [],
      summaryAnchors: [],
      reason: "仅对无重点主题且内容证据较弱的事件启用赛道语义救援。",
    };
  }

  const titleAnchors = matchingAnchors(item.title, track);
  const summaryAnchors = matchingAnchors(item.summary, track);

  if (titleAnchors.length) {
    return {
      status: "title-rescue",
      multiplier: 2,
      titleAnchors,
      summaryAnchors,
      reason: `标题直接出现当前赛道“${track}”的语义锚点（${titleAnchors.join("、")}）；弱内容证据的赛道贡献从 0.25 恢复到最多 0.5，但不升级为完整权重。`,
    };
  }

  if (new Set(summaryAnchors).size >= 2) {
    return {
      status: "summary-rescue",
      multiplier: 1.5,
      titleAnchors,
      summaryAnchors,
      reason: `摘要同时出现多个当前赛道“${track}”语义锚点（${summaryAnchors.join("、")}）；弱内容证据获得有限救援，但仍低于完整权重。`,
    };
  }

  return {
    status: "none",
    multiplier: 1,
    titleAnchors,
    summaryAnchors,
    reason: "未发现足够强的当前赛道语义锚点，不提升弱内容证据权重。",
  };
}
