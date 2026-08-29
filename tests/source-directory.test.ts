import assert from "node:assert/strict";
import test from "node:test";

import { coreSourceStats } from "../lib/core-sources";
import {
  researchPaperSources,
  sourceDirectory,
  sourceDirectoryStats,
  xDiscoverySources,
} from "../lib/source-directory";

test("enabled paper collectors appear as primary research source entities", () => {
  const arxiv = researchPaperSources.find((source) => source.id === "paper:arxiv-ai");
  assert.ok(arxiv);
  assert.equal(arxiv.kind, "论文 / 原始研究");
  assert.equal(arxiv.sourceRole, "primary");
  assert.equal(arxiv.platform, "arXiv");
  assert.equal(arxiv.url, "https://arxiv.org/");
  assert.equal(arxiv.endpoints.length, 1);
  assert.equal(arxiv.endpoints[0].label, "arXiv Atom API");
  assert.ok(arxiv.companies.includes("OpenAI"));
  assert.ok(arxiv.promotion);
});

test("disabled broad OpenAlex collector stays out of the public source directory", () => {
  assert.equal(
    sourceDirectory.some((source) => source.id === "paper:openalex-ai"),
    false,
  );
});

test("configured X profiles are discovery sources rather than primary sources", () => {
  assert.ok(xDiscoverySources.length > 0);
  const openai = xDiscoverySources.find((source) => source.id === "x:x-openai");
  assert.ok(openai);
  assert.equal(openai.kind, "X / 发现");
  assert.equal(openai.sourceRole, "discovery");
  assert.equal(openai.platform, "X");
  assert.equal(openai.url, "https://x.com/OpenAI");
  assert.equal(openai.endpoints[0].label, "X 公开时间线");
  assert.ok(openai.promotion);

  for (const source of xDiscoverySources) {
    assert.equal(source.sourceRole, "discovery");
    assert.notEqual(source.sourceRole, "primary");
  }
});

test("person X profiles retain person identity without fabricating a company", () => {
  const karpathy = xDiscoverySources.find((source) => source.id === "x:x-karpathy");
  assert.ok(karpathy);
  assert.ok(karpathy.people.includes("Andrej Karpathy"));
  assert.equal(karpathy.companies.length, 0);
});

test("source directory statistics include papers and X without mutating core source counts", () => {
  assert.equal(sourceDirectoryStats.total, sourceDirectory.length);
  assert.equal(sourceDirectoryStats.papers, researchPaperSources.length);
  assert.equal(sourceDirectoryStats.xProfiles, xDiscoverySources.length);
  assert.equal(
    sourceDirectory.length,
    coreSourceStats.total + researchPaperSources.length + xDiscoverySources.length,
  );
  assert.ok(sourceDirectoryStats.primary >= coreSourceStats.primary + researchPaperSources.length);
});

test("new research and social source types participate in the same lifecycle gate", () => {
  for (const source of [...researchPaperSources, ...xDiscoverySources]) {
    assert.ok(source.promotion);
    assert.equal(source.lifecycle, source.promotion.lifecycle);
    assert.notEqual(source.lifecycle, "candidate");
    assert.notEqual(source.lifecycle, "core");
  }
});
