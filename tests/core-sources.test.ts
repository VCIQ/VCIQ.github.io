import assert from "node:assert/strict";
import test from "node:test";

import { coreSources, coreSourceStats } from "../lib/core-sources";

test("core source directory exposes configured WeChat and feed sources without duplicate identities", () => {
  assert.ok(coreSources.length > 0);
  assert.ok(coreSourceStats.wechat > 0);
  assert.ok(coreSourceStats.total >= coreSourceStats.wechat);

  const identities = coreSources.map((item) => `${item.kind}\u0000${item.name}`.toLowerCase());
  assert.equal(new Set(identities).size, identities.length);
});

test("tracked source entries keep explicit lifecycle and safe source metadata", () => {
  for (const source of coreSources) {
    assert.equal(source.lifecycle, "tracked");
    assert.ok(source.id);
    assert.ok(source.name);
    assert.ok(source.region);
    assert.ok(source.platform);
    if (source.url) {
      assert.match(source.url, /^https?:\/\//);
    }
  }
});
