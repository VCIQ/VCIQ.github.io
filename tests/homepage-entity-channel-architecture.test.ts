import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("primary navigation separates live entity feeds from research directories", async () => {
  const header = await source("components/site-header.tsx");
  assert.match(header, /\["人物库", "\/people"\]/u);
  assert.match(header, /\["公司库", "\/companies"\]/u);
  assert.doesNotMatch(header, /\["核心人物", "\/people"\]/u);
  assert.doesNotMatch(header, /\["核心公司", "\/companies"\]/u);
});

test("technology people and company research pages do not duplicate homepage news feeds", async () => {
  const layout = await source("components/channel-split-layout.tsx");
  const people = await source("app/people/page.tsx");
  const companies = await source("app/companies/page.tsx");

  assert.match(layout, /\["technology", "people", "companies"\]\.includes\(channel\)/u);
  assert.match(layout, /const shouldShowUpdates = showUpdates \?\? !researchDirectoryChannel/u);
  assert.match(layout, /className=\{styles\.directoryOnly\}/u);
  assert.match(people, /<h1>人物库<\/h1>/u);
  assert.match(people, /showUpdates=\{false\}/u);
  assert.match(people, /统一在首页“人物”频道/u);
  assert.match(companies, /<h1>公司库<\/h1>/u);
  assert.match(companies, /showUpdates=\{false\}/u);
  assert.match(companies, /统一在首页“公司”频道/u);
});
