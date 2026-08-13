import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(path, "utf8");
const layout = read("app/layout.tsx");
const homepage = read("app/page.tsx");
const liveStatus = read("components/live-status.tsx");
const socialImageRoute = read("app/og-image.png/route.tsx");
const shareImage = read("components/site-share-image.tsx");

test("root metadata describes and previews the public research homepage", () => {
  assert.match(layout, /metadataBase: new URL\(SITE_URL\)/);
  assert.match(layout, /siteName: SITE_NAME/);
  assert.match(layout, /card: "summary_large_image"/);
  assert.doesNotMatch(layout, /alternates: \{ canonical:/);
  assert.doesNotMatch(layout, /openGraph:\s*\{[\s\S]*?\burl:/);
  assert.doesNotMatch(layout, /application\/ld\+json|CollectionPage|"@type": "WebSite"/);
  assert.match(homepage, /alternates: \{ canonical: "\/" \}/);
  assert.match(homepage, /openGraph:\s*\{[\s\S]*?url: "\/"/);
  assert.match(homepage, /type="application\/ld\+json"/);
  assert.match(homepage, /"@type": "CollectionPage"/);
});

test("public shell includes a keyboard skip target", () => {
  assert.match(layout, /className="skip-link" href="#main-content"/);
  assert.match(layout, /id="main-content" tabIndex=\{-1\}/);
});

test("header status distinguishes the event snapshot from whole-site health", () => {
  assert.match(liveStatus, /@\/public\/data\/articles\.json/);
  assert.match(liveStatus, /@\/public\/data\/pipeline_health\.json/);
  assert.match(liveStatus, /事件快照已更新/);
  assert.match(liveStatus, /全站部分过期/);
  assert.match(liveStatus, /pipelineCompleted === true/);
  assert.match(liveStatus, /qualityGate\?\.passed === true/);
  assert.match(liveStatus, /href="\/data\/pipeline_health\.json"/);
  assert.match(liveStatus, /https:\/\/vciq\.github\.io\/build-provenance\.json/);
  assert.match(liveStatus, /构建记录/);
  assert.doesNotMatch(liveStatus, /资料已同步/);
});

test("social previews use one static PNG route and a consistent 1200 by 630 design", () => {
  assert.match(layout, /url: "\/og-image\.png"/);
  assert.match(homepage, /url: "\/og-image\.png"/);
  assert.match(socialImageRoute, /new ImageResponse\(<SiteShareImage \/>, SITE_SHARE_IMAGE_SIZE\)/);
  assert.match(socialImageRoute, /dynamic = "force-static"/);
  assert.match(shareImage, /width: 1200/);
  assert.match(shareImage, /height: 630/);
  assert.match(shareImage, /核心技术 · 核心赛道 · 核心人物 · 核心公司/);
});
