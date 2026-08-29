import type { IntelligenceEvent, Source } from "./intelligence-data";
import type { ReportContent } from "./research-content";

export type TopicEvidenceMatchKind = "company" | "keyword" | "sector";

export type TopicEvidence = {
  evidenceId: string;
  event: IntelligenceEvent;
  matchKind: TopicEvidenceMatchKind;
  matchLabel: string;
};

type TopicRule = {
  keywords: string[];
  blockedKeywords?: string[];
  companyKeywordRequiredSlugs?: string[];
};

export type TopicResearchBrief = {
  generatedAt: string;
  readMinutes: number;
  evidence: TopicEvidence[];
  totalMatches: number;
  recent30Count: number;
  sourceCount: number;
  companyCount: number;
  dominantTypes: string[];
  coverageSummary: string;
  evidenceSummary: string;
};

const topicRules: Record<string, TopicRule> = {
  "humanoid-robotics": {
    keywords: [
      "humanoid",
      "人形机器人",
      "人形",
      "具身智能",
      "embodied ai",
      "embodied intelligence",
      "physical ai",
      "vision-language-action",
      "vision language action",
      "vla model",
      "biped",
      "dexterous manipulation",
      "灵巧操作",
      "全身控制",
      "whole-body",
      "whole body",
      "robot training data",
      "robot training dataset",
      "physical dataset",
      "unitree g1",
      "unitree h1",
      "fourier gr-1",
      "fourier gr-2",
      "gr-1 humanoid",
      "gr-2 humanoid",
    ],
    blockedKeywords: [
      "robotaxi",
      "robobus",
      "self-driving",
      "autonomous driving",
      "自动驾驶",
      "无人驾驶",
    ],
    companyKeywordRequiredSlugs: ["unitree", "fourier-intelligence"],
  },
  "autonomous-driving": {
    keywords: [
      "robotaxi",
      "self-driving",
      "self driving",
      "autonomous driving",
      "autonomous vehicle",
      "driverless",
      "自动驾驶",
      "无人驾驶",
      "无人出租车",
      "自动驾驶卡车",
      "advanced driver assistance",
      "adas",
    ],
    blockedKeywords: ["humanoid", "人形机器人", "具身智能"],
  },
  "ai-chips": {
    keywords: [
      "ai chip",
      "ai accelerator",
      "accelerator chip",
      "gpu",
      "inference chip",
      "training chip",
      "processor",
      "semiconductor",
      "芯片",
      "加速器",
      "推理芯片",
      "训练芯片",
      "处理器",
      "半导体",
    ],
  },
  "space-commercialization": {
    keywords: [
      "rocket",
      "launch",
      "spacecraft",
      "satellite",
      "starship",
      "neutron",
      "orbital",
      "space station",
      "火箭",
      "发射",
      "航天器",
      "卫星",
      "轨道",
      "空间站",
      "商业航天",
    ],
  },
  "ai-capital-2026": {
    keywords: [
      "funding",
      "financing",
      "fundraise",
      "fundraising",
      "investment",
      "capital expenditure",
      "capex",
      "data center",
      "datacenter",
      "融资",
      "投资",
      "资本开支",
      "数据中心",
      "算力投资",
    ],
    companyKeywordRequiredSlugs: [
      "openai",
      "anthropic",
      "xai",
      "deepseek",
      "databricks",
      "scale-ai",
    ],
  },
};

function normalizedText(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase("en-US");
}

function eventSearchText(event: IntelligenceEvent) {
  return normalizedText(`${event.title}\n${event.summary}`);
}

function firstMatchingKeyword(text: string, keywords: string[]) {
  return keywords.find((keyword) => text.includes(normalizedText(keyword)));
}

function sourceRank(source: Source) {
  const rank: Record<Source["level"], number> = {
    监管文件: 6,
    官方披露: 5,
    原始材料: 4,
    媒体报道: 3,
    数据库记录: 2,
    待交叉验证: 1,
  };
  return rank[source.level] ?? 0;
}

function isCoreEvidenceSource(source: Source) {
  return /^https?:\/\//u.test(source.url) && sourceRank(source) >= 2;
}

function normalizedTitleKey(title: string) {
  return normalizedText(title).replace(/[\p{P}\p{S}\s]+/gu, "");
}

function sortEvidence(
  left: Omit<TopicEvidence, "evidenceId">,
  right: Omit<TopicEvidence, "evidenceId">,
) {
  const dateOrder = right.event.publishedAt.localeCompare(left.event.publishedAt);
  if (dateOrder !== 0) return dateOrder;
  const sourceOrder = sourceRank(right.event.source) - sourceRank(left.event.source);
  if (sourceOrder !== 0) return sourceOrder;
  return right.event.importance - left.event.importance;
}

