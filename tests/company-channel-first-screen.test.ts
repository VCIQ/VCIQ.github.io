import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync("app/companies/page.tsx", "utf8");
const tabs = readFileSync("components/company-channel-tabs.tsx", "utf8");
const tabStyles = readFileSync("components/company-channel-tabs.module.css", "utf8");
const directoryStyles = readFileSync("components/company-directory.module.css", "utf8");
const eventStyles = readFileSync("components/channel-update-directory.module.css", "utf8");

test("company header exposes the curated event-cluster count with the correct channel number", () => {
  assert.match(page, /05 \/ CORE COMPANIES/);
  assert.match(page, /curateCompanyUpdateDirectory\(getChannelUpdateDirectory\("companies"\)\)/);
  assert.match(page, /companyUpdates\.items\.length\} 个重要事件簇/);
});

test("company directory and important events are keyboard-accessible tabs", () => {
  assert.match(page, /<CompanyChannelTabs/);
  assert.doesNotMatch(page, /<ChannelSplitLayout/);
  assert.match(tabs, /role="tablist"/);
  assert.match(tabs, /<strong>公司档案<\/strong>/);
  assert.match(tabs, /<strong>重要事件<\/strong>/);
  assert.match(tabs, /role="tabpanel"/);
  assert.match(tabs, /ArrowLeft/);
  assert.match(tabs, /ArrowRight/);
});

test("company workspace removes inner scroll and adapts controls for mobile", () => {
  assert.match(eventStyles, /\.directory\[data-layout="workspace"\] \.list \{[\s\S]*max-height:\s*none;[\s\S]*overflow:\s*visible;/);
  assert.match(directoryStyles, /@media \(max-width: 640px\)[\s\S]*min-height:\s*44px/);
  assert.match(directoryStyles, /@media \(max-width: 920px\)[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\)/);
  assert.match(tabStyles, /@media \(max-width: 720px\)/);
});
