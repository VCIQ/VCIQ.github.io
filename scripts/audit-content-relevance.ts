import rawArticles from "@/public/data/articles.json";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";

 type RawArticle = {
  id: string;
  title: string;
  sector: string;
  qualityScore?: number;
  qualityStatus?: string;
  qualitySignals?: string[];
  source?: { name?: string; platform?: string };
};

type RawPayload = { articles: RawArticle[] };

const rawById = new Map(
  (rawArticles as RawPayload).articles.map((article) => [article.id, article]),
);
const events = getChannelUpdateDirectory("technology").items.filter((item) => Boolean(item.track));

const rows = events.flatMap((item) => {
  const raw = rawById.get(item.id);
  if (!raw) return [];
  const topics = item.topicSlugs ?? [];
  const signals = raw.qualitySignals ?? [];
  return [{
    id: item.id,
    title: item.title,
    track: item.track ?? "",
    source: raw.source?.platform || raw.source?.name || item.source,
    topicCount: topics.length,
    topics: item.topicNames ?? [],
    qualityScore: raw.qualityScore ?? null,
    qualityStatus: raw.qualityStatus ?? "未标注",
    qualitySignals: signals,
    noValidTrackingTerm: signals.some((signal) => signal.includes("未命中有效追踪词")),
  }];
});

const lowConfidence = rows.filter((row) => row.qualityStatus === "低可信");
const lowConfidenceUntagged = lowConfidence.filter((row) => row.topicCount === 0);
const lowConfidenceTagged = lowConfidence.filter((row) => row.topicCount > 0);
const noTrackingTermUntagged = rows.filter(
  (row) => row.topicCount === 0 && row.noValidTrackingTerm,
);
const usableUntagged = rows.filter(
  (row) => row.topicCount === 0 && row.qualityStatus === "可用",
);

const sourceCounts = new Map<string, number>();
for (const row of noTrackingTermUntagged) {
  sourceCounts.set(row.source, (sourceCounts.get(row.source) ?? 0) + 1);
}

const audit = {
  eventCount: rows.length,
  taggedEventCount: rows.filter((row) => row.topicCount > 0).length,
  untaggedEventCount: rows.filter((row) => row.topicCount === 0).length,
  lowConfidenceCount: lowConfidence.length,
  lowConfidenceTaggedCount: lowConfidenceTagged.length,
  lowConfidenceUntaggedCount: lowConfidenceUntagged.length,
  noTrackingTermUntaggedCount: noTrackingTermUntagged.length,
  usableUntaggedCount: usableUntagged.length,
};

console.log(`CONTENT_RELEVANCE_AUDIT=${JSON.stringify(audit)}`);
console.log(`CONTENT_RELEVANCE_LOW_CONFIDENCE_TAGGED=${JSON.stringify(lowConfidenceTagged.slice(0, 20))}`);
console.log(`CONTENT_RELEVANCE_NO_TRACKING_UNTAGGED_SAMPLES=${JSON.stringify(noTrackingTermUntagged.slice(0, 40))}`);
console.log(`CONTENT_RELEVANCE_NO_TRACKING_UNTAGGED_SOURCES=${JSON.stringify([...sourceCounts.entries()].sort((left, right) => right[1] - left[1]).slice(0, 20))}`);
console.log(`CONTENT_RELEVANCE_USABLE_UNTAGGED_SAMPLES=${JSON.stringify(usableUntagged.slice(0, 30))}`);

if (noTrackingTermUntagged.length) {
  console.warn(
    `CONTENT_RELEVANCE_WARNING: ${noTrackingTermUntagged.length} technology-channel events have no priority topic and explicitly failed the crawler's valid-tracking-term check; review before using them at full sector Momentum weight`,
  );
}
