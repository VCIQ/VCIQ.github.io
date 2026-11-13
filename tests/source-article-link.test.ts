import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SourceArticleLink } from "../components/source-article-link";

test("expiring WeChat link renders a status, not a clickable href", () => {
  const html = renderToStaticMarkup(createElement(SourceArticleLink, {
    href: "https://mp.weixin.qq.com/s?new=1&signature=abc&timestamp=1794138303",
  }, "微容科技，IPO成功过会"));
  assert.match(html, /原文链接待更新/u);
  assert.match(html, /data-source-link-status="wechat-unverified"/u);
  assert.doesNotMatch(html, /<a /u);
  assert.doesNotMatch(html, /signature=abc/u);
});

test("shareable WeChat and non-WeChat sources remain clickable", () => {
  for (const href of [
    "https://mp.weixin.qq.com/s/hNvk76l8FzVEhglIQqebJg",
    "https://www.yunfu.gov.cn/zxzx/bmdt/content/post_2052905.html",
  ]) {
    const html = renderToStaticMarkup(createElement(SourceArticleLink, {
      href,
    }, "来源"));
    assert.match(html, /<a /u);
    assert.match(html, /target="_blank"/u);
  }
});


test("block link fallback preserves valid flow content", () => {
  const html = renderToStaticMarkup(createElement(SourceArticleLink, {
    href: "https://mp.weixin.qq.com/s?new=1&signature=abc&timestamp=1794138303",
    fallbackAs: "div",
  }, createElement("div", null, "事件摘要")));
  assert.match(html, /^<div /u);
  assert.match(html, /<div>事件摘要<\/div>/u);
  assert.doesNotMatch(html, /<a /u);
});

test("channel source fallback preserves existing inspection data attributes", () => {
  const html = renderToStaticMarkup(createElement(SourceArticleLink, {
    href: "https://mp.weixin.qq.com/s?new=1&signature=abc&timestamp=1794138303",
    fallbackAs: "div",
    "data-intelligence-item": "true",
    "data-intelligence-title": "保留原文元数据",
  }, createElement("h2", null, "待复核")));
  assert.match(html, /^<div /u);
  assert.match(html, /data-intelligence-item="true"/u);
  assert.match(html, /data-intelligence-title="保留原文元数据"/u);
  assert.doesNotMatch(html, /<a /u);
});
