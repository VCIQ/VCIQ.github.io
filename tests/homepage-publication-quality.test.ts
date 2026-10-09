import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { assessHomepagePublication, admitHomepageEvents } from "../lib/homepage-publication-quality";

const item = (title: string, extra = {}) => ({title, summary:"对应文章的有效摘要。", type:"技术突破", source:{url:"https://example.com/article"}, ...extra});

test("unrelated horoscope titles are rejected even with technology metadata", () => {
  const bad = item("水瓶座最容易显得笨", {sector:"新能源",importance:100,qualityStatus:"高可信"});
  assert.equal(assessHomepagePublication(bad).admitted, false);
  assert.equal(admitHomepageEvents([bad]).length, 0);
});

test("satellite constellations, scientific debunking and ordinary hard-tech events survive", () => {
  for (const title of ["低轨卫星星座完成组网测试", "心理学研究：星座运势如何造成认知偏差", "硅光芯片发布新产品", "机器人企业完成新一轮融资"]) {
    assert.equal(assessHomepagePublication(item(title)).admitted, true, title);
  }
});

test("routine share returns are regulatory disclosures, not IPO events", () => {
  for (const title of ["某公司股份变动月报表", "Monthly Return of Equity Issuer"]) {
    const original = item(title, {type:"IPO"});
    const [projected] = admitHomepageEvents([original]);
    assert.equal(projected.type, "监管文件");
    assert.equal(original.type, "IPO", "raw archive must remain immutable");
  }
  assert.equal(admitHomepageEvents([item("交易所受理IPO申请", {type:"IPO"})])[0].type, "IPO");
});

test("sidebar fragments and nonpublic protocol links cannot become public summaries", () => {
  assert.equal(assessHomepagePublication(item("芯片融资", {summary:"相关推荐：另一家公司获奖"})).admitted, false);
  assert.equal(assessHomepagePublication(item("芯片融资", {source:{url:"javascript:alert(1)"}})).admitted, false);
  assert.equal(assessHomepagePublication(item("芯片融资", {source:{url:"https://name:secret@example.com/"}})).admitted, false);
});

test("bootstrap and refreshed public article views share the data-free admission module", () => {
  const source = (path: string) => fs.readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
  assert.match(source("app/page.tsx"), /admitHomepageEvents\(snapshot\.articles\)/);
  assert.match(source("lib/use-articles.ts"), /admitHomepageEvents\(payload\.articles\)/);
  assert.doesNotMatch(source("lib/homepage-publication-quality.ts"), /public\/data|catalog-data|content-relevance/);
});
