import rawArticles from "@/public/data/articles.json";
import rawPeople from "@/public/data/people.json";
import rawResearchReports from "@/public/data/research_reports.json";
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

function articleSources(article: ArticleRecord): ChannelUpdateSource[] {
  return uniqueSources([
    {
      name: article.source.platform || article.source.name,
      href: article.source.url,
      title: article.title,
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
  const track = resolveCanonicalTrack(article.sector);
  if (!track) return null;
  const topics = technologyTopicsForText([
    article.title,
    article.summary,
    article.company,
    article.sector,
    ...(article.matchedTrackingTerms ?? []),
  ]);
  const sources = articleSources(article);
  const base = articleToUpdate(article, `${track} · ${article.region}`);

  return {
    ...base,
    track,
    region: article.region,
    topicSlugs: topics.map((topic) => topic.slug),
    topicNames: topics.map((topic) => topic.name),
    eventClusterId: article.eventClusterId,
    sources,
    sourceCount: Math.max(sources.length || 1, article.duplicateCount ?? 1),
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
