import assert from "node:assert/strict";
import test from "node:test";
import mapping from "../config/investor_registry_migration_map.json";
import mergeReport from "../config/investor_identity_merge_report.json";
import roster from "../config/innovation_global_investors.json";
import evidence from "../config/innovation_investor_evidence.json";
import identities from "../config/innovation_investor_project_identities.json";
import {
  globalInnovationInvestors, investorEvidenceRecords, validateInvestorResearch,
} from "../lib/innovation-investor-research";
import { innovationInvestorRegistryV2 } from "../lib/innovation-investor-registry-v2";
import { buildInvestorHomepagePublication } from "../lib/homepage-investor-publication";
import { buildHomepageFocusSelection } from "../lib/homepage-focus";
import type { HomepagePreferenceState } from "../lib/homepage-preferences";

test("all thirty original production IDs remain fixed, not replaced by draft spelling", () => {
  assert.equal(mapping.productionMutationAllowed, false);
  assert.equal(mapping.legacyGlobalMappings.length, roster.institutions.length);
  const byOld = new Map(mapping.legacyGlobalMappings.map((row) => [row.legacyId, row]));
  const v2Ids = new Set(innovationInvestorRegistryV2.map((row) => row.id));
  for (const original of roster.institutions) {
    const row = byOld.get(original.id);
    assert.deepEqual(row, {legacyId: original.id, canonicalId: original.id, action: "keep"});
    assert.ok(v2Ids.has(original.id));
  }
  const drafted = new Map(mapping.draftIdAliases.map((item) => [item.draftId, item]));
  assert.equal(drafted.get("hsg")?.canonicalId, "hongshan");
  assert.equal(drafted.get("source_code")?.canonicalId, "source-code");
  assert.equal(drafted.get("idg_china")?.canonicalId, "idg-capital");
  assert.ok(mapping.draftIdAliases.every((item) => item.migrationMode === "review-only"));
  assert.deepEqual(mapping.chinaCatalogOnboarding.map((row) => row.canonicalId).sort(),
    ["five-years", "gaorong", "matrix-china", "northern-light", "shunwei"]);
});

test("merge audit accounts for overlap and forbids moving Sequoia investment attribution to HongShan", () => {
  assert.equal(mergeReport.originalGlobalCount, roster.institutions.length);
  assert.equal(mergeReport.originalGlobalChinaCount, 8);
  assert.equal(mergeReport.proposedOverlap, 7);
  assert.equal(mergeReport.additionalCanonicalEntities, 5);
  assert.equal(mergeReport.unifiedCanonicalCount, innovationInvestorRegistryV2.length);
  const relation = mergeReport.decisions.find((row) => row.canonicalId === "sequoia");
  assert.equal(relation?.decision, "keep-separate-historical-lineage");
  assert.equal(relation?.evidenceMove, false);
  assert.ok(mergeReport.decisions.every((row) => row.evidenceMove === false));
});

test("all original evidence and company mappings resolve without rewriting institution IDs or provenance", () => {
  assert.deepEqual(validateInvestorResearch(), []);
  const known = new Set(innovationInvestorRegistryV2.map((row) => row.id));
  assert.ok(investorEvidenceRecords.every((record) => known.has(record.institutionId)));
  const rows = evidence.records.filter((row) => ["index","sequoia"].includes(row.institutionId));
  assert.ok(rows.some((row) => row.institutionId === "index" && row.project === "Oratomic"));
  assert.ok(rows.some((row) => row.institutionId === "sequoia" && row.project === "TypeSafe AI"));
  assert.ok(rows.some((row) => row.institutionId === "sequoia" && row.project === "Catalyst"));
  assert.ok(rows.every((row) => row.source.url.startsWith("https://")));
  assert.ok(new Set(identities.projects.map((row) => row.id)).size === identities.projects.length);
});

test("parallel registry cannot affect 科创 publication or personalized 重点 admission", () => {
  const moment = Date.parse("2026-10-11T12:00:00Z");
  const publication = buildInvestorHomepagePublication(investorEvidenceRecords, globalInnovationInvestors, moment);
  assert.ok(publication.events.some((row) => row.company === "Oratomic"));
  assert.ok(publication.events.some((row) => row.company === "Catalyst"));
  assert.equal(new Set(publication.events.map((row) => row.source.url)).size, publication.events.length);
  assert.ok(publication.events.length <= 12);
  const empty: HomepagePreferenceState = {
    schemaVersion: 1, followedSectors: [], dismissedEventIds: [], sectorDislikes: {},
  };
  assert.equal(buildHomepageFocusSelection(publication.events, empty, [], [], moment).items.length, 0);
  assert.equal(globalInnovationInvestors.length, roster.institutions.length);
});
