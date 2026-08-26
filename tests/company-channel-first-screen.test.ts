import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync("app/companies/page.tsx", "utf8");
const styles = readFileSync("app/companies/page.module.css", "utf8");

test("company header surfaces current event count", () => {
  assert.match(page, /getChannelUpdateDirectory\("companies"\)/);
  assert.match(page, /companyUpdates\.items\.length/);
});

test("mobile company filters use a compact grid instead of stacked controls", () => {
  assert.match(styles, /@media \(max-width: 560px\)[\s\S]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(styles, /directory-search[\s\S]*grid-column:\s*1 \/ -1/);
  assert.match(styles, /directory-filters > span[\s\S]*display:\s*none/);
});
