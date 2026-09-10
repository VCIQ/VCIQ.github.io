import assert from "node:assert/strict";
import test from "node:test";
import {
  findHomepagePersonMaterialReview,
  homepagePersonMaterialReviews,
} from "../lib/homepage-person-material-reviews";
import {
  mergeHomepagePersonChannelEvents,
  projectHomepagePersonDirectoryEvents,
  type HomepagePersonDirectoryItem,
  type HomepagePersonProfile,
} from "../lib/homepage-person-channel-events";

const feifei: HomepagePersonProfile = { slug: "fei-fei-li", name: "李飞飞" };
const hetingbo: HomepagePersonProfile = { slug: "person-918f5d53a8", name: "何庭波" };
const interview: HomepagePersonDirectoryItem = {
  id: "person-event-4bmdge",
  eventClusterId: "person-event-4bmdge",
  title: "对话 IDEA 张磊：「不以动作为输入条件，就不叫世界模型」",
  summary: "李飞飞 · 斯坦福大学教授、计算机视觉研究者",
  href: "https://www.leiphone.com/category/academic/wQny8Cer4EJz0RAU.html",
  source: "雷峰网",
  label: "演讲",
  context: "李飞飞",
  sortAt: "2026-08-06T00:00:00.000Z",
};
const researchReport: HomepagePersonDirectoryItem = {
  id: "person-event-1higdg5",
  eventClusterId: "person-event-1higdg5",
  title: "华为更新韬定律论文 最新机构解读来了 后道测试设备环节直接受益？",
  summary: "何庭波 · 企业家",
  href: "https://finance.eastmoney.com/a/202609073866203674.html",
  source: "东方财富",
  label: "论文",
  context: "何庭波",
  sortAt: "2026-09-07T00:00:00.000Z",
};

test("source-reviewed background mention is hidden only from the directory feed", () => {
  const events = projectHomepagePersonDirectoryEvents([interview], [feifei]);
  assert.equal(events.length, 1);
  assert.deepEqual(mergeHomepagePersonChannelEvents([], events), []);
});

test("historical research event retains its ID and corrects the person's role", () => {
  const [event] = projectHomepagePersonDirectoryEvents([interview], [feifei]);
  assert.ok(event);
  assert.equal(event.id, "person-directory:person-event-4bmdge");
  assert.equal(event.source.url, interview.href);
  assert.match(event.summary, /IDEA 张磊/u);
  assert.match(event.summary, /不代表李飞飞受访或演讲/u);
  assert.ok(event.qualitySignals?.some((signal) => signal.includes("仅背景提及")));
});

test("reported paper-update actor remains eligible but the URL is a media report", () => {
  const [event] = projectHomepagePersonDirectoryEvents([researchReport], [hetingbo]);
  assert.ok(event);
  assert.equal(event.personSlug, hetingbo.slug);
  assert.equal(event.type, "论文");
  assert.equal(event.source.level, "媒体报道");
  assert.match(event.summary, /非论文原文/u);
  assert.deepEqual(mergeHomepagePersonChannelEvents([], [event]), [event]);
});

test("reviewed relation never upgrades a D-grade source", () => {
  const [event] = projectHomepagePersonDirectoryEvents(
    [{ ...researchReport, sourceGrade: "D" }], [hetingbo],
  );
  assert.ok(event);
  assert.equal(event.source.level, "待交叉验证");
});

test("review exceptions are scoped to person plus exact source material", () => {
  assert.equal(findHomepagePersonMaterialReview("other-person", interview.href, interview.title), undefined);
  assert.equal(findHomepagePersonMaterialReview(feifei.slug, "https://example.org/other", interview.title), undefined);
  assert.equal(findHomepagePersonMaterialReview(feifei.slug, interview.href, "新访谈"), undefined);
  assert.equal(findHomepagePersonMaterialReview(undefined, interview.href, interview.title), undefined);
});

test("source identity permits tracking suffixes but preserves case-sensitive paths", () => {
  const expected = findHomepagePersonMaterialReview(feifei.slug, interview.href, interview.title);
  assert.ok(expected);
  assert.equal(findHomepagePersonMaterialReview(feifei.slug, `${interview.href}?utm_source=test#top`, interview.title), expected);
  assert.equal(findHomepagePersonMaterialReview(feifei.slug, interview.href.toLowerCase(), interview.title), undefined);
  assert.equal(findHomepagePersonMaterialReview(feifei.slug, `${interview.href}?article=other`, interview.title), undefined);
});

test("malformed or credential-bearing review URLs do not match", () => {
  for (const url of ["not a URL", "javascript:alert(1)", interview.href.replace("https://", "https://user:pass@")]) {
    assert.equal(findHomepagePersonMaterialReview(feifei.slug, url, interview.title), undefined);
  }
});

test("unreviewed strong-type records keep their existing behavior", () => {
  for (const label of ["采访", "演讲", "论文", "公开对话", "著作", "股东信", "官方资料", "公开材料"]) {
    const [event] = projectHomepagePersonDirectoryEvents(
      [{ ...interview, label, href: "https://example.com/different-material", title: "无需以标题姓名代替角色证据" }], [feifei],
    );
    assert.ok(event);
    assert.equal(event.summary, interview.summary);
    assert.deepEqual(mergeHomepagePersonChannelEvents([], [event]), [event]);
  }
});

test("generic-material title gate and formal-entity gate are not bypassed", () => {
  assert.deepEqual(projectHomepagePersonDirectoryEvents([researchReport], []), []);
  assert.deepEqual(projectHomepagePersonDirectoryEvents(
    [{ ...interview, label: "人物材料" }], [feifei],
  ), []);
});

test("canonical article input is unchanged by this directory-only correction", () => {
  const [event] = projectHomepagePersonDirectoryEvents([interview], [feifei]);
  assert.ok(event);
  const canonical = { ...event, id: "article-1", sourceId: "canonical-article" };
  assert.deepEqual(mergeHomepagePersonChannelEvents([canonical], [event]), [canonical]);
});

test("projection and merge do not rewrite the archival inputs", () => {
  const items = [interview, researchReport];
  const snapshot = structuredClone(items);
  const events = projectHomepagePersonDirectoryEvents(items, [feifei, hetingbo]);
  const eventSnapshot = structuredClone(events);
  mergeHomepagePersonChannelEvents([], events);
  assert.deepEqual(items, snapshot);
  assert.deepEqual(events, eventSnapshot);
});

test("every review keeps an auditable evidence reference and bounded identity", () => {
  const keys = homepagePersonMaterialReviews.map((review) => `${review.personSlug}|${review.sourceUrl}|${review.expectedTitle}`);
  assert.equal(new Set(keys).size, keys.length);
  for (const review of homepagePersonMaterialReviews) {
    assert.match(review.evidenceUrl, /^https:\/\//u);
    assert.ok(review.evidenceNote && review.reviewedAt && review.expectedTitle);
  }
});
