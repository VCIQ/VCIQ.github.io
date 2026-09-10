import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("deep research applies reviewed metadata and person-directory enrichment", async () => {
  const source = await readFile(
    new URL("../app/research-agent/investigate/research-investigation-client.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /applyArticleMetadataReviews\(merged\)/u);
  assert.match(source, /loadPersonDirectoryResearchEvents/u);
  assert.match(source, /homepageMaterialUrl\(canonicalEvent\.source\.url\)/u);
  assert.match(source, /mergeHomepagePersonChannelEvents\([\s\S]*?\[canonicalEvent\][\s\S]*?sameMaterial[\s\S]*?merged\.articles/u);
  assert.match(source, /eventId\.startsWith\("person-directory:"\)/u);
});

test("deep research shares the same summary and source-link semantics as homepage cards", async () => {
  const source = await readFile(
    new URL("../app/research-agent/investigate/research-investigation-client.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /homepageEventSummary\(item\)/u);
  assert.match(source, /homepageSourceEvidence\(item\)/u);
  assert.match(source, /来源链接 \{sourceEvidence\?\.totalLinks/u);
  assert.match(source, /其他来源链接 \{sourceEvidence\?\.additionalLinks\.length/u);
  assert.match(source, /链接数量不等同于独立信源或交叉验证次数/u);
  assert.doesNotMatch(source, /<p>关联来源 \{item\.relatedSources\?\.length/u);
});
