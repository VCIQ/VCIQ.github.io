import rawReviews from "@/config/article_metadata_reviews.json";
import { homepageMaterialUrl } from "./homepage-event-identity";
import type { ArticlePayload, LiveIntelligenceEvent } from "@/lib/use-articles";

type ReviewedField = "sector" | "type";
type MetadataReview = {
  id: string;
  sourceId: string;
  sourceUrl: string;
  expectedTitle: string;
  fields: Partial<Record<ReviewedField, { from: string; to: string }>>;
  removeTrackSlugs: string[];
  addTrackSlugs: string[];
};

const reviews = rawReviews.reviews as MetadataReview[];
const titleKey = (title: string) => title.normalize("NFKC").trim().replace(/\s+/gu, " ");

/** Same bounded manifest as the publication gate. Does not change importance or credibility. */
export function applyArticleMetadataReview<T extends LiveIntelligenceEvent>(article: T): T {
  const review = reviews.find((candidate) =>
    candidate.sourceId === article.sourceId &&
    titleKey(candidate.expectedTitle) === titleKey(article.title) &&
    homepageMaterialUrl(candidate.sourceUrl) === homepageMaterialUrl(article.source.url),
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
  return Object.keys(updates).length ? { ...article, ...updates } as T : article;
}

export function applyArticleMetadataReviews(payload: ArticlePayload): ArticlePayload {
  const articles = payload.articles.map(applyArticleMetadataReview);
  return articles.some((item, index) => item !== payload.articles[index])
    ? { ...payload, articles }
    : payload;
}
