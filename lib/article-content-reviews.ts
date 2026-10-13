import manifest from "@/config/article_content_reviews.json";
import type { HomepagePublicationCandidate } from "./homepage-publication-quality";

/** Narrow, guarded projection. A corrected upstream summary wins on the next sync. */
export function applyArticleContentReview<T extends HomepagePublicationCandidate>(item: T): T {
  const review = manifest.reviews.find(review => review.url === item.source.url &&
    review.titleIncludes.every(fragment => item.title.includes(fragment)) &&
    review.badSummaryIncludes.every(fragment => item.summary.includes(fragment)));
  return review ? {...item, summary: review.summary, type: review.type, sector: review.sector, importance: review.importance} : item;
}
