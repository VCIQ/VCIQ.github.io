import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizeChannelUpdateDate,
  UNDATED_CHANNEL_UPDATE_SORT_AT,
} from "../lib/channel-update-date";
import {
  ALL_CHANNEL_UPDATE_EVIDENCE,
  ALL_CHANNEL_UPDATE_KEYWORDS,
  ALL_CHANNEL_UPDATE_REGIONS,
  ALL_CHANNEL_UPDATE_TOPICS,
  ALL_CHANNEL_UPDATE_TRACKS,
  collectChannelUpdateEvidenceGrades,
  collectChannelUpdateKeywords,
  collectChannelUpdateRegions,
  collectChannelUpdateTopics,
  collectChannelUpdateTracks,
  countChannelUpdatesForSnapshotDay,
  filterAndSortChannelUpdates,
} from "../lib/channel-update-filter";
import { HOMEPAGE_CHANNEL_UPDATE_LIMIT } from "../lib/homepage-channel-update-config";
import {
  aggregateTechnologyEventUpdates,
  getChannelUpdateDirectory,
  type ChannelUpdateItem,
  type ChannelUpdateKey,
} from "../lib/channel-updates";

const channels: ChannelUpdateKey[] = [
  "technology",
  "companies",
  "institutions",
  "reports",
  "people",
];

const snapshotTime = "2026-07-26T02:10:42.000Z";

test("homepage channel update directory displays up to 200 deduplicated items", () => {
  assert.equal(HOMEPAGE_CHANNEL_UPDATE_LIMIT, 200);
});

test("channel snapshot counts exact and relative updates on the generated day", () => {
  const sample = getChannelUpdateDirectory("technology").items[0];
  assert.ok(sample);
  const items = [
    { ...sample, id: "today-exact", sortAt: "2026-08-03T10:00:00.000Z", datePrecision: "exact" as const },
    { ...sample, id: "today-relative", sortAt: "2026-08-03T00:00:00.000Z", datePrecision: "approximate" as const },
    { ...sample, id: "yesterday", sortAt: "2026-08-02T23:59:59.000Z", datePrecision: "exact" as const },
    { ...sample, id: "undated", sortAt: UNDATED_CHANNEL_UPDATE_SORT_AT, datePrecision: "undated" as const },
  ];

  assert.equal(
    countChannelUpdatesForSnapshotDay(items, "2026-08-03T12:17:00.000Z"),
    2,
  );
  assert.equal(countChannelUpdatesForSnapshotDay(items, "等待更新"), 0);
});

test("normalizes exact, relative and undated source labels", () => {
  const exact = normalizeChannelUpdateDate("2020-05-29", snapshotTime);
  assert.equal(exact.displayDate, "2020-05-29");
  assert.equal(exact.precision, "exact");

  const years = normalizeChannelUpdateDate("4年前", snapshotTime);
  assert.equal(years.displayDate, "约 2022-07-26");
  assert.equal(years.precision, "approximate");

  const months = normalizeChannelUpdateDate("8个月前", snapshotTime);
  assert.equal(months.displayDate, "约 2025-11-26");
  assert.ok(months.sortAt > years.sortAt);

  const ongoing = normalizeChannelUpdateDate("持续更新", snapshotTime);
  assert.equal(ongoing.displayDate, "持续更新");
  assert.equal(ongoing.precision, "undated");
  assert.equal(ongoing.sortAt, UNDATED_CHANNEL_UPDATE_SORT_AT);
});

test("mixed person time labels sort by their normalized calendar dates", () => {
  const rows = ["4年前", "8个月前", "7年前", "6年前", "2020-05-29"].map(
    (label) => ({ label, ...normalizeChannelUpdateDate(label, snapshotTime) }),
  );
  rows.sort((left, right) => right.sortAt.localeCompare(left.sortAt));
  assert.deepEqual(
    rows.map((row) => row.label),
    ["8个月前", "4年前", "6年前", "2020-05-29", "7年前"],
  );
});

test("all requested channels expose a non-empty update directory", () => {
  for (const channel of channels) {
    const directory = getChannelUpdateDirectory(channel);
    assert.ok(directory.title.length > 0, `${channel} is missing a title`);
    assert.ok(directory.generatedAt.length >= 10, `${channel} is missing snapshot time`);
    assert.ok(directory.items.length > 0, `${channel} has no update items`);
  }
});

