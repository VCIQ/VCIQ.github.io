import assert from "node:assert/strict";
import test from "node:test";
import priorRoster from "../config/innovation_global_investors.json";
import v2 from "../config/innovation_investor_registry_v2.json";
import {
  innovationInvestorRegistryV2, investorRegistryV2Errors,
  resolveInvestorRegistryV2,
} from "../lib/innovation-investor-registry-v2";

test("registry v2 has exactly one canonical entry per existing or newly added entity", () => {
  assert.equal(v2.schemaVersion, 2);
  assert.equal(v2.status, "draft-parallel-migration");
  assert.deepEqual(investorRegistryV2Errors(), []);
  const byId = new Map(innovationInvestorRegistryV2.map((row) => [row.id, row]));
  assert.equal(byId.size, v2.institutionCount);
  const oldIds = new Set(priorRoster.institutions.map((row) => row.id));
  assert.equal(oldIds.size, 30);
  for (const legacy of priorRoster.institutions) {
    const item = byId.get(legacy.id);
    assert.ok(item, `missing legacy ID ${legacy.id}`);
    assert.ok(item.cohorts.includes("global-core"));
    assert.equal(item.officialSources.homepage, legacy.officialUrl);
    assert.equal(item.officialSources.discovery,
      (legacy as {discoveryUrl?: string}).discoveryUrl ?? null);
  }
  const newIds = [...byId.keys()].filter((id) => !oldIds.has(id));
  assert.deepEqual(newIds.sort(), ["five-years", "gaorong", "matrix-china", "northern-light", "shunwei"]);
  assert.equal(v2.institutionCount, priorRoster.institutions.length + newIds.length);
  assert.equal(innovationInvestorRegistryV2.filter((item) => item.cohorts.includes("china-focus")).length, 13);
});

test("exact bilingual aliases do not merge independent or historically related firms", () => {
  assert.equal(resolveInvestorRegistryV2("Sequoia Capital"), "sequoia");
  assert.equal(resolveInvestorRegistryV2("HSG"), "hongshan");
  assert.equal(resolveInvestorRegistryV2("HongShan"), "hongshan");
  assert.equal(resolveInvestorRegistryV2("红杉中国"), "hongshan");
  assert.equal(resolveInvestorRegistryV2("Sequoia China"), "hongshan");
  assert.equal(resolveInvestorRegistryV2("红杉资本"), null, "ambiguous name must not silently merge identities");
  assert.equal(resolveInvestorRegistryV2("经纬中国"), "matrix-china");
  assert.equal(resolveInvestorRegistryV2("高榕资本"), "gaorong");
  assert.equal(resolveInvestorRegistryV2("五源资本"), "five-years");
  assert.equal(resolveInvestorRegistryV2("源码资本"), "source-code");
  assert.equal(resolveInvestorRegistryV2("Matrix Partners China"), "matrix-china");
  assert.equal(resolveInvestorRegistryV2("Unknown VC"), null);
  const sequoia = innovationInvestorRegistryV2.find((item) => item.id === "sequoia")!;
  const hongshan = innovationInvestorRegistryV2.find((item) => item.id === "hongshan")!;
  assert.deepEqual(sequoia.relationships.map((r) => r.targetId), ["hongshan"]);
  assert.deepEqual(hongshan.relationships.map((r) => r.targetId), ["sequoia"]);
});

test("partial registry rejects collisions, broken lineage, and invented source URLs", () => {
  const sourceRows = innovationInvestorRegistryV2;
  const duplicate = [...sourceRows, {...sourceRows[0], id: "duplicate-sample", aliases: ["Index Ventures"]}];
  assert.ok(investorRegistryV2Errors(duplicate).some((error) => error.includes("alias collision")));
  const broken = sourceRows.map((row) => row.id === "sequoia"
    ? {...row, relationships: [{type: "historical-lineage" as const, targetId: "missing", note: "wrong"}]}
    : row);
  assert.ok(investorRegistryV2Errors(broken).some((error) => error.includes("invalid investor relationship")));
  const fake = sourceRows.map((row) => row.id === "five-years"
    ? {...row, officialSources: {...row.officialSources, homepage: "https://guessed.example.com/"}}
    : row);
  assert.ok(investorRegistryV2Errors(fake).some((error) => error.includes("pending official source")));
});
