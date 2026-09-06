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

test("people and company cards lead with latest change and company secondary filters stay collapsed", async () => {
  const people = await source("app/people/page.tsx");
  const companies = await source("components/company-directory-client.tsx");
  const companyCss = await source("components/company-directory.module.css");

  assertOrder(
    people,
    "<b>最新变化</b>",
    "<b>为什么重要</b>",
    "person cards must surface the latest verified change before static importance context",
  );
  assertOrder(
    companies,
    "<strong>最新变化</strong>",
    "<strong>为什么重要</strong>",
    "company cards must surface the latest verified change before static importance context",
  );

  const advancedStart = companies.indexOf("<details className={styles.advancedFilters}>");
  const advancedEnd = companies.indexOf("</details>", advancedStart);
  assert.ok(advancedStart >= 0 && advancedEnd > advancedStart, "missing collapsed secondary company filters");
  const advancedFilters = companies.slice(advancedStart, advancedEnd);
  assert.match(advancedFilters, /value=\{region\}/);
  assert.match(advancedFilters, /value=\{sector\}/);
  assert.match(advancedFilters, /value=\{stage\}/);
  assert.doesNotMatch(advancedFilters, /value=\{signal\}|value=\{sortOrder\}/);
  assertOrder(
    companies,
    "value={signal}",
    "<details className={styles.advancedFilters}>",
    "research signal must remain a primary company filter",
  );
  assertOrder(
    companies,
    "value={sortOrder}",
    "<details className={styles.advancedFilters}>",
    "sort order must remain a primary company control",
  );

  assert.match(companyCss, /\.primaryFilters \{[\s\S]*grid-template-columns:\s*minmax\(220px, 1\.6fr\) repeat\(2, minmax\(118px, \.7fr\)\)/);
  assert.match(companyCss, /\.advancedFilters summary \{/);
  assert.match(companyCss, /\.advancedGrid \{[\s\S]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/);
});

test("people and company cards stay scan-dense without dropping research context", async () => {
  const people = await source("app/people/page.tsx");
  const peopleCss = await source("app/people/page.module.css");
  const companies = await source("components/company-directory-client.tsx");
  const companyCss = await source("components/company-directory.module.css");

  assert.match(companies, /className=\{styles\.cardMetrics\}/);
  assert.match(companies, /<dt>阶段<\/dt>/);
  assert.match(companies, /<dt>证据<\/dt>/);
  assert.match(companies, /<dt>研究分<\/dt>/);
  assert.match(companies, /companyDirectoryRelationTags\(company\)/);
  assert.match(companies, /company\.coverageLabel/);
  assert.match(companies, /company\.identityConfidence/);
  assert.match(companies, /company\.updatedAt/);
  assert.match(companyCss, /\.card \{[\s\S]*min-height:\s*228px/);
  assert.match(companyCss, /\.researchRows p \{[\s\S]*-webkit-line-clamp:\s*1/);
  assert.match(companyCss, /\.researchRows > div:first-child p \{[\s\S]*-webkit-line-clamp:\s*2/);
  assert.match(companyCss, /\.relationRow \{[\s\S]*flex-wrap:\s*nowrap/);
  assert.match(companyCss, /\.cardMetrics \{/);

  assert.doesNotMatch(people, /styles\.personCard/);
  assert.match(people, /className=\{filterClass\}/);
  assertOrder(
    people,
    "<header className={styles.personLead}>",
    "<section className={styles.cardResearch}>",
    "person identity should remain a compact lead-in before live research rows",
  );
  assert.match(people, /research\.priority\.level/);
  assert.match(people, /research\.coverage\.score/);
  assert.match(people, /statusLabels\[person\.status\]/);
  assert.match(peopleCss, /\.body :global\(\.people-grid > a\) \{[\s\S]*min-height:\s*212px/);
  assert.match(peopleCss, /\.personLead \{/);
  assert.match(peopleCss, /\.cardResearch > div \{[\s\S]*grid-template-columns:\s*48px minmax\(0, 1fr\)/);
  assert.match(peopleCss, /\.cardResearch > div:first-child p \{[\s\S]*-webkit-line-clamp:\s*2/);
});

test("sources render the live decision dashboard before lifecycle and governance explanations", async () => {
  const sources = await source("app/sources/page.tsx");
  const operations = await source("app/sources/source-operations-client.tsx");

  assert.match(operations, /SOURCE DECISION CONTROL PLANE/);
  assert.match(operations, /SOURCE ENTITIES/);
  assertOrder(
    sources,
    "<SourceOperationsClient",
    "<details className={styles.lifecycle}>",
    "live source decisions must render before Source Lifecycle methodology",
  );
  assertOrder(
    sources,
    "<SourceOperationsClient",
    "aria-label=\"信源治理原则\"",
    "source governance must remain below live source data",
  );
  assertOrder(
    sources,
    "<details className={styles.lifecycle}>",
    "aria-label=\"信源治理原则\"",
    "source governance must remain below lifecycle methodology",
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