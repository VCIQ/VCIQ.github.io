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
import { canonicalTracksForItem } from "../lib/canonical-sector-assignment";
import {
  aggregateTechnologyEventUpdates,
  getChannelUpdateDirectory,
  technologyEventHasResearchEvidence,
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

test("technology publication requires content evidence independently of source grade", () => {
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "AI / AGI",
      title: "President discusses ground beef imports",
      summary: "A domestic food-price policy story.",
      qualityStatus: "低可信",
      qualitySignals: ["标题命中公司/账号"],
      sourceGrade: "B",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "AI / AGI",
      title: "A general corporate announcement",
      summary: "No technology content is present.",
      qualityStatus: "可用",
      sourceGrade: "A",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 1,
      track: "Web3",
      title: "Claude agents launch a security workflow",
      summary: "The agent system automates incident response.",
      sourceGrade: "C",
    }),
    true,
  );
  for (const title of [
    "Edge AI Daily 早报（8月23日）",
    "AI Model Leaderboards & Benchmarks",
    "DeepSeek 招聘",
    "更新日志 | DeepSeek API Docs",
    "Claude Opus",
    "Mobileye Drive™ | Self-Driving System for Autonomous MaaS",
    "Technology | Commonwealth Fusion Systems",
    "SPARC: Proving commercial fusion energy is possible | Commonwealth Fusion Systems",
    "ARC: Putting fusion energy on the grid | Commonwealth Fusion Systems",
    "2026中国先进封装企业20强（TOP 20）",
    "半导体器件的失效分析及可靠性测试",
    "Understanding Why Agentic AI Demands a Massive CPU Renaissance and How IT Leaders Must Prepare Now | Techspective: A Unique Perspective on Technology",
    "晶圆厂转先进封装，值不值？",
    "Agentic AI in the enterprise: How to balance autonomy with constraints",
    "Getting the most out of GPT-5.6: Sol, Terra, and Luna",
    "Get access to ChatGPT, Claude & Gemini for just $69.97 today",
  ]) {
    assert.equal(
      technologyEventHasResearchEvidence({
        topicCount: 1,
        track: "AI / AGI",
        title,
        summary: "The page mentions a large language model.",
        sourceGrade: "B",
      }),
      false,
      `non-event technology page was admitted: ${title}`,
    );
  }
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 1,
      track: "AI / AGI",
      title: "OpenAI：RT @adamhfry: This week’s ChatGPT feature drop - Aug 21: Another Friday, another roundup of what we shipped this week: 1/ Recent photos:…",
      summary:
        "RT @adamhfry: This week’s ChatGPT feature drop - Aug 21: Another Friday, another roundup of what we shipped this week: 1/ Recent photos:…",
      sourceName: "X",
      sourceGrade: "B",
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 1,
      track: "AI / AGI",
      title:
        "Google DeepMind：RT @GeminiApp: Gemini 3.7 Flash is now available to all Pro and Ultra users in Gemini chat. This model update delivers improved reasoning…",
      summary:
        "RT @GeminiApp: Gemini 3.7 Flash is now available to all Pro and Ultra users in Gemini chat. This model update delivers improved reasoning…",
      sourceName: "X",
      sourceGrade: "B",
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 1,
      track: "AI / AGI",
      title: "A developer tests a new AI model workflow",
      summary: "A single-author community post.",
      sourceGrade: "C",
      sourceName: "DEV Community",
      sourceCount: 1,
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 1,
      track: "可控核聚变",
      title: "A generic technology overview",
      summary: "The page describes a planned fusion system.",
      sourceUrl: "https://cfs.energy/technology/sparc/\\",
      sourceGrade: "B",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 1,
      track: "机器人",
      title: "Three unrelated headlines joined into one crawler result",
      summary: "早报来啦~",
      sourceGrade: "B",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 1,
      track: "AI / AGI",
      title: "A developer tests a new AI model workflow",
      summary: "The event is corroborated by an additional source.",
      sourceGrade: "C",
      sourceName: "DEV Community",
      sourceCount: 2,
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "商业航天",
      title: "Rocket Lab schedules its next launch",
      summary: "The mission will deploy a satellite.",
      matchedTrackingTerms: ["Rocket Lab"],
      sourceGrade: "C",
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "AI语音",
      title: "以扎实举措推进农业农村现代化",
      summary: "农业与乡村发展政策解读。",
      qualitySignals: ["标题命中 2 个追踪词"],
      sourceGrade: "C",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "新能源",
      title: "Windows platform update reaches general availability",
      summary: "The software release improves desktop management.",
      sourceGrade: "B",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "生物科技",
      title: "General Electric expands an industrial service",
      summary: "The company announced a new maintenance contract.",
      sourceGrade: "B",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "新能源",
      title: "New wind farm begins commercial operation",
      summary: "The renewable power project entered service.",
      sourceGrade: "B",
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "生物科技",
      title: "Gene therapy enters a phase 2 clinical trial",
      summary: "The study enrolled its first patient.",
      sourceGrade: "B",
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "新能源",
      title: "The Apex Institute explains cloud hiring",
      summary: "Hiring managers discuss AI infrastructure roles.",
      qualitySignals: ["摘要命中 1 个追踪词", "包含明确事件动作"],
      sourceGrade: "C",
    }),
    false,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "AI / AGI",
      title: "MillworkSuite launches AI estimating and direct-to-CAD",
      summary: "The product converts architectural documents into a priced scope.",
      sourceGrade: "B",
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "AI / AGI",
      title: "Nscale seeks funding for an AI data center",
      summary: "The company is expanding infrastructure capacity.",
      qualityStatus: "可用",
      sourceGrade: "C",
    }),
    true,
  );
  assert.equal(
    technologyEventHasResearchEvidence({
      topicCount: 0,
      track: "AI / AGI",
      title: "The first deportation flight to Haiti landed",
      summary: "Immigration arrests are increasing.",
      sourceGrade: "B",
    }),
    false,
  );
});

