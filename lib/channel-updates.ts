import rawArticles from "@/public/data/articles.json";
import rawPeople from "@/public/data/people.json";
import rawResearchReports from "@/public/data/research_reports.json";
import { canonicalTracksForItem } from "@/lib/canonical-sector-assignment";
import { getChannelDocumentUpdateItems } from "@/lib/channel-documents";
import { resolveArticleCompanyEntities } from "@/lib/company-entity-registry";
import {
  normalizeChannelUpdateDate,
  type ChannelUpdateDatePrecision,
} from "@/lib/channel-update-date";
import {
  institutionDataLayerVersions,
  institutionEventLayerRecords,
  type InstitutionEventLayerRecord,
} from "@/lib/institution-data-layer-data";
import { technologyTopicsForText } from "@/lib/technology-topic-matching";
import { technologyTermMatchesText } from "@/lib/technology-term-matching";
import { trackedSectors } from "@/lib/tracked-sectors";

export type ChannelUpdateKey =
  | "technology"
  | "companies"
  | "institutions"
  | "reports"
  | "people";

export type SourceEvidenceGrade = "A" | "B" | "C" | "D";

export type ChannelUpdateSource = {
  name: string;
  href: string;
  title?: string;
};

export type ChannelUpdateItem = {
  id: string;
  title: string;
  summary: string;
  href: string;
  source: string;
  label: string;
  context: string;
  date: string;
  dateOriginal: string;
  datePrecision: ChannelUpdateDatePrecision;
  sortAt: string;
  keywords: string[];
  classifications?: string[];
  firstSeenAt?: string;
  firstSeenEstimated?: boolean;
  lastVerifiedAt?: string;
  lastVerifiedEstimated?: boolean;
  sourceGrade?: SourceEvidenceGrade;
  sourceGradeLabel?: string;
  sourceVerificationPolicy?: string;
  track?: string;
  publicTracks?: string[];
  region?: string;
  topicSlugs?: string[];
  topicNames?: string[];
  eventClusterId?: string;
  sources?: ChannelUpdateSource[];
  sourceCount?: number;
};

export type ChannelUpdateDirectory = {
  title: string;
  description: string;
  generatedAt: string;
  items: ChannelUpdateItem[];
};

type ArticleRelatedSource = {
  name: string;
  url: string;
  platform?: string;
  title?: string;
};

type ArticleRecord = {
  id: string;
  title: string;
  summary: string;
  type: string;
  region: string;
  sector: string;
  company?: string;
  companySlug?: string;
  companySlugs?: string[];
  companyMatch?: { slug: string; method: string; confidence: number };
  companyMatches?: { slug: string; method: string; confidence: number }[];
  companyCandidateSlugs?: string[];
  institutions?: string[];
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  matchedTrackingTerms?: string[];
  qualityStatus?: string;
  qualitySignals?: string[];
  publishedAt: string;
  importance?: number;
  firstSeenAt?: string;
  firstSeenEstimated?: boolean;
  lastVerifiedAt?: string;
  lastVerifiedEstimated?: boolean;
  duplicateCount?: number;
  eventClusterId?: string;
  relatedSources?: ArticleRelatedSource[];
  source: {
    name: string;
    url: string;
    platform?: string;
    evidenceGrade?: SourceEvidenceGrade;
    evidenceLabel?: string;
    evidencePolicy?: string;
  };
};

type ArticlePayload = {
  generatedAt: string;
  articles: ArticleRecord[];
};

type ResearchReportRecord = {
  id: string;
  title: string;
  publishedAt: string;
  institution: string;
  reportType: string;
  sector: string;
  summary: string;
  sourceName: string;
  sourcePageUrl?: string;
  originalPdfUrl?: string;
  archivedAt?: string;
};

type ResearchReportPayload = {
  generatedAt: string;
  reports: ResearchReportRecord[];
};

type PersonMaterial = {
  title: string;
  date: string;
  type: string;
  url: string;
  source: string;
};

