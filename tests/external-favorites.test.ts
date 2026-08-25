import assert from "node:assert/strict";
import test from "node:test";

import {
  buildExternalFavoriteInput,
  canonicalExternalArticleUrl,
  externalFavoriteId,
  isWeChatArticleUrl,
  manualTextHrefForFavorite,
  researchLeadHrefForFavorite,
} from "../lib/external-favorites";

test("external article urls are canonicalized without common tracking parameters", () => {
  const url = canonicalExternalArticleUrl(
    "https://mp.weixin.qq.com/s/kb8iLCQ_xfWt1Q-vjMezSw?utm_source=test&from=share#fragment",
  );
  assert.equal(url, "https://mp.weixin.qq.com/s/kb8iLCQ_xfWt1Q-vjMezSw");
});

test("WeChat public article URLs are detected without broad host false positives", () => {
  assert.equal(isWeChatArticleUrl("https://mp.weixin.qq.com/s/kb8iLCQ_xfWt1Q-vjMezSw"), true);
  assert.equal(isWeChatArticleUrl("https://mp.weixin.qq.com/s?__biz=test&mid=1"), true);
  assert.equal(isWeChatArticleUrl("https://mp.weixin.qq.com/cgi-bin/home?t=home/index"), false);
  assert.equal(isWeChatArticleUrl("https://example.com/s/test"), false);
});

test("external favorite input preserves research metadata without mirroring article content", () => {
  const input = buildExternalFavoriteInput({
    url: "https://example.com/research/article",
    title: " 高价值研究文章 ",
    summary: " 记录为什么值得持续追踪。 ",
    sourceName: "Example Research",
    category: "technology",
    keywords: "Agent | Runtime | Agent",
    sectors: "AI / AGI | 机器人",
    publishedAt: "2026-08-23",
  });

  assert.ok(input);
  assert.equal(input.href, "https://example.com/research/article");
  assert.equal(input.channel, "technology");
  assert.equal(input.channelLabel, "技术 / 赛道线索");
  assert.deepEqual(input.keywords, ["Agent", "Runtime"]);
  assert.deepEqual(input.sectors, ["AI / AGI", "机器人"]);
  assert.equal(input.sources?.[0]?.name, "Example Research");
  assert.equal(input.publishedAt, "2026-08-23");
});

test("external favorite ids are stable for canonical-equivalent urls", () => {
  assert.equal(
    externalFavoriteId("https://example.com/a?utm_source=x"),
    externalFavoriteId("https://example.com/a"),
  );
});

test("external favorites bridge into the protected research-lead capture flow", () => {
  const input = buildExternalFavoriteInput({
    url: "https://example.com/a",
    title: "Article A",
    summary: "Useful evidence",
    sourceName: "Example",
    keywords: ["Agent"],
    sectors: ["AI / AGI"],
  });
  assert.ok(input);

  const capture = researchLeadHrefForFavorite({
    ...input,
    keywords: input.keywords ?? [],
    sectors: input.sectors ?? [],
    sources: input.sources ?? [],
  });
  const url = new URL(capture);
  assert.equal(url.pathname, "/capture");
  assert.equal(url.searchParams.get("url"), "https://example.com/a");
  assert.equal(url.searchParams.get("title"), "Article A");
  assert.match(url.searchParams.get("channel") ?? "", /^favorites:/);
});

test("restricted articles can open the protected manual-text capture with the same metadata", () => {
  const input = buildExternalFavoriteInput({
    url: "https://mp.weixin.qq.com/s/kb8iLCQ_xfWt1Q-vjMezSw",
    title: "微信研究文章",
    summary: "值得进入研究线索。",
    sourceName: "示例公众号",
    keywords: ["Agent"],
    sectors: ["AI / AGI"],
  });
  assert.ok(input);

  const manual = manualTextHrefForFavorite({
    ...input,
    keywords: input.keywords ?? [],
    sectors: input.sectors ?? [],
    sources: input.sources ?? [],
  });
  const url = new URL(manual);
  assert.equal(url.pathname, "/capture/manual-text");
  assert.equal(url.searchParams.get("url"), "https://mp.weixin.qq.com/s/kb8iLCQ_xfWt1Q-vjMezSw");
  assert.equal(url.searchParams.get("title"), "微信研究文章");
  assert.equal(url.searchParams.get("source"), "示例公众号");
  assert.match(url.searchParams.get("keywords") ?? "", /Agent/);
});
