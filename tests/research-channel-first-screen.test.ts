import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("research object methodology is a compact secondary path instead of a large first-screen graph", async () => {
  const strip = await source("components/research-synergy-strip.tsx");
  const css = await source("components/research-synergy-strip.module.css");

  assert.match(strip, /RESEARCH PATH/);
  assert.match(strip, /<details className=\{styles\.method\}>/);
  assert.match(strip, /currentChannel/);
  assert.doesNotMatch(strip, /RESEARCH OBJECT GRAPH/);
  assert.match(css, /grid-template-columns:\s*auto minmax\(0, 1fr\) auto/);
  assert.match(css, /\.method > div/);
});

test("technology pulse is placed before the compact research path and research panels use dense headers", async () => {
  const layout = await source("components/channel-split-layout.tsx");
  const css = await source("components/channel-split-layout.module.css");

  const pulseSlot = layout.indexOf("{afterResearchSynergy}");
  const researchPath = layout.indexOf("<ResearchSynergyStrip currentChannel={researchChannel}");
  assert.ok(pulseSlot >= 0 && researchPath > pulseSlot);
  assert.match(layout, /styles\.researchDense/);
  assert.match(css, /\.researchDense[\s\S]*--channel-split-panel-height:\s*900px/);
  assert.match(css, /\.researchDense \.panelHeader[\s\S]*min-height:\s*120px/);
});

test("people and company headers expose current research signals rather than methodology chips", async () => {
  const people = await source("app/people/page.tsx");
  const companies = await source("app/companies/page.tsx");
  const companyCss = await source("app/companies/page.module.css");

  assert.match(people, /research-channel-header\.module\.css/);
  assert.match(people, /getChannelUpdateDirectory\("people"\)/);
  assert.match(people, /peopleUpdates\.items\.length/);
  assert.doesNotMatch(people, /按研究优先级排序/);
  assert.doesNotMatch(people, /公司关系仅按显式任职证据挂接/);

  assert.match(companies, /research-channel-header\.module\.css/);
  assert.match(companies, /getChannelUpdateDirectory\("companies"\)/);
  assert.match(companies, /companyUpdates\.items\.length/);
  assert.doesNotMatch(companies, /按研究优先级与最新变化排序/);
  assert.match(companyCss, /\.body :global\(\.directory-filters\)[\s\S]*position:\s*sticky/);
});

test("source cards appear after a collapsed lifecycle rule and expose coverage at a glance", async () => {
  const page = await source("app/sources/page.tsx");
  const css = await source("app/sources/page.module.css");

  assert.match(page, /research-channel-header\.module\.css/);
  assert.match(page, /<details className=\{styles\.lifecycle\}>/);
  assert.match(page, /Candidate → Tracked → Core/);
  assert.match(page, /className=\{styles\.coverageRow\}/);
  assert.match(page, /source\.sectors\.length/);
  assert.match(page, /source\.companies\.length/);
  assert.match(page, /source\.people\.length/);
  assert.match(css, /\.lifecycle summary[\s\S]*min-height:\s*54px/);
  assert.match(css, /\.coverageRow/);
});
