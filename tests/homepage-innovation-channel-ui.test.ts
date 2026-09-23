import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const component = fs.readFileSync(
  new URL("../components/homepage-news-feed.tsx", import.meta.url),
  "utf8",
);
const page = fs.readFileSync(
  new URL("../app/page.tsx", import.meta.url),
  "utf8",
);
const packageJson = fs.readFileSync(
  new URL("../package.json", import.meta.url),
  "utf8",
);

test("homepage places innovation between latest and AI / AGI", () => {
  const latest = component.indexOf('{ id: "latest", label: "快讯" }');
  const innovation = component.indexOf('{ id: "innovation", label: "科创" }');
  const ai = component.indexOf('{ id: "ai", label: "AI / AGI"');
  assert.ok(latest >= 0);
  assert.ok(innovation > latest);
  assert.ok(ai > innovation);
});

test("innovation homepage channel uses projection membership instead of keyword-only admission", () => {
  assert.match(component, /matchesHomepageInnovationCapitalChannel/);
  assert.match(component, /buildHomepageInnovationCapitalIndex/);
  assert.match(component, /homepageInnovationCapitalAnnotation/);
  assert.doesNotMatch(
    component,
    /id: "innovation"[\s\S]{0,160}keywords:/u,
  );
  assert.match(component, /五大券商项目、上市生命周期、硬科技投资机构和成熟期候选/u);
  assert.match(component, /未核验证据不会自动推断辅导券商或上市板块/u);
});

test("innovation cards expose auditable context and research navigation", () => {
  assert.match(component, /科创关联/u);
  assert.match(component, /科创优先度/u);
  assert.match(component, /查看科创项目/u);
  assert.match(component, /href="\/innovation-capital\//u);
});

test("homepage server bootstrap includes innovation events outside ordinary tracked-sector aliases", () => {
  assert.match(page, /buildHomepageInnovationCapitalIndex/);
  assert.match(page, /matchesHomepageInnovationCapitalChannel/);
  assert.match(page, /rawInnovationCapitalFeed/);
  assert.match(page, /innovationCapitalFeed:/);
});

test("site builds regenerate the lightweight innovation projection", () => {
  assert.match(packageJson, /build:innovation-capital-feed/u);
  assert.match(packageJson, /build-innovation-capital-feed\.ts/u);
  assert.match(
    packageJson,
    /build:innovation-capital-feed && npm run build:search-index/u,
  );
});
