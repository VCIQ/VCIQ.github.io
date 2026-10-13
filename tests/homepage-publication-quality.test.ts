import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { assessHomepagePublication, admitHomepageEvents, normalizeHomepageText } from "../lib/homepage-publication-quality";

const item = (title: string, extra = {}) => ({title, summary:"对应文章的有效摘要。", type:"技术突破", source:{url:"https://example.com/article"}, ...extra});

test("routine trading and an observed report sales page do not occupy the research feed", () => {
  for (const title of ["蓝箭电子(301348)10月9日主力资金净卖出795.25万元", "港股收评:恒指涨0.25%", "科创芯片ETF获资金持续加码"]) {
    assert.equal(assessHomepagePublication(item(title)).reason, "routine-market-trading");
  }
  assert.equal(assessHomepagePublication(item("半导体特种气体市场规模、份额、增长,2034年", {source:{url:"https://straitsresearch.com/zh/report/semiconductor-specialty-gas-market"}})).admitted, false);
  for (const title of ["半导体公司完成数亿元A轮融资", "机器人企业收购芯片研发团队", "交易所发布首只科技ETF上市公告", "半导体气体企业获得客户订单"]) {
    assert.equal(assessHomepagePublication(item(title)).admitted, true, title);
  }
});

test("HTML entities are decoded as plain text without changing source archive or metadata", () => {
  const original = {...item("芯片&amp;机器人", {summary:"量产&nbsp;进展 &quot;已披露&quot; &#xB7; &#20013;文"}), id:"stable-id", importance:100};
  const [projected] = admitHomepageEvents([original]);
  assert.equal(projected.title, "芯片&机器人");
  assert.equal(projected.summary, '量产 进展 "已披露" · 中文');
  assert.equal(original.title, "芯片&amp;机器人");
  assert.equal(projected.id, original.id);
  assert.equal(projected.importance, original.importance);
  assert.equal(normalizeHomepageText("&#x110000; &#xD800; &unknown;"), "&#x110000; &#xD800; &unknown;");
  assert.equal(normalizeHomepageText("&amp;nbsp;实际进展"), "实际进展");
});

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

