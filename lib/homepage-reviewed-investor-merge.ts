import { homepageMaterialUrl } from "@/lib/homepage-event-identity";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export const REVIEWED_INVESTOR_SOURCE_ID = "reviewed-investor-official";

/**
 * Keep the canonical published article authoritative if it already has the
 * official original URL. This also preserves formal investor source projections
 * after the browser replaces its initial feed with /data/articles.json.
 */
export function mergeReviewedInvestorHomepageEvents(
  canonical: readonly LiveIntelligenceEvent[],
  reviewed: readonly LiveIntelligenceEvent[],
): LiveIntelligenceEvent[] {
  const seen = new Set(canonical.map((row) => homepageMaterialUrl(row.source.url)).filter(Boolean));
  const result = [...canonical];
  for (const row of reviewed) {
    if (row.sourceId !== REVIEWED_INVESTOR_SOURCE_ID) continue;
    const url = homepageMaterialUrl(row.source.url);
    if (!url || seen.has(url)) continue;
    seen.add(url);
    result.push(row);
  }
  return result;
}
