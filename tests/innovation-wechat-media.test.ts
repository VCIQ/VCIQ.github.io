import assert from "node:assert/strict";
import test from "node:test";
import { parseInnovationWechatMedia } from "../lib/innovation-wechat-media";

const article = {
  url: "https://mp.weixin.qq.com/s/SYNTHETIC_ARTICLE",
  title: "合成测试报道",
  publisher: "合成测试公众号",
  publishedAt: "2026-10-22",
};

test("public WeChat media supports both canonical article links and orders by original publication date", () => {
  const other = { ...article, url: "https://mp.weixin.qq.com/s?__biz=U1lO%3D&mid=12&idx=1", publishedAt: "2026-10-23" };
  assert.deepEqual(parseInnovationWechatMedia([]), []);
  assert.deepEqual(parseInnovationWechatMedia([article, other]), [other, article]);
});

test("public WeChat media rejects private fields, tracking and unsafe URLs, duplicates and invalid dates", () => {
  for (const input of [
    [{ ...article, excerpt: "private" }],
    [{ ...article, url: `${article.url}?token=tracking` }],
    [{ ...article, url: `${article.url}\n` }],
    [{ ...article, url: "https://mp.weixin.qq.com.evil.example/s/ARTICLE" }],
    [{ ...article, title: "<img>" }],
    [{ ...article, publisher: "" }],
    [{ ...article, publishedAt: "2026-02-29" }],
    [article, article],
  ]) {
    assert.throws(() => parseInnovationWechatMedia(input), /Invalid public innovation WeChat media snapshot/u);
  }
});