test("technology publication preserves observed tracks and applies reviewed analysis corrections", () => {
  const items = getChannelUpdateDirectory("technology").items;
  const claudeAgents = items.find((item) =>
    item.title.includes("Claude agents launching a turf war"),
  );
  assert.ok(claudeAgents);
  assert.equal(claudeAgents.track, "Web3");
  assert.deepEqual(claudeAgents.publicTracks, ["AI / AGI", "AI安全"]);
  assert.match(claudeAgents.context, /^AI \/ AGI ·/u);
  assert.ok(claudeAgents.classifications?.includes("规范赛道纠错"));
  const correction = canonicalTracksForItem(claudeAgents);
  assert.equal(correction.applied, true);
  assert.deepEqual(correction.canonicalTracks, ["AI / AGI", "AI安全"]);

  const reviewedCases: Array<[string, string[]]> = [
    ["Vantage and Nebius move first", ["AI / AGI"]],
    ["DeepSeek to introduce peak and off-peak pricing", ["AI / AGI"]],
    ["Pixels could soon get AI-powered", ["AI智能终端", "AI / AGI"]],
    ["Pony AI Inc.’s Second Quarter 2026 Earnings", ["机器人", "智能交通"]],
    ["Mobileye to establish vertically integrated robotaxi", ["机器人", "智能交通"]],
    ["Mobileye To Acquire Mentee Robotics", ["机器人", "智能交通"]],
    ["晶泰科技AI赋能孔道独立调控", ["新材料"]],
    ["Honor Launches Robot Phone", ["AI智能终端", "AI / AGI"]],
    ["Grok exfiltrates user data", ["AI / AGI", "AI安全"]],
    ["Microsoft finally patches critical one-click Copilot", ["AI / AGI", "AI安全"]],
    ["Google's AI can see your business data", ["AI / AGI", "AI安全"]],
    ["Helion 完成 Vela 可控核聚变脉冲电源规模测试", ["可控核聚变"]],
  ];
  for (const [title, publicTracks] of reviewedCases) {
    const item = items.find((candidate) => candidate.title.includes(title));
    assert.ok(item, `${title} is missing from the public event directory`);
    assert.deepEqual(item.publicTracks, publicTracks, `${title} has stale public tracks`);
  }
});

test("technology publication repairs incomplete metadata for verified events", () => {
  const items = getChannelUpdateDirectory("technology").items;
  const deepMind = items.find(
    (item) => item.id === "user-x-googledeepmind-25b4f20ecfb62f41",
  );
  assert.ok(deepMind);
  assert.equal(
    deepMind.title,
    "AlphaEvolve 用 AI 将矩阵乘法指数上界推进至 ω < 2.371177",
  );
  assert.equal(deepMind.label, "论文");
  assert.deepEqual(deepMind.keywords, ["论文"]);
  assert.match(deepMind.summary, /2\.371339.*2\.371177/u);
  assert.ok(
    deepMind.sources?.some(
      (source) => source.href === "https://arxiv.org/abs/2608.16884",
    ),
  );

  const helion = items.find(
    (item) => item.id === "official-helion-7df714571d811ffc",
  );
  assert.ok(helion);
  assert.match(helion.title, /Vela.*Tiny Merge/u);
  assert.match(helion.summary, /1 Hz.*11 GJ/u);
  assert.equal(helion.track, "新能源");
  assert.deepEqual(helion.publicTracks, ["可控核聚变"]);
});

