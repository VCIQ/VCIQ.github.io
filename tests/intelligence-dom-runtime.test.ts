import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = process.cwd();
const read = (relativePath: string) => readFileSync(path.join(ROOT, relativePath), "utf8");

const runtime = read("lib/intelligence-dom-runtime.ts");
const favorite = read("components/homepage-favorite-controls.tsx");
const hotness = read("components/intelligence-hotness-controls.tsx");

const publicControls = [favorite, hotness];

test("public intelligence controls share one MutationObserver", () => {
  assert.equal((runtime.match(/new MutationObserver/g) ?? []).length, 1);
  for (const source of publicControls) {
    assert.equal((source.match(/new MutationObserver/g) ?? []).length, 0);
    assert.match(source, /subscribeIntelligenceDom/);
  }
});

test("shared observer ignores mutations created by its own mounted controls", () => {
  assert.match(runtime, /data-intelligence-favorite-mount/);
  assert.match(runtime, /data-intelligence-hotness-mount/);
  assert.doesNotMatch(runtime, /data-intelligence-capture-mount/);
  assert.match(runtime, /records\.every\(isControlOnlyMutation\)/);
  assert.match(runtime, /changedNodes\.every\(isInsideControlMount\)/);
});

test("shared DOM scan runs favorite before hotness", () => {
  assert.match(favorite, /subscribeIntelligenceDom\(scan, \{ priority: 10 \}\)/);
  assert.match(hotness, /subscribeIntelligenceDom\(scan, \{ priority: 30 \}\)/);
  assert.match(runtime, /left\.priority - right\.priority/);
});

test("public DOM runtime has no tracking-capture scope", () => {
  assert.match(favorite, /isIntelligenceDomRow\(row, "favorite"\)/);
  assert.match(hotness, /isIntelligenceDomRow\(row, "hotness"\)/);
  assert.doesNotMatch(runtime, /"capture"/);
  assert.match(runtime, /\.favorite-intelligence-card/);
  assert.match(runtime, /\.timeline > div/);
  assert.match(runtime, /\.market-news-item\[href\]/);
});
