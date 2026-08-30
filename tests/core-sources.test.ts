import assert from "node:assert/strict";
import test from "node:test";

import { coreSources, coreSourceStats } from "../lib/core-sources";

test("source directory exposes configured publishers without duplicate identities", () => {
  assert.ok(coreSources.length > 0);
  assert.ok(coreSourceStats.wechat > 0);
  assert.ok(coreSourceStats.official > 0);
  assert.ok(coreSourceStats.primary > 0);
  assert.equal(coreSourceStats.total, coreSources.length);

  const identities = coreSources.map((item) => `${item.kind}\u0000${item.name}`.toLowerCase());
  assert.equal(new Set(identities).size, identities.length);
});

test("source entries keep explicit lifecycle role health promotion and safe metadata", () => {
  for (const source of coreSources) {
    assert.ok(["candidate", "tracked", "core"].includes(source.lifecycle));
    assert.ok(["primary", "corroboration", "discovery"].includes(source.sourceRole));
    assert.ok(["ok", "partial", "error", "unknown"].includes(source.healthStatus));
    assert.ok(source.promotion);
    assert.ok([
      "candidate",
      "evidence_pending",
      "review_pending",
      "blocked",
      "core",
    ].includes(source.promotion.state));
    assert.equal(source.lifecycle, source.promotion.lifecycle);
    assert.ok(source.id);
    assert.ok(source.name);
    assert.ok(source.region);
    assert.ok(source.platform);
    assert.ok(source.endpoints.length > 0);
    if (source.url) {
      assert.match(source.url, /^https?:\/\//);
    }
  }
});

test("homepage-only official companies remain candidates instead of pretending to be tracked", () => {
  const candidates = coreSources.filter(
    (source) => source.sourceRole === "primary" && source.lifecycle === "candidate",
  );
  assert.equal(candidates.length, coreSourceStats.candidate);
  assert.ok(candidates.length > 0);
  for (const source of candidates) {
    assert.equal(source.kind, "官方 / 原始");
    assert.equal(source.sourceRole, "primary");
    assert.equal(source.promotion?.state, "candidate");
  }
});

test("configured regulator and company newsroom sources enter the primary layer", () => {
  const primary = coreSources.filter((source) => source.sourceRole === "primary");
  assert.equal(primary.length, coreSourceStats.primary);
  assert.ok(primary.some((source) => source.id.startsWith("official-company:")));
  assert.ok(primary.some((source) => source.id.startsWith("regulatory:")));
  assert.ok(primary.some((source) => source.lifecycle === "tracked"));
});

test("empty explicit Core review registry cannot silently promote a publisher", () => {
  assert.equal(coreSourceStats.core, 0);
  assert.equal(coreSources.some((source) => source.lifecycle === "core"), false);
  for (const source of coreSources.filter((item) => item.lifecycle === "tracked")) {
    assert.notEqual(source.promotion?.manualDecision, "approved");
  }
});

test("publisher-owned copies keep their real endpoint labels", () => {
  const expected = new Map([
    ["芯智讯", "官方同步稿 · 搜狐号"],
    ["芯东西", "官网文章"],
    ["芯师爷", "官网文章"],
  ]);
  for (const [name, label] of expected) {
    const source = coreSources.find((item) => item.name === name);
    assert.ok(source, `${name} should be present`);
    assert.equal(source.healthStatus, "ok");
    assert.ok(source.endpoints.some((endpoint) => endpoint.label === label));
    assert.equal(
      source.endpoints.some((endpoint) => endpoint.label === "微信公开索引"),
      false,
    );
    assert.ok(source.endpoints.some((endpoint) => endpoint.scanned > 0));
    assert.ok(source.endpoints.some((endpoint) => endpoint.accepted > 0));
  }
});
