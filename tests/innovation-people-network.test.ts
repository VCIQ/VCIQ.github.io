import assert from "node:assert/strict";
import test from "node:test";
import { buildPeopleNetwork, normalizeLinkedInProfile, peopleNetworkSeed, validatePeopleNetwork, peopleNetworkCoverage, reviewedAttributionGroups } from "../lib/innovation-people-network";

test("LinkedIn identity review does not create investment edges", () => {
  assert.deepEqual(validatePeopleNetwork(), []);
  const people = buildPeopleNetwork();
  assert.equal(people.length, 30);
  assert.equal(people.filter(p => p.linkedin?.status === "matched").length, 26);
  assert.equal(people.find(p => p.id === "marc-andreessen")!.linkedin, null);
  const founder = people.find(p => p.id === "brett-adcock")!;
  assert.equal(founder.relations.length, 0);
  assert.equal(founder.institutionId, null);
  assert.ok(people.flatMap(p => p.relations).every(r => ["viewpoint", "portfolio-partner"].includes(r.type)));
});
test("project paths preserve reviewed source and attribution boundary", () => {
  const people = buildPeopleNetwork();
  const lin = people.find(p => p.id === "alfred-lin")!;
  const pi = lin.relations.find(r => r.projectId === "physical-intelligence")!;
  assert.equal(pi.type, "portfolio-partner");
  assert.match(pi.sourceUrl, /sequoiacap.com\/companies\/physical-intelligence/);
  assert.match(pi.caveat, /不证明/);
  const zhou = people.find(p => p.id === "zhou-zhifeng")!;
  assert.equal(zhou.relations[0].date, "2026-09-01");
  assert.match(zhou.relations[0].caveat, /未核验/);
  assert.equal(peopleNetworkCoverage().pendingAttributions.length, 0);
});
test("profile URLs reject unsafe links and normalize regional hosts", () => {
  assert.equal(normalizeLinkedInProfile("https://cn.linkedin.com/in/example/?trk=test#bio"), "https://www.linkedin.com/in/example");
  for (const url of ["javascript:alert(1)", "https://linkedin.com.evil.test/in/name", "https://evil.test/in/name", "https://www.linkedin.com/posts/name", "https://user:pass@linkedin.com/in/name", "https://linkedin.com:8443/in/name"]) assert.equal(normalizeLinkedInProfile(url), null);
});
test("duplicate identities and unsupported verification claims fail closed", () => {
  const people = structuredClone(peopleNetworkSeed);
  people[1].linkedin!.url = people[0].linkedin!.url;
  assert.ok(validatePeopleNetwork(people).some(e => /duplicate LinkedIn/.test(e)));
  const wrong = structuredClone(peopleNetworkSeed);
  wrong[0].institutionId = "hongshan";
  assert.ok(validatePeopleNetwork(wrong).some(e => /unmapped evidence/.test(e)));
  const unsafe = structuredClone(peopleNetworkSeed);
  unsafe[0].officialSource.url = "javascript:alert(1)";
  assert.ok(validatePeopleNetwork(unsafe).some(e => /identity evidence/.test(e)));
});

test("coauthors map only through an explicit, source-scoped review", () => {
  const reviewed = buildPeopleNetwork();
  const unreviewed = buildPeopleNetwork(peopleNetworkSeed, []);
  for (const id of ["ben-horowitz", "martin-casado", "raghu-raghuram", "david-ulevitch", "david-george"]) {
    assert.ok(reviewed.find(p => p.id === id)!.relations.some(r => r.sourceUrl === reviewedAttributionGroups[0].sourceUrl));
    assert.ok(!unreviewed.find(p => p.id === id)!.relations.some(r => r.sourceUrl === reviewedAttributionGroups[0].sourceUrl));
  }
  const wrongSource = structuredClone(reviewedAttributionGroups);
  wrongSource[0].sourceUrl = "https://a16z.com/another-article/";
  assert.ok(validatePeopleNetwork(peopleNetworkSeed, wrongSource).some(e => /attribution group/.test(e)));
  const wrongMember = structuredClone(reviewedAttributionGroups);
  wrongMember[0].personIds.push("josh-wolfe");
  assert.ok(validatePeopleNetwork(peopleNetworkSeed, wrongMember).some(e => /attribution group/.test(e)));
});
test("a matched profile requires public LinkedIn identity evidence", () => {
  const rows = structuredClone(peopleNetworkSeed);
  rows[0].linkedin!.profileEvidenceUrl = "https://example.com/profile";
  assert.ok(validatePeopleNetwork(rows).some(e => /LinkedIn identity evidence/.test(e)));
  rows[0].linkedin!.profileEvidenceUrl = "javascript:alert(1)";
  assert.ok(validatePeopleNetwork(rows).some(e => /LinkedIn identity evidence/.test(e)));
});
