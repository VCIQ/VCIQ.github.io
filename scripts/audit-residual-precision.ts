import { buildSectorQualityReviewQueue } from "@/lib/sector-quality-audit";
import { technologyTermMatchesText } from "@/lib/technology-term-matching";
import { technologyTopicDefinitions } from "@/lib/technology-topics";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";

function normalize(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

const directory = getChannelUpdateDirectory("technology");
const events = directory.items.filter((item) => Boolean(item.track));
const topicBySlug = new Map(technologyTopicDefinitions.map((topic) => [topic.slug, topic]));

const mismatches = events.flatMap((item) =>
  (item.topicSlugs ?? []).flatMap((slug) => {
    const topic = topicBySlug.get(slug);
    if (!topic || topic.trackNames.some((name) => normalize(name) === normalize(item.track ?? ""))) {
      return [];
    }
    const titleTerms = topic.matchTerms.filter((term) => technologyTermMatchesText(item.title, term));
    const summaryTerms = topic.matchTerms.filter((term) => technologyTermMatchesText(item.summary, term));
    return [{
      id: item.id,
      title: item.title,
      track: item.track ?? "",
      topic: topic.name,
      topicSlug: topic.slug,
      titleTerms,
      summaryTerms,
      source: item.source,
    }];
  }),
);

const termStats = new Map<string, { topic: string; term: string; count: number; titleCount: number; summaryCount: number }>();
for (const row of mismatches) {
  for (const term of new Set([...row.titleTerms, ...row.summaryTerms])) {
    const key = `${row.topic}\u0000${term}`;
    const stat = termStats.get(key) ?? { topic: row.topic, term, count: 0, titleCount: 0, summaryCount: 0 };
    stat.count += 1;
    if (row.titleTerms.includes(term)) stat.titleCount += 1;
    if (row.summaryTerms.includes(term)) stat.summaryCount += 1;
    termStats.set(key, stat);
  }
}

const reviewQueue = buildSectorQualityReviewQueue(events);
const highConfidence = reviewQueue.filter((item) => item.category === "high-confidence-misclassification");
const needsReview = reviewQueue.filter((item) => item.category === "needs-review");
const crossSector = reviewQueue.filter((item) => item.category === "reasonable-cross-sector");

const separatorSensitiveTerms = [...termStats.values()]
  .filter((row) => /[.\-_/\s]/u.test(row.term) && /[a-z0-9]/iu.test(row.term))
  .sort((left, right) => right.count - left.count || left.term.localeCompare(right.term));

const audit = {
  eventCount: events.length,
  topicMismatchAssignmentCount: mismatches.length,
  topicMismatchEventCount: new Set(mismatches.map((row) => row.id)).size,
  highConfidenceSectorCount: highConfidence.length,
  needsReviewSectorCount: needsReview.length,
  reasonableCrossSectorCount: crossSector.length,
  separatorSensitiveMismatchCount: separatorSensitiveTerms.reduce((sum, row) => sum + row.count, 0),
};

console.log(`RESIDUAL_PRECISION_AUDIT=${JSON.stringify(audit)}`);
console.log(`RESIDUAL_PRECISION_TERM_STATS=${JSON.stringify([...termStats.values()].sort((left, right) => right.count - left.count || left.topic.localeCompare(right.topic, "zh-CN") || left.term.localeCompare(right.term)).slice(0, 60))}`);
console.log(`RESIDUAL_PRECISION_MISMATCH_SAMPLES=${JSON.stringify(mismatches.slice(0, 60))}`);
console.log(`RESIDUAL_PRECISION_HIGH_CONFIDENCE=${JSON.stringify(highConfidence.slice(0, 20))}`);
console.log(`RESIDUAL_PRECISION_NEEDS_REVIEW=${JSON.stringify(needsReview.slice(0, 30))}`);

if (separatorSensitiveTerms.length) {
  console.warn(`RESIDUAL_PRECISION_WARNING: ${separatorSensitiveTerms.length} separator-sensitive terms contribute to cross-track topic assignments; inspect for normalization false positives`);
}
