import assert from "node:assert/strict";
import test from "node:test";

import {
  hasPersonResearchAction,
  isLowSignalPersonTitle,
  isTrustedPersonChangeSource,
} from "../lib/person-material-quality";
import { aggregatePeopleUpdateDirectory } from "../lib/people-event-updates";

test("person material quality rejects clickbait and social-event association", () => {
  assert.equal(isLowSignalPersonTitle("JUST RECORDED: Elon Musk Leaves Audience Speechless (MUST WATCH)"), true);
  assert.equal(isLowSignalPersonTitle("Gwyneth Paltrow is allegedly throwing a party for Sam Altman"), true);
  assert.equal(isLowSignalPersonTitle("造AI的人比用AI的人更分裂：李飞飞捅破了这层窗户纸"), true);
  assert.equal(isLowSignalPersonTitle("【双语音+文稿】完整版演讲：宣布多项重大消息"), true);
  assert.equal(isLowSignalPersonTitle("预言未来12个月将改变世界"), true);
  assert.equal(isLowSignalPersonTitle("WATCH NOW: FULL INTERVIEW"), true);
  assert.equal(isLowSignalPersonTitle("🔥听皮衣刀客聊透AI未来"), true);
  assert.equal(isLowSignalPersonTitle("OpenAI 发布新的模型能力评估"), false);
});

test("person research actions cover technical and organizational changes", () => {
  assert.equal(hasPersonResearchAction("DeepMind CEO steps aside amid leadership change"), true);
  assert.equal(hasPersonResearchAction("宇树科技推进机器人模型自进化研发"), true);
  assert.equal(hasPersonResearchAction("A private dinner in the Hamptons"), false);
});

test("latest-change source policy rejects aggregators and keeps traceable media", () => {
  assert.equal(isTrustedPersonChangeSource("Google News 英文", "https://news.google.com/example"), false);
  assert.equal(isTrustedPersonChangeSource("Wikidata", "https://www.wikidata.org/wiki/Q1"), false);
  assert.equal(isTrustedPersonChangeSource("Reuters", "https://reuters.com/example"), true);
  assert.equal(isTrustedPersonChangeSource("媒体报道 · 雷峰网", "https://leiphone.com/example"), true);
});

test("people update directory removes generic association and retains research actions", () => {
  const directory = aggregatePeopleUpdateDirectory({
    title: "人物材料更新目录",
    description: "test",
    generatedAt: "2026-08-23T00:00:00Z",
    items: [
      {
        id: "social",
        title: "Celebrity is allegedly throwing a dinner for OpenAI CEO Sam Altman",
        summary: "Sam Altman",
        href: "https://example.com/social",
        source: "Lifestyle Media",
        label: "人物材料",
        context: "Sam Altman",
        date: "2026-08-22",
        dateOriginal: "2026-08-22",
        datePrecision: "exact",
        sortAt: "2026-08-22T00:00:00Z",
        keywords: ["人物材料"],
      },
      {
        id: "generic-post",
        title: "The greatest privilege is working with incredible people",
        summary: "Sam Altman",
        href: "https://example.com/generic",
        source: "Public Post",
        label: "人物材料",
        context: "Sam Altman",
        date: "2026-08-21",
        dateOriginal: "2026-08-21",
        datePrecision: "exact",
        sortAt: "2026-08-21T00:00:00Z",
        keywords: ["人物材料"],
      },
      {
        id: "release",
        title: "OpenAI 发布新的模型能力评估",
        summary: "Sam Altman",
        href: "https://example.com/release",
        source: "OpenAI",
        label: "人物材料",
        context: "Sam Altman",
        date: "2026-08-20",
        dateOriginal: "2026-08-20",
        datePrecision: "exact",
        sortAt: "2026-08-20T00:00:00Z",
        keywords: ["人物材料"],
      },
    ],
  });

  assert.equal(directory.items.length, 1);
  assert.equal(directory.items[0]?.title, "OpenAI 发布新的模型能力评估");
});
