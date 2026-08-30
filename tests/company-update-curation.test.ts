import assert from "node:assert/strict";
import test from "node:test";

import { curateCompanyUpdateDirectory } from "../lib/company-update-curation";
import type {
  ChannelUpdateDirectory,
  ChannelUpdateItem,
} from "../lib/channel-updates";

function item(
  overrides: Partial<ChannelUpdateItem> & Pick<ChannelUpdateItem, "id" | "title">,
): ChannelUpdateItem {
  return {
    id: overrides.id,
    title: overrides.title,
    summary: overrides.summary ?? "公司宣布一项可核验的重要变化。",
    href: overrides.href ?? `https://example.com/${overrides.id}`,
    source: overrides.source ?? "测试信源",
    label: overrides.label ?? "公司动态",
    context: overrides.context ?? "测试公司 · AI / AGI",
    date: overrides.date ?? "2026-08-20",
    dateOriginal: overrides.dateOriginal ?? "2026-08-20",
    datePrecision: overrides.datePrecision ?? "exact",
    sortAt: overrides.sortAt ?? "2026-08-20T00:00:00.000Z",
    keywords: overrides.keywords ?? [overrides.label ?? "公司动态"],
    classifications: overrides.classifications,
    sourceGrade: overrides.sourceGrade,
    sourceGradeLabel: overrides.sourceGradeLabel,
    sourceVerificationPolicy: overrides.sourceVerificationPolicy,
    eventClusterId: overrides.eventClusterId,
    sources: overrides.sources,
    sourceCount: overrides.sourceCount,
  };
}

function directory(items: ChannelUpdateItem[]): ChannelUpdateDirectory {
  return {
    title: "公司更新目录",
    description: "fixture",
    generatedAt: "2026-08-22T00:00:00.000Z",
    items,
  };
}

test("company update curation removes evergreen, undated and D-grade records", () => {
  const curated = curateCompanyUpdateDirectory(directory([
    item({ id: "brand", title: "Brand Guidelines", label: "技术突破" }),
    item({ id: "undated", title: "公司宣布新产品", datePrecision: "undated" }),
    item({ id: "d", title: "公司宣布完成融资", label: "融资", sourceGrade: "D" }),
    item({ id: "keep", title: "公司宣布完成新一轮融资", label: "融资", sourceGrade: "B" }),
  ]));

  assert.deepEqual(curated.items.map((entry) => entry.id), ["keep"]);
  assert.equal(curated.title, "重要公司事件");
});

test("company update curation aggregates duplicate event titles and preserves sources", () => {
  const curated = curateCompanyUpdateDirectory(directory([
    item({
      id: "media",
      title: "测试公司宣布完成 B 轮融资",
      href: "https://media.example.com/story",
      source: "媒体",
      sourceGrade: "C",
      label: "融资",
    }),
    item({
      id: "official",
      title: "测试公司宣布完成 B 轮融资",
      href: "https://company.example.com/news",
      source: "公司官网",
      sourceGrade: "B",
      label: "融资",
    }),
  ]));

  assert.equal(curated.items.length, 1);
  assert.equal(curated.items[0]?.id, "official");
  assert.equal(curated.items[0]?.sourceCount, 2);
  assert.deepEqual(
    curated.items[0]?.sources?.map((source) => source.name).sort(),
    ["公司官网", "媒体"],
  );
});
