export const VCIQ_RESEARCH_HANDOFF_VERSION = 1;

export type ResearchRelatedSource = {
  name: string;
  url: string;
  level?: string;
  title?: string;
  publishedAt?: string;
};

export type ResearchWorkspaceHandoff = {
  eventId: string;
  title: string;
  url: string;
  summary: string;
  sector: string;
  company?: string;
  people?: string[];
  companies?: string[];
  relatedSources?: ResearchRelatedSource[];
  importance: number;
  publishedAt: string;
  sourceName: string;
  sourceLevel?: string;
  matchedTrackingTerms?: string[];
  curated?: boolean;
  sectorFollowed?: boolean;
  savedForLater?: boolean;
};

const PUBLIC_ORIGIN = "https://vciq.github.io";
const ARTICLE_DATA_URL = `${PUBLIC_ORIGIN}/data/articles.json`;
const RANKED_DATA_URL = `${PUBLIC_ORIGIN}/data/ranked-intelligence.json`;

function clean(value: string | undefined) {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function unique(values: readonly string[] | undefined) {
  return [...new Set((values ?? []).map((value) => clean(value)).filter(Boolean))];
}

export function buildResearchInvestigationHref(eventId: string) {
  const params = new URLSearchParams();
  params.set("event", eventId);
  return `/research-agent/investigate/?${params.toString()}`;
}

export function buildResearchContextUrl(eventId: string, origin = PUBLIC_ORIGIN) {
  const base = origin.replace(/\/+$/, "");
  return `${base}${buildResearchInvestigationHref(eventId)}`;
}

export function buildResearchWorkspaceLaunchUrl(
  workspaceUrl: string | undefined,
  eventId: string,
  contextUrl = buildResearchContextUrl(eventId),
) {
  const raw = clean(workspaceUrl);
  if (!raw) return "";
  try {
    const url = new URL(raw);
    url.searchParams.set("vciq_handoff", String(VCIQ_RESEARCH_HANDOFF_VERSION));
    url.searchParams.set("vciq_event", eventId);
    url.searchParams.set("vciq_context", contextUrl);
    url.searchParams.set("vciq_articles", ARTICLE_DATA_URL);
    url.searchParams.set("vciq_ranked", RANKED_DATA_URL);
    return url.toString();
  } catch {
    return "";
  }
}

export function buildResearchWorkspacePrompt(input: ResearchWorkspaceHandoff) {
  const people = unique(input.people);
  const companies = unique([input.company ?? "", ...(input.companies ?? [])]);
  const trackingSignals = [
    input.sectorFollowed ? `已显式关注赛道「${clean(input.sector)}」` : "",
    input.curated ? "VCIQ 人工精选" : "",
    input.savedForLater ? "已加入稍后读" : "",
    ...unique(input.matchedTrackingTerms).map((term) => `命中追踪词「${term}」`),
  ].filter(Boolean);
  const sources = (input.relatedSources ?? [])
    .filter((source) => clean(source.url))
    .slice(0, 8)
    .map((source, index) => {
      const label = clean(source.title) || clean(source.name) || `关联来源 ${index + 1}`;
      const level = clean(source.level);
      return `${index + 1}. ${label}${level ? `（${level}）` : ""}\n   ${clean(source.url)}`;
    });

  return [
    "请围绕下面这条 VCIQ 情报开展一次可复核的深度研究。不要把摘要、媒体措辞或模型推断直接当成事实；关键结论必须回到原始材料或独立来源核验，并明确区分【事实】【推断】【待验证】。",
    "",
    "## 当前事件",
    `- 标题：${clean(input.title)}`,
    `- 原始 URL：${clean(input.url)}`,
    `- 发布时间：${clean(input.publishedAt) || "未知"}`,
    `- 赛道：${clean(input.sector) || "未知"}`,
    `- 公司：${companies.join("、") || "未明确"}`,
    `- 人物：${people.join("、") || "未明确"}`,
    `- 来源：${clean(input.sourceName) || "未知"}${clean(input.sourceLevel) ? `（${clean(input.sourceLevel)}）` : ""}`,
    `- 重要度：${Number.isFinite(input.importance) ? input.importance : "未知"}`,
    `- VCIQ 追踪状态：${trackingSignals.join("；") || "暂无显式追踪信号"}`,
    `- 摘要：${clean(input.summary) || "无"}`,
    "",
    "## 关联来源",
    ...(sources.length ? sources : ["暂无额外关联来源，请主动寻找至少 2 个独立来源进行交叉核验。"]),
    "",
    "## 研究任务",
    "1. 事实核验：确认事件到底发生了什么、时间、主体、关键数字和原始出处，并列出互相独立的证据。",
    "2. 历史变化：对比过去 30 天 / 90 天同主题事件，判断这是延续、加速、反转还是首次出现的新信号。",
    "3. 关系扩展：识别相关公司、人物、产品、供应链、客户、竞争者和监管主体，并说明关系强弱。",
    "4. 产业影响：分析它对当前赛道格局、供需、成本、技术路线和竞争壁垒可能产生的影响。",
    "5. 投资判断：分别给出 bull case、bear case、最关键的反证，以及哪些结论目前证据仍不足。",
    "6. 下一证据：列出最值得继续追踪的 3–5 个问题、信源或可验证事件。",
    "",
    "输出时优先引用原始 URL 与高质量独立来源；对每个关键判断标注证据强弱。",
  ].join("\n");
}
