import rawReviews from "@/config/article_metadata_reviews.json";
import { homepageMaterialUrl } from "./homepage-event-identity";
import type { ArticlePayload } from "@/lib/use-articles";

type ReviewedField = "sector" | "type" | "company";
type ReviewableArticle = {
  id: string;
  sourceId?: string;
  title: string;
  summary: string;
  company: string;
  sector?: string;
  type?: string;
  source: { url: string };
};
type MetadataReview = {
  id: string;
  articleId: string;
  sourceId: string;
  sourceUrl: string;
  expectedTitle: string;
  expectedSummaryContains?: string;
  removeCompanySlugs?: string[];
  removeMentionedCompanies?: string[];
  fields: Partial<Record<ReviewedField, { from: string; to: string }>>;
  removeTrackSlugs: string[];
  addTrackSlugs: string[];
};

const reviews = rawReviews.reviews as MetadataReview[];
const titleKey = (title: string) => title.normalize("NFKC").trim().replace(/\s+/gu, " ");

/** Same bounded manifest as the publication gate. Does not change importance or credibility. */
export function applyArticleMetadataReview<T extends ReviewableArticle>(article: T): T {
  const review = reviews.find((candidate) =>
    candidate.articleId === article.id &&
    candidate.sourceId === article.sourceId &&
    titleKey(candidate.expectedTitle) === titleKey(article.title) &&
    homepageMaterialUrl(candidate.sourceUrl) === homepageMaterialUrl(article.source.url) &&
    (!candidate.expectedSummaryContains || article.summary.includes(candidate.expectedSummaryContains)),
  );
  if (!review) return article;
  const fields = Object.entries(review.fields) as [ReviewedField, { from: string; to: string }][];
  // A later, different classification is not silently overwritten by an old review.
  if (fields.some(([field, change]) => article[field] !== change.from && article[field] !== change.to)) {
    return article;
  }
  const updates: Record<string, unknown> = {};
  for (const [field, change] of fields) {
    if (article[field] !== change.to) updates[field] = change.to;
  }
  const tracks = (article as T & { trackSlugs?: string[] }).trackSlugs;
  if (Array.isArray(tracks) && (review.removeTrackSlugs.length || review.addTrackSlugs.length)) {
    const next = [...new Set([
      ...tracks.filter((slug) => !review.removeTrackSlugs.includes(slug)),
      ...review.addTrackSlugs,
    ])];
    if (JSON.stringify(next) !== JSON.stringify(tracks)) updates.trackSlugs = next;
  }
  const result = { ...article, ...updates } as Record<string, unknown>;
  if (review.fields.company) {
    const removed = new Set(review.removeCompanySlugs ?? []);
    for (const key of ["companySlugs", "companyCandidateSlugs"]) {
      if (Array.isArray(result[key])) {
        const remaining = (result[key] as string[]).filter((slug) => !removed.has(slug));
        if (remaining.length) result[key] = remaining;
        else delete result[key];
      }
    }
    if (removed.has(String(result.companySlug ?? ""))) delete result.companySlug;
    const match = result.companyMatch as { slug?: string } | undefined;
    if (match && removed.has(match.slug ?? "")) delete result.companyMatch;
    if (Array.isArray(result.companyMatches)) {
      const remaining = (result.companyMatches as { slug?: string }[])
        .filter((row) => !removed.has(row?.slug ?? ""));
      if (remaining.length) result.companyMatches = remaining;
      else delete result.companyMatches;
    }
    if (Array.isArray(result.mentionedCompanies)) {
      const removedNames = new Set(review.removeMentionedCompanies ?? []);
      result.mentionedCompanies = [...new Set([
        ...(result.mentionedCompanies as string[]).filter((name) => !removedNames.has(name)),
        review.fields.company.to,
      ])];
    }
  }
  return JSON.stringify(result) === JSON.stringify(article) ? article : result as T;
}

export function applyArticleMetadataReviews(payload: ArticlePayload): ArticlePayload {
  const articles = payload.articles.map(applyArticleMetadataReview);
  return articles.some((item, index) => item !== payload.articles[index])
    ? { ...payload, articles }
    : payload;
}
