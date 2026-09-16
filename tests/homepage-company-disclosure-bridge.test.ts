import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  mergeHomepageCompanyChannelEvents,
  projectHomepageCompanyDisclosureEvents,
} from "../lib/homepage-company-disclosure-events";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const homepage = await readFile(
  new URL("../app/page.tsx", import.meta.url),
  "utf8",
);
const feed = await readFile(
  new URL("../components/homepage-news-feed.tsx", import.meta.url),
  "utf8",
);
const companiesPage = await readFile(
  new URL("../app/companies/page.tsx", import.meta.url),
  "utf8",
);

test("material official disclosures project into the formal company channel", () => {
  const events = projectHomepageCompanyDisclosureEvents(120);
  assert.ok(events.length > 0);
  assert.ok(
    events.every(
      (event) =>
        Boolean(event.companySlug) &&
        event.source.level === "监管文件" &&
        event.sourceId === "listed-company-disclosures" &&
        event.qualityStatus === "高可信",
    ),
  );
  assert.ok(events.some((event) => event.qualitySignals?.includes("CNINFO 结构化披露")));
  assert.ok(events.some((event) => event.type === "财报"));
});

test("routine governance disclosures do not enter the homepage company projection", () => {
  const events = projectHomepageCompanyDisclosureEvents(200);
  assert.equal(
    events.some((event) => /日常关联交易预计|股东大会通知|董事会会议通知/u.test(event.title)),
    false,
  );
});

test("canonical article wins URL dedupe while gaining formal disclosure binding", () => {
  const disclosure = projectHomepageCompanyDisclosureEvents(1)[0];
  assert.ok(disclosure);
  const canonical: LiveIntelligenceEvent = {
    ...disclosure,
    id: "canonical-article",
    company: "",
    companySlug: undefined,
    sourceId: "article-pool",
    qualitySignals: ["canonical article"],
    importance: Math.max(1, disclosure.importance - 5),
  };

  const merged = mergeHomepageCompanyChannelEvents(
    [canonical],
    [disclosure],
    [canonical],
  );
  assert.equal(merged.length, 1);
  assert.equal(merged[0]?.id, "canonical-article");
  assert.equal(merged[0]?.companySlug, disclosure.companySlug);
  assert.equal(merged[0]?.company, disclosure.company);
  assert.ok(merged[0]?.qualitySignals?.includes("官方监管披露"));
  assert.equal(merged[0]?.importance, disclosure.importance);
});

test("same report title from different companies is not cross-company deduplicated", () => {
  const projected = projectHomepageCompanyDisclosureEvents(200).filter(
    (event) => event.type === "财报",
  );
  const byTitle = new Map<string, LiveIntelligenceEvent[]>();
  for (const event of projected) {
    const rows = byTitle.get(event.title) ?? [];
    rows.push(event);
    byTitle.set(event.title, rows);
  }
  const sameTitleDifferentCompanies = [...byTitle.values()].find(
    (rows) => new Set(rows.map((event) => event.companySlug)).size >= 2,
  );
  assert.ok(sameTitleDifferentCompanies);
  const pair = sameTitleDifferentCompanies.slice(0, 2);
  const merged = mergeHomepageCompanyChannelEvents([], pair, []);
  assert.equal(merged.length, 2);
  assert.notEqual(merged[0]?.companySlug, merged[1]?.companySlug);
});

test("company library and homepage company channel share one disclosure bridge", () => {
  assert.match(homepage, /projectHomepageCompanyDisclosureEvents\(36\)/u);
  assert.match(homepage, /companyChannelEvents=\{companyChannelEvents\}/u);
  assert.match(feed, /mergeHomepageCompanyChannelEvents/u);
  assert.match(feed, /channel === "companies"/u);
  assert.match(companiesPage, /上市公司官方披露/u);
  assert.match(companiesPage, /CNINFO/u);
  assert.match(companiesPage, /projectHomepageCompanyDisclosureEvents\(6\)/u);
});
