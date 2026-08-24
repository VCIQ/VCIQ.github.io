import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { canonicalTracksForItem } from "../lib/canonical-sector-assignment";
import {
  getChannelUpdateDirectory,
  technologyEventHasResearchEvidence,
  type ChannelUpdateItem,
} from "../lib/channel-updates";

const reviewedCorrectionFixtures: Array<{
  id: string;
  observedTrack: string;
  canonicalTracks: string[];
}> = [
  {
    id: "professional-media-techradar-6c418df3c6e6cf11",
    observedTrack: "Web3",
    canonicalTracks: ["AI / AGI", "AI安全"],
  },
  {
    id: "professional-media-itpro-0fefccec63002c6a",
    observedTrack: "半导体",
    canonicalTracks: ["AI / AGI"],
  },
  {
    id: "user-source-source-manual-9218cafd750da2e9-1336f626f78c2a1b",
    observedTrack: "机器人",
    canonicalTracks: ["AI / AGI"],
  },
  {
    id: "user-source-source-android-authority-2a4d3ece0efd4fc8",
    observedTrack: "新能源",
    canonicalTracks: ["AI智能终端", "AI / AGI"],
  },
  {
    id: "user-source-source-track-13f64em-4cccf9ca06142500",
    observedTrack: "AI / AGI",
    canonicalTracks: ["机器人", "智能交通"],
  },
  {
    id: "official-mobileye-2499d6166e00c9de",
    observedTrack: "半导体",
    canonicalTracks: ["机器人", "智能交通"],
  },
  {
    id: "official-mobileye-9bd9dce1719f03a1",
    observedTrack: "半导体",
    canonicalTracks: ["机器人", "智能交通"],
  },
  {
    id: "user-source-source-track-1ihs8gk-79857b8f07bb66af",
    observedTrack: "半导体",
    canonicalTracks: ["新材料"],
  },
  {
    id: "user-source-source-manual-0f2ec1b400afc6c5-0d6ce12ec333c96b",
    observedTrack: "机器人",
    canonicalTracks: ["AI智能终端", "AI / AGI"],
  },
  {
    id: "professional-media-ars-technica-a9e7d80754e6f186",
    observedTrack: "Web3",
    canonicalTracks: ["AI / AGI", "AI安全"],
  },
  {
    id: "user-source-source-manual-a729f43ed853bbb2-1fef709088455404",
    observedTrack: "新能源",
    canonicalTracks: ["AI / AGI", "AI安全"],
  },
  {
    id: "user-source-source-zdnet-407c7af6f0899076",
    observedTrack: "商业航天",
    canonicalTracks: ["AI / AGI", "AI安全"],
  },
  {
    id: "official-helion-7df714571d811ffc",
    observedTrack: "新能源",
    canonicalTracks: ["可控核聚变"],
  },
];

test("reviewed technology corrections remain stable when source events roll out of the live snapshot", () => {
  const items = getChannelUpdateDirectory("technology").items;
  const sample = items.find((item) => item.track);
  assert.ok(sample);

  for (const fixture of reviewedCorrectionFixtures) {
    const syntheticItem: ChannelUpdateItem = {
      ...sample,
      id: fixture.id,
      track: fixture.observedTrack,
    };
    const correction = canonicalTracksForItem(syntheticItem);
    assert.equal(correction.applied, true, `${fixture.id} correction is no longer applied`);
    assert.deepEqual(
      correction.canonicalTracks,
      fixture.canonicalTracks,
      `${fixture.id} has stale canonical tracks`,
    );
  }

  for (const item of items.filter((candidate) =>
    candidate.classifications?.includes("规范赛道纠错"),
  )) {
    const correction = canonicalTracksForItem(item);
    assert.equal(correction.applied, true, `${item.id} is marked corrected without an active correction`);
    assert.deepEqual(
      item.publicTracks,
      correction.canonicalTracks,
      `${item.id} publication does not match its reviewed correction`,
    );
  }
});

test("technology publication curation stays registered independently of rolling source retention", () => {
  const source = readFileSync(new URL("../lib/channel-updates.ts", import.meta.url), "utf8");

  for (const fragment of [
    '"user-x-googledeepmind-25b4f20ecfb62f41": {',
    "AlphaEvolve 用 AI 将矩阵乘法指数上界推进至 ω < 2.371177",
    "https://arxiv.org/abs/2608.16884",
    '"official-helion-7df714571d811ffc": {',
    "Helion 完成 Vela 可控核聚变脉冲电源规模测试并推进 Tiny Merge 集成",
    "1 Hz",
    "11 GJ",
  ]) {
    assert.ok(source.includes(fragment), `technology publication curation lost: ${fragment}`);
  }

  const items = getChannelUpdateDirectory("technology").items;
  const deepMind = items.find(
    (item) => item.id === "user-x-googledeepmind-25b4f20ecfb62f41",
  );
  if (deepMind) {
    assert.equal(
      deepMind.title,
      "AlphaEvolve 用 AI 将矩阵乘法指数上界推进至 ω < 2.371177",
    );
    assert.equal(deepMind.label, "论文");
    assert.deepEqual(deepMind.keywords, ["论文"]);
    assert.match(deepMind.summary, /2\.371339.*2\.371177/u);
    assert.ok(
      deepMind.sources?.some(
        (sourceItem) => sourceItem.href === "https://arxiv.org/abs/2608.16884",
      ),
    );
  }

  const helion = items.find(
    (item) => item.id === "official-helion-7df714571d811ffc",
  );
  if (helion) {
    assert.match(helion.title, /Vela.*Tiny Merge/u);
    assert.match(helion.summary, /1 Hz.*11 GJ/u);
    assert.equal(helion.track, "新能源");
    assert.deepEqual(helion.publicTracks, ["可控核聚变"]);
  }
});

test("technology directory rejects known collisions while preserving long-tail research semantics", () => {
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

  const retainedCases = [
    {
      topicCount: 0,
      track: "AI / AGI",
      title: "MillworkSuite launches AI estimating and direct-to-CAD",
      summary: "The product converts architectural documents into a priced scope.",
      sourceGrade: "B" as const,
    },
    {
      topicCount: 0,
      track: "AI / AGI",
      title: "Nscale seeks funding for an AI data center",
      summary: "The company is expanding infrastructure capacity.",
      qualityStatus: "可用",
      sourceGrade: "C" as const,
    },
    {
      topicCount: 0,
      track: "商业航天",
      title: "朱雀三号完成新一轮火箭试验",
      summary: "商业火箭项目继续推进轨道发射准备。",
      sourceGrade: "B" as const,
    },
    {
      topicCount: 1,
      track: "AI / AGI",
      title: "AlphaEvolve 用 AI 将矩阵乘法指数上界推进至 ω < 2.371177",
      summary: "研究团队使用 AI 与现代优化方法改进矩阵乘法指数上界。",
      sourceGrade: "A" as const,
    },
    {
      topicCount: 0,
      track: "可控核聚变",
      title: "Helion 完成 Vela 可控核聚变脉冲电源规模测试并推进 Tiny Merge 集成",
      summary: "Vela 以 1 Hz 运行，团队继续推进聚变试验台集成。",
      sourceGrade: "A" as const,
    },
  ];

  for (const retainedCase of retainedCases) {
    assert.equal(
      technologyEventHasResearchEvidence(retainedCase),
      true,
      `relevant long-tail technology semantics were rejected: ${retainedCase.title}`,
    );
  }
});
