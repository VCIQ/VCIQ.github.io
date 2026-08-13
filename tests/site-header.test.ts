import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../components/site-header.tsx", import.meta.url), "utf8");

test("settings gear opens the protected tracking admin directly", () => {
  assert.match(source, /const TRACKING_ADMIN_URL = "https:\/\/vciq-tracking-console\.pages\.dev\/";/);
  assert.match(source, /href=\{TRACKING_ADMIN_URL\}/);
  assert.match(source, /target="_blank"/);
  assert.match(source, /rel="noopener noreferrer"/);
  assert.match(source, /aria-label="追踪管理台（外部链接，在新标签页打开）"/);
  assert.doesNotMatch(source, /href="\/tracking"[^>]*>\s*<Settings/);
});

test("primary navigation exposes current-route and mobile disclosure semantics", () => {
  assert.match(source, /usePathname\(\)/);
  assert.match(source, /id=\{PRIMARY_NAVIGATION_ID\}/);
  assert.match(source, /aria-current=\{current \? "page" : undefined\}/);
  assert.match(source, /aria-controls=\{PRIMARY_NAVIGATION_ID\}/);
  assert.match(source, /aria-expanded=\{open\}/);
  assert.match(source, /aria-label=\{open \? "收起导航" : "展开导航"\}/);
  assert.match(source, /if \(event\.key === "Escape"\) setOpen\(false\)/);
});

test("mobile navigation repeats hidden header tools as labeled destinations", () => {
  assert.match(source, /className="mobile-nav-tools"/);
  assert.match(source, /className="header-optional-status"/);
  assert.equal(source.match(/className="icon-button header-optional-tool"/gu)?.length, 3);
  for (const label of [
    "研究助手",
    "收藏",
    "追踪管理台 ↗",
    "全局搜索",
    "数据健康",
    "构建记录",
  ]) {
    assert.match(source, new RegExp(label));
  }
});
