import assert from "node:assert/strict";
import test from "node:test";

import { companies } from "../lib/catalog-data";
import { buildCompanyResearchSnapshot } from "../lib/company-research";

test("company directory summaries prefer curated research context over scraped backgrounds", () => {
  const ionq = companies.find((company) => company.slug === "ionq");
  assert.ok(ionq, "IonQ must remain in the company registry");

  const snapshot = buildCompanyResearchSnapshot(ionq);
  const stablePrefix = ionq.summary.slice(0, Math.min(24, ionq.summary.length));

  assert.ok(
    snapshot.whyImportant.startsWith(stablePrefix),
    `expected curated company summary prefix, received: ${snapshot.whyImportant}`,
  );
  assert.doesNotMatch(snapshot.whyImportant, /^About\s+IonQ\b/iu);
});
