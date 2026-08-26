import assert from "node:assert/strict";
import test from "node:test";
import {
  isPersonDirectoryChangeRecent,
  matchesPersonDirectoryRecord,
} from "../lib/person-directory-filter";

const record = {
  text: "王兴兴 宇树科技创始人 机器人 Physical AI",
  sectors: ["机器人", "AI / AGI"],
  status: "complete",
  recentChange: true,
};

test("person directory filters combine text sector status and change state", () => {
  assert.equal(matchesPersonDirectoryRecord(record, {
    query: "宇树科技",
    sector: "机器人",
    status: "complete",
    change: "recent",
  }), true);

  assert.equal(matchesPersonDirectoryRecord(record, {
    query: "宇树科技",
    sector: "半导体",
    status: "complete",
    change: "recent",
  }), false);

  assert.equal(matchesPersonDirectoryRecord(record, {
    query: "不存在",
    sector: "all",
    status: "all",
    change: "all",
  }), false);
});

test("person directory search is whitespace and case tolerant", () => {
  assert.equal(matchesPersonDirectoryRecord(record, {
    query: "  physical   AI ",
    sector: "all",
    status: "all",
    change: "all",
  }), true);
});

test("recent person changes use the generated snapshot as deterministic as-of", () => {
  assert.equal(isPersonDirectoryChangeRecent("2026-08-01", "2026-08-22T00:00:00Z"), true);
  assert.equal(isPersonDirectoryChangeRecent("2026-04-01", "2026-08-22T00:00:00Z"), false);
  assert.equal(isPersonDirectoryChangeRecent("2026-09-01", "2026-08-22T00:00:00Z"), false);
  assert.equal(isPersonDirectoryChangeRecent(undefined, "2026-08-22T00:00:00Z"), false);
});
