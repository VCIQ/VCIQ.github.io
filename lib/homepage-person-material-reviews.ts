import type { IntelligenceSource } from "@/lib/use-articles";

export type HomepagePersonMaterialReview = {
  id: string;
  personSlug: string;
  sourceUrl: string;
  expectedTitle: string;
  relation: "context-only" | "reported-actor";
  sourceLevel: IntelligenceSource["level"];
  summary: string;
  signal: string;
  evidenceUrl: string;
  evidenceNote: string;
  reviewedAt: string;
};

/**
 * Source-reviewed exceptions, NOT a classifier for all interviews or papers.
 * An entity-library match proves identity, not speaker/author/subject status.
 * Keep source URL, expected title and person identity together so an exception
 * cannot silently transfer to another person or to different source material.
 */
export const homepagePersonMaterialReviews: readonly HomepagePersonMaterialReview[] = [
  {
    id: "leiphone-idea-zhang-lei-not-fei-fei-li",
    personSlug: "fei-fei-li",
    sourceUrl: "https://www.leiphone.com/category/academic/wQny8Cer4EJz0RAU.html",
    expectedTitle: "对话 IDEA 张磊：「不以动作为输入条件，就不叫世界模型」",
    relation: "context-only",
    sourceLevel: "媒体报道",
    summary: "该材料是雷峰网对 IDEA 张磊的访谈；李飞飞团队仅在背景中被提及，不代表李飞飞受访或演讲。",
    signal: "已核实：仅背景提及，非该人物受访或演讲",
    evidenceUrl: "https://www.leiphone.com/category/academic/wQny8Cer4EJz0RAU.html",
    evidenceNote: "原文开头明确深访 IDEA 张磊，问答回答者为张磊；李飞飞团队出现在 DINO 被使用或引用的背景描述中。",
    reviewedAt: "2026-09-10",
  },
  {
    id: "eastmoney-he-tingbo-research-update-report",
    personSlug: "person-918f5d53a8",
    sourceUrl: "https://finance.eastmoney.com/a/202609073866203674.html",
    expectedTitle: "华为更新韬定律论文 最新机构解读来了 后道测试设备环节直接受益？",
    relation: "reported-actor",
    sourceLevel: "媒体报道",
    summary: "财联社报道何庭波更新韬定律相关论文，并解读产业影响；当前链接为东方财富转载的新闻报道，非论文原文。",
    signal: "已核实：论文更新行为的新闻报道",
    evidenceUrl: "https://finance.eastmoney.com/a/202609073866203674.html",
    evidenceNote: "页面署名科创板日报宋子乔、来源财联社；首段明确报道何庭波更新论文。此证据支持报道中的人物行为，不独立证明论文作者名单或技术结论。",
    reviewedAt: "2026-09-10",
  },
];

function reviewUrlKey(value: string) {
  try {
    const url = new URL(value.trim());
    if (!/^https?:$/.test(url.protocol) || url.username || url.password) return "";
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (key.toLowerCase().startsWith("utm_")) url.searchParams.delete(key);
    }
    // Paths and query values can be case-sensitive. Do not lowercase them.
    return url.toString();
  } catch {
    return "";
  }
}

function reviewTitleKey(value: string) {
  return value.normalize("NFKC").trim().replace(/\s+/gu, " ");
}

export function findHomepagePersonMaterialReview(
  personSlug: string | undefined,
  sourceUrl: string,
  title: string,
): HomepagePersonMaterialReview | undefined {
  if (!personSlug) return undefined;
  const urlKey = reviewUrlKey(sourceUrl);
  if (!urlKey) return undefined;
  return homepagePersonMaterialReviews.find((review) =>
    review.personSlug === personSlug &&
    reviewUrlKey(review.sourceUrl) === urlKey &&
    reviewTitleKey(review.expectedTitle) === reviewTitleKey(title),
  );
}