test("technology track filters use reviewed public tracks without erasing provenance", () => {
  const claudeAgents = getChannelUpdateDirectory("technology").items.find(
    (item) => item.title.includes("Claude agents launching a turf war"),
  );
  assert.ok(claudeAgents);

  const options = collectChannelUpdateTracks([claudeAgents]);
  assert.deepEqual(options, [
    { keyword: "AI / AGI", count: 1 },
    { keyword: "AI安全", count: 1 },
  ]);
  const filtered = filterAndSortChannelUpdates({
    items: [claudeAgents],
    keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
    track: "AI / AGI",
    sortOrder: "newest",
  });
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].track, "Web3");
});

test("technology directory excludes known identity-only and unrelated source collisions", () => {
  const items = getChannelUpdateDirectory("technology").items;
  const titles = items.map((item) => item.title);
  assert.ok(
    items.every((item) => !/^早报来啦[~～！!]*$/iu.test(item.summary.trim())),
    "multi-headline morning digests remain in the technology event directory",
  );
  const unrelatedPatterns = [
    /ground beef imports/iu,
    /Bethenny Frankel/iu,
    /deportation flight to Haiti/iu,
    /Pastry chef Katrina Blancaflor/iu,
    /玻利维亚女律师遭/u,
    /墨西哥两名渔民船只失事/u,
    /关久旸：战舰700/u,
    /以扎实举措推进农业农村现代化/u,
    /The Apex Institute Reveals What Hiring Managers/iu,
    /HTX Research Examines U\.S\. AI Equities/iu,
    /greatest privilege of my life/iu,
    /IonQ Announces Record Second Quarter 2026 Revenues/iu,
    /摩根大通：阿里云12%利润率/iu,
    /Edge AI Daily 早报/iu,
    /AI Model Leaderboards & Benchmarks/iu,
    /^Investors$/iu,
    /^DeepSeek 招聘$/iu,
    /lifetime subscription/iu,
    /Bundle Teaches You How To Use AI/iu,
    /project management training for \$20/iu,
    /AI models for life for \$54\.97/iu,
    /ChatGPT, Claude & Gemini for just \$69\.97/iu,
    /^睿小鉴 - AI导航 - 猫目$/iu,
    /钛晨报/iu,
    /^模型 & 价格 \| DeepSeek API Docs$/iu,
    /^更新日志 \| DeepSeek API Docs$/iu,
    /^Legal AI solutions for law firms \| Harvey$/iu,
    /^IROS：国际智能机器人与系统会议$/iu,
    /^Mobileye Drive™ \| Self-Driving System for Autonomous MaaS$/iu,
    /^Technology \| Commonwealth Fusion Systems$/iu,
    /^SPARC: Proving commercial fusion energy is possible \| Commonwealth Fusion Systems$/iu,
    /^ARC: Putting fusion energy on the grid \| Commonwealth Fusion Systems$/iu,
    /^Claude (?:Opus|Sonnet)$/iu,
    /^2026中国先进封装企业20强（TOP 20）$/iu,
    /this free browser extension made it ridiculously easy$/iu,
    /^Anthropic：For more on how Claude ran this experiment and the full results, see our blog:/iu,
    /^半导体器件的失效分析及可靠性测试$/iu,
    /^Understanding Why Agentic AI Demands a Massive CPU Renaissance/iu,
    /^晶圆厂转先进封装，值不值？$/iu,
    /^Agentic AI in the enterprise: How to balance autonomy with constraints$/iu,
    /^Getting the most out of GPT-5\.6: Sol, Terra, and Luna$/iu,
    /^Google Pixel (?:Watch 5|11 Pro XL) Review:/iu,
    /^Don’t use Gemini or ChatGPT for studying — use this free app instead$/iu,
    /Leveling up OpenCode/iu,
    /We built a benchmark, then caught it strangling/iu,
    /cheapest model on my plan loses every benchmark/iu,
    /Google Gemini Notebook Expands Into AI Mode Search/iu,
    /Microsoft Expands MAI Playground/iu,
    /An AI Agent Has Run This SaaS/iu,
  ];
  for (const pattern of unrelatedPatterns) {
    assert.ok(
      titles.every((title) => !pattern.test(title)),
      `unrelated technology event remains public: ${pattern}`,
    );
  }

  for (const retainedPattern of [
    /MillworkSuite Launches AI Estimating/iu,
    /AI data center builder Nscale/iu,
    /朱雀三号/iu,
    /AlphaEvolve 用 AI 将矩阵乘法指数上界推进至 ω < 2\.371177/iu,
    /Helion 完成 Vela 可控核聚变脉冲电源规模测试并推进 Tiny Merge 集成/iu,
  ]) {
    assert.ok(
      titles.some((title) => retainedPattern.test(title)),
      `relevant long-tail technology event was removed: ${retainedPattern}`,
    );
  }
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
      publicTracks: undefined,
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
      publicTracks: undefined,
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
      publicTracks: undefined,
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
