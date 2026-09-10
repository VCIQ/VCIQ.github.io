import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync("app/companies/page.tsx", "utf8");
const styles = readFileSync("app/companies/page.module.css", "utf8");

test("company library delegates event news to the homepage stream", () => {
  assert.doesNotMatch(page, /getChannelUpdateDirectory\("companies"\)/);
  assert.match(page, /showUpdates=\{false\}/);
  assert.match(page, /事件新闻统一进入首页“公司”频道/);
});

test("mobile company filters use a compact grid instead of stacked controls", () => {
  assert.match(styles, /@media \(max-width: 560px\)[\s\S]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(styles, /directory-search[\s\S]*grid-column:\s*1 \/ -1/);
  assert.match(styles, /directory-filters > span[\s\S]*display:\s*none/);
});
