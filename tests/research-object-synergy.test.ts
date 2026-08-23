import assert from "node:assert/strict";
import test from "node:test";

import { companies } from "../lib/catalog-data";
import { researchPeople } from "../lib/people-data";
import {
  getCompanyResearchRelations,
  getPersonResearchRelations,
  getTrackResearchRelations,
  researchSynergySummary,
} from "../lib/research-relations";
import { trackedSectors } from "../lib/tracked-sectors";

function uniqueHrefs(values: { href: string }[]) {
  return new Set(values.map((item) => item.href)).size === values.length;
}

test("research synergy summary stays aligned with published object catalogs", () => {
  assert.equal(researchSynergySummary.companyCount, companies.length);
  assert.equal(researchSynergySummary.peopleCount, researchPeople.length);
  assert.equal(researchSynergySummary.trackCount, trackedSectors.length);
  assert.ok(researchSynergySummary.topicCount > 0);
  assert.ok(researchSynergySummary.companyPersonEdges >= 0);
});

test("company, person and track relations expose unique internal research links", () => {
  for (const company of companies) {
    const relations = getCompanyResearchRelations(company.slug);
    assert.ok(uniqueHrefs(relations.tracks));
    assert.ok(uniqueHrefs(relations.topics));
    assert.ok(uniqueHrefs(relations.people));
    assert.ok(relations.tracks.every((item) => item.href.startsWith("/technologies/tracks/")));
    assert.ok(relations.people.every((item) => item.href.startsWith("/people/")));
  }

  for (const person of researchPeople) {
    const relations = getPersonResearchRelations(person.slug);
    assert.ok(uniqueHrefs(relations.tracks));
    assert.ok(uniqueHrefs(relations.topics));
    assert.ok(uniqueHrefs(relations.companies));
    assert.ok(relations.companies.every((item) => item.href.startsWith("/companies/")));
  }

  for (const track of trackedSectors) {
    const relations = getTrackResearchRelations(track.slug);
    assert.ok(uniqueHrefs(relations.topics));
    assert.ok(uniqueHrefs(relations.people));
    assert.ok(uniqueHrefs(relations.companies));
    assert.ok(relations.companies.every((item) => item.href.startsWith("/companies/")));
  }
});

test("IonQ evidence does not turn a person's surname into the Kimi model brand", () => {
  const topics = getCompanyResearchRelations("ionq").topics.map((item) => item.name);
  assert.ok(topics.includes("量子计算"));
  assert.equal(topics.includes("大模型"), false);
});
