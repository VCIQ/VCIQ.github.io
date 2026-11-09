import assert from "node:assert/strict";
import test from "node:test";
import { getProfessionalProfile, professionalProfileCoverage, professionalProfiles, validateProfessionalProfiles } from "../lib/professional-profiles";

test("the reviewed directory has explicit outcomes and sourced identity bindings", () => {
  assert.deepEqual(validateProfessionalProfiles(), []);
  assert.equal(professionalProfiles.length, 186);
  const coverage = professionalProfileCoverage(professionalProfiles.map(p => p.personSlug));
  assert.deepEqual(coverage, {matched:25, unresolved:84, no_result:56, needs_identity:21, search_error:0, not_reviewed:0});
  assert.equal(getProfessionalProfile("shunyu-yao")!.linkedinUrl, "https://www.linkedin.com/in/shunyu-yao-099a41115");
  assert.equal(getProfessionalProfile("gavin-baker")!.linkedinUrl, "https://www.linkedin.com/in/gavinbaker-portfoliomanager");
  assert.equal(getProfessionalProfile("oracle-cloud-infrastructure")!.linkedinUrl, null);
});
test("future directory additions remain unreviewed and coverage counts only displayed people", () => {
  assert.equal(getProfessionalProfile("future-person"), undefined);
  assert.deepEqual(professionalProfileCoverage(["shunyu-yao", "shunyu-yao", "future-person"]), {
    matched:1, unresolved:0, no_result:0, needs_identity:0, search_error:0, not_reviewed:1,
  });
});
test("candidate results cannot silently become a public identity binding", () => {
  const row = structuredClone(professionalProfiles.find(p => p.status === "unresolved")!);
  row.linkedinUrl = "https://www.linkedin.com/in/unreviewed";
  assert.ok(validateProfessionalProfiles([row]).some(e => /unreviewed binding/.test(e)));
  row.status = "matched";
  assert.ok(validateProfessionalProfiles([row]).some(e => /unsupported identity/.test(e)));
});
test("identity review rejects unsafe, duplicate, and one-source bindings", () => {
  const row = structuredClone(professionalProfiles.find(p => p.status === "matched")!);
  row.sources[0].url = "javascript:alert(1)";
  assert.ok(validateProfessionalProfiles([row]).some(e => /unsafe source/.test(e)));
  row.sources = [row.sources[1]];
  assert.ok(validateProfessionalProfiles([row]).some(e => /unsupported identity/.test(e)));
  const original = professionalProfiles.find(p => p.status === "matched")!;
  assert.ok(validateProfessionalProfiles([original, {...original, personSlug:"duplicate-person"}]).some(e => /unsupported identity/.test(e)));
  assert.ok(validateProfessionalProfiles([original, original]).some(e => /duplicate slug/.test(e)));
});
