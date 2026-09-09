import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const feed = await readFile(
  new URL("../components/homepage-news-feed.tsx", import.meta.url),
  "utf8",
);
const splitLayout = await readFile(
  new URL("../components/channel-split-layout.tsx", import.meta.url),
  "utf8",
);

test("homepage exposes people and company streams after sector channels", () => {
  assert.match(feed, /\{ id: "hbm", label: "HBM"[\s\S]*\{ id: "people", label: "人物" \}[\s\S]*\{ id: "companies", label: "公司" \}/u);
});

test("people stream uses structured person evidence instead of name keywords", () => {
  assert.match(feed, /channelId === "people"/u);
  assert.match(feed, /Boolean\(item\.personSlug\)/u);
  assert.match(feed, /item\.type === "人物观点"/u);
  assert.match(feed, /item\.mentionedPeople\?\.length/u);
  assert.doesNotMatch(feed, /id: "people"[^\n]*keywords:/u);
});

test("company stream uses structured company evidence instead of company-name keywords", () => {
  assert.match(feed, /channelId === "companies"/u);
  assert.match(feed, /Boolean\(item\.companySlug\)/u);
  assert.match(feed, /item\.mentionedCompanies\?\.length/u);
  assert.doesNotMatch(feed, /id: "companies"[^\n]*keywords:/u);
});

test("research papers remain visibly typed inside topical homepage streams", () => {
  assert.match(feed, /item\.type === "论文" \? "研究 \/ 论文" : item\.type/u);
  assert.match(feed, /eventTypeLabel\(item\)/u);
});

test("technology research defaults to a directory-only layout", () => {
  assert.match(splitLayout, /showUpdates \?\? channel !== "technology"/u);
  assert.match(splitLayout, /shouldShowUpdates/u);
});
