import assert from "node:assert/strict";
import test from "node:test";

import { clusterPersonEventItems } from "../lib/person-event-clustering";
import { validatePersonIdentity } from "../lib/person-identity-validation";

test("person identity gate rejects non-people and title bleed", () => {
  assert.equal(validatePersonIdentity({ name: "混合专家模型" }).valid, false);
  assert.equal(validatePersonIdentity({ name: "C Class Presiden Thomas Sonderman" }).valid, false);
  assert.equal(validatePersonIdentity({ name: "Massachusetts Governo Chris Ballance" }).valid, false);
  assert.equal(validatePersonIdentity({ name: "王兴兴", englishName: "Wang Xingxing" }).valid, true);
  assert.equal(validatePersonIdentity({ name: "Chris Ballance" }).valid, true);
});

test("same-person coverage of one event clusters while preserving sources", () => {
  const items = [
    {
      title: "王兴兴：人形机器人量产与具身智能最新进展",
      date: "2026-08-20",
      href: "https://example.com/a",
      source: "Source A",
      context: "王兴兴",
    },
    {
      title: "专访王兴兴：谈人形机器人量产与具身智能进展",
      date: "2026-08-21",
      href: "https://example.com/b",
      source: "Source B",
      context: "王兴兴",
    },
  ];
  const clusters = clusterPersonEventItems(items, {
    referenceDate: "2026-08-22T00:00:00Z",
    scopeKey: (item) => item.context,
  });
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].sourceCount, 2);
  assert.equal(clusters[0].items.length, 2);
});

test("event clustering never merges different people or distant events", () => {
  const items = [
    {
      title: "人形机器人量产与具身智能进展",
      date: "2026-08-20",
      href: "https://example.com/a",
      source: "Source A",
      context: "王兴兴",
    },
    {
      title: "人形机器人量产与具身智能进展",
      date: "2026-08-20",
      href: "https://example.com/b",
      source: "Source B",
      context: "另一人物",
    },
    {
      title: "人形机器人量产与具身智能进展",
      date: "2026-04-01",
      href: "https://example.com/c",
      source: "Source C",
      context: "王兴兴",
    },
  ];
  const clusters = clusterPersonEventItems(items, {
    referenceDate: "2026-08-22T00:00:00Z",
    scopeKey: (item) => item.context,
  });
  assert.equal(clusters.length, 3);
});
