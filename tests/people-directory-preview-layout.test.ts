import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Lock the index/detail presentation boundary without changing person research data.
const page = readFileSync("app/people/page.tsx", "utf8");

test("people directory keeps only the two decision-useful preview rows", () => {
  assert.match(page, /<b>为什么重要<\/b>/);
  assert.match(page, /<b>最新变化<\/b>/);
  assert.doesNotMatch(page, /<b>下一步观察<\/b>/);
});

test("fuller person research remains delegated to the detail page", () => {
  assert.match(page, /完整判断、技术主线、观点演进、组织关系和事件证据进入人物详情查看/);
});
