import process from "node:process";

import { findCompoundTrackingEntities } from "../lib/tracking-entity-integrity";
import { userTrackingConfig } from "../lib/user-tracking";

const issues = findCompoundTrackingEntities(userTrackingConfig);

if (issues.length) {
  for (const issue of issues) {
    const label = issue.entityType === "person" ? "人物" : "公司";
    console.error(
      `TRACKING_ENTITY_INTEGRITY_ERROR: ${issue.trackName} (${issue.trackSlug}) / ${label} “${issue.value}” → ${issue.parts.join("、")}。请拆分为独立实体。`,
    );
  }
  console.error(
    `TRACKING_ENTITY_INTEGRITY_ERROR: detected ${issues.length} compound person/company occurrence(s); refusing clean-state validation.`,
  );
  process.exit(1);
}

console.log(
  `Tracking entity integrity valid: ${userTrackingConfig.tracks.length} tracks, 0 compound person/company occurrences.`,
);