test("channel updates are newest-first and link to original public sources", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    // Crawled records link to their original public source; manually imported
    // documents link to the in-site reader page.
    assert.ok(
      items.every((item) =>
        /^https?:\/\//u.test(item.href) || item.href.startsWith("/documents/"),
      ),
    );
    assert.ok(items.every((item) => item.title && item.source && item.date));
    assert.ok(
      items.every((item) =>
        item.datePrecision === "undated"
          ? item.sortAt === UNDATED_CHANNEL_UPDATE_SORT_AT
          : /^\d{4}-\d{2}-\d{2}T/u.test(item.sortAt),
      ),
    );
    for (let index = 1; index < items.length; index += 1) {
      assert.ok(
        items[index - 1].sortAt.localeCompare(items[index].sortAt) >= 0,
        `${channel} is not sorted newest-first at index ${index}`,
      );
    }
  }
});

test("person dates use one visible calendar format without treating ongoing pages as new", () => {
  const items = getChannelUpdateDirectory("people").items;
  for (const item of items) {
    if (item.datePrecision === "exact") {
      assert.match(item.date, /^\d{4}-\d{2}-\d{2}$/u);
    } else if (item.datePrecision === "approximate") {
      assert.match(item.date, /^约 \d{4}-\d{2}-\d{2}$/u);
      assert.notEqual(item.date, item.dateOriginal);
    } else {
      assert.ok(item.date === "持续更新" || item.date === "日期未标明");
      assert.equal(item.sortAt, UNDATED_CHANNEL_UPDATE_SORT_AT);
    }
  }

  const relativeSortDates = new Map(
    items
      .filter((item) => item.datePrecision === "approximate")
      .map((item) => [item.dateOriginal, item.sortAt]),
  );
  if (relativeSortDates.has("8个月前") && relativeSortDates.has("4年前")) {
    assert.ok(relativeSortDates.get("8个月前")! > relativeSortDates.get("4年前")!);
  }
});

test("channel directories deduplicate repeated original links", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const keys = items.map(
      (item) => `${item.href.toLocaleLowerCase("en-US")}|${item.title.toLocaleLowerCase("zh-CN")}`,
    );
    assert.equal(new Set(keys).size, keys.length, `${channel} contains duplicate entries`);
  }
});

test("technology directory contains at most one public row per event cluster", () => {
  const items = getChannelUpdateDirectory("technology").items;
  const clusters = items
    .map((item) => item.eventClusterId)
    .filter((value): value is string => Boolean(value));
  assert.equal(new Set(clusters).size, clusters.length);
  assert.ok(
    items
      .filter((item) => item.track)
      .every((item) => item.region && Array.isArray(item.topicNames)),
  );
});

test("technology event aggregation keeps the strongest source and merges source evidence", () => {
  const sample = getChannelUpdateDirectory("technology").items.find((item) => item.track);
  assert.ok(sample);
  const items: ChannelUpdateItem[] = [
    {
      ...sample,
      id: "cluster-b",
      title: "媒体转载",
      href: "https://media.example/event",
      source: "媒体",
      sourceGrade: "B",
      sourceGradeLabel: "专业媒体",
      eventClusterId: "same-event",
      sortAt: "2026-08-21T12:00:00.000Z",
      date: "2026-08-21",
      dateOriginal: "2026-08-21",
      topicNames: ["具身智能"],
      topicSlugs: ["embodied-ai"],
      sources: [{ name: "媒体", href: "https://media.example/event" }],
      sourceCount: 1,
    },
    {
      ...sample,
      id: "cluster-a",
      title: "官方发布",
      href: "https://official.example/event",
      source: "官方",
      sourceGrade: "A",
      sourceGradeLabel: "官方披露",
      eventClusterId: "same-event",
      sortAt: "2026-08-21T10:00:00.000Z",
      date: "2026-08-21",
      dateOriginal: "2026-08-21",
      topicNames: ["人形机器人"],
      topicSlugs: ["humanoid-robots"],
      sources: [{ name: "官方", href: "https://official.example/event" }],
      sourceCount: 1,
    },
  ];

  const aggregated = aggregateTechnologyEventUpdates(items);
  assert.equal(aggregated.length, 1);
  assert.equal(aggregated[0].href, "https://official.example/event");
  assert.equal(aggregated[0].sourceGrade, "A");
  assert.equal(aggregated[0].sortAt, "2026-08-21T12:00:00.000Z");
  assert.equal(aggregated[0].sourceCount, 2);
  assert.deepEqual(
    [...(aggregated[0].topicNames ?? [])].sort(),
    ["人形机器人", "具身智能"].sort(),
  );
});

