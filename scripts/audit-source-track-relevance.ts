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
    samples: row.samples,
  };
}

const audit = {
  eventCount: directory.items.length,
  sourceCount: new Set(rows.map((row) => row.source)).size,
  sourceTrackPairCount: rows.length,
  broadSourceCount: broadSources.length,
  severeCandidatePairCount: severe.length,
  moderateCandidatePairCount: moderate.length,
  severeCandidateEventCount: severe.reduce((sum, row) => sum + row.pairCount, 0),
  moderateCandidateEventCount: moderate.reduce(
    (sum, row) => sum + row.pairCount,
    0,
  ),
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

if (severe.length) {
  console.warn(
    `SOURCE_TRACK_RELEVANCE_WARNING: ${severe.length} broad-source × track pairs have >=70% weak evidence and <30% event-level direct evidence; only weak/partial events should receive extra source-track downweighting`,
  );
}
if (moderate.length) {
  console.warn(
    `SOURCE_TRACK_RELEVANCE_NOTICE: ${moderate.length} additional source-track pairs have mixed topical precision; strong evidence should bypass the source-track gate`,
  );
}
