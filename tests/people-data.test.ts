import assert from "node:assert/strict";
import test from "node:test";
import { excludedPersonAccounts, researchPeople } from "../lib/people-data";
import { parsePersonIdentityLabel } from "../lib/person-name-normalization";

test("all real tracked people appear in the people research catalog", () => {
  const names = new Set(researchPeople.map((person) => person.name));
  for (const expected of [
    "Sam Altman",
    "Demis Hassabis",
    "何恺明",
    "姚顺雨",
    "埃隆·马斯克",
    "李飞飞",
    "梁文峰",
    "唐杰",
    "汪滔",
    "李泽湘",
    "王兴兴",
    "杨钊",
    "Bob Mumgaard",
    "David Kirtley",
    "Michl Binderbauer",
  ]) {
    assert.ok(names.has(expected), `${expected} should have a person page`);
  }
});

test("organization accounts are excluded from person pages", () => {
  const names = new Set(researchPeople.map((person) => person.name));
  assert.equal(names.has("OpenAI"), false);
  assert.equal(names.has("Anthropic"), false);
  assert.ok(excludedPersonAccounts.some((value) => value.includes("OpenAI")));
});

test("generated people expose the unified research schema", () => {
  const person = researchPeople.find((item) => item.slug === "elon-musk");
  assert.ok(person);
  assert.ok(person.tracked);
  assert.ok(person.sectors.includes("AI / AGI"));
  assert.ok(person.organizations.includes("SpaceX"));
  assert.ok(person.products.includes("Starship"));
  assert.ok(person.materials.some((material) => material.url.startsWith("https://")));
});

test("tracking identity labels tolerate bilingual punctuation and handles", () => {
  assert.deepEqual(parsePersonIdentityLabel("黄仁勋(Jensen Huang"), {
    name: "黄仁勋",
    englishName: "Jensen Huang",
    handle: "",
  });
  assert.deepEqual(parsePersonIdentityLabel("克莱门特·德朗格（Clément Delangue）"), {
    name: "克莱门特·德朗格",
    englishName: "Clément Delangue",
    handle: "",
  });
  assert.deepEqual(parsePersonIdentityLabel("埃隆·马斯克 @elonmusk"), {
    name: "埃隆·马斯克",
    englishName: "",
    handle: "elonmusk",
  });
});

test("generated bilingual person names are normalized before publication", () => {
  const jensen = researchPeople.find((item) => item.slug === "jensen-huang");
  assert.ok(jensen);
  assert.equal(jensen.name, "黄仁勋");
  assert.equal(jensen.englishName, "Jensen Huang");
  assert.ok(jensen.aliases.includes("黄仁勋"));
  assert.ok(jensen.aliases.includes("Jensen Huang"));
  assert.equal(jensen.aliases.some((value) => value.includes("黄仁勋(Jensen Huang")), false);

  const clement = researchPeople.find((item) => item.slug === "cl-ment-delangue");
  assert.ok(clement);
  assert.equal(clement.name, "克莱门特·德朗格");
  assert.equal(clement.englishName, "Clément Delangue");
});

test("sourced papers and talks populate works and speeches", () => {
  const kaiming = researchPeople.find((item) => item.slug === "kaiming-he");
  assert.ok(kaiming);
  assert.ok(kaiming.works.some((title) => title.includes("Deep Residual Learning")));

  const munger = researchPeople.find((item) => item.slug === "charlie-munger");
  assert.ok(munger);
  assert.ok(munger.speeches.some((material) => material.type === "speech"));
});

test("curated investment people remain available", () => {
  const slugs = new Set(researchPeople.map((person) => person.slug));
  assert.ok(slugs.has("warren-buffett"));
  assert.ok(slugs.has("charlie-munger"));
  assert.ok(slugs.has("duan-yongping"));
});
