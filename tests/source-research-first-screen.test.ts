import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync("app/sources/page.tsx", "utf8");
const styles = readFileSync("app/sources/page.module.css", "utf8");

test("source lifecycle methodology is collapsed before tracked source cards", () => {
  assert.match(page, /<details className=\{styles\.lifecycle\}>/);
  assert.match(page, /Candidate → Tracked → Core/);
  assert.match(styles, /\.lifecycle summary[\s\S]*min-height:\s*54px/);
});

test("source cards expose compact coverage counts", () => {
  assert.match(page, /className=\{styles\.coverageRow\}/);
  assert.match(page, /source\.sectors\.length/);
  assert.match(page, /source\.companies\.length/);
  assert.match(page, /source\.people\.length/);
  assert.match(page, /source\.keywords\.length/);
});
