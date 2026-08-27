import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

function assertOrder(sourceText: string, first: string, second: string, message: string) {
  const firstIndex = sourceText.indexOf(first);
  const secondIndex = sourceText.indexOf(second);
  assert.ok(firstIndex >= 0, `missing first marker: ${first}`);
  assert.ok(secondIndex >= 0, `missing second marker: ${second}`);
  assert.ok(firstIndex < secondIndex, message);
}

test("1440x900 core-channel contract puts live panels before research methodology", async () => {
  const layout = await source("components/channel-split-layout.tsx");
  const css = await source("components/channel-split-layout.module.css");

  assertOrder(
    layout,
    "{beforeResearchSynergy}",
    "<div className={styles.splitLayout}>",
    "technology research-now signal must stay ahead of the live split panels",
  );
  assertOrder(
    layout,
    "<div className={styles.splitLayout}>",
    "<ResearchSynergyStrip compactOnMobile />",
    "live directory/update panels must render before the Research Object Graph",
  );
  assertOrder(
    layout,
    "<ResearchSynergyStrip compactOnMobile />",
    "<details className={styles.directoryNote}>",
    "directory explanation must remain secondary to live research content",
  );
  assert.doesNotMatch(layout, /className=\{styles\.panelDescription\}/);

  assert.match(css, /min-height:\s*88px/);
  assert.match(css, /grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(css, /div:first-child\) \{\s*display:\s*none;/);
});

test("people and company channel headers expose current signals before explanations", async () => {
  const people = await source("app/people/page.tsx");
  const companies = await source("app/companies/page.tsx");

  assert.match(people, /getChannelUpdateDirectory\("people"\)/);
  assert.match(people, /peopleUpdates\.items\.length\} 条人物更新/);
  assertOrder(
    people,
    "<ChannelSplitLayout",
    "<details className={styles.methodology}>",
    "people methodology must sit below the live directory and event panels",
  );
  assertOrder(
    companies,
    "<ChannelSplitLayout",
    "<details className={styles.methodology}>",
    "company methodology must sit below the live directory and event panels",
  );

  const peopleHeader = people.slice(
    people.indexOf("<header className={`page-header ${styles.channelHeader}`}>"),
    people.indexOf("</header>"),
  );
  const companyHeader = companies.slice(
    companies.indexOf("<header className={`page-header ${styles.channelHeader}`}>"),
    companies.indexOf("</header>"),
  );
  assert.doesNotMatch(peopleHeader, /人物频道解释|公司关系仅按显式任职证据挂接/);
  assert.doesNotMatch(companyHeader, /公司频道负责把赛道与技术变量/);
});

test("sources render tracked source cards before lifecycle and governance explanations", async () => {
  const sources = await source("app/sources/page.tsx");

  assertOrder(
    sources,
    "{groups.map((group) => {",
    "<details className={styles.lifecycle}>",
    "tracked source groups must render before Source Lifecycle methodology",
  );
  assertOrder(
    sources,
    "<div className={styles.grid}>",
    "<p className=\"intro-copy\">{group.description}</p>",
    "source cards must render before per-group explanatory copy",
  );
  assertOrder(
    sources,
    "<details className={styles.lifecycle}>",
    "aria-label=\"信源治理原则\"",
    "source governance must remain below tracked source data",
  );
});

test("technology keeps current data first and pushes taxonomy methodology to the bottom", async () => {
  const technology = await source("app/technologies/page.tsx");
  const css = await source("app/technologies/page.module.css");

  assertOrder(
    technology,
    "beforeResearchSynergy={",
    "<section className={styles.layer} id=\"core-tracks\">",
    "Technology Pulse must remain the research-now signal before taxonomy content",
  );
  assertOrder(
    technology,
    "<div className={styles.trackGrid}>",
    "<summary><strong>科技研究口径与方法说明</strong></summary>",
    "track cards must appear before the methodology disclosure",
  );
  assertOrder(
    technology,
    "<div className={styles.topicGrid}>",
    "<summary><strong>科技研究口径与方法说明</strong></summary>",
    "topic cards must appear before the methodology disclosure",
  );
  assertOrder(
    technology,
    "<section className={styles.layer} id=\"core-technologies\">",
    "<summary><strong>科技研究口径与方法说明</strong></summary>",
    "technology-entity content must appear before the methodology disclosure",
  );
  assert.doesNotMatch(technology, /<h3>核心赛道<\/h3>\s*<p>/);
  assert.doesNotMatch(technology, /<h3>重点技术主题<\/h3>\s*<p>/);
  assert.doesNotMatch(technology, /<h3>核心技术对象<\/h3>\s*<p>/);
  assert.match(css, /\.headerIntro,\s*\.analysisPolicy \{\s*display:\s*none;/);
  assert.match(css, /\.pulseHeader > p \{\s*display:\s*none;/);
  assert.match(css, /\.pulseHeader \{[\s\S]*grid-template-columns:\s*minmax\(180px, 1fr\) auto;/);
});
