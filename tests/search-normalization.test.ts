import assert from "node:assert/strict";
import test from "node:test";
import { searchTextIncludesQuery } from "../lib/search-normalization";

test("global search tolerates whitespace and punctuation differences in visible titles", () => {
  const indexedTitle = "蓝虫 具身 发布模块化人形机器人Mantis Standard“小白”，0.98 万元起";
  const copiedTitle = "蓝虫具身发布模块化人形机器人 Mantis Standard “小白”, 0.98万元起";

  assert.equal(searchTextIncludesQuery(indexedTitle, copiedTitle), true);
});

test("global search keeps ordinary exact substring matching", () => {
  assert.equal(
    searchTextIncludesQuery(
      "Agent Harness vs Agent Framework vs MCP: Which Layer Owns the Loop, State, Tools ...",
      "Agent Framework",
    ),
    true,
  );
});