type PersonRecord = {
  slug: string;
  name: string;
  role: string;
  updatedAt?: string;
  materials?: PersonMaterial[];
};

type PeoplePayload = {
  generatedAt: string;
  people: PersonRecord[];
};

const articlesPayload = rawArticles as ArticlePayload;
const researchReportsPayload = rawResearchReports as ResearchReportPayload;
const peoplePayload = rawPeople as PeoplePayload;

const materialTypeLabels: Record<string, string> = {
  speech: "演讲",
  interview: "采访",
  qa: "公开对话",
  research_paper: "论文",
  authored_work: "著作",
  shareholder_letter: "股东信",
  public_document: "公开材料",
  official_profile: "官方资料",
  biography: "人物资料",
};

function normalize(value: string) {
  return value.toLocaleLowerCase("zh-CN").replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

const canonicalTrackByKey = new Map(
  trackedSectors.flatMap((sector) =>
    [sector.name, ...(sector.aliases ?? [])]
      .map((name) => normalize(name))
      .filter(Boolean)
      .map((key) => [key, sector.name] as const),
  ),
);

function resolveCanonicalTrack(value: string) {
  return canonicalTrackByKey.get(normalize(value));
}

function uniqueKeywords(values: string[]) {
  const seen = new Set<string>();
  return values.filter((value) => {
    const keyword = value.trim();
    const normalized = normalize(keyword);
    if (!normalized || seen.has(normalized)) return false;
    seen.add(normalized);
    return true;
  });
}

export type TechnologyEventResearchEvidenceInput = {
  topicCount: number;
  track: string;
  title: string;
  summary: string;
  sourceUrl?: string;
  matchedTrackingTerms?: string[];
  qualityStatus?: string;
  qualitySignals?: string[];
  sourceGrade?: SourceEvidenceGrade;
  sourceName?: string;
  sourceCount?: number;
};

const technologyEventTrackAnchorTerms: Record<string, string[]> = {
  "AI / AGI": ["AI", "artificial intelligence", "人工智能", "AGI", "大模型", "LLM"],
  机器人: ["机器人", "robot", "robotics", "humanoid", "具身智能", "灵巧手"],
  半导体: ["半导体", "芯片", "晶圆", "wafer", "foundry", "封装", "光刻", "DRAM", "HBM"],
  新能源: ["新能源", "电池", "储能", "光伏", "风电", "电网", "battery", "energy storage", "solar", "wind"],
  生物科技: ["生物科技", "biotech", "药物", "蛋白", "基因", "临床", "分子", "drug", "protein", "gene", "clinical"],
  量子计算: ["量子计算", "quantum computing", "qubit", "量子比特"],
  商业航天: ["商业航天", "火箭", "卫星", "轨道", "航天器", "rocket", "satellite", "orbit", "spacecraft"],
  Web3: ["Web3", "区块链", "blockchain", "加密货币", "cryptocurrency", "比特币", "Bitcoin", "Ethereum", "稳定币", "stablecoin", "RWA", "链上"],
  新材料: ["新材料", "材料", "先进材料", "半导体材料", "光刻胶", "陶瓷", "合金", "复合材料", "material", "ceramic", "alloy", "composite"],
  智能制造: ["智能制造", "工业自动化", "工业软件", "数字工厂", "机器视觉", "manufacturing", "factory", "industrial automation"],
  可控核聚变: ["可控核聚变", "核聚变", "聚变能源", "fusion", "tokamak", "托卡马克", "stellarator", "仿星器"],
  风险投资: ["风险投资", "venture capital", "私募股权", "private equity", "天使轮", "种子轮", "融资轮"],
  新消费: ["新消费", "即时零售", "消费品牌", "consumer brand", "retail technology"],
  智能交通: ["智能交通", "车路协同", "自动驾驶", "低空经济", "eVTOL", "mobility", "autonomous driving"],
  商业模式创新: ["商业模式创新", "business model innovation", "平台经济", "订阅模式"],
  AI安全: ["AI安全", "AI safety", "AI alignment", "人工智能安全", "模型安全", "越狱", "jailbreak", "red teaming", "guardrail"],
  心理学: ["心理学", "psychology", "心理健康", "mental health", "认知科学", "cognitive science"],
  医疗科技: ["医疗科技", "医疗器械", "数字医疗", "诊断", "medtech", "medical device", "diagnostic", "digital health"],
  AI智能终端: ["AI智能终端", "AI终端", "AI手机", "AI PC", "AI眼镜", "端侧AI", "on-device AI", "edge AI"],
  AI网络通信: ["AI网络通信", "AI-RAN", "CXL", "高速互连", "网络芯片", "networking chip", "telecom AI"],
  AI语音: ["AI语音", "语音模型", "语音识别", "语音合成", "voice AI", "speech AI", "ASR", "TTS", "text to speech"],
  AI影视: ["AI影视", "AI电影", "AI视频", "生成视频", "AI video", "generative video", "VFX"],
  GEO: ["GEO", "生成式引擎优化", "generative engine optimization", "AI搜索优化", "AI推荐优化"],
  AI音乐创作与产业发展: ["AI音乐", "AI music", "音乐生成", "music generation", "音乐产业"],
};

function escapeTechnologyEventAnchorRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function technologyEventTrackAnchorMatchesText(text: string, term: string) {
  const normalizedTerm = term.normalize("NFKC").toLocaleLowerCase("en-US").trim();
  if (/^[a-z0-9][a-z0-9\s._:/+\-]*$/iu.test(normalizedTerm)) {
    const pieces = normalizedTerm.split(/[^a-z0-9]+/iu).filter(Boolean);
    if (!pieces.length) return false;
    const body = pieces
      .map(escapeTechnologyEventAnchorRegExp)
      .join("[\\s._:/+\\-]+");
    return new RegExp(`(^|[^a-z0-9])${body}([^a-z0-9]|$)`, "iu").test(
      text.normalize("NFKC").toLocaleLowerCase("en-US"),
    );
  }
  return technologyTermMatchesText(text, term);
}

function matchingTechnologyEventTrackAnchors(text: string, track: string) {
  return (technologyEventTrackAnchorTerms[track] ?? []).filter((term) =>
    technologyEventTrackAnchorMatchesText(text, term),
  );
}

const nonEventTechnologyTitlePatterns = [
  /(?:早报|晨报|日报|周报)/iu,
  /(?:lifetime subscription|\bbundle\b.*\b(?:training|teaches)\b|\btraining\b.*\$\d|\bget\b.*\bfor\b(?:\s+just)?\s*\$\d|\bfor life for\s*\$\d|\baccess to\b.*\bfor\b(?:\s+just)?\s*\$\d)/iu,
  /^(?:investors?|AI Model Leaderboards?\s*&\s*Benchmarks?|DeepSeek 招聘|模型 & 价格 \| DeepSeek API Docs|更新日志 \| DeepSeek API Docs|Legal AI solutions for law firms \| Harvey|IROS：国际智能机器人与系统会议|Mobileye Drive™ \| Self-Driving System for Autonomous MaaS|Technology \| Commonwealth Fusion Systems|SPARC: Proving commercial fusion energy is possible \| Commonwealth Fusion Systems|ARC: Putting fusion energy on the grid \| Commonwealth Fusion Systems|Claude (?:Opus|Sonnet)|2026中国先进封装企业20强（TOP 20）|Don’t use Gemini or ChatGPT for studying — use this free app instead|睿小鉴\s*-\s*AI导航\s*-\s*猫目)$/iu,
  /this free browser extension made it ridiculously easy$/iu,
  /^Anthropic：For more on how Claude ran this experiment and the full results, see our blog:/iu,
  /^Google Pixel (?:Watch 5|11 Pro XL) Review:/iu,
];

const nonEventTechnologyExactTitles = new Set(
  [
    "半导体器件的失效分析及可靠性测试",
    "Understanding Why Agentic AI Demands a Massive CPU Renaissance and How IT Leaders Must Prepare Now | Techspective: A Unique Perspective on Technology",
    "晶圆厂转先进封装，值不值？",
    "Agentic AI in the enterprise: How to balance autonomy with constraints",
    "Getting the most out of GPT-5.6: Sol, Terra, and Luna",
  ].map((title) => title.toLocaleLowerCase("en-US")),
);

type TechnologyEventPublicationCuration = {
  title: string;
  summary: string;
  label?: string;
  additionalSources?: ChannelUpdateSource[];
};

const technologyEventPublicationCurationById: Record<
  string,
  TechnologyEventPublicationCuration
> = {
  "user-x-googledeepmind-25b4f20ecfb62f41": {
    title: "AlphaEvolve 用 AI 将矩阵乘法指数上界推进至 ω < 2.371177",
    summary:
      "Google DeepMind 联合研究团队使用现代优化、机器学习算法与 AlphaEvolve，将矩阵乘法指数的已知上界从 2.371339 改进至 ω < 2.371177。",
    label: "论文",
    additionalSources: [
      {
        name: "arXiv",
        href: "https://arxiv.org/abs/2608.16884",
        title:
          "Improving the matrix multiplication exponent with modern optimization and AlphaEvolve",
      },
    ],
  },
  "official-helion-7df714571d811ffc": {
    title: "Helion 完成 Vela 可控核聚变脉冲电源规模测试并推进 Tiny Merge 集成",
    summary:
      "Helion 披露 Vela 以 1 Hz 运行，并向模拟 Polaris 压缩磁体累计传输超过 11 GJ 能量；团队随后启动 Junior Formation，近期开始集成 Tiny Merge 可控核聚变试验台。",
  },
};

const nonEventTechnologySummaryPatterns = [/^早报来啦[~～！!]*$/iu];
const nonEventTechnologyUrlPatterns = [
  /^https?:\/\/(?:www\.)?cfs\.energy\/technology(?:\/(?:sparc|arc))?\/?$/iu,
  /^https?:\/\/(?:www\.)?mobileye\.com\/products\/drive\/?$/iu,
  /^https?:\/\/(?:www\.)?anthropic\.com\/claude\/(?:opus|sonnet)\/?$/iu,
  /^https?:\/\/api-docs\.deepseek\.com\/zh-cn\/updates\/?$/iu,
];

function isNonEventTechnologyPage(
  title: string,
  summary: string,
  sourceUrl = "",
) {
  const normalizedTitle = title.trim();
  const normalizedSummary = summary.trim();
  const normalizedSourceUrl = sourceUrl.trim().replace(/\\+$/u, "");
  return (
    nonEventTechnologyExactTitles.has(
      normalizedTitle.toLocaleLowerCase("en-US"),
    ) ||
    nonEventTechnologyTitlePatterns.some((pattern) => pattern.test(normalizedTitle)) ||
    nonEventTechnologySummaryPatterns.some((pattern) => pattern.test(normalizedSummary)) ||
    nonEventTechnologyUrlPatterns.some((pattern) => pattern.test(normalizedSourceUrl))
  );
}

/**
 * Evidence quality and content relevance are separate publication gates.
 * A/B sources can strengthen a relevant event, but cannot make an unrelated
 * article relevant on their own. Long-tail evidence must first match the
 * current track in the title, or through multiple anchors in the summary.
 */
export function technologyEventHasResearchEvidence(
  input: TechnologyEventResearchEvidenceInput,
) {
  if (isNonEventTechnologyPage(input.title, input.summary, input.sourceUrl)) return false;
  if (
    input.sourceGrade === "C" &&
    input.sourceCount === 1 &&
    input.sourceName?.trim().toLocaleLowerCase("en-US") === "dev community"
  ) {
    return false;
  }
  if (input.topicCount > 0) return true;
  if ((input.matchedTrackingTerms ?? []).some((term) => term.trim())) return true;

  const trackingHitCounts = (input.qualitySignals ?? []).flatMap((signal) => {
    const match = signal.match(/(?:标题|摘要)命中\s*(\d+)\s*个追踪词/u);
    return match ? [Number(match[1])] : [];
  });
  const strongestTrackingHit = Math.max(0, ...trackingHitCounts);
  const hasExplicitEventAction = (input.qualitySignals ?? []).some((signal) =>
    signal.includes("包含明确事件动作"),
  );

  const titleAnchors = matchingTechnologyEventTrackAnchors(
    input.title,
    input.track,
  );
  const summaryAnchors = matchingTechnologyEventTrackAnchors(
    input.summary,
    input.track,
  );
  const hasTrackContentEvidence =
    titleAnchors.length > 0 || new Set(summaryAnchors).size >= 2;
  if (!hasTrackContentEvidence) return false;

  const hasAssessedQuality =
    input.qualityStatus === "可用" || input.qualityStatus === "高可信";
  const hasReliableSource =
    input.sourceGrade === "A" || input.sourceGrade === "B";
  const hasExplicitTrackingEvidence =
    strongestTrackingHit >= 2 ||
    (strongestTrackingHit >= 1 && hasExplicitEventAction);

  return hasAssessedQuality || hasReliableSource || hasExplicitTrackingEvidence;
}

function uniqueSources(values: ChannelUpdateSource[]) {
  const seen = new Set<string>();
  return values.filter((value) => {
    const href = value.href.trim();
    const key = href.toLocaleLowerCase("en-US");
    if (!href || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function articleSources(
  article: ArticleRecord,
  primaryTitle = article.title,
): ChannelUpdateSource[] {
  return uniqueSources([
    {
      name: article.source.platform || article.source.name,
      href: article.source.url,
      title: primaryTitle,
    },
    ...(article.relatedSources ?? []).map((source) => ({
      name: source.platform || source.name,
      href: source.url,
      title: source.title,
    })),
  ]);
}

function dedupeAndSort(items: ChannelUpdateItem[]) {
  const seen = new Set<string>();
  return items
    .filter((item) => {
      const key = `${item.href.trim().toLocaleLowerCase("en-US")}|${normalize(item.title)}`;
      if (!item.href || !item.title || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort(
      (left, right) =>
        right.sortAt.localeCompare(left.sortAt) || right.title.localeCompare(left.title, "zh-CN"),
    );
}

function articleToUpdate(
  article: ArticleRecord,
  context: string,
  additionalClassifications: string[] = [],
): ChannelUpdateItem {
  const normalizedDate = normalizeChannelUpdateDate(
    article.publishedAt,
    articlesPayload.generatedAt,
  );
  const sourceClassifications = article.source.evidenceGrade
    ? [`${article.source.evidenceGrade}级来源`]
    : [];
  if (article.source.evidenceGrade === "D") {
    sourceClassifications.push("待交叉验证");
  }

  return {
    id: article.id,
    title: article.title,
    summary: article.summary,
    href: article.source.url,
    source: article.source.platform || article.source.name,
    label: article.type,
    context,
    date: normalizedDate.displayDate,
    dateOriginal: normalizedDate.originalDate,
    datePrecision: normalizedDate.precision,
    sortAt: normalizedDate.sortAt,
    keywords: [article.type],
    classifications: uniqueKeywords([
      ...additionalClassifications,
      ...sourceClassifications,
    ]),
    firstSeenAt: article.firstSeenAt,
    firstSeenEstimated: article.firstSeenEstimated,
    lastVerifiedAt: article.lastVerifiedAt,
    lastVerifiedEstimated: article.lastVerifiedEstimated,
    sourceGrade: article.source.evidenceGrade,
    sourceGradeLabel: article.source.evidenceLabel,
    sourceVerificationPolicy: article.source.evidencePolicy,
  };
}

const sourceGradeRank: Record<SourceEvidenceGrade, number> = {
  A: 4,
  B: 3,
  C: 2,
  D: 1,
};

function preferredEventRepresentative(items: ChannelUpdateItem[]) {
  return [...items].sort((left, right) => {
    const gradeDelta =
      (right.sourceGrade ? sourceGradeRank[right.sourceGrade] : 0) -
      (left.sourceGrade ? sourceGradeRank[left.sourceGrade] : 0);
    return (
      gradeDelta ||
      right.sortAt.localeCompare(left.sortAt) ||
      (right.sourceCount ?? 1) - (left.sourceCount ?? 1)
    );
  })[0];
}

export function aggregateTechnologyEventUpdates(items: ChannelUpdateItem[]) {
  const groups = new Map<string, ChannelUpdateItem[]>();
  for (const item of items) {
    const clusterId = item.eventClusterId?.trim();
    const key = clusterId ? `cluster:${clusterId}` : `item:${item.id}`;
    const group = groups.get(key) ?? [];
    group.push(item);
    groups.set(key, group);
  }

  return [...groups.values()].map((group) => {
    const representative = preferredEventRepresentative(group);
    if (!representative) throw new Error("technology event group has no representative");

    const newest = [...group].sort((left, right) => right.sortAt.localeCompare(left.sortAt))[0];
    const sources = uniqueSources(group.flatMap((item) => item.sources ?? []));
    const sourceCount = Math.max(
      sources.length || 1,
      ...group.map((item) => item.sourceCount ?? 1),
    );
    const firstSeenAt = group
      .map((item) => item.firstSeenAt)
      .filter((value): value is string => Boolean(value))
      .sort()[0];
    const lastVerifiedAt = group
      .map((item) => item.lastVerifiedAt)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1);

    return {
      ...representative,
      date: newest?.date ?? representative.date,
      dateOriginal: newest?.dateOriginal ?? representative.dateOriginal,
      datePrecision: newest?.datePrecision ?? representative.datePrecision,
      sortAt: newest?.sortAt ?? representative.sortAt,
      topicSlugs: uniqueKeywords(group.flatMap((item) => item.topicSlugs ?? [])),
      topicNames: uniqueKeywords(group.flatMap((item) => item.topicNames ?? [])),
      classifications: uniqueKeywords(
        group.flatMap((item) => item.classifications ?? []),
      ),
      sources,
      sourceCount,
      firstSeenAt,
      firstSeenEstimated: firstSeenAt
        ? group.find((item) => item.firstSeenAt === firstSeenAt)?.firstSeenEstimated
        : representative.firstSeenEstimated,
      lastVerifiedAt,
      lastVerifiedEstimated: lastVerifiedAt
        ? group.find((item) => item.lastVerifiedAt === lastVerifiedAt)?.lastVerifiedEstimated
        : representative.lastVerifiedEstimated,
    } satisfies ChannelUpdateItem;
  });
}

function technologyArticleToUpdate(article: ArticleRecord): ChannelUpdateItem | null {
  const observedTrack = resolveCanonicalTrack(article.sector);
  if (!observedTrack) return null;
  const publicationCuration = technologyEventPublicationCurationById[article.id];
  const title = publicationCuration?.title ?? article.title;
  const summary = publicationCuration?.summary ?? article.summary;
  // Publication topics must be proven by the article content. Company and raw
  // sector fields remain provenance/context; letting either enter this corpus
  // would allow an assigned sector to prove its own relevance.
  const topics = technologyTopicsForText([
    title,
    summary,
  ]);
  // Keep the observed canonical track on the record. Reviewed semantic
  // corrections get a separate publicTracks projection so display/filtering
  // can be accurate without mutating provenance or analysis inputs.
  const track = observedTrack;
  const sources = uniqueSources([
    ...articleSources(article, title),
    ...(publicationCuration?.additionalSources ?? []),
  ]);
  const base = {
    ...articleToUpdate(article, `${track} · ${article.region}`),
    title,
    summary,
    label: publicationCuration?.label ?? article.type,
    keywords: [publicationCuration?.label ?? article.type],
  };

  // Keep every raw article in articles.json for provenance, while preventing
  // weak identity/source collisions and unassessed track-only items from
  // entering the public technology event directory. Source grade measures
  // evidence reliability, not technology relevance.
  if (
    !technologyEventHasResearchEvidence({
      topicCount: topics.length,
      track: observedTrack,
      title,
      summary,
      sourceUrl: article.source.url,
      matchedTrackingTerms: article.matchedTrackingTerms,
      qualityStatus: article.qualityStatus,
      qualitySignals: article.qualitySignals,
      sourceGrade: article.source.evidenceGrade,
      sourceName: article.source.platform || article.source.name,
      sourceCount: Math.max(sources.length || 1, article.duplicateCount ?? 1),
    })
  ) {
    return null;
  }

  const canonicalResolution = canonicalTracksForItem({
    ...base,
    track,
    region: article.region,
    topicSlugs: topics.map((topic) => topic.slug),
    topicNames: topics.map((topic) => topic.name),
  });
  const publicTracks = canonicalResolution.applied
    ? canonicalResolution.canonicalTracks
    : [track];

  return {
    ...base,
    context: `${publicTracks.join(" · ")} · ${article.region}`,
    track,
    publicTracks,
    region: article.region,
    topicSlugs: topics.map((topic) => topic.slug),
    topicNames: topics.map((topic) => topic.name),
    eventClusterId: article.eventClusterId,
    sources,
    sourceCount: Math.max(sources.length || 1, article.duplicateCount ?? 1),
    classifications: uniqueKeywords([
      ...(base.classifications ?? []),
      ...(canonicalResolution.applied ? ["规范赛道纠错"] : []),
    ]),
  };
}

function institutionEventToUpdate(
  event: InstitutionEventLayerRecord,
): ChannelUpdateItem {
  const normalizedDate = normalizeChannelUpdateDate(
    event.publishedAt,
    institutionDataLayerVersions.eventsGeneratedAt,
  );
  const sourceClassifications = event.source.evidenceGrade
    ? [`${event.source.evidenceGrade}级来源`]
    : [];
  if (event.source.evidenceGrade === "D") {
    sourceClassifications.push("待交叉验证");
  }
  const institutionNames = event.institutionNames.slice(0, 3);
  const channelClassification =
    event.scope === "institution-event" ? "机构动态" : "资本事件";

  return {
    id: event.id,
    title: event.title,
    summary: event.summary,
    href: event.source.url,
    source: event.source.platform || event.source.name,
    label: event.eventType,
    context:
      event.scope === "institution-event"
        ? `${institutionNames.join("、")} · ${event.sector}`
        : `资本事件 · ${event.sector}`,
    date: normalizedDate.displayDate,
    dateOriginal: normalizedDate.originalDate,
    datePrecision: normalizedDate.precision,
    sortAt: normalizedDate.sortAt,
    keywords: [event.eventType],
    classifications: uniqueKeywords([
      channelClassification,
      ...sourceClassifications,
    ]),
    firstSeenAt: event.firstSeenAt,
    firstSeenEstimated: event.firstSeenEstimated,
    lastVerifiedAt: event.lastVerifiedAt,
    lastVerifiedEstimated: event.lastVerifiedEstimated,
    sourceGrade: event.source.evidenceGrade,
    sourceGradeLabel: event.source.evidenceLabel,
    sourceVerificationPolicy: event.source.evidencePolicy,
  };
}

function technologyDirectory(): ChannelUpdateDirectory {
  const articleItems = articlesPayload.articles
    .map(technologyArticleToUpdate)
    .filter((item): item is ChannelUpdateItem => Boolean(item));
  const eventItems = aggregateTechnologyEventUpdates(articleItems);

  return {
    title: "科技事件更新目录",
    description:
      "按核心赛道、技术主题、事件类型、地区与证据等级筛选；同一事件的重复报道聚合为一条，并保留多个公开信源。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("technology"),
      ...eventItems,
    ]),
  };
}

function companiesDirectory(): ChannelUpdateDirectory {
  const items = articlesPayload.articles.flatMap((article) => {
    const matchedCompanies = resolveArticleCompanyEntities(article);
    if (!matchedCompanies.length) return [];
    const companyNames = matchedCompanies
      .slice(0, 3)
      .map((company) => company.name)
      .join("、");
    return [articleToUpdate(article, `${companyNames} · ${article.sector}`)];
  });
  return {
    title: "公司更新目录",
    description: "与已收录公司直接相关的融资、产品、经营和资本市场更新，仅按绿色事件标签筛选。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("companies"),
      ...items,
    ]),
  };
}

function institutionsDirectory(): ChannelUpdateDirectory {
  const items = institutionEventLayerRecords.map(institutionEventToUpdate);
  return {
    title: "机构与资本事件更新目录",
    description:
      "读取独立机构事件数据层：已识别具体机构的记录归为“机构动态”；未识别机构的融资、并购与 IPO 归为“资本事件”。每条机构归属均保留结构化字段、官网域名或审核别名证据。",
    generatedAt: institutionDataLayerVersions.eventsGeneratedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("institutions"),
      ...items,
    ]),
  };
}

function reportsDirectory(): ChannelUpdateDirectory {
  const items = researchReportsPayload.reports.map((report) => {
    const href = report.originalPdfUrl || report.sourcePageUrl || "";
    const orderingDate = report.archivedAt || report.publishedAt;
    const normalizedDate = normalizeChannelUpdateDate(
      orderingDate,
      researchReportsPayload.generatedAt,
    );
    return {
      id: report.id,
      title: report.title,
      summary: report.summary,
      href,
      source: report.sourceName || report.institution,
      label: report.reportType,
      context: `${report.institution} · ${report.sector}`,
      date: normalizedDate.displayDate,
      dateOriginal: normalizedDate.originalDate,
      datePrecision: normalizedDate.precision,
      sortAt: normalizedDate.sortAt,
      keywords: [report.reportType],
    } satisfies ChannelUpdateItem;
  });
  return {
    title: "研报更新目录",
    description: "新归档的公开研报与 PDF 原文，仅按记录前的绿色报告类型标签筛选。",
    generatedAt: researchReportsPayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("reports"),
      ...items,
    ]),
  };
}