test("filter options are exactly the visible green event labels", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    assert.ok(items.every((item) => item.keywords.length === 1));
    assert.ok(items.every((item) => item.keywords[0] === item.label));

    const optionLabels = collectChannelUpdateKeywords(items).map((option) => option.keyword);
    const visibleLabels = [...new Set(items.map((item) => item.label))];
    assert.deepEqual(
      [...optionLabels].sort((left, right) => left.localeCompare(right, "zh-CN")),
      [...visibleLabels].sort((left, right) => left.localeCompare(right, "zh-CN")),
      `${channel} exposes filters that are not visible event labels`,
    );
  }
});

test("event label options classify every channel and report accurate counts", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const options = collectChannelUpdateKeywords(items);
    assert.ok(options.length > 0, `${channel} has no event label options`);

    for (const option of options) {
      const actual = items.filter((item) => item.label === option.keyword).length;
      assert.equal(option.count, actual, `${channel} event count is wrong for ${option.keyword}`);
    }
  }
});

test("technology filters combine track topic event region and evidence", () => {
  const sample = getChannelUpdateDirectory("technology").items.find((item) => item.track);
  assert.ok(sample);
  const items: ChannelUpdateItem[] = [
    {
      ...sample,
      id: "robotics-a",
      label: "技术突破",
      keywords: ["技术突破"],
      track: "机器人",
      region: "中国",
      topicNames: ["具身智能"],
      topicSlugs: ["embodied-ai"],
      sourceGrade: "A",
    },
    {
      ...sample,
      id: "robotics-b",
      label: "融资",
      keywords: ["融资"],
      track: "机器人",
      region: "美国",
      topicNames: ["人形机器人"],
      topicSlugs: ["humanoid-robots"],
      sourceGrade: "B",
    },
    {
      ...sample,
      id: "semiconductor-a",
      label: "技术突破",
      keywords: ["技术突破"],
      track: "半导体",
      region: "中国",
      topicNames: ["硅光与光计算"],
      topicSlugs: ["silicon-photonics"],
      sourceGrade: "A",
    },
  ];

  assert.deepEqual(
    collectChannelUpdateTracks(items).map((option) => option.keyword).sort(),
    ["半导体", "机器人"].sort(),
  );
  assert.ok(collectChannelUpdateTopics(items).some((option) => option.keyword === "具身智能"));
  assert.ok(collectChannelUpdateRegions(items).some((option) => option.keyword === "中国"));
  assert.deepEqual(
    collectChannelUpdateEvidenceGrades(items).map((option) => option.keyword),
    ["A", "B"],
  );

  const filtered = filterAndSortChannelUpdates({
    items,
    keyword: "技术突破",
    track: "机器人",
    topic: "具身智能",
    region: "中国",
    evidence: "A",
    sortOrder: "newest",
  });
  assert.deepEqual(filtered.map((item) => item.id), ["robotics-a"]);

  const all = filterAndSortChannelUpdates({
    items,
    keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
    track: ALL_CHANNEL_UPDATE_TRACKS,
    topic: ALL_CHANNEL_UPDATE_TOPICS,
    region: ALL_CHANNEL_UPDATE_REGIONS,
    evidence: ALL_CHANNEL_UPDATE_EVIDENCE,
    sortOrder: "newest",
  });
  assert.equal(all.length, items.length);
});

test("event-filtered updates remain time ordered", () => {
  for (const channel of channels) {
    const items = getChannelUpdateDirectory(channel).items;
    const keyword = collectChannelUpdateKeywords(items)[0]?.keyword;
    assert.ok(keyword, `${channel} has no event label to test`);

    const newest = filterAndSortChannelUpdates({ items, keyword, sortOrder: "newest" });
    assert.ok(newest.length > 0);
    assert.ok(newest.every((item) => item.label === keyword));
    for (let index = 1; index < newest.length; index += 1) {
      assert.ok(newest[index - 1].sortAt.localeCompare(newest[index].sortAt) >= 0);
    }

    const oldest = filterAndSortChannelUpdates({ items, keyword, sortOrder: "oldest" });
    for (let index = 1; index < oldest.length; index += 1) {
      assert.ok(oldest[index - 1].sortAt.localeCompare(oldest[index].sortAt) <= 0);
    }

    const all = filterAndSortChannelUpdates({
      items,
      keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
      sortOrder: "newest",
    });
    assert.equal(all.length, items.length);
  }
});