export function resolveTopicEvidence({
  slug,
  content,
  events,
  limit = 12,
}: {
  slug: string;
  content: ReportContent;
  events: IntelligenceEvent[];
  limit?: number;
}) {
  const rule = topicRules[slug];
  const candidates: Omit<TopicEvidence, "evidenceId">[] = [];

  for (const event of events) {
    // Core briefs require a directly traceable public source and exclude records
    // explicitly marked as awaiting cross-validation. Those records can remain in
    // the broader intelligence dataset without being promoted into research claims.
    if (!isCoreEvidenceSource(event.source)) continue;

    const inTopicSector = content.eventSectors.includes(event.sector);
    const inTopicCompany = Boolean(
      event.companySlug && content.companySlugs.includes(event.companySlug),
    );
    const text = eventSearchText(event);
    const blockedKeyword = rule
      ? firstMatchingKeyword(text, rule.blockedKeywords ?? [])
      : undefined;
    const topicKeyword = rule ? firstMatchingKeyword(text, rule.keywords) : undefined;

    if (blockedKeyword && !inTopicCompany) continue;

    if (inTopicCompany) {
      const requiresKeyword = Boolean(
        rule?.companyKeywordRequiredSlugs?.includes(event.companySlug ?? ""),
      );
      if (requiresKeyword && !topicKeyword) continue;
      if (blockedKeyword) continue;
      candidates.push({
        event,
        matchKind: "company",
        matchLabel: topicKeyword
          ? `专题公司 · ${topicKeyword}`
          : "专题公司",
      });
      continue;
    }

    if (!inTopicSector) continue;

    if (rule) {
      if (!topicKeyword || blockedKeyword) continue;
      candidates.push({
        event,
        matchKind: "keyword",
        matchLabel: `专题关键词 · ${topicKeyword}`,
      });
      continue;
    }

    // Reports without a dedicated V1 rule retain the legacy sector fallback,
    // while still obeying the source-quality gate above.
    candidates.push({
      event,
      matchKind: "sector",
      matchLabel: `赛道 · ${event.sector}`,
    });
  }

  candidates.sort(sortEvidence);

  const seenTitles = new Set<string>();
  const deduped = candidates.filter((candidate) => {
    const key = normalizedTitleKey(candidate.event.title);
    if (!key || seenTitles.has(key)) return false;
    seenTitles.add(key);
    return true;
  });

  return {
    totalMatches: deduped.length,
    evidence: deduped.slice(0, Math.max(0, limit)).map((candidate, index) => ({
      ...candidate,
      evidenceId: `E${String(index + 1).padStart(2, "0")}`,
    })),
  };
}

function subtractDays(date: string, days: number) {
  const parsed = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return "";
  parsed.setUTCDate(parsed.getUTCDate() - days);
  return parsed.toISOString().slice(0, 10);
}

function topValues(values: string[], limit: number) {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (!value) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit)
    .map(([value]) => value);
}

export function buildTopicResearchBrief({
  slug,
  content,
  events,
  snapshotDate,
  limit = 12,
}: {
  slug: string;
  content: ReportContent;
  events: IntelligenceEvent[];
  snapshotDate: string;
  limit?: number;
}): TopicResearchBrief {
  const resolved = resolveTopicEvidence({ slug, content, events, limit });
  const recentThreshold = subtractDays(snapshotDate, 30);
  const recent30Count = recentThreshold
    ? resolved.evidence.filter(
        ({ event }) =>
          event.publishedAt >= recentThreshold && event.publishedAt <= snapshotDate,
      ).length
    : 0;
  const sourceCount = new Set(
    resolved.evidence.map(({ event }) => event.source.url).filter(Boolean),
  ).size;
  const companyCount = new Set(
    resolved.evidence
      .map(({ event }) => event.companySlug || event.company)
      .filter(Boolean),
  ).size;
  const dominantTypes = topValues(
    resolved.evidence.map(({ event }) => event.type),
    2,
  );

  const coverageSummary = resolved.evidence.length
    ? `专题规则共筛出 ${resolved.totalMatches} 条相关事件；当前展示最近 ${resolved.evidence.length} 条，覆盖 ${sourceCount} 个可追溯来源与 ${companyCount} 个公司/主体。过去 30 天有 ${recent30Count} 条进入当前核心证据集。`
    : "当前快照尚未筛出满足专题规则与来源质量门的事件；页面保留研究框架与后续跟踪项，并等待新的可验证证据。";
  const evidenceSummary = dominantTypes.length
    ? `当前核心证据主要集中在${dominantTypes.map((item) => `“${item}”`).join("、")}。这些事实用于更新专题判断，但不会把同赛道的邻近事件自动视为本专题证据。`
    : "当前没有足够的专题证据形成事件类型分布。";

  return {
    generatedAt: snapshotDate,
    readMinutes: 3,
    evidence: resolved.evidence,
    totalMatches: resolved.totalMatches,
    recent30Count,
    sourceCount,
    companyCount,
    dominantTypes,
    coverageSummary,
    evidenceSummary,
  };
}
