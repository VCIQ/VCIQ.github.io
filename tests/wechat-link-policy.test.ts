import assert from "node:assert/strict";
import test from "node:test";
import { classifyWeChatArticleUrl, isNonDurableWeChatArticleUrl } from "../lib/wechat-link-policy";

test("shareable short and complete long WeChat article forms remain usable", () => {
  for (const url of [
    "https://mp.weixin.qq.com/s/hNvk76l8FzVEhglIQqebJg",
    "https://mp.weixin.qq.com/s?__biz=Mzk0&mid=2247496030&idx=1&sn=abc&chksm=xyz",
    "https://mp.weixin.qq.com/s/hNvk76l8FzVEhglIQqebJg?scene=1",
  ]) {
    assert.equal(classifyWeChatArticleUrl(url), "durable");
    assert.equal(isNonDurableWeChatArticleUrl(url), false);
  }
});

test("search-index signed and malformed WeChat links are not presented as live source URLs", () => {
  for (const url of [
    "https://mp.weixin.qq.com/s?new=1&signature=abc%2Adef&src=11&timestamp=1794138303&ver=7076",
    "https://mp.weixin.qq.com/s?__biz=Mzk0&mid=2247496030&idx=1&sn=abc&signature=s",
    "https://mp.weixin.qq.com/s?__biz=Mzk0&mid=2247496030",
    "http://mp.weixin.qq.com/s/hNvk76l8FzVEhglIQqebJg",
  ]) {
    assert.equal(isNonDurableWeChatArticleUrl(url), true);
  }
});

test("ordinary media and official sources are not blocked as WeChat", () => {
  for (const url of [
    "https://www.yunfu.gov.cn/zxzx/bmdt/content/post_2052905.html",
    "https://www.zhidx.com/p/608449.html",
    "https://mp.weixin.qq.com.evil.example/s/abc",
  ]) {
    assert.equal(classifyWeChatArticleUrl(url), "other");
  }
});