function peopleDirectory(): ChannelUpdateDirectory {
  const items = peoplePayload.people.flatMap((person) =>
    (person.materials ?? []).map((material, index) => {
      const normalizedDate = normalizeChannelUpdateDate(
        material.date,
        peoplePayload.generatedAt,
      );
      const materialLabel = materialTypeLabels[material.type] || "人物材料";
      return {
        id: `${person.slug}-${index}-${normalize(material.title)}`,
        title: material.title,
        summary: `${person.name} · ${person.role}`,
        href: material.url,
        source: material.source,
        label: materialLabel,
        context: person.name,
        date: normalizedDate.displayDate,
        dateOriginal: normalizedDate.originalDate,
        datePrecision: normalizedDate.precision,
        sortAt: normalizedDate.sortAt,
        keywords: [materialLabel],
      } satisfies ChannelUpdateItem;
    }),
  );
  return {
    title: "人物材料更新目录",
    description: "人物演讲、采访、公开对话、论文与著作等材料，仅按记录前的绿色材料类型标签筛选。",
    generatedAt: peoplePayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("people"),
      ...items,
    ]),
  };
}

export function getChannelUpdateDirectory(
  channel: ChannelUpdateKey,
): ChannelUpdateDirectory {
  switch (channel) {
    case "technology":
      return technologyDirectory();
    case "companies":
      return companiesDirectory();
    case "institutions":
      return institutionsDirectory();
    case "reports":
      return reportsDirectory();
    case "people":
      return peopleDirectory();
  }
}
