import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import { buildSourceTrackRelevanceProfiles } from "@/lib/source-track-relevance";

const directory = getChannelUpdateDirectory("technology");
const profiles = buildSourceTrackRelevanceProfiles(directory.items);
const rows = [...profiles.values()];

const severe = rows
  .filter((row) => row.status === "severe")
  .sort(
    (left, right) =>
      right.weakEvidenceCount - left.weakEvidenceCount ||
      right.pairCount - left.pairCount,
  );
const moderate = rows
  .filter((row) => row.status === "moderate")
  .sort(
    (left, right) =>
      right.weakEvidenceCount - left.weakEvidenceCount ||
      right.pairCount - left.pairCount,
  );
const provisional = rows
  .filter((row) => row.status === "provisional")
  .sort(
    (left, right) =>
      right.weakEvidenceCount - left.weakEvidenceCount ||
      right.pairCount - left.pairCount,
  );
const broadSources = [
  ...new Map(
    rows
      .filter((row) => row.broadSource)
      .map((row) => [
        row.source,
        {
          source: row.source,
          eventCount: row.sourceEventCount,
          trackCount: row.sourceTrackCount,
        },
      ]),
  ).values(),
].sort(
  (left, right) =>
    right.eventCount - left.eventCount || right.trackCount - left.trackCount,
);

function auditRow(row: (typeof rows)[number]) {
  return {
    source: row.source,
    track: row.track,
    status: row.status,
    count: row.pairCount,
    topicBacked: row.topicBackedCount,
    crawlerUsable: row.crawlerUsableCount,
    partialEvidence: row.partialEvidenceCount,
    weakEvidence: row.weakEvidenceCount,
    primaryEvidence: row.primaryEvidenceCount,
    companyEvidence: row.companyEvidenceCount,
    trackingTermEvidence: row.trackingTermEvidenceCount,
    directEvidence: row.directEvidenceCount,
    sourceEventCount: row.sourceEventCount,
    sourceTrackCount: row.sourceTrackCount,
    weakRate: row.weakRate,
    directEvidenceRate: row.directEvidenceRate,
    observedDayCount: row.observedDayCount,
    observationSpanDays: row.observationSpanDays,
    samples: row.samples,
  };
}

const unstablePenalties = rows.filter(
  (row) =>
    (row.status === "severe" &&
      (row.pairCount < 8 || row.observedDayCount < 3 || row.observationSpanDays < 7)) ||
    (row.status === "moderate" &&
      (row.pairCount < 6 || row.observedDayCount < 2 || row.observationSpanDays < 3)),
);

const audit = {
  eventCount: directory.items.length,
  sourceCount: new Set(rows.map((row) => row.source)).size,
  sourceTrackPairCount: rows.length,
  broadSourceCount: broadSources.length,
  severeStablePairCount: severe.length,
  moderateStablePairCount: moderate.length,
  provisionalPairCount: provisional.length,
  severeStableEventCount: severe.reduce((sum, row) => sum + row.pairCount, 0),
  moderateStableEventCount: moderate.reduce(
    (sum, row) => sum + row.pairCount,
    0,
  ),
  provisionalEventCount: provisional.reduce((sum, row) => sum + row.pairCount, 0),
  unstablePenaltyCount: unstablePenalties.length,
};

console.log(`SOURCE_TRACK_RELEVANCE_AUDIT=${JSON.stringify(audit)}`);
console.log(
  `SOURCE_TRACK_RELEVANCE_BROAD_SOURCES=${JSON.stringify(broadSources.slice(0, 30))}`,
);
console.log(
  `SOURCE_TRACK_RELEVANCE_SEVERE=${JSON.stringify(severe.slice(0, 30).map(auditRow))}`,
);
console.log(
  `SOURCE_TRACK_RELEVANCE_MODERATE=${JSON.stringify(moderate.slice(0, 30).map(auditRow))}`,
);
console.log(
  `SOURCE_TRACK_RELEVANCE_PROVISIONAL=${JSON.stringify(provisional.slice(0, 30).map(auditRow))}`,
);

if (severe.length) {
  console.warn(
    `SOURCE_TRACK_RELEVANCE_WARNING: ${severe.length} source-track pairs remain severe after >=3 observation days spanning >=7 days; only weak/partial events receive the extra penalty`,
  );
}
if (moderate.length) {
  console.warn(
    `SOURCE_TRACK_RELEVANCE_NOTICE: ${moderate.length} source-track pairs meet stable moderate criteria after cross-day observation`,
  );
}
if (provisional.length) {
  console.warn(
    `SOURCE_TRACK_RELEVANCE_NOTICE: ${provisional.length} noisy source-track pairs are still provisional and receive no automatic source-track penalty until temporal stability is established`,
  );
}

if (unstablePenalties.length) {
  console.error(
    `SOURCE_TRACK_RELEVANCE_AUDIT_ERROR: ${unstablePenalties.length} severe/moderate profiles violate temporal stability gates`,
  );
  process.exitCode = 1;
}
