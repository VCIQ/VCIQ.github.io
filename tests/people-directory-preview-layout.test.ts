import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Lock the index/detail presentation boundary without changing person research data.
const page = readFileSync("app/people/page.tsx", "utf8");
const styles = readFileSync("app/people/page.module.css", "utf8");

test("people directory keeps only the two decision-useful preview rows", () => {
  assert.match(page, /<b>为什么重要<\/b>/);
  assert.match(page, /<b>最新变化<\/b>/);
  assert.doesNotMatch(page, /<b>下一步观察<\/b>/);
});

test("fuller person research stays in profiles while event news moves to the homepage", () => {
  assert.match(page, /人物库解释关键人物的技术判断、组织选择和路线演进/);
  assert.match(page, /统一进入首页“人物”频道/);
});

test("people directory avoids repeated per-card row classes", () => {
  assert.doesNotMatch(page, /styles\.researchRow/);
  assert.doesNotMatch(page, /styles\.latestChange/);
  assert.match(styles, /\.cardResearch > div \{/);
  assert.match(styles, /\.cardResearch > div:first-child p \{/);
});
